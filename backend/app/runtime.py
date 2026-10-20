"""Explicit hosted configuration; local defaults never become a public demo."""
import os
from urllib.parse import parse_qs, urlsplit


def hosted():
    return os.environ.get("SOULFLOW_HOSTED") == "1"


def public_origin():
    if not hosted():
        return None
    value = os.environ.get("SOULFLOW_PUBLIC_ORIGIN", "")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname and not parsed.username
                 and not parsed.password and parsed.path in ("", "/")
                 and not parsed.query and not parsed.fragment and parsed.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise RuntimeError("SOULFLOW_PUBLIC_ORIGIN benötigt die genaue HTTPS-App-Adresse ohne Zugangsdaten.")
    return value.rstrip("/")


def allowed_hosts():
    origin = public_origin()
    return [urlsplit(origin).hostname] if origin else ["localhost", "127.0.0.1", "[::1]", "testserver"]


def validate_hosted_settings():
    if not hosted():
        return
    if os.environ.get("SOULFLOW_DEMO") == "1":
        raise RuntimeError("Lokale Demo-Zugänge dürfen nicht öffentlich gehostet werden.")
    public_origin()
    url = os.environ.get("DATABASE_URL", "")
    parsed = urlsplit(url)
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
        raise RuntimeError("Onlinebetrieb benötigt eine dauerhafte DATABASE_URL.")
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1") and parse_qs(parsed.query).get("sslmode", [""])[0] not in ("require", "verify-ca", "verify-full"):
        raise RuntimeError("Die dauerhafte Datenbank benötigt TLS (sslmode=require oder strenger).")
    license_choice = os.environ.get("SOULFLOW_SWISS_LICENSE", "")
    if license_choice not in ("agpl-3.0", "professional"):
        raise RuntimeError("Vor öffentlichem Betrieb ist eine ausdrückliche Swiss-Ephemeris-Lizenzwahl nötig.")
    if license_choice == "agpl-3.0":
        source = urlsplit(os.environ.get("SOULFLOW_SOURCE_URL", ""))
        if source.scheme != "https" or not source.hostname or source.username or source.password:
            raise RuntimeError("Die freigegebene AGPL-Fassung benötigt einen zugänglichen Quellcode-Link.")
