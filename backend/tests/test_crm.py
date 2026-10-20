"""Real request/database tests; all identities and records are synthetic."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SOULFLOW_DB", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("SOULFLOW_DEMO", "1")
    from app.main import app
    with TestClient(app) as client:
        yield client


def login(api, role="admin"):
    accounts = api.get("/api/demo").json()["accounts"]
    account = next(a for a in accounts if a["role"] == role)
    r = api.post("/api/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"X-SoulFlow": "1"})
    assert r.status_code == 200, r.text
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    return r.json()


def post(api, path, data):
    return api.post(path, json=data, headers={"X-SoulFlow": "1"})


def future_slot(days=10):
    return (datetime.now(ZoneInfo("Europe/Berlin")) + timedelta(days=days)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()


def test_auth_csrf_logout_and_cookie(api):
    assert api.get("/api/clients").status_code == 401
    assert api.post("/api/auth/login", json={"email": "x@example.test", "password": "bad"}).status_code == 403
    login(api)
    assert api.cookies.get("soulflow_session")
    assert api.get("/api/clients").headers["cache-control"] == "no-store"
    assert post(api, "/api/auth/logout", {}).status_code == 200
    assert api.get("/api/auth/me").status_code == 401


def test_portal_hides_other_clients_private_notes_and_unshared_chart(api):
    login(api)
    clients = api.get("/api/clients").json()
    own_id = clients[0]["id"]
    private = post(api, f"/api/clients/{own_id}/resources", {"kind": "note", "title": "Intern", "body": "synthetisch", "shared": False}).json()
    shared = post(api, f"/api/clients/{own_id}/resources", {"kind": "task", "title": "Freigegeben", "body": "Reflexion", "shared": True}).json()
    user = login(api, "client")
    portal = api.get("/api/portal").json()
    assert portal["client"]["id"] == user["client_id"]
    assert portal["client"]["chart"] is None
    assert shared["id"] in [r["id"] for r in portal["resources"]]
    assert private["id"] not in [r["id"] for r in portal["resources"]]
    assert api.get("/api/clients").status_code == 403
    assert api.get(f"/api/clients/{clients[-1]['id']}").status_code == 403
    assert post(api, f"/api/clients/{own_id}/resources", {"kind":"note","title":"Hack","body":"x","shared":True}).status_code == 403


def test_booking_collision_and_preparation_gate(api):
    login(api)
    clients = api.get("/api/clients").json()
    payload = {"client_id": clients[0]["id"], "start_at": future_slot(), "title": "Testsitzung", "duration_minutes": 60}
    first = post(api, "/api/appointments", payload)
    assert first.status_code == 201, first.text
    appointment = first.json()
    assert post(api, "/api/appointments", {**payload, "client_id": clients[-1]["id"]}).status_code == 409
    assert post(api, f"/api/appointments/{appointment['id']}/start", {}).status_code == 409
    assert post(api, f"/api/appointments/{appointment['id']}/prepare", {"acknowledged": True}).status_code == 200
    # Future appointments cannot accidentally be started now.
    assert post(api, f"/api/appointments/{appointment['id']}/start", {}).status_code == 409


def test_client_cannot_book_for_others_or_set_price(api):
    login(api)
    ids = [c["id"] for c in api.get("/api/clients").json()]
    user = login(api, "client")
    other = next(i for i in ids if i != user["client_id"])
    assert post(api, "/api/appointments", {"client_id": other, "start_at": future_slot(), "title": "X"}).status_code == 403
    assert post(api, "/api/appointments", {"client_id": user["client_id"], "start_at": future_slot(), "title":"X", "price_cents":5000}).status_code == 403


def test_invalid_inputs_and_origin(api):
    login(api)
    assert post(api, "/api/clients", {"name": "X", "email": "not-email"}).status_code == 422
    assert post(api, "/api/clients", {"name": "X", "email": "x@example.org", "birth_date": "2020-02-31"}).status_code == 422
    assert post(api, "/api/clients/1/resources", {"kind":"audio", "title":"Test", "body":"", "shared":True,"audio_url":"javascript:alert(1)"}).status_code == 422
    assert api.post("/api/auth/logout", json={}, headers={"X-SoulFlow":"1", "Origin":"https://evil.example"}).status_code == 403


def test_login_throttle(api):
    for _ in range(5):
        r = post(api, "/api/auth/login", {"email":"wrong@example.org", "password":"wrong"})
        assert r.status_code == 401
    assert post(api, "/api/auth/login", {"email":"wrong@example.org", "password":"wrong"}).status_code == 429


def test_session_flow_requires_preparation_and_valid_state(api):
    login(api)
    from app.db import get_db
    with get_db() as conn:
        aid = conn.execute("INSERT INTO appointments(client_id,start_at,duration_minutes,title) VALUES(1,?,60,'Laufender Test')", ((datetime.now(ZoneInfo("UTC"))-timedelta(minutes=5)).isoformat(),)).lastrowid
    assert post(api, f"/api/appointments/{aid}/start", {}).status_code == 409
    assert post(api, f"/api/appointments/{aid}/prepare", {"acknowledged":True}).status_code == 200
    assert post(api, f"/api/appointments/{aid}/start", {}).json()["status"] == "in_progress"
    assert api.patch(f"/api/appointments/{aid}",json={"status":"completed"},headers={"X-SoulFlow":"1"}).json()["status"] == "completed"
    assert post(api, f"/api/appointments/{aid}/start", {}).status_code == 409


def test_birth_changes_revoke_chart_release(api):
    login(api)
    from app.db import get_db
    with get_db() as conn:
        conn.execute("UPDATE clients SET chart='{}',chart_shared=1 WHERE id=1")
    updated = api.patch("/api/clients/1",json={"birth_time":"10:00"},headers={"X-SoulFlow":"1"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["chart"] is None
    assert updated.json()["chart_shared"] is False


def test_practitioner_cannot_create_accounts_or_scan(api):
    login(api,"practitioner")
    assert post(api,"/api/clients/2/portal-account",{"password":"LongTestPassword234"}).status_code==403
    assert post(api,"/api/admin/scan",{"simulate":True}).status_code==403


def test_concurrent_booking_has_one_winner(api):
    from concurrent.futures import ThreadPoolExecutor
    login(api)
    payload={"client_id":1,"start_at":future_slot(15),"title":"Parallel angefragt"}
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses=list(executor.map(lambda _:post(api,"/api/appointments",payload),range(2)))
    assert sorted(r.status_code for r in responses)==[201,409]


def test_logout_revokes_replayed_cookie(api):
    login(api)
    old_token=api.cookies.get("soulflow_session")
    post(api,"/api/auth/logout",{})
    api.cookies.set("soulflow_session",old_token)
    assert api.get("/api/auth/me").status_code==401


def test_chart_payload_and_permissions_are_not_browser_controlled(api):
    login(api)
    assert post(api,"/api/clients/1/chart",{"place_id":"anything", "latitude":52.5,"longitude":13.4}).status_code==422
    assert api.patch("/api/clients/1",json={"role":"admin"},headers={"X-SoulFlow":"1"}).status_code==422


def test_plain_local_mode_has_no_demo_passwords(tmp_path,monkeypatch):
    monkeypatch.setenv("SOULFLOW_DB",str(tmp_path/"local.sqlite3"))
    monkeypatch.setenv("SOULFLOW_DEMO","0")
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/api/demo").status_code==404
        assert client.get("/api/auth/me").status_code==401
        from app.db import get_db
        with get_db() as conn:
            assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0


def test_password_whitespace_roundtrips_without_silent_normalization(api):
    login(api)
    password=" leading-and-trailing "
    assert post(api,"/api/clients/2/portal-account",{"password":password}).status_code==201
    result=post(api,"/api/auth/login",{"email":"jonas@example.org","password":password})
    assert result.status_code==200,result.text
    assert post(api,"/api/auth/login",{"email":"jonas@example.org","password":password.strip()}).status_code==401


def test_booking_respects_seconds_at_closing_time(api):
    login(api)
    closing=(datetime.now(ZoneInfo("Europe/Berlin"))+timedelta(days=30)).replace(hour=18,minute=45,second=30,microsecond=0)
    result=post(api,"/api/appointments",{"client_id":1,"start_at":closing.isoformat(),"duration_minutes":15,"title":"Nach Schluss"})
    assert result.status_code==422,result.text


def test_concurrent_birth_edit_does_not_save_stale_chart(api,monkeypatch):
    login(api)
    from app import astro
    from app.db import get_db
    place=astro.resolve_places("Berlin")[0]
    def edit_while_calculating(*args):
        with get_db() as conn:
            conn.execute("UPDATE clients SET birth_date='2001-02-03' WHERE id=1")
        return {"test":"chart from outdated snapshot"}
    monkeypatch.setattr(astro,"calculate_chart",edit_while_calculating)
    result=post(api,"/api/clients/1/chart",{"place_id":place["id"]})
    assert result.status_code==409,result.text
    assert api.get("/api/clients/1").json()["chart"] is None
