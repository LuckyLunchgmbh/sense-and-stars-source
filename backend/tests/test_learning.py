"""Learning acceptance checks use real role/session resolution and an isolated DB."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import sys
from types import ModuleType

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import learning
from app.db import get_db, init_schema
from app.security import token_hash


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SOULFLOW_DB", str(tmp_path / "learning.sqlite3"))
    monkeypatch.setenv("SOULFLOW_DEMO", "1")
    with get_db() as conn:
        init_schema(conn)
        for user_id, role in enumerate(("admin", "practitioner", "client"), 1):
            conn.execute(
                "INSERT INTO users(id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)",
                (user_id, role, role + "@example.invalid", "unused", role, "2026-01-01T00:00:00+00:00"),
            )
            conn.execute("INSERT INTO sessions VALUES(?,?,?)", (token_hash(role), user_id, "2099-01-01T00:00:00+00:00"))
        learning.init_learning(conn)
    app = FastAPI()
    app.include_router(learning.router)
    with TestClient(app) as client:
        client.cookies.set("soulflow_session", "practitioner")
        yield client


def as_role(api, role):
    api.cookies.clear()
    if role:
        api.cookies.set("soulflow_session", role)
    return api


def lessons(api):
    response = api.get("/api/learning")
    assert response.status_code == 200
    return response.json()["lessons"]


def correct_answers(lesson_id):
    with get_db() as conn:
        row = conn.execute("SELECT quiz FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone()
        return {item["id"]: item["correct_index"] for item in json.loads(row["quiz"])}


def pass_quiz(api, lesson_id):
    response = api.post(f"/api/learning/{lesson_id}/quiz", json={"answers": correct_answers(lesson_id)})
    assert response.status_code == 200
    assert response.json()["passed"] is True


def new_lesson(**updates):
    value = {
        "title": "Redaktioneller Testentwurf", "category": "Astro-Wissen",
        "summary": "Eine synthetische Testlektion.",
        "body": "Testinhalt zur Unterscheidung von Beobachtung und Deutung.", "week": 4,
        "source_url": "https://ssd.jpl.nasa.gov/horizons/manual.html", "source_title": "JPL Horizons",
        "quiz": [{"id": "q1", "question": "Was braucht eine überprüfbare Aussage?",
                  "options": ["Belege", "Nur Zustimmung"], "correct_index": 0}],
    }
    value.update(updates)
    return value


def test_library_has_open_published_lessons_and_answers_are_hidden(api):
    data = api.get("/api/learning").json()
    assert len(data["lessons"]) == 15
    assert [item["week"] for item in data["lessons"]] == [1, 2, 3, *range(5, 17)]
    assert all(item["available"] and item["body"] and item["quiz"] for item in data["lessons"])
    assert "correct_index" not in json.dumps(data)
    assert data["progress"]["completed_ids"] == []
    assert data["next_unlock_at"] is None


@pytest.mark.parametrize("role,status", [(None, 401), ("client", 403)])
def test_learning_is_staff_only_for_read_quiz_and_completion(api, role, status):
    first_id = lessons(api)[0]["id"]
    as_role(api, role)
    assert api.get("/api/learning").status_code == status
    assert api.post(f"/api/learning/{first_id}/quiz", json={"answers": {"q1": 0}}).status_code == status
    assert api.post(f"/api/learning/{first_id}/complete", json={}).status_code == status


def test_quiz_requires_complete_valid_answer_set_for_any_lesson(api):
    first, second = lessons(api)[:2]
    answers = correct_answers(first["id"])
    assert api.post(f"/api/learning/{second['id']}/quiz", json={"answers": correct_answers(second["id"])}).status_code == 200
    for invalid in ({}, {"unknown": 0}, dict(answers, unknown=0)):
        assert api.post(f"/api/learning/{first['id']}/quiz", json={"answers": invalid}).status_code == 422
    for invalid_value in (-1, 99, True, "0", 0.5):
        invalid = {key: invalid_value for key in answers}
        assert api.post(f"/api/learning/{first['id']}/quiz", json={"answers": invalid}).status_code == 422
    assert api.post(f"/api/learning/{first['id']}/quiz", json={"answers": answers, "passed": True}).status_code == 422


def test_read_acknowledgement_has_no_quiz_predecessor_or_week_requirement(api, monkeypatch):
    now = datetime(2026, 10, 25, 23, 45, tzinfo=timezone.utc)
    monkeypatch.setattr(learning, "utc_now", lambda: now)
    first, second, third = lessons(api)[:3]
    assert api.post(f"/api/learning/{third['id']}/complete", json={}).status_code == 200
    wrong = {item["id"]: (item["correct_index"] + 1) % len(item["options"])
             for item in _stored_quiz(first["id"])}
    failed = api.post(f"/api/learning/{first['id']}/quiz", json={"answers": wrong}).json()
    assert failed["score"] == 0 and failed["passed"] is False
    assert api.post(f"/api/learning/{first['id']}/complete", json={}).status_code == 200
    assert api.post(f"/api/learning/{second['id']}/complete", json={}).status_code == 200
    state = api.get("/api/learning").json()
    assert state["progress"]["completed_ids"] == [first["id"], second["id"], third["id"]]
    assert state["next_unlock_at"] is None
    assert all(item["available"] for item in state["lessons"])


def _stored_quiz(lesson_id):
    with get_db() as conn:
        return json.loads(conn.execute("SELECT quiz FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone()["quiz"])


def test_progress_is_per_user_persistent_and_completion_is_idempotent(api, monkeypatch):
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(learning, "utc_now", lambda: now)
    first = lessons(api)[0]
    pass_quiz(api, first["id"])
    api.post(f"/api/learning/{first['id']}/complete", json={})
    first_unlock = api.get("/api/learning").json()["next_unlock_at"]
    monkeypatch.setattr(learning, "utc_now", lambda: now + timedelta(days=1))
    assert api.post(f"/api/learning/{first['id']}/complete", json={}).json() == {"ok": True}
    assert api.get("/api/learning").json()["next_unlock_at"] == first_unlock
    with get_db() as conn:
        assert conn.execute("SELECT completed_at FROM learning_progress WHERE user_id=2 AND lesson_id=?", (first["id"],)).fetchone()[0] == now.isoformat()
    as_role(api, "admin")
    assert api.get("/api/learning").json()["progress"]["completed_ids"] == []
    as_role(api, "practitioner")
    assert api.get("/api/learning").json()["progress"]["quiz_scores"][str(first["id"])] == 100


def test_admin_drafts_are_private_and_publish_requires_valid_new_week(api):
    assert api.get("/api/admin/lessons").status_code == 403
    assert api.post("/api/admin/lessons", json=new_lesson()).status_code == 403
    as_role(api, "admin")
    response = api.post("/api/admin/lessons", json=new_lesson())
    assert response.status_code == 200
    draft = response.json()
    assert draft["status"] == "draft"
    assert draft["quiz"][0]["correct_index"] == 0
    as_role(api, "practitioner")
    assert draft["id"] not in [item["id"] for item in lessons(api)]
    assert api.post(f"/api/learning/{draft['id']}/quiz", json={"answers": {"q1": 0}}).status_code == 404
    assert api.post(f"/api/admin/lessons/{draft['id']}/publish", json={}).status_code == 403
    as_role(api, "admin")
    assert api.post(f"/api/admin/lessons/{draft['id']}/publish", json={}).json()["status"] == "published"
    duplicate = api.post("/api/admin/lessons", json=new_lesson(week=1)).json()
    assert api.post(f"/api/admin/lessons/{duplicate['id']}/publish", json={}).status_code == 409


@pytest.mark.parametrize("updates", [
    {"week": 0}, {"week": 1000000}, {"week": True}, {"title": "   "},
    {"source_url": "javascript:alert(1)"}, {"source_url": "https://user:secret@example.org/private"},
    {"quiz": []}, {"quiz": [{"id": "q1", "question": "Test?", "options": ["A", "B"], "correct_index": 2}]},
    {"quiz": [{"id": "q1", "question": "Test?", "options": ["A", "B"], "correct_index": True}]},
    {"status": "published"},
])
def test_lesson_validation_rejects_invalid_or_privileged_payloads(api, updates):
    as_role(api, "admin")
    assert api.post("/api/admin/lessons", json=new_lesson(**updates)).status_code == 422
    assert len(api.get("/api/admin/lessons").json()) == 15


def test_simulated_weekly_scan_is_explicit_private_and_idempotent(api, monkeypatch):
    monkeypatch.setattr(learning, "utc_now", lambda: datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert api.post("/api/admin/scan", json={"simulate": True}).status_code == 403
    as_role(api, "admin")
    first = api.post("/api/admin/scan", json={"simulate": True})
    assert first.status_code == 200
    assert first.json()["mode"] == "simulation" and first.json()["created"] == 1
    repeat = api.post("/api/admin/scan", json={"simulate": True}).json()
    assert repeat["created"] == 0
    drafts = [item for item in api.get("/api/admin/lessons").json() if item["status"] == "draft"]
    assert len(drafts) == 1 and "SIMULATION" in drafts[0]["title"]
    assert "keine" in drafts[0]["body"].lower()
    assert api.post(f"/api/admin/lessons/{drafts[0]['id']}/publish", json={}).status_code == 409
    as_role(api, "practitioner")
    assert len(lessons(api)) == 15
    monkeypatch.setattr(learning, "utc_now", lambda: datetime(2026, 10, 27, tzinfo=timezone.utc))
    as_role(api, "admin")
    assert api.post("/api/admin/scan", json={"simulate": True}).json()["created"] == 1


def test_unknown_lessons_and_extra_completion_fields_are_rejected(api):
    assert api.post("/api/learning/999/complete", json={}).status_code == 404
    assert api.post("/api/learning/999/quiz", json={"answers": {"q1": 0}}).status_code == 404
    assert api.post("/api/learning/1/complete", json={"completed_at": "2000-01-01"}).status_code == 422
    as_role(api, "admin")
    assert api.post("/api/admin/lessons/999/publish", json={}).status_code == 404
    assert api.post("/api/admin/scan", json={"simulate": "false"}).status_code == 422


def test_live_scan_only_creates_reviewable_source_metadata_and_retries_failed_sources(api, monkeypatch):
    as_role(api, "admin")
    calls = []

    def unavailable(url):
        calls.append(url)
        raise OSError("private diagnostic detail must not escape")

    monkeypatch.setattr(learning, "_fetch_rss", unavailable)
    failed = api.post("/api/admin/scan", json={"simulate": False})
    assert failed.status_code == 200 and failed.json()["created"] == 0
    assert failed.json()["sources"][0]["status"] == "unavailable"
    assert "private diagnostic" not in failed.text
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM learning_scans").fetchone()[0] == 0

    def official_feed(url):
        calls.append(url)
        return [{"title": "Synthetische Quellenüberschrift für den Test", "url": "https://www.nasa.gov/test-entry/",
                 "excerpt": "Ein klar als Test definierter Quellenauszug."}]

    monkeypatch.setattr(learning, "_fetch_rss", official_feed)
    response = api.post("/api/admin/scan", json={"simulate": False}).json()
    assert response["mode"] == "rss" and response["created"] == 1
    assert calls == [learning.RSS_SOURCES[0][1]] * 2
    draft = next(item for item in api.get("/api/admin/lessons").json() if item["status"] == "draft")
    assert draft["source_url"] == "https://www.nasa.gov/test-entry/"
    assert draft["quiz"] == [] and draft["source_kind"] == "rss_metadata"
    assert "fachlich ungeprüft" in draft["body"]
    assert api.post(f"/api/admin/lessons/{draft['id']}/publish", json={}).status_code == 409
    assert api.post("/api/admin/scan", json={"simulate": False}).json()["created"] == 0
    assert len(calls) == 2  # Repeating a successful weekly run performs no network call.


def test_rss_parser_handles_plain_metadata_and_ignores_unsafe_entry_links():
    data = b'''<rss><channel><item><title>Example &amp; title</title>
    <link>javascript:alert(1)</link></item><item><title>Official title</title>
    <link>https://www.nasa.gov/test/</link><description>&lt;b&gt;Excerpt&lt;/b&gt;</description>
    </item><item><title>Duplicate</title><link>https://www.nasa.gov/test/</link></item></channel></rss>'''
    assert learning._parse_rss(data) == [{"title": "Official title", "url": "https://www.nasa.gov/test/", "excerpt": "Excerpt"}]
    with pytest.raises(ValueError):
        learning._fetch_rss("https://127.0.0.1/private")
    with pytest.raises(ValueError):
        learning._parse_rss(b"X" * (learning.MAX_FEED_BYTES + 1))


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_rss_parser_rejects_xml_entity_definitions_in_every_supported_encoding(encoding):
    data = '<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY injected "EXPANDED">]><rss><channel><item><title>&injected;</title><link>https://www.nasa.gov/test/</link></item></channel></rss>'
    with pytest.raises(ValueError):
        learning._parse_rss(data.encode(encoding))


def test_learning_write_rolls_back_when_audit_write_fails(api, monkeypatch):
    as_role(api, "admin")

    def broken_audit(*args, **kwargs):
        raise RuntimeError("synthetic database failure")

    monkeypatch.setattr(learning, "_audit", broken_audit)
    with pytest.raises(RuntimeError, match="synthetic database failure"):
        api.post("/api/admin/lessons", json=new_lesson())
    assert len(api.get("/api/admin/lessons").json()) == 15


def test_repeated_initialization_preserves_progress_and_seed_count(api):
    first = lessons(api)[0]
    pass_quiz(api, first["id"])
    api.post(f"/api/learning/{first['id']}/complete", json={})
    with get_db() as conn:
        learning.init_learning(conn)
        learning.init_learning(conn)
        assert conn.execute("SELECT COUNT(*) FROM learning_lessons").fetchone()[0] == 15
    assert api.get("/api/learning").json()["progress"]["completed_ids"] == [first["id"]]


STATE_KEYS = ("bookmarked", "pinned", "practiced", "reflected")


def test_personal_lesson_states_persist_independently_and_do_not_mark_read(api):
    lesson_id = lessons(api)[-1]["id"]
    assert all(lessons(api)[-1][key] is False for key in STATE_KEYS)
    changed = api.patch(f"/api/learning/{lesson_id}/state", json={"bookmarked": True, "practiced": True})
    assert changed.status_code == 200
    assert {key: changed.json()[key] for key in STATE_KEYS} == {
        "bookmarked": True, "pinned": False, "practiced": True, "reflected": False,
    }
    assert changed.json()["completed"] is False
    api.patch(f"/api/learning/{lesson_id}/state", json={"pinned": True, "reflected": True})
    api.patch(f"/api/learning/{lesson_id}/state", json={"bookmarked": False})
    stored = next(item for item in lessons(api) if item["id"] == lesson_id)
    assert {key: stored[key] for key in STATE_KEYS} == {
        "bookmarked": False, "pinned": True, "practiced": True, "reflected": True,
    }
    as_role(api, "admin")
    assert all(next(item for item in lessons(api) if item["id"] == lesson_id)[key] is False for key in STATE_KEYS)
    as_role(api, "practitioner")
    assert next(item for item in lessons(api) if item["id"] == lesson_id)["pinned"] is True


@pytest.mark.parametrize("payload", [{}, {"pinned": None}, {"pinned": 1}, {"bookmarked": "false"},
                                     {"practiced": []}, {"reflected": True, "user_id": 1}])
def test_personal_state_rejects_empty_non_boolean_and_privileged_fields(api, payload):
    lesson_id = lessons(api)[0]["id"]
    assert api.patch(f"/api/learning/{lesson_id}/state", json=payload).status_code == 422


def test_notebook_creates_free_and_linked_notes_and_keeps_source_snapshot_after_edits(api, monkeypatch):
    initial_time = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
    monkeypatch.setattr(learning, "utc_now", lambda: initial_time)
    lesson = lessons(api)[-1]
    response = api.post("/api/learning/notebook", json={"lesson_id": lesson["id"], "title": "Mein Impuls", "body": "Meine private Reflexion."})
    assert response.status_code == 200
    linked = response.json()
    assert linked["user_id"] == 2 and linked["lesson_id"] == lesson["id"]
    assert linked["lesson_title_snapshot"] == lesson["title"]
    assert linked["lesson_version_snapshot"] == lesson["content_version"]
    assert linked["created_at"] == linked["updated_at"] == initial_time.isoformat()
    free = api.post("/api/learning/notebook", json={"lesson_id": None, "title": "Freier Gedanke", "body": "Unabhängig vom Text."}).json()
    assert free["lesson_id"] is None and free["lesson_title_snapshot"] is None and free["lesson_version_snapshot"] is None
    with get_db() as conn:
        conn.execute("UPDATE learning_lessons SET title='Neuer Inhaltstitel',content_version=99,source_url='https://example.org/changed-source' WHERE id=?", (lesson["id"],))
    later = initial_time + timedelta(hours=2)
    monkeypatch.setattr(learning, "utc_now", lambda: later)
    patched = api.patch(f"/api/learning/notebook/{linked['id']}", json={"body": "Überarbeitete Reflexion."})
    assert patched.status_code == 200
    patched = patched.json()
    assert patched["title"] == "Mein Impuls" and patched["body"] == "Überarbeitete Reflexion."
    assert patched["created_at"] == initial_time.isoformat() and patched["updated_at"] == later.isoformat()
    assert patched["lesson_title_snapshot"] == lesson["title"] and patched["lesson_version_snapshot"] == lesson["content_version"]
    stored = api.get("/api/learning/notebook").json()
    assert {item["id"] for item in stored} == {linked["id"], free["id"]}
    export = api.get("/api/learning/notebook/export")
    assert export.status_code == 200
    assert export.json()["filename"].endswith(".md")
    content = export.json()["content"]
    assert "Überarbeitete Reflexion." in content and "Freier Gedanke" in content
    assert lesson["title"] in content and f"Version {lesson['content_version']}" in content
    assert "Neuer Inhaltstitel" not in content
    assert f"Lektion {lesson['id']}" in content
    assert lesson["source_url"] in content
    assert "https://example.org/changed-source" not in content


def test_notebook_is_private_even_between_staff_and_export_excludes_others(api):
    own = api.post("/api/learning/notebook", json={"lesson_id": None, "title": "Privater Hinweis", "body": "Nur bei mir."}).json()
    as_role(api, "admin")
    assert api.get("/api/learning/notebook").json() == []
    assert "Nur bei mir." not in api.get("/api/learning/notebook/export").json()["content"]
    assert api.patch(f"/api/learning/notebook/{own['id']}", json={"title": "Übernahme"}).status_code == 404
    assert api.patch("/api/learning/notebook/99999", json={"body": "Unbekannt"}).status_code == 404
    as_role(api, "practitioner")
    assert api.get("/api/learning/notebook").json()[0]["title"] == "Privater Hinweis"


@pytest.mark.parametrize("role,status", [(None, 401), ("client", 403)])
def test_all_new_learning_routes_require_staff(api, role, status):
    lesson_id = lessons(api)[0]["id"]
    own = api.post("/api/learning/notebook", json={"lesson_id": None, "title": "Privat", "body": "Gedanke"}).json()
    as_role(api, role)
    assert api.patch(f"/api/learning/{lesson_id}/state", json={"bookmarked": True}).status_code == status
    assert api.get("/api/learning/notebook").status_code == status
    assert api.get("/api/learning/notebook/export").status_code == status
    assert api.post("/api/learning/notebook", json={"lesson_id": None, "title": "Neu", "body": "Text"}).status_code == status
    assert api.patch(f"/api/learning/notebook/{own['id']}", json={"body": "Text"}).status_code == status


@pytest.mark.parametrize("payload", [
    {"title": "", "body": "Text"}, {"title": "   ", "body": "Text"},
    {"title": "x" * 161, "body": "Text"}, {"title": "Titel", "body": ""},
    {"title": "Titel", "body": "x" * 12001}, {"title": "Titel", "body": "Text\x00"},
    {"title": "Titel", "body": "Text", "user_id": 1},
    {"title": "Titel", "body": "Text", "lesson_id": True},
    {"title": "Titel", "body": "Text", "lesson_title_snapshot": "Manipuliert"},
])
def test_notebook_create_validates_content_and_rejects_owner_and_snapshot_overrides(api, payload):
    assert api.post("/api/learning/notebook", json=payload).status_code == 422


@pytest.mark.parametrize("payload", [{}, {"title": None}, {"body": "   "}, {"title": "x" * 161},
                                     {"body": "x" * 12001}, {"lesson_id": 1}, {"user_id": 1}])
def test_notebook_update_validates_nonempty_changes_and_cannot_change_links_or_owner(api, payload):
    own = api.post("/api/learning/notebook", json={"lesson_id": None, "title": "Gedanke", "body": "Text"}).json()
    assert api.patch(f"/api/learning/notebook/{own['id']}", json=payload).status_code == 422


def test_unpublished_and_unknown_lessons_cannot_be_marked_or_linked_in_notes(api):
    as_role(api, "admin")
    draft = api.post("/api/admin/lessons", json=new_lesson()).json()
    for role in ("admin", "practitioner"):
        as_role(api, role)
        for lesson_id in (draft["id"], 99999):
            assert api.patch(f"/api/learning/{lesson_id}/state", json={"pinned": True}).status_code == 404
            assert api.post("/api/learning/notebook", json={"lesson_id": lesson_id, "title": "Notiz", "body": "Text"}).status_code == 404


def test_admin_metadata_is_validated_persisted_and_has_backward_compatible_defaults(api):
    as_role(api, "admin")
    metadata = {
        "track": "Quellenpraxis", "level": "deepening", "learning_objective": "Aussagen einordnen.",
        "exercise": "Drei Arten von Aussagen trennen.", "reflection_prompt": "Was bleibt ungeklärt?",
        "content_version": 3, "source_note": "Quelle für Definitionen; eigene redaktionelle Übung.",
    }
    created = api.post("/api/admin/lessons", json=new_lesson(**metadata))
    assert created.status_code == 200
    assert {key: created.json()[key] for key in metadata} == metadata
    published = api.post(f"/api/admin/lessons/{created.json()['id']}/publish", json={})
    assert published.status_code == 200
    as_role(api, "practitioner")
    stored = next(item for item in lessons(api) if item["id"] == created.json()["id"])
    assert {key: stored[key] for key in metadata} == metadata
    legacy = lessons(api)[0]
    assert legacy["level"] == "foundation" and legacy["content_version"] == 1
    assert all(isinstance(legacy[key], str) for key in ("track", "learning_objective", "exercise", "reflection_prompt", "source_note"))


@pytest.mark.parametrize("updates", [{"level": "expert"}, {"content_version": 0}, {"content_version": True},
                                     {"track": []}, {"source_note": "x" * 2001}, {"exercise": "bad\x00"}])
def test_admin_rejects_invalid_new_metadata(api, updates):
    as_role(api, "admin")
    assert api.post("/api/admin/lessons", json=new_lesson(**updates)).status_code == 422


def test_initialization_migrates_old_schema_without_overwriting_content_ids_or_progress(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO users VALUES(7)")
    conn.execute("""CREATE TABLE learning_lessons(id INTEGER PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,
        summary TEXT NOT NULL,body TEXT NOT NULL,week INTEGER NOT NULL,source_url TEXT NOT NULL,
        source_title TEXT NOT NULL,quiz TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',
        source_kind TEXT NOT NULL DEFAULT 'editorial',seed_key TEXT UNIQUE,scan_key TEXT UNIQUE,
        created_at TEXT NOT NULL,published_at TEXT)""")
    conn.execute("""CREATE TABLE learning_progress(user_id INTEGER NOT NULL REFERENCES users(id),
        lesson_id INTEGER NOT NULL REFERENCES learning_lessons(id),quiz_score INTEGER NOT NULL DEFAULT 0,
        quiz_passed INTEGER NOT NULL DEFAULT 0,quiz_passed_at TEXT,completed_at TEXT,PRIMARY KEY(user_id,lesson_id))""")
    conn.execute("""INSERT INTO learning_lessons VALUES(101,'Historischer eigener Titel','Alt','Erhalten','Eigener Text',1,
        'https://example.org/source','Quelle','[]','published','editorial','editorial-v1-1',NULL,'2026-01-01',NULL)""")
    conn.execute("INSERT INTO learning_progress VALUES(7,101,50,1,'2026-01-02','2026-01-03')")
    learning.init_learning(conn)
    learning.init_learning(conn)
    original = conn.execute("SELECT * FROM learning_lessons WHERE id=101").fetchone()
    assert original["title"] == "Historischer eigener Titel" and original["body"] == "Eigener Text"
    assert original["level"] == "foundation" and original["content_version"] == 1
    progress = conn.execute("SELECT * FROM learning_progress WHERE user_id=7 AND lesson_id=101").fetchone()
    assert progress["quiz_score"] == 50 and progress["completed_at"] == "2026-01-03"
    assert all(progress[key] == 0 for key in STATE_KEYS)
    assert conn.execute("SELECT COUNT(*) FROM learning_lessons").fetchone()[0] == 15
    conn.close()


def test_reinitialization_preserves_notebook_snapshots_and_personal_state(api):
    lesson_id = lessons(api)[-1]["id"]
    api.patch(f"/api/learning/{lesson_id}/state", json={"bookmarked": True, "reflected": True})
    note = api.post("/api/learning/notebook", json={"lesson_id": lesson_id, "title": "Bleibt", "body": "Privater Text"}).json()
    with get_db() as conn:
        learning.init_learning(conn)
        learning.init_learning(conn)
    assert api.get("/api/learning/notebook").json() == [note]
    stored = next(item for item in lessons(api) if item["id"] == lesson_id)
    assert stored["bookmarked"] is True and stored["reflected"] is True


def test_workspace_seeds_keep_existing_sort_positions_and_still_insert_every_chapter(api):
    with get_db() as conn:
        conn.execute("DELETE FROM learning_lessons WHERE seed_key NOT LIKE 'editorial-v1-%'")
        conn.execute("""INSERT INTO learning_lessons(title,category,summary,body,week,source_url,source_title,quiz,
            status,created_at) VALUES('Eigene bestehende Lektion','Praxis','Erhalten','Mein eigener Text',5,
            'https://example.org/source','Quelle','[]','published','2026-01-01')""")
        preserved_id = conn.execute("SELECT id FROM learning_lessons WHERE title='Eigene bestehende Lektion'").fetchone()[0]
        learning.init_learning(conn)
        learning.init_learning(conn)
        assert conn.execute("SELECT COUNT(*) FROM learning_lessons").fetchone()[0] == 16
        original = conn.execute("SELECT * FROM learning_lessons WHERE id=?", (preserved_id,)).fetchone()
        assert original["body"] == "Mein eigener Text" and original["week"] == 5
        seeded = conn.execute("SELECT id,week,seed_key FROM learning_lessons WHERE seed_key NOT LIKE 'editorial-v1-%'").fetchall()
        assert len(seeded) == 12
        assert len({row["seed_key"] for row in seeded}) == 12
        assert len({row["week"] for row in seeded}) == 12 and all(row["week"] >= 6 for row in seeded)


def test_non_demo_content_seeds_are_drafts_and_reinitialization_never_promotes_them(tmp_path, monkeypatch):
    content = ModuleType("app.learning_content")
    content.WORKSPACE_LESSONS = [dict(new_lesson(), seed_key="test-private-start-lesson")]
    monkeypatch.setitem(sys.modules, "app.learning_content", content)
    monkeypatch.setenv("SOULFLOW_DB", str(tmp_path / "non-demo.sqlite3"))
    monkeypatch.setenv("SOULFLOW_DEMO", "0")
    with get_db() as conn:
        init_schema(conn)
        learning.init_learning(conn)
        assert conn.execute("SELECT COUNT(*) FROM learning_lessons WHERE status='published'").fetchone()[0] == 3
        row = conn.execute("SELECT * FROM learning_lessons WHERE seed_key='test-private-start-lesson'").fetchone()
        assert row["status"] == "draft"
        monkeypatch.setenv("SOULFLOW_DEMO", "1")
        learning.init_learning(conn)
        repeated = conn.execute("SELECT * FROM learning_lessons WHERE id=?", (row["id"],)).fetchone()
        assert repeated["status"] == "draft" and repeated["body"] == row["body"]


@pytest.mark.parametrize("control", ["\n", "\r", "\t", "\x00"])
def test_source_urls_reject_embedded_controls_before_markdown_export(control):
    with pytest.raises(ValueError):
        learning._source_url(f"https://example.org/{control}confusing-source")


def test_reading_and_personal_states_never_invent_quiz_attempts_or_overwrite_quiz_history(api):
    lesson_id = lessons(api)[-1]["id"]
    assert api.post(f"/api/learning/{lesson_id}/complete", json={}).status_code == 200
    assert api.patch(f"/api/learning/{lesson_id}/state", json={"pinned": True}).status_code == 200
    assert api.get("/api/learning").json()["progress"]["quiz_scores"] == {}
    pass_quiz(api, lesson_id)
    assert api.patch(f"/api/learning/{lesson_id}/state", json={"bookmarked": True}).status_code == 200
    assert api.post(f"/api/learning/{lesson_id}/complete", json={}).status_code == 200
    data = api.get("/api/learning").json()
    assert data["progress"]["quiz_scores"] == {str(lesson_id): 100}
    state = next(item for item in data["lessons"] if item["id"] == lesson_id)
    assert state["completed"] is True and state["pinned"] is True and state["bookmarked"] is True


@pytest.mark.parametrize("demo", ["0", "1"], ids=["non-demo-drafts", "demo-published"])
def test_seed_allocation_reserves_existing_drafts_and_uses_free_gaps_before_maximum(api, monkeypatch, demo):
    as_role(api, "admin")
    with get_db() as conn:
        conn.execute("DELETE FROM learning_lessons WHERE seed_key NOT LIKE 'editorial-v1-%'")
    # Preserve a published lesson at the desired first slot, an unpublished
    # lesson at the next slot, and a distant published slot at the upper bound.
    existing_ids = []
    for week, publish in ((5, True), (6, False), (260, True)):
        response = api.post("/api/admin/lessons", json=new_lesson(title=f"Vorhandener eigener Inhalt {week}", week=week))
        assert response.status_code == 200
        lesson_id = response.json()["id"]
        existing_ids.append(lesson_id)
        if publish:
            assert api.post(f"/api/admin/lessons/{lesson_id}/publish", json={}).status_code == 200
    with get_db() as conn:
        before = [dict(conn.execute("SELECT * FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone())
                  for lesson_id in existing_ids]
    monkeypatch.setenv("SOULFLOW_DEMO", demo)
    with get_db() as conn:
        learning.init_learning(conn)
        learning.init_learning(conn)
        workspace = conn.execute("SELECT * FROM learning_lessons WHERE seed_key NOT LIKE 'editorial-v1-%' ORDER BY week").fetchall()
        assert len(workspace) == 12
        assert [row["week"] for row in workspace] == list(range(7, 19))
        assert all(row["status"] == ("published" if demo == "1" else "draft") for row in workspace)
        after = [dict(conn.execute("SELECT * FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone())
                 for lesson_id in existing_ids]
        assert after == before
    # Both fresh non-demo seeds and the previously existing draft remain
    # publishable through the existing API, without a missing edit endpoint.
    for lesson_id in [*(row["id"] for row in workspace), existing_ids[1]]:
        response = api.post(f"/api/admin/lessons/{lesson_id}/publish", json={})
        assert response.status_code == 200, response.text
    assert len(lessons(api)) == 18
