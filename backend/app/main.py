"""Sense & Stars single-origin API. Start via scripts/run.py; no public demo exposure."""
import json
import os
import secrets
import sqlite3
import time as clock
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .db import ROOT, db_path, get_db, init_schema
from .config import setting
from .runtime import allowed_hosts, hosted, public_origin, validate_hosted_settings
from .schemas import (AppointmentUpdate, Booking, ChartRequest, ClientCreate, ClientUpdate,
                      Login, PortalAccount, Prepare, ProfileUpdate, ResourceCreate, Share)
from .security import (LEGACY_SESSION_COOKIE, SESSION_COOKIE, hash_password, now_iso,
                       public_user, require_admin, require_staff, require_user, token_hash,
                       verify_password)

BERLIN = ZoneInfo("Europe/Berlin")
DIST = ROOT / "frontend" / "dist"


def demo_mode():
    return setting("DEMO", "0") == "1"


def init_practice_schema(conn):
    """Additive migration: existing records remain real; nothing is reclassified."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(clients)")}
    for name, definition in (("is_test", "INTEGER NOT NULL DEFAULT 0"),
                             ("test_owner_id", "INTEGER REFERENCES users(id)"),
                             ("archived_at", "TEXT"),
                             ("test_email", "TEXT")):
        if name not in columns:
            conn.execute(f"ALTER TABLE clients ADD COLUMN {name} {definition}")
    # A fictional contact address is display data, not a globally unique real
    # client identity. Preserve old test addresses while releasing that identity
    # slot; notes, charts, owners, archive state and all real rows are unchanged.
    for row in conn.execute("SELECT id,email FROM clients WHERE is_test=1 AND test_email IS NULL"):
        conn.execute("UPDATE clients SET test_email=?,email=? WHERE id=? AND is_test=1 AND test_email IS NULL",
                     (row["email"], f"practice-{secrets.token_hex(20)}@sense-and-stars.invalid", row["id"]))
    if "archived_at" not in {row["name"] for row in conn.execute("PRAGMA table_info(appointments)")}:
        conn.execute("ALTER TABLE appointments ADD COLUMN archived_at TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS practice_examples(
        user_id INTEGER NOT NULL REFERENCES users(id), example_key TEXT NOT NULL,
        client_id INTEGER NOT NULL UNIQUE REFERENCES clients(id),
        PRIMARY KEY(user_id, example_key))""")
    conn.execute("CREATE INDEX IF NOT EXISTS practice_clients_owner ON clients(is_test,test_owner_id,archived_at)")


def client_json(row, *, portal=False):
    data = dict(row)
    data["themes"] = json.loads(data["themes"])
    data["chart_shared"] = bool(data["chart_shared"])
    data["is_test"] = bool(data["is_test"])
    test_email = data.pop("test_email", None)
    if data["is_test"] and test_email is not None:
        data["email"] = test_email
    data["chart"] = json.loads(data["chart"]) if data["chart"] and (not portal or data["chart_shared"]) else None
    if portal:
        # Internal client themes and birth details are deliberately withheld.
        data["themes"] = []
    return data


def appointment_json(row):
    data = dict(row)
    data["prepared"] = bool(data["prepared"])
    return data


def resource_json(row):
    data = dict(row)
    data["shared"] = bool(data["shared"])
    return data


def client_row(conn, client_id, user, *, allow_archived=False):
    row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if (not row or (row["archived_at"] and not allow_archived)
            or (row["is_test"] and (user["role"] == "client" or row["test_owner_id"] != user["id"]))):
        raise HTTPException(404, "Klient nicht gefunden.")
    return row


def appointment_row(conn, appointment_id, user):
    row = conn.execute("SELECT a.*,c.name AS client_name FROM appointments a JOIN clients c ON c.id=a.client_id WHERE a.id=?", (appointment_id,)).fetchone()
    if not row or row["archived_at"]:
        raise HTTPException(404, "Termin nicht gefunden.")
    client_row(conn, row["client_id"], user)
    return row


def client_scope(user, practice, *, archived=False, alias="c"):
    """Only this user's synthetic cases or shared non-synthetic practice data."""
    if practice:
        if user["role"] not in ("admin", "practitioner"):
            raise HTTPException(403, "Der Übungsmodus ist für die Beraterin.")
        return f"{alias}.is_test=1 AND {alias}.test_owner_id=? AND {alias}.archived_at IS {'NOT ' if archived else ''}NULL", (user["id"],)
    return f"{alias}.is_test=0 AND {alias}.archived_at IS NULL", ()


def insert_client(conn, data, user, *, practice=False, chart_data=None):
    identity_email = f"practice-{secrets.token_hex(20)}@sense-and-stars.invalid" if practice else data["email"]
    cid = conn.execute("""INSERT INTO clients(name,email,birth_date,birth_time,birth_place,themes,
                          created_at,is_test,test_owner_id,chart,test_email) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                       (data["name"], identity_email, data["birth_date"], data["birth_time"],
                        data["birth_place"], json.dumps(data["themes"]), now_iso(), int(practice),
                        user["id"] if practice else None, json.dumps(chart_data, ensure_ascii=False) if chart_data else None,
                        data["email"] if practice else None)).lastrowid
    audit(conn, user, "practice.client.create" if practice else "client.create", cid)
    return client_json(client_row(conn, cid, user))


def archive_practice_clients(conn, user, client_ids):
    """Archive without deleting notes, charts or appointment state."""
    changed_clients = changed_appointments = 0
    stamp = now_iso()
    for cid in client_ids:
        changed_clients += conn.execute("UPDATE clients SET archived_at=? WHERE id=? AND is_test=1 AND test_owner_id=? AND archived_at IS NULL", (stamp, cid, user["id"])).rowcount
        changed_appointments += conn.execute("UPDATE appointments SET archived_at=? WHERE client_id=? AND archived_at IS NULL AND EXISTS(SELECT 1 FROM clients WHERE id=? AND is_test=1 AND test_owner_id=?)", (stamp, cid, cid, user["id"])).rowcount
    return {"ok": True, "archived_clients": changed_clients, "archived_appointments": changed_appointments}


def audit(conn, user, action, resource_id=None):
    conn.execute("INSERT INTO audit(user_id,action,resource_id,created_at) VALUES(?,?,?,?)", (user["id"], action, resource_id, now_iso()))


def seed_demo(conn):
    credentials_path = db_path().parent / "demo-accounts.json"
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return
    clients = [("Lea Winter", "lea@example.org", "1992-05-14", "09:35", "Berlin", ["Grenzen im Berufsalltag", "Eigene Bedürfnisse"]),
               ("Jonas Licht", "jonas@example.org", "1987-11-02", "14:20", "Hamburg", ["Neuorientierung"]),
               ("Nora Berg", "nora@example.org", "1995-03-21", "07:10", "München", ["Selbstvertrauen", "Reflexion"])]
    for name,email,bdate,btime,place,themes in clients:
        conn.execute("INSERT INTO clients(name,email,birth_date,birth_time,birth_place,themes,created_at) VALUES(?,?,?,?,?,?,?)", (name,email,bdate,btime,place,json.dumps(themes),now_iso()))
    accounts = []
    for name,email,role,cid in [("Betreiber · Demo","admin@sense-and-stars.example.org","admin",None), ("Beraterin · Demo","praxis@sense-and-stars.example.org","practitioner",None), ("Lea · Demo","lea@example.org","client",1)]:
        password = secrets.token_urlsafe(18)
        conn.execute("INSERT INTO users(name,email,password_hash,role,client_id,created_at) VALUES(?,?,?,?,?,?)", (name,email,hash_password(password),role,cid,now_iso()))
        accounts.append({"name":name,"email":email,"password":password,"role":role})
    base = (datetime.now(BERLIN) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    for cid,days,title,fee in [(1,0,"Raum für deine Bedürfnisse",8500),(2,0,"Neue Perspektiven",8500),(3,1,"Ankommen & Kennenlernen",0)]:
        start = base + timedelta(days=days,hours=2 if cid==2 else 0)
        conn.execute("INSERT INTO appointments(client_id,start_at,duration_minutes,title,price_cents) VALUES(?,?,?,?,?)", (cid,start.astimezone(timezone.utc).isoformat(),60,title,fee))
    conn.execute("INSERT INTO resources(client_id,kind,title,body,shared,created_at) VALUES(1,'task',?,?,1,?)", ("Dein kleiner Wochenimpuls", "Notiere eine Situation, in der du dir mehr Raum gewünscht hast. Was wäre ein freundlicher nächster Schritt?",now_iso()))
    conn.execute("INSERT INTO resources(client_id,kind,title,body,shared,created_at) VALUES(1,'note',?,?,0,?)", ("Interne Beispielnotiz", "Synthetische Demodaten. Im Portal nicht sichtbar.",now_iso()))
    credentials_path.write_text(json.dumps({"accounts":accounts},ensure_ascii=False,indent=2),encoding="utf-8")
    credentials_path.chmod(0o600)


def initialize():
    validate_hosted_settings()
    from .learning import init_learning
    with get_db() as conn:
        init_schema(conn)
        init_practice_schema(conn)
        mode = "demo" if demo_mode() else "local"
        stored = conn.execute("SELECT value FROM meta WHERE key='mode'").fetchone()
        if stored and stored[0] != mode:
            raise RuntimeError("Demo und lokale Praxis brauchen getrennte Datenbanken. SENSE_AND_STARS_DB prüfen.")
        conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('mode',?)",(mode,))
        if demo_mode():
            seed_demo(conn)
        init_learning(conn)


@asynccontextmanager
async def lifespan(_app):
    initialize()
    yield


app = FastAPI(title="Sense & Stars",version="1.2.1",lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts())


@app.middleware("http")
async def guard(request: Request, call_next):
    if hosted() and request.url.hostname != urlparse(public_origin()).hostname:
        if request.method != "GET" or request.url.path != "/api/internal/learning-updates":
            return JSONResponse({"detail":"Ungültige App-Adresse."},status_code=400)
    # The loopback guard applies only to the explicitly local runtime.
    if not hosted() and request.client and request.client.host not in ("127.0.0.1","::1","testclient"):
        return JSONResponse({"detail":"Diese lokale V1 ist nur über Loopback freigegeben."},status_code=403)
    if request.url.path.startswith("/api") and request.method in ("POST","PUT","PATCH","DELETE"):
        origin = request.headers.get("origin")
        expected = public_origin() if hosted() else f"{request.url.scheme}://{request.headers.get('host','')}"
        valid_csrf = (request.headers.get("x-sense-and-stars") == "1"
                      or request.headers.get("x-soulflow") == "1")
        if not valid_csrf or (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail":"Sicherheitsprüfung fehlgeschlagen. Bitte Sense & Stars direkt öffnen."},status_code=403)
        try:
            size = int(request.headers.get("content-length","0"))
        except ValueError:
            return JSONResponse({"detail":"Ungültige Anfragegröße."},status_code=400)
        if size > 262144:
            return JSONResponse({"detail":"Anfrage zu groß (maximal 256 KiB)."},status_code=413)
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; media-src 'self' https:; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if hosted():
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(_request, _exc):
    return JSONResponse({"detail":"Dieser Datensatz oder diese E-Mail-Adresse existiert bereits. Bitte Angaben prüfen."},status_code=409)


@app.exception_handler(sqlite3.OperationalError)
async def database_error(_request, _exc):
    return JSONResponse({"detail":"Die Datenbank ist vorübergehend nicht verfügbar. Bitte erneut versuchen."},status_code=503)


@app.get("/api/health")
def health():
    return {"status":"ok","mode":"hosted" if hosted() else "demo" if demo_mode() else "local","version":"1.2.1",
            "source_url":setting("SOURCE_URL") if setting("SWISS_LICENSE")=="agpl-3.0" else None,
            "license":"AGPL-3.0-only" if setting("SWISS_LICENSE")=="agpl-3.0" else None}


@app.get("/api/demo")
def demo():
    if hosted() or not demo_mode():
        raise HTTPException(404,"Demozugänge sind deaktiviert.")
    path = db_path().parent / "demo-accounts.json"
    if not path.exists():
        raise HTTPException(503,"Lokale Demo-Zugangsdatei fehlt. Kein Passwort wird automatisch zurückgesetzt.")
    return {**json.loads(path.read_text()),"notice":"Lokale Demo mit ausschließlich erfundenen Klienten. Keine echten Daten eingeben."}


@app.post("/api/auth/login")
def login(data: Login, request: Request, response: Response):
    # Limit per account and local peer; hash the key so attempts do not store emails.
    key = token_hash((request.client.host if request.client else "local") + ":" + data.email.lower())
    now = clock.time()
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM login_attempts WHERE first_at<?",(now-600,))
        attempt = conn.execute("SELECT * FROM login_attempts WHERE key=?",(key,)).fetchone()
        if attempt and attempt["failures"] >= 5:
            raise HTTPException(429,"Zu viele Anmeldeversuche. Bitte in zehn Minuten erneut versuchen.")
        row = conn.execute("SELECT * FROM users WHERE email=?",(data.email.lower(),)).fetchone()
        valid = verify_password(data.password, row["password_hash"] if row else DUMMY_HASH)
        if not row or not valid:
            conn.execute("INSERT INTO login_attempts(key,failures,first_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET failures=login_attempts.failures+1",(key,now))
            conn.commit()  # Failed attempts survive the HTTP exception rollback.
            raise HTTPException(401,"E-Mail-Adresse oder Passwort ist nicht korrekt.")
        conn.execute("DELETE FROM login_attempts WHERE key=?",(key,))
        conn.execute("DELETE FROM sessions WHERE expires_at<?",(now_iso(),))
        token = secrets.token_urlsafe(40)
        expiry = (datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()
        conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",(token_hash(token),row["id"],expiry))
        audit(conn,row,"login")
    response.set_cookie(SESSION_COOKIE,token,httponly=True,samesite="strict",secure=hosted() or request.url.scheme=="https",max_age=28800,path="/")
    return public_user(row)


DUMMY_HASH = hash_password("dummy-verification-not-an-account")


@app.get("/api/auth/me")
def me(request: Request):
    return require_user(request)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    with get_db() as conn:
        for cookie in (SESSION_COOKIE, LEGACY_SESSION_COOKIE):
            token = request.cookies.get(cookie, "")
            if token:
                conn.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash(token),))
    response.delete_cookie(SESSION_COOKIE,path="/",httponly=True,samesite="strict")
    response.delete_cookie(LEGACY_SESSION_COOKIE,path="/",httponly=True,samesite="strict")
    return {"ok":True}


@app.patch("/api/auth/me")
def profile(data: ProfileUpdate,request: Request):
    user = require_user(request)
    with get_db() as conn:
        conn.execute("UPDATE users SET tour_completed=? WHERE id=?",(int(data.tour_completed),user["id"]))
    return {**user,"tour_completed":data.tour_completed}


@app.get("/api/clients")
def clients(request: Request, practice: bool = False, archived: bool = False):
    user = require_staff(request)
    where, args = client_scope(user, practice, archived=archived)
    with get_db() as conn:
        return [client_json(row) for row in conn.execute("SELECT c.* FROM clients c WHERE " + where + " ORDER BY c.id", args)]


@app.post("/api/clients",status_code=201)
def create_client(data: ClientCreate,request: Request):
    user = require_staff(request)
    d = data.model_dump(mode="json")
    with get_db() as conn:
        return insert_client(conn, d, user)


@app.post("/api/practice/clients", status_code=201)
def create_practice_client(data: ClientCreate, request: Request):
    user = require_staff(request)
    with get_db() as conn:
        return insert_client(conn, data.model_dump(mode="json"), user, practice=True)


@app.post("/api/practice/clients/examples")
def practice_examples(request: Request):
    from .astro import calculate_chart, resolve_places
    user = require_staff(request)
    # These three fixed places are in the existing offline gazetteer. No identity
    # or birth data is sent to a provider; actual charts use the regular engine.
    fixtures = (
        ("mira", "Mira Morgen (fiktiv)", "1992-05-14", "09:35", "Berlin", ["Eigene Bedürfnisse", "Grenzen üben"]),
        ("jan", "Jan Wandel (fiktiv)", "1987-11-02", "14:20", "Wien", ["Neuorientierung", "Gespräch üben"]),
        ("nora", "Nora Licht (fiktiv)", "1995-03-21", "07:10", "Zürich", ["Selbstvertrauen", "Reflexion üben"]),
    )
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        result = []
        for key, name, bdate, btime, place, themes in fixtures:
            existing = conn.execute("SELECT c.* FROM practice_examples p JOIN clients c ON c.id=p.client_id WHERE p.user_id=? AND p.example_key=? AND c.is_test=1 AND c.test_owner_id=? AND c.archived_at IS NULL", (user["id"], key, user["id"])).fetchone()
            if existing:
                result.append(client_json(existing))
                continue
            place_data = resolve_places(place)[0]
            chart_data = calculate_chart(bdate, btime, place_data)
            data = {"name": name, "email": f"practice-{user['id']}-{key}-{secrets.token_hex(5)}@example.org", "birth_date": bdate, "birth_time": btime, "birth_place": place, "themes": themes}
            created = insert_client(conn, data, user, practice=True, chart_data=chart_data)
            conn.execute("INSERT INTO practice_examples(user_id,example_key,client_id) VALUES(?,?,?) ON CONFLICT(user_id,example_key) DO UPDATE SET client_id=excluded.client_id", (user["id"], key, created["id"]))
            result.append(created)
        return result


@app.delete("/api/practice/clients/{client_id}")
def archive_practice_client(client_id: int, request: Request):
    user = require_staff(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = client_row(conn, client_id, user, allow_archived=True)
        if not row["is_test"]:
            raise HTTPException(404, "Übungsfall nicht gefunden.")
        archive_practice_clients(conn, user, [client_id])
        audit(conn, user, "practice.client.archive", client_id)
    return {"ok": True}


@app.post("/api/practice/clients/{client_id}/restore")
def restore_practice_client(client_id: int, request: Request):
    user = require_staff(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = client_row(conn, client_id, user, allow_archived=True)
        if not row["is_test"]:
            raise HTTPException(404, "Übungsfall nicht gefunden.")
        # Restoring also restores appointment state. Do not silently create two
        # active bookings for a slot reused since this case was archived.
        if row["archived_at"]:
            restored_times = conn.execute("SELECT start_at,duration_minutes FROM appointments WHERE client_id=? AND archived_at IS NOT NULL AND status!='cancelled'", (client_id,)).fetchall()
            active_times = conn.execute("SELECT a.start_at,a.duration_minutes FROM appointments a JOIN clients c ON c.id=a.client_id WHERE c.is_test=1 AND c.test_owner_id=? AND c.archived_at IS NULL AND a.archived_at IS NULL AND a.status!='cancelled'", (user["id"],)).fetchall()
            for old in restored_times:
                old_start = datetime.fromisoformat(old["start_at"])
                old_end = old_start + timedelta(minutes=old["duration_minutes"])
                for active in active_times:
                    active_start = datetime.fromisoformat(active["start_at"])
                    if old_start < active_start + timedelta(minutes=active["duration_minutes"]) and active_start < old_end:
                        raise HTTPException(409, "Ein früherer Übungstermin überschneidet sich mit einem aktiven Übungstermin. Bitte den aktiven Übungstermin zuerst absagen; danach den Testfall wiederherstellen.")
        conn.execute("UPDATE clients SET archived_at=NULL WHERE id=?", (client_id,))
        conn.execute("UPDATE appointments SET archived_at=NULL WHERE client_id=?", (client_id,))
        audit(conn, user, "practice.client.restore", client_id)
        return client_json(client_row(conn, client_id, user))


@app.post("/api/practice/reset")
def reset_practice(request: Request):
    user = require_staff(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ids = [r["id"] for r in conn.execute("SELECT id FROM clients WHERE is_test=1 AND test_owner_id=? AND archived_at IS NULL", (user["id"],))]
        result = archive_practice_clients(conn, user, ids)
        audit(conn, user, "practice.reset")
        return result


@app.get("/api/clients/{client_id}")
def client_detail(client_id: int,request: Request):
    user = require_staff(request)
    with get_db() as conn:
        return client_json(client_row(conn,client_id,user))


@app.patch("/api/clients/{client_id}")
def update_client(client_id: int,data: ClientUpdate,request: Request):
    user = require_staff(request)
    changes = data.model_dump(exclude_unset=True,mode="json")
    if any(changes.get(k,"ok") is None for k in ("name","email","themes","chart_shared")):
        raise HTTPException(422,"Name, E-Mail, Themen und Freigabe dürfen nicht null sein.")
    with get_db() as conn:
        old = client_row(conn,client_id,user)
        linked = conn.execute("SELECT id FROM users WHERE client_id=?",(client_id,)).fetchone()
        if linked and "email" in changes and changes["email"] != old["email"]:
            raise HTTPException(409,"Für diesen Klienten besteht ein Portalzugang. E-Mail-Wechsel benötigt eine kontrollierte Kontomigration.")
        if old["is_test"] and "email" in changes:
            changes["test_email"] = changes.pop("email")
        birth_changed = any(k in changes and changes[k] != old[k] for k in ("birth_date","birth_time","birth_place"))
        if birth_changed:
            changes.update(chart=None,chart_shared=False)
        for key,value in changes.items():
            if key == "themes": value = json.dumps(value)
            if key == "chart_shared": value = int(value)
            conn.execute(f"UPDATE clients SET {key}=? WHERE id=?",(value,client_id))  # keys only from strict model
        audit(conn,user,"client.update",client_id)
        return client_json(client_row(conn,client_id,user))


@app.post("/api/clients/{client_id}/portal-account",status_code=201)
def portal_account(client_id: int,data: PortalAccount,request: Request):
    user = require_admin(request)
    with get_db() as conn:
        client = client_row(conn,client_id,user)
        if client["is_test"]:
            raise HTTPException(409, "Für fiktive Übungsfälle wird kein Kundenportal-Konto angelegt.")
        conn.execute("INSERT INTO users(name,email,password_hash,role,client_id,created_at) VALUES(?,?,?,'client',?,?)",(client["name"],client["email"],hash_password(data.password),client_id,now_iso()))
        audit(conn,user,"portal.create",client_id)
    return {"ok":True,"email":client["email"]}


@app.get("/api/clients/{client_id}/resources")
def resources(client_id: int,request: Request):
    user = require_staff(request)
    with get_db() as conn:
        client_row(conn,client_id,user)
        return [resource_json(r) for r in conn.execute("SELECT * FROM resources WHERE client_id=? ORDER BY id DESC",(client_id,))]


@app.post("/api/clients/{client_id}/resources",status_code=201)
def create_resource(client_id: int,data: ResourceCreate,request: Request):
    user = require_staff(request)
    if data.kind=="audio" and not data.audio_url:
        raise HTTPException(422,"Für eine Audio-Meditation wird ein HTTPS-Audio-Link benötigt.")
    with get_db() as conn:
        client_row(conn,client_id,user)
        rid = conn.execute("INSERT INTO resources(client_id,kind,title,body,shared,audio_url,created_at) VALUES(?,?,?,?,?,?,?)",(client_id,data.kind,data.title,data.body,int(data.shared),data.audio_url,now_iso())).lastrowid
        audit(conn,user,"resource.create",rid)
        return resource_json(conn.execute("SELECT * FROM resources WHERE id=?",(rid,)).fetchone())


@app.patch("/api/resources/{resource_id}")
def share_resource(resource_id: int,data: Share,request: Request):
    user = require_staff(request)
    with get_db() as conn:
        row = conn.execute("SELECT * FROM resources WHERE id=?",(resource_id,)).fetchone()
        if not row: raise HTTPException(404,"Inhalt nicht gefunden.")
        client_row(conn, row["client_id"], user)
        conn.execute("UPDATE resources SET shared=? WHERE id=?",(int(data.shared),resource_id))
        audit(conn,user,"resource.share" if data.shared else "resource.unshare",resource_id)
        return resource_json(conn.execute("SELECT * FROM resources WHERE id=?",(resource_id,)).fetchone())


@app.get("/api/appointments")
def appointments(request: Request, practice: bool = False):
    user = require_user(request)
    where, args = client_scope(user, practice)
    if user["role"] == "client":
        where += " AND a.client_id=?"
        args += (user["client_id"],)
    with get_db() as conn:
        return [appointment_json(r) for r in conn.execute("SELECT a.*,c.name AS client_name FROM appointments a JOIN clients c ON c.id=a.client_id WHERE a.archived_at IS NULL AND "+where+" ORDER BY start_at",args)]


@app.post("/api/appointments",status_code=201)
def book(data: Booking,request: Request):
    user = require_user(request)
    if user["role"]=="client" and (data.client_id != user["client_id"] or data.price_cents != 0):
        raise HTTPException(403,"Du kannst ausschließlich für dich selbst einen Folgetermin ohne Preisänderung buchen.")
    start = data.start_at.astimezone(timezone.utc)
    end = start + timedelta(minutes=data.duration_minutes)
    local_start,local_end = start.astimezone(BERLIN),end.astimezone(BERLIN)
    if start <= datetime.now(timezone.utc):
        raise HTTPException(422,"Bitte einen zukünftigen Termin wählen.")
    if start > datetime.now(timezone.utc)+timedelta(days=366):
        raise HTTPException(422,"Termine sind bis zu einem Jahr im Voraus buchbar.")
    if local_start.time() < time(8) or local_end.time() > time(19) or local_start.date()!=local_end.date():
        raise HTTPException(422,"Die Praxiszeiten sind 08:00 bis 19:00 Uhr (Europe/Berlin).")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")  # Serializes overlap check + insert across requests.
        client = client_row(conn,data.client_id,user)
        where, args = client_scope(user, bool(client["is_test"]))
        for row in conn.execute("SELECT a.start_at,a.duration_minutes FROM appointments a JOIN clients c ON c.id=a.client_id WHERE a.status!='cancelled' AND a.archived_at IS NULL AND "+where, args):
            other = datetime.fromisoformat(row["start_at"])
            if start < other+timedelta(minutes=row["duration_minutes"]) and other < end:
                raise HTTPException(409,"Dieser Zeitraum ist bereits belegt. Bitte einen anderen Termin wählen.")
        aid = conn.execute("INSERT INTO appointments(client_id,start_at,duration_minutes,title,price_cents) VALUES(?,?,?,?,?)",(data.client_id,start.isoformat(),data.duration_minutes,data.title,data.price_cents)).lastrowid
        audit(conn,user,"appointment.book",aid)
        return appointment_json(appointment_row(conn,aid,user))


@app.post("/api/appointments/{appointment_id}/prepare")
def prepare(appointment_id: int,data: Prepare,request: Request):
    user = require_staff(request)
    with get_db() as conn:
        row=appointment_row(conn,appointment_id,user)
        if row["status"]!="scheduled": raise HTTPException(409,"Nur geplante Termine können vorbereitet werden.")
        conn.execute("UPDATE appointments SET prepared=1 WHERE id=?",(appointment_id,))
        audit(conn,user,"appointment.prepare",appointment_id)
        return appointment_json(appointment_row(conn,appointment_id,user))


@app.post("/api/appointments/{appointment_id}/start")
def start_session(appointment_id: int,request: Request):
    user = require_staff(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row=appointment_row(conn,appointment_id,user)
        if not row["prepared"]: raise HTTPException(409,"Bitte zuerst im Empathischen Schutzbereich ankommen und die Vorbereitung bestätigen.")
        if row["status"]!="scheduled": raise HTTPException(409,"Dieser Termin ist nicht mehr geplant.")
        start=datetime.fromisoformat(row["start_at"])
        now=datetime.now(timezone.utc)
        if now < start-timedelta(minutes=15) or now > start+timedelta(minutes=row["duration_minutes"]):
            raise HTTPException(409,"Eine Sitzung kann ab 15 Minuten vor Beginn und während des Terminzeitraums gestartet werden.")
        conn.execute("UPDATE appointments SET status='in_progress' WHERE id=?",(appointment_id,))
        audit(conn,user,"appointment.start",appointment_id)
        return appointment_json(appointment_row(conn,appointment_id,user))


@app.patch("/api/appointments/{appointment_id}")
def appointment_status(appointment_id: int,data: AppointmentUpdate,request: Request):
    user = require_staff(request)
    with get_db() as conn:
        row=appointment_row(conn,appointment_id,user)
        if row["status"] in ("completed","cancelled") or (data.status=="completed" and row["status"]!="in_progress"):
            raise HTTPException(409,"Dieser Statuswechsel ist für den Termin nicht möglich.")
        conn.execute("UPDATE appointments SET status=? WHERE id=?",(data.status,appointment_id))
        audit(conn,user,"appointment."+data.status,appointment_id)
        return appointment_json(appointment_row(conn,appointment_id,user))


@app.get("/api/dashboard")
def dashboard(request: Request, practice: bool = False):
    user = require_staff(request)
    where, args = client_scope(user, practice)
    with get_db() as conn:
        appointment_scope = " FROM appointments a JOIN clients c ON c.id=a.client_id WHERE a.archived_at IS NULL AND " + where
        return {"clients_count":conn.execute("SELECT COUNT(*) FROM clients c WHERE " + where, args).fetchone()[0],
                "upcoming_count":conn.execute("SELECT COUNT(*)" + appointment_scope + " AND a.status='scheduled' AND a.start_at>?", (*args, now_iso())).fetchone()[0],
                "completed_count":conn.execute("SELECT COUNT(*)" + appointment_scope + " AND a.status='completed'", args).fetchone()[0],
                "revenue_cents":0 if practice else conn.execute("SELECT COALESCE(SUM(a.price_cents),0)" + appointment_scope + " AND a.status='completed'", args).fetchone()[0],
                "appointments":[appointment_json(r) for r in conn.execute("SELECT a.*,c.name AS client_name" + appointment_scope + " AND a.status IN ('scheduled','in_progress') ORDER BY a.start_at LIMIT 6", args)],
                "clients":[client_json(r) for r in conn.execute("SELECT c.* FROM clients c WHERE " + where + " ORDER BY c.id LIMIT 5", args)]}


@app.post("/api/clients/{client_id}/chart")
def chart(client_id: int,data: ChartRequest,request: Request):
    from .astro import calculate_chart, get_place
    user = require_staff(request)
    with get_db() as conn:
        row=client_row(conn,client_id,user)
    if not row["birth_date"] or not row["birth_time"]:
        raise HTTPException(422,"Bitte zuerst Geburtsdatum und genaue Geburtszeit im Klientenprofil ergänzen.")
    place=get_place(data.place_id)
    result=calculate_chart(row["birth_date"],row["birth_time"],place,data.fold)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current=client_row(conn,client_id,user)
        if any(current[key] != row[key] for key in ("birth_date","birth_time","birth_place")):
            raise HTTPException(409,"Die Geburtsdaten wurden während der Berechnung geändert. Bitte mit den aktuellen Daten erneut berechnen.")
        # Never silently republish a changed chart; every recalculation clears release.
        conn.execute("UPDATE clients SET chart=?,chart_shared=0,birth_place=? WHERE id=?",(json.dumps(result,ensure_ascii=False),place["label"],client_id))
        audit(conn,user,"chart.calculate",client_id)
    return result


@app.get("/api/portal")
def portal(request: Request):
    user = require_user(request)
    if user["role"]!="client" or not user["client_id"]:
        raise HTTPException(403,"Dieser Bereich ist für Klienten mit eigenem Portalzugang.")
    with get_db() as conn:
        return {"client":client_json(client_row(conn,user["client_id"],user),portal=True),
                "appointments":[appointment_json(r) for r in conn.execute("SELECT a.*,c.name AS client_name FROM appointments a JOIN clients c ON c.id=a.client_id WHERE a.client_id=? ORDER BY start_at",(user["client_id"],))],
                "resources":[resource_json(r) for r in conn.execute("SELECT * FROM resources WHERE client_id=? AND shared=1 ORDER BY id DESC",(user["client_id"],))]}


from .astro import router as astro_router
from .learning import router as learning_router
app.include_router(astro_router)
app.include_router(learning_router)


@app.get("/{path:path}",include_in_schema=False)
def frontend(path: str):
    if path.startswith("api/") or path=="api":
        raise HTTPException(404,"Schnittstelle nicht gefunden.")
    candidate=(DIST/path).resolve()
    if DIST.resolve() in candidate.parents and candidate.is_file():
        response=FileResponse(candidate)
        if path=="sw.js": response.headers["Cache-Control"]="no-cache"
        return response
    if Path(path).suffix:
        raise HTTPException(404,"Datei nicht gefunden.")
    if (DIST/"index.html").exists():
        return FileResponse(DIST/"index.html",headers={"Cache-Control":"no-cache"})
    raise HTTPException(503,"Frontend ist noch nicht gebaut. Bitte npm run build im frontend-Ordner ausführen.")
