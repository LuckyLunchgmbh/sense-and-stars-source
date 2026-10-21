"""Private, account-bound letters; no recipient or personal text is bundled."""
import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, StrictInt, ValidationError

from .db import get_db
from .schemas import StrictModel
from .security import LEGACY_SESSION_COOKIE, SESSION_COOKIE, now_iso, require_user, token_hash

router = APIRouter(prefix="/api/dedication")


class DedicationContent(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    salutation: Annotated[str, Field(min_length=1, max_length=200)]
    paragraphs: Annotated[list[Annotated[str, Field(min_length=1, max_length=2000)]], Field(min_length=1, max_length=20)]
    closing: Annotated[str, Field(min_length=1, max_length=200)]
    sender: Annotated[str, Field(min_length=1, max_length=150)]


class DedicationDismiss(StrictModel):
    id: Annotated[StrictInt, Field(ge=1)]
    version: Annotated[StrictInt, Field(ge=1)]


def _active_session(conn, request, user_id):
    # Recheck under the write lock on dismissal: revocation must win over stale
    # authentication. Cookie aliases retain the same order as require_user.
    for cookie in (SESSION_COOKIE, LEGACY_SESSION_COOKIE):
        token = request.cookies.get(cookie, "")
        if token and len(token) <= 200:
            digest = token_hash(token)
            row = conn.execute("SELECT token_hash FROM sessions WHERE token_hash=? AND user_id=? AND expires_at>?",
                               (digest, user_id, now_iso())).fetchone()
            if row:
                return digest
    raise HTTPException(401, "Die Sitzung ist abgelaufen. Bitte erneut anmelden.")


def _public_letter(row):
    try:
        content = DedicationContent(title=row["title"], salutation=row["salutation"],
            paragraphs=json.loads(row["paragraphs_json"]), closing=row["closing"], sender=row["sender"])
        return {"id": row["id"], "version": row["content_version"], **content.model_dump()}
    except (ValidationError, ValueError, TypeError):
        # No validation exception can echo private stored text into logs/errors.
        raise HTTPException(503, "Die persönliche Widmung ist gerade nicht verfügbar. Bitte versuche es erneut.") from None


@router.get("")
def own_dedication(request: Request):
    user = require_user(request)
    with get_db() as conn:
        row = conn.execute("SELECT * FROM personal_dedications WHERE user_id=?", (user["id"],)).fetchone()
        if row is None:
            return {"dedication": None, "auto_open": False}
        session = _active_session(conn, request, user["id"])
        viewed = conn.execute("SELECT 1 FROM personal_dedication_views WHERE dedication_id=? AND session_token_hash=? AND content_version=?",
                              (row["id"], session, row["content_version"])).fetchone()
        return {"dedication": _public_letter(row), "auto_open": viewed is None}


@router.post("/dismiss")
def dismiss_dedication(data: DedicationDismiss, request: Request):
    user = require_user(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        session = _active_session(conn, request, user["id"])
        row = conn.execute("SELECT id FROM personal_dedications WHERE user_id=? AND id=? AND content_version=?",
                           (user["id"], data.id, data.version)).fetchone()
        if row is None:
            raise HTTPException(404, "Diese persönliche Widmung ist nicht verfügbar.")
        conn.execute("""INSERT INTO personal_dedication_views
          (dedication_id,session_token_hash,content_version,dismissed_at) VALUES(?,?,?,?)
          ON CONFLICT(dedication_id,session_token_hash,content_version) DO NOTHING""",
          (data.id,session,data.version,now_iso()))
    return {"ok": True}
