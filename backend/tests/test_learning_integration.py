"""Exercise the learning workspace through the complete app and its security guard."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SOULFLOW_DB", str(tmp_path / "workspace.sqlite3"))
    monkeypatch.setenv("SOULFLOW_DEMO", "1")
    from app.main import app
    with TestClient(app) as client:
        yield client


def login(api, role):
    account = next(item for item in api.get("/api/demo").json()["accounts"] if item["role"] == role)
    result = api.post("/api/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"X-SoulFlow": "1"})
    assert result.status_code == 200


def write(api, method, path, body):
    return api.request(method, path, json=body, headers={"X-SoulFlow": "1"})


def test_notebook_is_private_even_from_admin_and_survives_new_session(api):
    login(api, "practitioner")
    lesson = api.get("/api/learning").json()["lessons"][-1]
    response = write(api, "POST", "/api/learning/notebook", {"lesson_id": lesson["id"], "title": "TEST · Meine eigene Übung", "body": "Nur mein synthetischer persönlicher Lernstand."})
    assert response.status_code == 200, response.text
    note = response.json()
    assert note["lesson_title_snapshot"] == lesson["title"]
    assert note["lesson_version_snapshot"] == lesson["content_version"]
    login(api, "admin")
    assert api.get("/api/learning/notebook").json() == []
    denied = write(api, "PATCH", f"/api/learning/notebook/{note['id']}", {"body": "TEST · fremde Änderung"})
    assert denied.status_code == 404
    assert note["body"] not in api.get("/api/learning/notebook/export").json()["content"]
    login(api, "practitioner")
    own = api.get("/api/learning/notebook")
    assert own.headers["cache-control"] == "no-store"
    assert own.json() == [note]
    exported = api.get("/api/learning/notebook/export")
    assert exported.headers["cache-control"] == "no-store"
    assert note["body"] in exported.json()["content"]


def test_new_workspace_mutations_require_same_origin_and_csrf(api):
    login(api, "practitioner")
    note = {"lesson_id": None, "title": "TEST · CSRF", "body": "Synthetischer Inhalt."}
    assert api.post("/api/learning/notebook", json=note).status_code == 403
    assert api.post("/api/learning/notebook", json=note, headers={"X-SoulFlow": "1", "Origin": "https://foreign.example"}).status_code == 403
    assert api.get("/api/learning/notebook").json() == []
    created = write(api, "POST", "/api/learning/notebook", note)
    assert created.status_code == 200, created.text
    login(api, "client")
    assert api.get("/api/learning/notebook").status_code == 403
    assert api.get("/api/learning/notebook/export").status_code == 403
    assert write(api, "POST", "/api/learning/notebook", note).status_code == 403


def test_direct_entry_and_personal_states_persist_without_blocking_quiz(api):
    login(api, "practitioner")
    data = api.get("/api/learning").json()
    assert all(item["available"] and item["body"] for item in data["lessons"])
    lesson = data["lessons"][-1]
    result = write(api, "PATCH", f"/api/learning/{lesson['id']}/state", {"bookmarked": True, "pinned": True, "practiced": True, "reflected": True})
    assert result.status_code == 200, result.text
    assert write(api, "POST", f"/api/learning/{lesson['id']}/complete", {}).status_code == 200
    write(api, "POST", "/api/auth/logout", {})
    login(api, "practitioner")
    reread = api.get("/api/learning").json()
    saved = next(item for item in reread["lessons"] if item["id"] == lesson["id"])
    assert all(saved[key] for key in ("bookmarked", "pinned", "practiced", "reflected", "completed"))
    assert reread["next_unlock_at"] is None
    login(api, "admin")
    other = next(item for item in api.get("/api/learning").json()["lessons"] if item["id"] == lesson["id"])
    assert not any(other[key] for key in ("bookmarked", "pinned", "practiced", "reflected", "completed"))
