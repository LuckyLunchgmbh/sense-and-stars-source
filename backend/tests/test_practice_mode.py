"""Practice data stays private, recoverable and outside real practice totals."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SOULFLOW_DB", str(tmp_path / "practice.sqlite3"))
    monkeypatch.setenv("SOULFLOW_DEMO", "1")
    from app.main import app
    with TestClient(app) as client:
        yield client


def login(api, role="practitioner"):
    account = next(a for a in api.get("/api/demo").json()["accounts"] if a["role"] == role)
    result = mutate(api, "POST", "/api/auth/login", {"email": account["email"], "password": account["password"]})
    assert result.status_code == 200, result.text
    return result.json()


def mutate(api, method, path, body=None):
    return api.request(method, path, json=body or {}, headers={"X-SoulFlow": "1"})


def examples(api):
    result = mutate(api, "POST", "/api/practice/clients/examples")
    assert result.status_code == 200, result.text
    return result.json()


def slot(days=10):
    return (datetime.now(ZoneInfo("Europe/Berlin")) + timedelta(days=days)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()


def test_examples_are_complete_idempotent_and_separate_from_real_clients(api):
    owner = login(api)
    real = api.get("/api/clients").json()
    created = examples(api)
    assert len(created) == 3
    assert created == examples(api)
    assert api.get("/api/clients").json() == real
    assert api.get("/api/clients?practice=1").json() == created
    for item in created:
        assert item["is_test"] is True
        assert item["test_owner_id"] == owner["id"]
        assert item["archived_at"] is None
        assert item["birth_date"] and item["birth_time"] and item["birth_place"]
        assert item["chart"]["planets"]
        assert "fiktiv" in item["name"].lower()


def test_test_owner_cannot_be_forged_in_normal_or_practice_creation(api):
    owner = login(api)
    payload = {"name": "Fiktiv · eigener Fall", "email": "practice-new@example.org", "birth_date": "1990-02-03", "birth_time": "10:30", "birth_place": "Berlin"}
    result = mutate(api, "POST", "/api/practice/clients", payload)
    assert result.status_code == 201, result.text
    assert result.json()["is_test"] is True
    assert result.json()["test_owner_id"] == owner["id"]
    for route in ("/api/clients", "/api/practice/clients"):
        assert mutate(api, "POST", route, {**payload, "test_owner_id": 1}).status_code == 422
        assert mutate(api, "POST", route, {**payload, "is_test": False}).status_code == 422


def test_foreign_staff_cannot_read_or_change_test_clients_resources_or_charts(api):
    login(api)
    case = examples(api)[0]
    resource = mutate(api, "POST", f"/api/clients/{case['id']}/resources", {"kind": "note", "title": "Privater Übungsfall", "body": "Nur mein Test", "shared": False})
    assert resource.status_code == 201, resource.text
    login(api, "admin")
    assert api.get("/api/clients?practice=1").json() == []
    for method, path, body in (
        ("GET", f"/api/clients/{case['id']}", {}),
        ("PATCH", f"/api/clients/{case['id']}", {"name": "Fremd"}),
        ("GET", f"/api/clients/{case['id']}/resources", {}),
        ("POST", f"/api/clients/{case['id']}/resources", {"kind": "note", "title": "Fremd"}),
        ("PATCH", f"/api/resources/{resource.json()['id']}", {"shared": True}),
        ("POST", f"/api/clients/{case['id']}/chart", {"place_id": "unknown"}),
        ("DELETE", f"/api/practice/clients/{case['id']}", {}),
        ("POST", f"/api/practice/clients/{case['id']}/restore", {}),
    ):
        result = mutate(api, method, path, body)
        assert result.status_code == 404, (method, path, result.text)
    assert api.get("/api/clients").json()  # Shared real records remain available.


def test_archive_and_restore_retain_notebook_chart_and_appointment(api):
    login(api)
    case = examples(api)[0]
    note = mutate(api, "POST", f"/api/clients/{case['id']}/resources", {"kind": "note", "title": "Aufbewahren", "body": "Wiederherstellbare Testnotiz"}).json()
    appt = mutate(api, "POST", "/api/appointments", {"client_id": case["id"], "start_at": slot(), "title": "Übungssitzung"}).json()
    assert mutate(api, "DELETE", f"/api/practice/clients/{case['id']}").status_code == 200
    assert api.get(f"/api/clients/{case['id']}").status_code == 404
    assert api.get("/api/appointments?practice=1").json() == []
    archived = api.get("/api/clients?practice=1&archived=1").json()
    assert [a["id"] for a in archived] == [case["id"]]
    assert archived[0]["archived_at"]
    restored = mutate(api, "POST", f"/api/practice/clients/{case['id']}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["chart"] == case["chart"]
    assert api.get(f"/api/clients/{case['id']}/resources").json() == [note]
    assert [a["id"] for a in api.get("/api/appointments?practice=1").json()] == [appt["id"]]
    assert mutate(api, "POST", f"/api/practice/clients/{case['id']}/restore").status_code == 200


def test_reset_only_archives_own_test_records_and_new_examples_start_fresh(api):
    login(api, "admin")
    real = api.get("/api/clients").json()
    real_appt = mutate(api, "POST", "/api/appointments", {"client_id": real[0]["id"], "start_at": slot(), "title": "Echte Praxis"})
    assert real_appt.status_code == 201
    other = examples(api)
    login(api)
    own = examples(api)
    practice_appt = mutate(api, "POST", "/api/appointments", {"client_id": own[0]["id"], "start_at": slot(), "title": "Eigene Übung"})
    assert practice_appt.status_code == 201, practice_appt.text
    reset = mutate(api, "POST", "/api/practice/reset")
    assert reset.status_code == 200, reset.text
    assert reset.json() == {"ok": True, "archived_clients": 3, "archived_appointments": 1}
    assert api.get("/api/clients?practice=1").json() == []
    assert api.get("/api/appointments?practice=1").json() == []
    assert api.get("/api/clients").json() == real
    assert real_appt.json() in api.get("/api/appointments").json()
    fresh = examples(api)
    assert len(fresh) == 3
    assert not set(c["id"] for c in fresh) & set(c["id"] for c in own)
    assert len(api.get("/api/clients?practice=1&archived=1").json()) == 3
    login(api, "admin")
    assert api.get("/api/clients?practice=1").json() == other


def test_tests_do_not_change_real_totals_and_foreign_appointments_are_protected(api):
    login(api)
    before = api.get("/api/dashboard").json()
    case = examples(api)[0]
    appt = mutate(api, "POST", "/api/appointments", {"client_id": case["id"], "start_at": slot(), "title": "Testsitzung", "price_cents": 9900})
    assert appt.status_code == 201, appt.text
    assert api.get("/api/dashboard").json() == before
    own_dashboard = api.get("/api/dashboard?practice=1").json()
    assert own_dashboard["clients_count"] == 3
    assert own_dashboard["upcoming_count"] == 1
    assert own_dashboard["revenue_cents"] == 0
    login(api, "admin")
    assert api.get("/api/appointments?practice=1").json() == []
    for method, path, body in (
        ("POST", "/api/appointments", {"client_id": case["id"], "start_at": slot(11), "title": "Fremd"}),
        ("POST", f"/api/appointments/{appt.json()['id']}/prepare", {"acknowledged": True}),
        ("POST", f"/api/appointments/{appt.json()['id']}/start", {}),
        ("PATCH", f"/api/appointments/{appt.json()['id']}", {"status": "cancelled"}),
    ):
        assert mutate(api, method, path, body).status_code == 404, path


def test_test_accounts_cannot_create_portal_accounts_and_clients_cannot_use_practice(api):
    login(api, "admin")
    case = examples(api)[0]
    result = mutate(api, "POST", f"/api/clients/{case['id']}/portal-account", {"password": "SyntheticPassword-1234"})
    assert result.status_code == 409, result.text
    real_id = api.get("/api/clients").json()[0]["id"]
    assert mutate(api, "DELETE", f"/api/practice/clients/{real_id}").status_code == 404
    assert mutate(api, "POST", f"/api/practice/clients/{real_id}/restore").status_code == 404
    login(api, "client")
    for path in ("/api/practice/reset", "/api/practice/clients/examples"):
        assert mutate(api, "POST", path).status_code == 403
    assert mutate(api, "POST", "/api/practice/clients", {"name": "Fiktiv", "email": "client-created@example.org"}).status_code == 403
    assert api.get("/api/clients?practice=1").status_code == 403
    assert api.get("/api/appointments?practice=1").status_code == 403


def test_practice_mutations_require_csrf_and_preserve_history_in_database(api):
    login(api)
    assert api.post("/api/practice/clients/examples", json={}).status_code == 403
    created = examples(api)
    mutate(api, "POST", "/api/practice/reset")
    from app.db import get_db
    from app.main import initialize
    initialize()
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM clients WHERE is_test=1").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM clients WHERE is_test=0 AND archived_at IS NULL").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM clients WHERE archived_at IS NOT NULL").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM audit WHERE action='practice.reset'").fetchone()[0] == 1
    assert [c["id"] for c in api.get("/api/clients?practice=1&archived=1").json()] == [c["id"] for c in created]


def test_example_charts_never_call_external_geocoder(api, monkeypatch):
    from app import astro
    def forbidden_provider(_query):
        raise AssertionError("Practice example sent data outside the app")
    monkeypatch.setattr(astro, "_query_provider", forbidden_provider)
    login(api)
    assert len(examples(api)) == 3


def test_archived_case_blocks_resources_and_bookings_until_restored(api):
    login(api)
    case = examples(api)[0]
    note = mutate(api, "POST", f"/api/clients/{case['id']}/resources", {"kind": "note", "title": "Nicht mehr aktiv"}).json()
    mutate(api, "DELETE", f"/api/practice/clients/{case['id']}")
    for method, path, body in (
        ("GET", f"/api/clients/{case['id']}/resources", {}),
        ("PATCH", f"/api/resources/{note['id']}", {"shared": True}),
        ("POST", "/api/appointments", {"client_id": case["id"], "title": "Archiviert", "start_at": slot()}),
    ):
        assert mutate(api, method, path, body).status_code == 404


def test_restoring_overlapping_test_appointments_is_refused_without_partial_restore(api):
    login(api)
    first, second = examples(api)[:2]
    for case in (first, second):
        booking = mutate(api, "POST", "/api/appointments", {"client_id": case["id"], "title": "Übungszeit", "start_at": slot()})
        if case == first:
            assert booking.status_code == 201
            mutate(api, "DELETE", f"/api/practice/clients/{case['id']}")
        else:
            assert booking.status_code == 201  # Archived times no longer reserve a slot.
    restore = mutate(api, "POST", f"/api/practice/clients/{first['id']}/restore")
    assert restore.status_code == 409, restore.text
    assert api.get(f"/api/clients/{first['id']}").status_code == 404
    assert len(api.get("/api/appointments?practice=1").json()) == 1


def test_identical_fictional_form_can_start_fresh_after_reset(api):
    login(api)
    payload = {"name": "Fiktiv · wiederholbarer Fall", "email": "same-form@example.org", "birth_date": "1990-02-03", "birth_time": "10:30", "birth_place": "Berlin"}
    first = mutate(api, "POST", "/api/practice/clients", payload)
    assert first.status_code == 201, first.text
    assert mutate(api, "POST", "/api/practice/reset").status_code == 200
    second = mutate(api, "POST", "/api/practice/clients", payload)
    assert second.status_code == 201, second.text
    assert second.json()["email"] == first.json()["email"] == payload["email"]
    assert second.json()["id"] != first.json()["id"]
    archived = api.get("/api/clients?practice=1&archived=1").json()
    assert archived[0]["email"] == payload["email"]


def test_same_fictional_address_is_private_and_reusable_for_each_owner(api):
    login(api)
    payload = {"name": "Fiktiv · gemeinsam gewählter Name", "email": "same-address@example.org"}
    first = mutate(api, "POST", "/api/practice/clients", payload)
    assert first.status_code == 201, first.text
    login(api, "admin")
    second = mutate(api, "POST", "/api/practice/clients", payload)
    assert second.status_code == 201, second.text
    assert second.json()["email"] == payload["email"]
    assert second.json()["test_owner_id"] != first.json()["test_owner_id"]
    assert [c["id"] for c in api.get("/api/clients?practice=1").json()] == [second.json()["id"]]
    assert api.get(f"/api/clients/{first.json()['id']}").status_code == 404


def test_fictional_address_does_not_take_real_address_but_real_uniqueness_stays(api):
    login(api)
    original = api.get("/api/clients").json()[0]
    fictional = mutate(api, "POST", "/api/practice/clients", {"name": "Fiktiv · gleiche Adresse", "email": original["email"]})
    assert fictional.status_code == 201, fictional.text
    assert fictional.json()["email"] == original["email"]
    assert mutate(api, "POST", "/api/clients", {"name": "Doppelte echte Adresse", "email": original["email"]}).status_code == 409
    other = api.get("/api/clients").json()[1]
    assert mutate(api, "PATCH", f"/api/clients/{other['id']}", {"email": original["email"]}).status_code == 409
    assert api.get(f"/api/clients/{original['id']}").json() == original
    practice_only_address = "later-real-client@example.org"
    assert mutate(api, "POST", "/api/practice/clients", {"name": "Fiktiv · zuerst", "email": practice_only_address}).status_code == 201
    real_created = mutate(api, "POST", "/api/clients", {"name": "Reale Kategorie · synthetischer Test", "email": practice_only_address})
    assert real_created.status_code == 201, real_created.text
    assert real_created.json()["is_test"] is False
    assert real_created.json()["email"] == practice_only_address
    assert mutate(api, "POST", "/api/clients", {"name": "Doppelte reale Kategorie", "email": practice_only_address}).status_code == 409


def test_changing_test_address_preserves_internal_identity_through_archive_restore(api):
    login(api)
    created = mutate(api, "POST", "/api/practice/clients", {"name": "Fiktiv · bearbeitbar", "email": "before@example.org"}).json()
    from app.db import get_db
    with get_db() as conn:
        internal = conn.execute("SELECT email FROM clients WHERE id=?", (created["id"],)).fetchone()["email"]
    assert internal.endswith(".invalid")
    real_address = api.get("/api/clients").json()[0]["email"]
    updated = mutate(api, "PATCH", f"/api/clients/{created['id']}", {"email": real_address})
    assert updated.status_code == 200, updated.text
    assert updated.json()["email"] == real_address
    with get_db() as conn:
        row = conn.execute("SELECT email,test_email FROM clients WHERE id=?", (created["id"],)).fetchone()
        assert row["email"] == internal
        assert row["test_email"] == real_address
    mutate(api, "DELETE", f"/api/practice/clients/{created['id']}")
    restored = mutate(api, "POST", f"/api/practice/clients/{created['id']}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["email"] == real_address


def test_existing_test_address_migration_is_idempotent_and_keeps_real_data(api):
    owner = login(api)
    real = api.get("/api/clients").json()
    from app.db import get_db
    from app.main import init_practice_schema
    from app.security import now_iso
    with get_db() as conn:
        cid = conn.execute("INSERT INTO clients(name,email,themes,created_at,is_test,test_owner_id,chart) VALUES(?,?,?,?,1,?,?)", ("Fiktiver Altbestand", "legacy-test@example.org", '["Altbestand"]', now_iso(), owner["id"], '{"legacy":true}')).lastrowid
        init_practice_schema(conn)
        migrated = dict(conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone())
        assert migrated["email"].endswith(".invalid")
        assert migrated["test_email"] == "legacy-test@example.org"
        init_practice_schema(conn)
        assert dict(conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()) == migrated
    shown = api.get(f"/api/clients/{cid}").json()
    assert shown["email"] == "legacy-test@example.org"
    assert shown["themes"] == ["Altbestand"]
    assert shown["chart"] == {"legacy": True}
    assert api.get("/api/clients").json() == real
