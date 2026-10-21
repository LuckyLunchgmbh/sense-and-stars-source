"""Single-use, account-bound recovery independent of the login lockout."""
import secrets
import time
import logging

from fastapi import APIRouter, HTTPException, Request

from .db import get_db
from . import recovery_mail
from .schemas import PasswordResetConfirm, PasswordResetRequest
from .security import hash_password, now_iso, token_hash


router = APIRouter(prefix="/api/auth")
TOKEN_LIFETIME = 30 * 60
REQUEST_WINDOW = 7
REQUEST_MESSAGE = "Die Anfrage wurde aufgenommen. Prüfe dein E-Mail-Postfach und den Spamordner. Falls keine Nachricht ankommt, versuche es später erneut oder wende dich an die Person, die deinen Zugang eingerichtet hat."
INVALID_LINK = "Dieser Rücksetzlink ist ungültig oder abgelaufen. Bitte fordere einen neuen Link an."
logger = logging.getLogger(__name__)


def _peer(request):
    # The ASGI server supplies the peer. Never trust a caller-provided forwarding header.
    return request.client.host if request.client else "local"


def _rate_limit(conn, limits, now):
    conn.execute("DELETE FROM password_reset_limits WHERE first_at<?", (now - 3600,))
    rows = []
    for identity, count, window, cooldown in limits:
        key = token_hash(identity)
        row = conn.execute("SELECT * FROM password_reset_limits WHERE key=?", (key,)).fetchone()
        active = row and row["first_at"] > now - window
        if active and (row["count"] >= count or row["last_at"] > now - cooldown):
            return False
        rows.append((key, row if active else None))
    for key, row in rows:
        if row:
            conn.execute("UPDATE password_reset_limits SET count=count+1,last_at=? WHERE key=?", (now, key))
        else:
            conn.execute("INSERT INTO password_reset_limits(key,count,first_at,last_at) VALUES(?,1,?,?) ON CONFLICT(key) DO UPDATE SET count=1,first_at=excluded.first_at,last_at=excluded.last_at", (key, now, now))
    return True


def _audit(conn, user_id, action):
    conn.execute("INSERT INTO audit(user_id,action,resource_id,created_at) VALUES(?,?,?,?)", (user_id, action, user_id, now_iso()))


def _record_delivery(user_id, action, failed_token=None):
    # The request/password transaction has already committed. A later mail-audit
    # outage must not turn a completed reset into a misleading failure response,
    # or reveal that an address exists through a different request response.
    try:
        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if failed_token is not None:
                conn.execute("DELETE FROM password_reset_tokens WHERE token_hash=?", (failed_token,))
            _audit(conn, user_id, action)
    except Exception:
        # Static operational signal only: no exception, email, token or user ID.
        logger.warning("Recovery mail result could not be persisted.")


def _deliver_reset(settings, email, token, token_digest, user_id):
    try:
        recovery_mail.send_reset(settings, email, token)
    except Exception:
        # SMTP exceptions can contain recipient addresses or credentials. Do not log them.
        _record_delivery(user_id, "password_reset.mail_failed", failed_token=token_digest)
        return
    _record_delivery(user_id, "password_reset.mail_accepted")


def _deliver_changed(settings, email, user_id):
    try:
        recovery_mail.send_changed(settings, email)
        action = "password_reset.notice_accepted"
    except Exception:
        action = "password_reset.notice_failed"
    _record_delivery(user_id, action)


@router.get("/recovery")
def recovery_status():
    return {"available": recovery_mail.mail_settings() is not None}


@router.post("/password-reset/request", status_code=202)
def request_reset(data: PasswordResetRequest, request: Request):
    settings = recovery_mail.mail_settings()
    if settings is None:
        raise HTTPException(503, "Passwort-Zurücksetzen ist derzeit nicht verfügbar. Bitte wende dich an die Person, die deinen Zugang eingerichtet hat.")
    email = str(data.email).lower()
    now = time.time()
    response_at = time.monotonic() + REQUEST_WINDOW
    # SMTP is fully awaited before the response, outside the transaction. The
    # same minimum response window applies to known and unknown identities.
    # Database delays may extend it; only the SMTP worker has a hard deadline.
    token = secrets.token_urlsafe(32)
    digest = token_hash(token)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        limits = (("request.account:" + email, 3, 3600, 60),
                  ("request.peer:" + _peer(request), 20, 3600, 0),
                  ("request.global", 100, 3600, 0))
        if not _rate_limit(conn, limits, now):
            conn.commit()
            raise HTTPException(429, "Bitte warte etwas, bevor du einen weiteren Rücksetzlink anforderst.")
        conn.execute("DELETE FROM password_reset_tokens WHERE expires_at<=?", (now,))
        user = conn.execute("SELECT id,email,password_hash FROM users WHERE email=?", (email,)).fetchone()
        if user:
            conn.execute("INSERT INTO password_reset_tokens(token_hash,user_id,credential_fingerprint,expires_at,created_at) VALUES(?,?,?,?,?)",
                         (digest, user["id"], token_hash(user["password_hash"]), now + TOKEN_LIFETIME, now))
    if user:
        _deliver_reset(settings, user["email"], token, digest, user["id"])
    remaining = response_at - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)
    return {"message": REQUEST_MESSAGE}


@router.post("/password-reset/confirm")
def confirm_reset(data: PasswordResetConfirm, request: Request):
    digest = token_hash(data.token)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Re-read after acquiring the shared lock: a token can expire while
        # this request waits for another login/reset transaction to finish.
        now = time.time()
        if not _rate_limit(conn, (("confirm.peer:" + _peer(request), 10, 600, 0),
                                  ("confirm.global", 120, 600, 0)), now):
            conn.commit()
            raise HTTPException(429, "Zu viele Versuche. Bitte versuche es in zehn Minuten erneut.")
        token = conn.execute("SELECT * FROM password_reset_tokens WHERE token_hash=?", (digest,)).fetchone()
        user = conn.execute("SELECT id,email,password_hash FROM users WHERE id=?", (token["user_id"],)).fetchone() if token else None
        if not token or not user or token["expires_at"] <= now or token["credential_fingerprint"] != token_hash(user["password_hash"]):
            conn.execute("DELETE FROM password_reset_tokens WHERE token_hash=?", (digest,))
            conn.commit()
            raise HTTPException(400, INVALID_LINK)
        # Serializes with both login and other confirmations on SQLite/Postgres.
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(data.password), user["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id=?", (user["id"],))
        legacy_current_peer = token_hash(_peer(request) + ":" + user["email"].lower())
        conn.execute("DELETE FROM login_attempts WHERE account_key=? OR key=?", (token_hash(user["email"].lower()), legacy_current_peer))
        _audit(conn, user["id"], "password_reset.completed")
    settings = recovery_mail.mail_settings()
    if settings is not None:
        _deliver_changed(settings, user["email"], user["id"])
    return {"ok": True, "message": "Dein Passwort wurde geändert. Bitte melde dich mit deinem neuen Passwort an."}
