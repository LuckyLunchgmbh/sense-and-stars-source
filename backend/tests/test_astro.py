"""Offline contract, DST, and independent astronomical reference checks.

Reference fixture: NASA/JPL Horizons, geocentre 500@399, observer quantity 31,
UTC 2000-01-01 12:00, apparent ecliptic-of-date longitude. Retrieved 2026-10-20
from https://ssd.jpl.nasa.gov/api/horizons.api (commands 10,301,499,599).
Reproducible Sun request (replace COMMAND by 301/499/599 for other bodies):
https://ssd.jpl.nasa.gov/api/horizons.api?format=text&COMMAND=%2710%27&CENTER=%27500%40399%27&MAKE_EPHEM=%27YES%27&EPHEM_TYPE=%27OBSERVER%27&START_TIME=%272000-01-01%2012%3A00%27&STOP_TIME=%272000-01-01%2012%3A01%27&STEP_SIZE=%271%20m%27&QUANTITIES=%2731%27&CSV_FORMAT=%27YES%27
Definitions: https://ssd.jpl.nasa.gov/horizons/manual.html#observer-table
The 0.01 degree tolerance covers Moshier versus JPL DE441/model differences;
this is a reference check, not a certification of all epochs/coordinates.
"""

import json

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import astro

_REAL_PROVIDER = astro._query_provider


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SOULFLOW_ASTRO_CACHE", str(tmp_path / "places.sqlite3"))

    def no_network(_query):
        raise AssertionError("Tests must explicitly mock every remote place query")

    monkeypatch.setattr(astro, "_query_provider", no_network)


@pytest.fixture
def berlin():
    return astro.resolve_places("Berlin")[0]


def test_curated_place_is_source_attributed_and_persistently_selected(berlin):
    assert berlin["label"] == "Berlin, Deutschland"
    assert berlin["timezone"] == "Europe/Berlin"
    assert "wikidata.org/wiki/Q64" in berlin["source"]
    assert berlin["id"].startswith("pl_")
    assert astro.get_place(berlin["id"]) == berlin
    assert astro.resolve_places(" berlin ")[0]["id"] == berlin["id"]


def test_ambiguous_name_returns_explicit_choices():
    places = astro.resolve_places("Frankfurt")
    assert len(places) == 2
    assert any("Main" in place["label"] for place in places)
    assert any("Oder" in place["label"] for place in places)
    assert len({p["id"] for p in places}) == 2


@pytest.mark.parametrize("query", ["", "A", "52.5,13.4", "name@example.com", "Berlin\nNotiz", "A" * 101])
def test_invalid_query_is_rejected_before_any_network(query):
    with pytest.raises(HTTPException) as error:
        astro.resolve_places(query)
    assert error.value.status_code == 422


def test_unknown_place_id_is_not_a_coordinate_override(berlin):
    with pytest.raises(HTTPException) as error:
        astro.get_place(berlin["id"][:-1] + ("0" if berlin["id"][-1] != "0" else "1"))
    assert error.value.status_code == 404


def test_provider_results_are_cached_and_keep_distinct_places(monkeypatch):
    calls = []

    def provider(query):
        calls.append(query)
        return [
            {"display_name": "Neustadt A, Deutschland", "lat": "49.35", "lon": "8.14", "osm_type": "relation", "osm_id": 100},
            {"display_name": "Neustadt B, Deutschland", "lat": "50.73", "lon": "11.76", "osm_type": "relation", "osm_id": 101},
        ]

    monkeypatch.setattr(astro, "_query_provider", provider)
    first = astro.resolve_places("Neustadt")
    second = astro.resolve_places("NEUSTADT")
    assert first == second and len(calls) == 1
    assert len(first) == 2
    assert "OpenStreetMap" in first[0]["source"]
    assert "openstreetmap.org/relation/100" in first[0]["source"]
    assert astro.get_place(first[0]["id"]) == first[0]


def test_provider_failure_returns_actionable_error(monkeypatch):
    def unavailable(_query):
        raise httpx.ConnectError("synthetic outage")

    monkeypatch.setattr(astro, "_query_provider", unavailable)
    with pytest.raises(HTTPException) as error:
        astro.resolve_places("Neustadt")
    assert error.value.status_code == 503
    assert "erneut" in error.value.detail


def test_malformed_provider_response_is_not_silently_accepted(monkeypatch):
    monkeypatch.setattr(astro, "_query_provider", lambda _q: {"error": "unavailable"})
    with pytest.raises(HTTPException) as error:
        astro.resolve_places("Neustadt")
    assert error.value.status_code == 503


def test_provider_rate_limit_and_transmitted_data(monkeypatch):
    clock = [1000.0]
    calls = []

    def get(url, **options):
        calls.append((clock[0], url, options))
        return httpx.Response(200, json=[], request=httpx.Request("GET", url))

    monkeypatch.setattr(astro.httpx, "get", get)
    monkeypatch.setattr(astro.time, "time", lambda: clock[0])
    monkeypatch.setattr(astro.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    _REAL_PROVIDER("Heidelberg")
    _REAL_PROVIDER("Neustadt")
    assert calls[1][0] - calls[0][0] >= 1.0
    assert calls[0][2]["params"] == {"q": "Heidelberg", "format": "jsonv2", "limit": 8, "featureType": "settlement", "accept-language": "de,en"}
    assert calls[0][2]["headers"]["User-Agent"].startswith("SoulFlow/")
    assert calls[0][2]["timeout"] <= 10
    assert "json" not in calls[0][2] and "data" not in calls[0][2]


def test_j2000_matches_independent_jpl_reference(berlin):
    chart = astro.calculate_chart("2000-01-01", "13:00", berlin)
    actual = {planet["name"]: planet["longitude"] for planet in chart["planets"]}
    reference = {"Sonne": 280.3689092, "Mond": 223.3237860, "Mars": 327.9632921, "Jupiter": 25.2530685}
    for name, longitude in reference.items():
        assert actual[name] == pytest.approx(longitude, abs=0.01)
    assert chart["utc_datetime"] == "2000-01-01T12:00:00+00:00"
    assert len(chart["planets"]) == 10
    assert len(chart["houses"]) == 12
    assert chart["ascendant"]["longitude"] == pytest.approx(chart["houses"][0]["longitude"])
    assert chart["house_system"] == "Placidus"
    assert chart["zodiac"] == "tropical"
    assert all(1 <= planet["house"] <= 12 for planet in chart["planets"])
    assert all(0 <= planet["degree"] < 30 for planet in chart["planets"])
    assert chart["source"]["actual_ephemerides"]
    assert all(planet["calculation_flags"] > 0 for planet in chart["planets"])
    json.dumps(chart, allow_nan=False)


def test_unambiguous_summer_time_and_historical_double_dst(berlin):
    summer = astro.calculate_chart("1990-07-01", "12:00", berlin)
    historical = astro.calculate_chart("1945-07-01", "12:00", berlin)
    assert summer["utc_datetime"] == "1990-07-01T10:00:00+00:00"
    assert historical["utc_datetime"] == "1945-07-01T09:00:00+00:00"
    assert any("1970" in warning for warning in historical["warnings"])


def test_nonexistent_dst_time_is_rejected_even_with_fold(berlin):
    for fold in (None, 0, 1):
        with pytest.raises(HTTPException) as error:
            astro.calculate_chart("2024-03-31", "02:30", berlin, fold=fold)
        assert error.value.status_code == 409
        assert "existiert" in error.value.detail


def test_ambiguous_dst_time_requires_explicit_choice(berlin):
    with pytest.raises(HTTPException) as error:
        astro.calculate_chart("2024-10-27", "02:30", berlin)
    assert error.value.status_code == 409
    assert "zweimal" in error.value.detail
    first = astro.calculate_chart("2024-10-27", "02:30", berlin, fold=0)
    second = astro.calculate_chart("2024-10-27", "02:30", berlin, fold=1)
    assert first["utc_datetime"] == "2024-10-27T00:30:00+00:00"
    assert second["utc_datetime"] == "2024-10-27T01:30:00+00:00"
    assert first["ascendant"]["longitude"] != second["ascendant"]["longitude"]


@pytest.mark.parametrize("day,clock,fold", [("1899-12-31", "12:00", None), ("2101-01-01", "12:00", None), ("2000-02-30", "12:00", None), ("2000-01-01", "24:00", None), ("2000-01-01", "12:00+01:00", None), ("2000-01-01", "12:00", 2), ("2000-01-01", "12:00", True)])
def test_invalid_chart_input_has_clear_error(berlin, day, clock, fold):
    with pytest.raises(HTTPException) as error:
        astro.calculate_chart(day, clock, berlin, fold=fold)
    assert error.value.status_code == 422


def test_uncached_browser_coordinates_are_rejected(berlin):
    tampered = {**berlin, "latitude": 0.0}
    with pytest.raises(HTTPException) as error:
        astro.calculate_chart("2000-01-01", "13:00", tampered)
    assert error.value.status_code == 422


def test_polar_placidus_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(astro, "_query_provider", lambda _q: [{"display_name": "Longyearbyen, Svalbard", "lat": "78.22", "lon": "15.65", "osm_type": "node", "osm_id": 1}])
    place = astro.resolve_places("Longyearbyen")[0]
    with pytest.raises(HTTPException) as error:
        astro.calculate_chart("2000-01-01", "13:00", place)
    assert error.value.status_code == 422
    assert "Placidus" in error.value.detail


def test_ephemeris_fallback_is_visible(berlin, monkeypatch, tmp_path):
    monkeypatch.setenv("SOULFLOW_EPHE_PATH", str(tmp_path / "no-ephemeris-files"))
    chart = astro.calculate_chart("2000-01-01", "13:00", berlin)
    assert "Moshier" in chart["source"]["actual_ephemerides"]
    assert any("Moshier" in warning for warning in chart["warnings"])


def test_angle_rounding_preserves_zodiac_boundaries():
    assert astro._position(359.999999999) == {"longitude": 0.0, "sign": "Widder", "degree": 0.0}
    assert astro._position(29.999999999) == {"longitude": 30.0, "sign": "Stier", "degree": 0.0}


def test_search_route_checks_staff_before_resolving(monkeypatch):
    def denied(_request):
        raise HTTPException(401, "Bitte anmelden.")

    monkeypatch.setattr(astro, "require_staff", denied)
    app = FastAPI()
    app.include_router(astro.router)
    response = TestClient(app).get("/api/astro/places?q=Berlin")
    assert response.status_code == 401
