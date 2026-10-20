"""Source-attributed place lookup and computed (not interpreted) natal charts.

V1 convention: 1900-01-01..2100-12-31, Gregorian calendar, apparent geocentric
ecliptic positions, tropical zodiac, Placidus. House membership uses Swiss
Ephemeris house_pos including ecliptic latitude, not equal 30-degree sectors.
The engine is pyswisseph; actual return flags identify Swiss/JPL/Moshier data.
No ephemeris files are downloaded. SENSE_AND_STARS_EPHE_PATH may point to local files.

Primary documentation checked 2026-10-20:
https://www.astro.com/swisseph/swephprg.htm
https://pypi.org/project/pyswisseph/  (AGPLv3; this release is AGPL-3.0-only)
https://www.astro.com/swisseph/  (Swiss Ephemeris dual licensing)
https://operations.osmfoundation.org/policies/nominatim/
https://nominatim.org/release-docs/latest/api/Search/
https://timezonefinder.readthedocs.io/en/latest/1_usage.html
https://docs.python.org/3/library/zoneinfo.html

TimezoneFinder maps current coordinate boundaries to an IANA name. ZoneInfo
provides that zone's historical offsets. Historical political boundaries and
pre-1970 IANA records are not a guarantee of exact historical civil time.
Only explicitly searched place names are sent to the geocoder; birth data and
client identities stay local. City centres are approximate birth locations.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from contextlib import contextmanager
from datetime import date, datetime, timezone
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import swisseph as swe
from fastapi import APIRouter, HTTPException, Query, Request
from timezonefinder import TimezoneFinder

from .security import require_staff
from .config import compatible_database_path, setting

router = APIRouter(prefix="/api/astro", tags=["astro"])
_EPHEMERIS_LOCK = threading.Lock()
_PROVIDER_LOCK = threading.Lock()
_CACHE_DAYS = 30
_DATE_MIN = date(1900, 1, 1)
_DATE_MAX = date(2100, 12, 31)
_SIGNS = ("Widder", "Stier", "Zwillinge", "Krebs", "Löwe", "Jungfrau", "Waage", "Skorpion", "Schütze", "Steinbock", "Wassermann", "Fische")
_PLANETS = (("Sonne", swe.SUN), ("Mond", swe.MOON), ("Merkur", swe.MERCURY), ("Venus", swe.VENUS), ("Mars", swe.MARS), ("Jupiter", swe.JUPITER), ("Saturn", swe.SATURN), ("Uranus", swe.URANUS), ("Neptun", swe.NEPTUNE), ("Pluto", swe.PLUTO))
# Orbs are explicit V1 conventions, not astronomical discoveries.
_ASPECTS = (("Konjunktion", 0, 8), ("Sextil", 60, 4), ("Quadrat", 90, 6), ("Trigon", 120, 6), ("Opposition", 180, 8))
_PLACE_FIELDS = ("label", "latitude", "longitude", "timezone", "source")

# Small offline gazetteer. Coordinates are P625 snapshots of the linked
# Wikidata items (CC0), checked 2026-10-20, intentionally city-level only.
_LOCAL_PLACES = (
    (("berlin", "berlin deutschland", "berlin germany"), "Berlin, Deutschland", 52 + 31 / 60, 13 + 23 / 60, "Q64"),
    (("wien", "vienna", "wien osterreich", "vienna austria"), "Wien, Österreich", 48 + 12 / 60 + 30 / 3600, 16 + 22 / 60 + 21 / 3600, "Q1741"),
    (("zurich", "zuerich", "zurich schweiz"), "Zürich, Schweiz", 47 + 22 / 60 + 28 / 3600, 8 + 32 / 60 + 28 / 3600, "Q72"),
    (("frankfurt", "frankfurt am main", "frankfurt main"), "Frankfurt am Main, Hessen, Deutschland", 50 + 6 / 60 + 38 / 3600, 8 + 40 / 60 + 56 / 3600, "Q1794"),
    (("frankfurt", "frankfurt oder", "frankfurt an der oder"), "Frankfurt (Oder), Brandenburg, Deutschland", 52 + 20 / 60 + 31.5 / 3600, 14 + 33 / 60 + 6 / 3600, "Q4024"),
)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold()).replace("ß", "ss")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.sub(r"[,().]", " ", value).split())


def _cache_path() -> Path:
    explicit = setting("ASTRO_CACHE")
    if explicit:
        return Path(explicit).expanduser()
    root = Path(__file__).resolve().parents[2]
    database = Path(setting("DB") or compatible_database_path(root / "data")).expanduser()
    return database.parent / "astro-places.sqlite3"


@contextmanager
def _cache():
    if os.environ.get("DATABASE_URL"):
        from .db import get_db
        conn = get_db(cache=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS places (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS queries (query TEXT PRIMARY KEY, ids TEXT NOT NULL, expires REAL NOT NULL)")
            conn.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES ('place_key',?)", (secrets.token_hex(32),))
            conn.commit()
            yield conn
        finally:
            conn.close()
        return
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS places (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS queries (query TEXT PRIMARY KEY, ids TEXT NOT NULL, expires REAL NOT NULL)")
            conn.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES ('place_key',?)", (secrets.token_hex(32),))
        yield conn
    finally:
        conn.close()


def _canonical(place: dict) -> str:
    return json.dumps({key: place[key] for key in _PLACE_FIELDS}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _place_id(conn: sqlite3.Connection, payload: str) -> str:
    key = bytes.fromhex(conn.execute("SELECT value FROM metadata WHERE key='place_key'").fetchone()[0])
    return "pl_" + hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _store_places(query: str, places: list[dict]) -> list[dict]:
    stored = []
    with _cache() as conn, conn:
        for place in places:
            payload = _canonical(place)
            identifier = _place_id(conn, payload)
            conn.execute("INSERT OR IGNORE INTO places(id,payload) VALUES (?,?)", (identifier, payload))
            stored.append({"id": identifier, **place})
        # Negative results have a shorter cache lifetime.
        lifetime = _CACHE_DAYS * 86400 if places else 3600
        conn.execute("INSERT INTO queries(query,ids,expires) VALUES (?,?,?) ON CONFLICT(query) DO UPDATE SET ids=excluded.ids,expires=excluded.expires", (query, json.dumps([p["id"] for p in stored]), time.time() + lifetime))
    return stored


def get_place(place_id: str) -> dict:
    """Resolve an opaque server-issued identifier, never browser coordinates."""
    if not isinstance(place_id, str) or not re.fullmatch(r"pl_[0-9a-f]{32}", place_id):
        raise HTTPException(404, "Ort nicht gefunden. Bitte den Geburtsort erneut suchen und auswählen.")
    with _cache() as conn:
        row = conn.execute("SELECT payload FROM places WHERE id=?", (place_id,)).fetchone()
        if row is None or not hmac.compare_digest(_place_id(conn, row["payload"]), place_id):
            raise HTTPException(404, "Ort nicht gefunden. Bitte den Geburtsort erneut suchen und auswählen.")
        return {"id": place_id, **json.loads(row["payload"])}


@lru_cache(maxsize=1)
def _timezone_finder() -> TimezoneFinder:
    return TimezoneFinder(in_memory=True)


def _timezone_name(latitude: float, longitude: float) -> str:
    identifier = _timezone_finder().timezone_at(lng=longitude, lat=latitude)
    if not identifier:
        raise HTTPException(422, "Für diesen Ort wurde keine IANA-Zeitzone gefunden. Bitte einen präziseren Ort auswählen.")
    try:
        ZoneInfo(identifier)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(503, "Die lokale Zeitzonendatenbank ist unvollständig. Bitte die Installation prüfen.") from exc
    return identifier


def _query_provider(query: str) -> list[dict]:
    """Single explicit query with an application-wide persistent rate limit."""
    endpoint = setting("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
    with _PROVIDER_LOCK:
        # Reserving starts in SQLite also coordinates multiple local workers.
        with _cache() as conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute("SELECT value FROM metadata WHERE key='provider_last_start'").fetchone()
            delay = max(0.0, 1.05 - (time.time() - float(previous[0]))) if previous else 0
            # A corrupt/future timestamp must not block a request for long.
            time.sleep(min(delay, 1.05))
            conn.execute("INSERT INTO metadata(key,value) VALUES ('provider_last_start',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(time.time()),))
            conn.commit()
        response = httpx.get(
            endpoint,
            params={"q": query, "format": "jsonv2", "limit": 8, "featureType": "settlement", "accept-language": "de,en"},
            headers={"User-Agent": "Sense-And-Stars/1.1 (local single-practice PWA; explicit place search)", "Accept": "application/json"},
            timeout=8.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        return response.json()


def resolve_places(q: str) -> list[dict]:
    if not isinstance(q, str) or "\n" in q or "\r" in q:
        raise HTTPException(422, "Bitte nur einen Ortsnamen mit 2 bis 100 Zeichen eingeben.")
    query = " ".join(q.strip().split())
    if not 2 <= len(query) <= 100 or not all(char.isalpha() or char in " -',().’" for char in query):
        raise HTTPException(422, "Bitte nur einen Ortsnamen mit 2 bis 100 Zeichen eingeben, keine Koordinaten oder persönlichen Angaben.")
    normalized = _normalized(query)
    with _cache() as conn:
        row = conn.execute("SELECT ids FROM queries WHERE query=? AND expires>?", (normalized, time.time())).fetchone()
    if row:
        return [get_place(identifier) for identifier in json.loads(row["ids"])]
    local = []
    for aliases, label, latitude, longitude, wikidata in _LOCAL_PLACES:
        if normalized in aliases:
            local.append({"label": label, "latitude": latitude, "longitude": longitude, "timezone": _timezone_name(latitude, longitude), "source": f"Lokales Ortsverzeichnis · Wikidata (CC0), Stadtkoordinate, Stand 20.10.2026 · https://www.wikidata.org/wiki/{wikidata}"})
    if local:
        return _store_places(normalized, local)
    try:
        results = _query_provider(query)
        if not isinstance(results, list):
            raise ValueError("Geocoder returned no result list")
        places = []
        seen = set()
        for item in results[:8]:
            if not isinstance(item, dict):
                raise ValueError("Invalid geocoder entry")
            latitude, longitude = float(item["lat"]), float(item["lon"])
            if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("Invalid geocoder coordinates")
            label = str(item["display_name"]).strip()[:500]
            if not label:
                raise ValueError("Missing place label")
            key = (latitude, longitude, label)
            if key in seen:
                continue
            seen.add(key)
            osm_type = item.get("osm_type")
            osm_id = str(item.get("osm_id", ""))
            reference = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type in ("node", "way", "relation") and osm_id.isdigit() else "https://www.openstreetmap.org/copyright"
            places.append({"label": label, "latitude": latitude, "longitude": longitude, "timezone": _timezone_name(latitude, longitude), "source": f"Nominatim · © OpenStreetMap-Mitwirkende (ODbL) · {reference}"})
        return _store_places(normalized, places)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(503, "Die Ortssuche ist vorübergehend nicht verfügbar. Bitte später erneut suchen; bereits ausgewählte Orte und das lokale Ortsverzeichnis bleiben nutzbar.") from exc


@router.get("/places")
def search_places(request: Request, q: str = Query(min_length=2, max_length=100)) -> list[dict]:
    require_staff(request)
    return resolve_places(q)


def _local_to_utc(birth_date: str, birth_time: str, zone_name: str, fold: int | None) -> tuple[datetime, datetime]:
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise HTTPException(422, "Bei einer doppelten Ortszeit muss fold ausdrücklich 0 oder 1 sein.")
    try:
        if not isinstance(birth_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", birth_date):
            raise ValueError
        if not isinstance(birth_time, str) or not re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", birth_time):
            raise ValueError
        day = date.fromisoformat(birth_date)
        if not _DATE_MIN <= day <= _DATE_MAX:
            raise ValueError
        local = datetime.fromisoformat(f"{birth_date}T{birth_time}")
    except ValueError as exc:
        raise HTTPException(422, "Bitte ein gültiges Geburtsdatum von 1900 bis 2100 und eine lokale Uhrzeit als HH:MM oder HH:MM:SS angeben.") from exc
    zone = ZoneInfo(zone_name)
    candidates = {}
    for candidate_fold in (0, 1):
        candidate = local.replace(tzinfo=zone, fold=candidate_fold)
        utc = candidate.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == local:
            candidates[candidate_fold] = (candidate, utc)
    if not candidates:
        raise HTTPException(409, "Diese Ortszeit existiert wegen der Zeitumstellung nicht. Bitte die dokumentierte Geburtszeit prüfen.")
    ambiguous = len({utc for _, utc in candidates.values()}) > 1
    if ambiguous and fold is None:
        raise HTTPException(409, "Diese Ortszeit kommt bei der Zeitumstellung zweimal vor. Bitte fold 0 für das erste oder fold 1 für das zweite Vorkommen auswählen.")
    return candidates[fold if ambiguous else min(candidates)]


def _position(longitude: float) -> dict:
    # Derive all display fields from the same rounded angle, including the
    # 29.999999999/359.999999999 boundaries.
    normalized = round(longitude % 360, 8) % 360
    return {"longitude": normalized, "sign": _SIGNS[int(normalized // 30)], "degree": round(normalized % 30, 8)}


def _ephemeris_label(flags: int) -> str:
    if flags & swe.FLG_JPLEPH:
        return "JPL"
    if flags & swe.FLG_SWIEPH:
        return "Swiss Ephemeris files"
    if flags & swe.FLG_MOSEPH:
        return "Moshier"
    return "Unbekannte Ephemeride"


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "system"


def calculate_chart(birth_date: str, birth_time: str, place: dict, fold: int | None = None) -> dict:
    """Calculate explicit source/zone metadata; never infer an uncertain time."""
    if not isinstance(place, dict) or "id" not in place:
        raise HTTPException(422, "Bitte einen Ort aus der serverseitigen Ortssuche auswählen.")
    cached = get_place(place["id"])
    if any(place.get(key) != cached[key] for key in _PLACE_FIELDS):
        raise HTTPException(422, "Die Ortsdaten stimmen nicht mit der Auswahl überein. Bitte den Ort erneut auswählen.")
    local, utc = _local_to_utc(birth_date, birth_time, cached["timezone"], fold)
    latitude, longitude = cached["latitude"], cached["longitude"]
    warnings = ["Stadtkoordinaten sind Näherungen. Eine ungenaue Geburtszeit oder ein abweichender Geburtsort beeinflusst Aszendent und Häuser.", "Astrologie ist ein spirituelles Reflexionsmodell, keine Diagnose, Behandlung oder wissenschaftlich belegte Therapie."]
    if local.year < 1970:
        warnings.append("Historische Ortszeit vor 1970: IANA-Daten und heutige Zeitzonengrenzen können historische Besonderheiten unvollständig abbilden. Originalunterlagen und lokale Zeitgeschichte prüfen.")
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    planets, ephemerides = [], set()
    # Swiss Ephemeris owns process-level state (path, Delta-T configuration).
    with _EPHEMERIS_LOCK:
        swe.set_ephe_path(setting("EPHE_PATH", str(Path(__file__).resolve().parents[2] / "data" / "ephemeris")))
        julian_day = swe.julday(utc.year, utc.month, utc.day, hour, swe.GREG_CAL)
        try:
            cusps, ascmc = swe.houses_ex(julian_day, latitude, longitude, b"P", 0)
            ecliptic, _ = swe.calc_ut(julian_day, swe.ECL_NUT, flags)
        except swe.Error as exc:
            raise HTTPException(422, "Placidus-Häuser lassen sich für diesen Ort und Zeitpunkt nicht berechnen, insbesondere in Polargebieten. V1 wechselt das Häusersystem nicht stillschweigend.") from exc
        for name, planet_number in _PLANETS:
            try:
                position, actual_flags = swe.calc_ut(julian_day, planet_number, flags)
                if not all(math.isfinite(value) for value in position):
                    raise ValueError("Nonfinite ephemeris result")
                house_position = swe.house_pos(ascmc[2], latitude, ecliptic[0], position[:2], b"P")
                if not 1 <= house_position < 13:
                    raise ValueError("Invalid house position")
            except (swe.Error, ValueError) as exc:
                raise HTTPException(422, "Die astronomische Berechnung konnte nicht vollständig durchgeführt werden. Bitte Ephemerideninstallation, Ort und Zeitpunkt prüfen.") from exc
            ephemerides.add(_ephemeris_label(actual_flags))
            planets.append({"name": name, **_position(position[0]), "house": int(house_position), "retrograde": position[3] < 0, "latitude": round(position[1], 8), "speed": round(position[3], 8), "calculation_flags": actual_flags, "ephemeris": _ephemeris_label(actual_flags)})
    if "Moshier" in ephemerides:
        warnings.append("Lokale Swiss-Ephemeris-Dateien fehlen für mindestens einen Körper: tatsächlich verwendeter rechnerischer Fallback ist Moshier. Diese Quelle wird je Planet ausgewiesen.")
    aspects = []
    for index, first in enumerate(planets):
        for second in planets[index + 1:]:
            separation = abs((first["longitude"] - second["longitude"] + 180) % 360 - 180)
            for name, angle, maximum_orb in _ASPECTS:
                orb = abs(separation - angle)
                if orb <= maximum_orb:
                    aspects.append({"planet1": first["name"], "planet2": second["name"], "aspect": name, "orb": round(orb, 5), "angle": angle})
    return {
        "ascendant": _position(ascmc[0]),
        "midheaven": _position(ascmc[1]),
        "planets": planets,
        "houses": [{"house": index, **_position(cusp)} for index, cusp in enumerate(cusps, 1)],
        "aspects": aspects,
        "timezone": cached["timezone"],
        "utc_datetime": utc.isoformat(),
        "local_datetime": local.isoformat(),
        "local_time_fold": local.fold,
        "utc_offset_seconds": int(local.utcoffset().total_seconds()),
        "timezone_source": f"timezonefinder {_package_version('timezonefinder')} (heutige Ortsgrenzen) + Python zoneinfo/IANA (historische UTC-Offsets); tzdata {_package_version('tzdata')}",
        "coordinates": {"latitude": latitude, "longitude": longitude, "place_id": cached["id"], "label": cached["label"], "source": cached["source"]},
        "source": {"engine": "pyswisseph", "version": swe.__version__, "swiss_ephemeris_version": swe.version, "requested_ephemeris": "Swiss Ephemeris", "actual_ephemerides": sorted(ephemerides), "reference": "https://www.astro.com/swisseph/swephprg.htm", "license": "pyswisseph AGPLv3; Sense & Stars AGPL-3.0-only (siehe LICENSE)"},
        "house_system": "Placidus",
        "house_membership": "Swiss Ephemeris house_pos with ecliptic latitude",
        "zodiac": "tropical",
        "coordinate_system": "apparent geocentric ecliptic of date",
        "date_range": {"from": _DATE_MIN.isoformat(), "to": _DATE_MAX.isoformat()},
        "aspect_orbs": {name: orb for name, _, orb in _ASPECTS},
        "warnings": warnings,
    }
