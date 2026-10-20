"""Opaque revocable sessions; secrets never appear in browser storage or URLs."""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from .db import get_db


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, expected = stored.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(row) -> dict:
    return {"id":row["id"], "name":row["name"], "email":row["email"], "role":row["role"],
            "client_id":row["client_id"], "tour_completed":bool(row["tour_completed"])}


def require_user(request: Request) -> dict:
    token = request.cookies.get("soulflow_session", "")
    if not token or len(token) > 200:
        raise HTTPException(401, "Bitte melde dich an.")
    with get_db() as conn:
        row = conn.execute("SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?", (token_hash(token), now_iso())).fetchone()
    if row is None:
        raise HTTPException(401, "Die Sitzung ist abgelaufen. Bitte erneut anmelden.")
    return public_user(row)


def require_staff(request: Request) -> dict:
    user = require_user(request)
    if user["role"] not in ("admin", "practitioner"):
        raise HTTPException(403, "Dieser Bereich ist für die Beraterin geschützt.")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(403, "Nur der Betreiber darf diese Änderung vornehmen.")
    return user
