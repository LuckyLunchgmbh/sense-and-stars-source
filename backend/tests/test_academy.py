"""Academy acceptance: real sessions, isolated databases and synthetic content."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import academy, learning
from app.db import get_db, init_schema
from app.security import token_hash


def authored_course(slug="grundlagen", count=2):
    # Repetition is intentionally limited to this synthetic validation fixture;
    # real editorial quality is independently checked against the authored files.
    words = "Synthetischer Text zur technischen Prüfung ohne fachliche Lehrbehauptung. "
    return {"id": slug, "title": "Synthetischer Kurs " + slug, "summary": "Isolierter technischer Testbestand.",
        "tradition": "Synthetischer Test", "level": "foundation", "prerequisites": [], "lessons": [
            {"key": f"academy-{slug}-{i:02d}", "title": f"Testlektion {i}", "summary": "Eigener Test.",
             "objective": "Den technischen Ablauf prüfen.", "level": "foundation", "minutes": 20,
             "body": words * 60,
             "examples": [{"title": "Beispiel A", "body": words * 9}, {"title": "Beispiel B", "body": words * 9}],
             "practice": {"prompt": "Beschreibe deine eigene synthetische Bearbeitung.", "model_answer": words * 18,
                          "rubric": ["Kontext angegeben", "Begründung erläutert", "Grenzen beschrieben"]},
             "quiz": [{"id": f"q{j}", "question": f"Technische Testfrage {j}?", "options": ["A", "B"],
                       "correct_index": j % 2, "explanation": f"Erklärung zur Testfrage {j}."} for j in range(1, 4)],
             "sources": [{"url": "https://example.org/original", "title": "Synthetische Originalquelle",
                          "author": "Testredaktion", "note": "Nur technische Testdaten.", "checked_at": "2026-10-20"}]}
            for i in range(1, count + 1)]}


def test_full_catalog_import_uses_bounded_database_round_trips(tmp_path, monkeypatch):
    """Cloud cold starts must not scan every preceding sort slot per lesson."""
    folder = tmp_path / "complete-content"
    folder.mkdir()
    for slug, count in academy.COURSE_COUNTS.items():
        (folder / f"{slug}.json").write_text(json.dumps(authored_course(slug, count)))
    monkeypatch.setattr(academy, "CONTENT_DIR", folder)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(tmp_path / "bounded.sqlite3"))
    monkeypatch.setenv("SENSE_AND_STARS_DEMO", "0")
    class Counted:
        def __init__(self, conn):
            self.conn, self.queries = conn, 0
        def execute(self, *args):
            self.queries += 1
            return self.conn.execute(*args)
    with get_db() as conn:
        init_schema(conn)
        learning.init_learning(conn)
        measured = Counted(conn)
        academy.init_academy(measured)
        assert measured.queries < 1000, f"Excessive round trips: {measured.queries}"
        assert conn.execute("SELECT COUNT(*) FROM academy_lessons").fetchone()[0] == 120
        measured.queries = 0
        academy.init_academy(measured)
        assert measured.queries < 50, f"Warm start repeats lookup per lesson: {measured.queries}"


@pytest.fixture
def content(tmp_path, monkeypatch):
    folder = tmp_path / "content"
    folder.mkdir()
    (folder / "01_grundlagen.json").write_text(json.dumps(authored_course()), encoding="utf-8")
    monkeypatch.setattr(academy, "CONTENT_DIR", folder)
    monkeypatch.setattr(academy, "COURSE_COUNTS", {"grundlagen": 2})
    monkeypatch.setattr(academy, "EXPECTED_LESSONS", 2)
    return folder


@pytest.fixture
def api(tmp_path, monkeypatch, content):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(tmp_path / "academy.sqlite3"))
    monkeypatch.setenv("SENSE_AND_STARS_DEMO", "1")
    monkeypatch.setenv("SENSE_AND_STARS_HOSTED", "0")
    with get_db() as conn:
        init_schema(conn)
        for user_id, role in enumerate(("admin", "practitioner", "client"), 1):
            conn.execute("INSERT INTO users(id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)",
                         (user_id, role, role + "@example.invalid", "unused", role, "2026-10-20"))
            conn.execute("INSERT INTO sessions VALUES(?,?,?)", (token_hash(role), user_id, "2099-01-01T00:00:00+00:00"))
        learning.init_learning(conn)
        academy.init_academy(conn)
    app = FastAPI()
    app.include_router(learning.router)
    app.include_router(academy.router)
    with TestClient(app) as client:
        client.cookies.set("sense_and_stars_session", "practitioner")
        yield client


def role(api, value):
    api.cookies.clear()
    if value:
        api.cookies.set("sense_and_stars_session", value)
    return api


def ids(api):
    return [item["id"] for item in api.get("/api/academy/courses/grundlagen").json()["lessons"]]


def answers():
    return {f"q{i}": i % 2 for i in range(1, 4)}


def practice(checked=True):
    return {"response": "Meine ausführliche eigene synthetische Bearbeitung begründet die gewählten Schritte und ihre Grenzen.",
            "self_checks": [checked, checked, checked]}


def make_drafts():
    with get_db() as conn:
        conn.execute("UPDATE learning_lessons SET status='draft',published_at=NULL WHERE academy_key IS NOT NULL")


def test_open_courses_have_hidden_answers_and_no_prerequisite_gate(api):
    overview = api.get("/api/academy").json()
    assert overview["courses"][0]["lesson_count"] == 2
    assert overview["progress"] == {"points": 0, "read_count": 0, "passed_count": 0, "practice_count": 0}
    assert overview["preview_available"] is False
    second = ids(api)[1]
    detail = api.get(f"/api/academy/lessons/{second}").json()
    assert detail["lesson"]["available"] is True
    assert "correct_index" not in json.dumps(detail)
    assert "explanation" not in json.dumps(detail)
    assert len(detail["examples"]) == 2
    assert detail["practice"]["model_answer"]
    assert api.post(f"/api/academy/lessons/{second}/complete", json={}).json()["points_awarded"] == 5


@pytest.mark.parametrize("who,status", [(None, 401), ("client", 403)])
def test_all_academy_routes_restrict_roles(api, who, status):
    lesson_id = ids(api)[0]
    role(api, who)
    for path in ("/api/academy", "/api/academy/courses/grundlagen", f"/api/academy/lessons/{lesson_id}"):
        assert api.get(path).status_code == status
    for suffix, body in (("complete", {}), ("quiz", {"answers": answers()}), ("practice", practice())):
        assert api.post(f"/api/academy/lessons/{lesson_id}/{suffix}", json=body).status_code == status


def test_preview_is_admin_only_and_no_draft_mutation_or_legacy_bypass(api):
    lesson_id = ids(api)[0]
    make_drafts()
    assert api.get("/api/academy").json()["courses"][0]["published_count"] == 0
    assert api.get("/api/academy/courses/grundlagen").json()["lessons"] == []
    assert api.get("/api/academy/courses/grundlagen?preview=1").status_code == 403
    assert api.get(f"/api/academy/lessons/{lesson_id}?preview=1").status_code == 403
    role(api, "admin")
    assert api.get(f"/api/academy/lessons/{lesson_id}").status_code == 404
    detail = api.get(f"/api/academy/lessons/{lesson_id}?preview=1").json()
    assert detail["lesson"]["body"] and detail["lesson"]["available"] is False
    for suffix, body in (("complete", {}), ("quiz", {"answers": answers()}), ("practice", practice())):
        assert api.post(f"/api/academy/lessons/{lesson_id}/{suffix}?preview=1", json=body).status_code == 409
    assert api.post(f"/api/learning/{lesson_id}/complete", json={}).status_code == 404
    assert api.post(f"/api/admin/lessons/{lesson_id}/publish", json={}).status_code == 409
    assert api.get("/api/academy").json()["progress"]["points"] == 0



def test_published_preview_cannot_mutate_or_award_points(api):
    lesson_id = ids(api)[0]
    role(api, "admin")
    for suffix, body in (("complete", {}), ("quiz", {"answers": answers()}), ("practice", practice())):
        assert api.post(f"/api/academy/lessons/{lesson_id}/{suffix}?preview=1", json=body).status_code == 409
    assert api.get("/api/academy").json()["progress"]["points"] == 0
    assert api.get(f"/api/academy/lessons/{lesson_id}").json()["attempts"] == []
    assert api.post(f"/api/learning/{lesson_id}/complete?preview=1", json={}).status_code == 409
    assert api.post(f"/api/learning/{lesson_id}/quiz?preview=1", json={"answers": answers()}).status_code == 409

def test_complete_lifecycle_feedback_revisions_points_badges_and_user_isolation(api, monkeypatch):
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(learning, "utc_now", lambda: now)
    first, second = ids(api)
    wrong = {key: 1 - value for key, value in answers().items()}
    failed = api.post(f"/api/academy/lessons/{second}/quiz", json={"answers": wrong}).json()
    assert failed["passed"] is False and failed["points_awarded"] == 0
    assert failed["review_due_at"] == (now + timedelta(days=1)).isoformat()
    assert all(not item["correct"] and item["explanation"] for item in failed["feedback"])
    for lesson_id in (second, first):
        url = f"/api/academy/lessons/{lesson_id}"
        assert api.post(url + "/complete", json={}).json()["points_awarded"] == 5
        assert api.post(url + "/complete", json={}).json()["points_awarded"] == 0
        assert api.post(url + "/quiz", json={"answers": answers()}).json()["points_awarded"] == 15
        assert api.post(url + "/quiz", json={"answers": answers()}).json()["points_awarded"] == 0
        incomplete = api.post(url + "/practice", json=practice(False)).json()
        assert incomplete["points_awarded"] == 0
        complete = api.post(url + "/practice", json=practice()).json()
        assert complete["attempt"]["assessment"] == "self_assessment"
        assert complete["points_awarded"] == 20
        assert api.post(url + "/practice", json=practice()).json()["points_awarded"] == 0
        api.post(url + "/quiz", json={"answers": answers()})
    overview = api.get("/api/academy").json()
    assert overview["progress"] == {"points": 80, "read_count": 2, "passed_count": 2, "practice_count": 2}
    assert len(overview["badges"]) == 1 and "Lernabzeichen" in overview["badges"][0]["title"]
    assert overview["courses"][0]["badge_earned"] is True
    assert len(overview["reviews"]) == 2
    detail = api.get(f"/api/academy/lessons/{second}").json()
    assert detail["state"] == {"read": True, "quiz_passed": True, "practice_completed": True,
                               "review_due_at": (now + timedelta(days=7)).isoformat()}
    assert len(detail["attempts"]) == 7
    role(api, "admin")
    assert api.get("/api/academy").json()["progress"]["points"] == 0
    assert api.get(f"/api/academy/lessons/{second}").json()["attempts"] == []
    role(api, "practitioner")
    assert api.get("/api/academy").json()["progress"]["points"] == 80


@pytest.mark.parametrize("bad", [{}, {"q1": 0}, {"q1": 1, "q2": 0, "q3": 1, "extra": 0},
                                {"q1": True, "q2": 0, "q3": 1}, {"q1": 1.0, "q2": 0, "q3": 1},
                                {"q1": -1, "q2": 0, "q3": 1}, {"q1": 99, "q2": 0, "q3": 1}])
def test_invalid_answers_never_create_attempt_or_points(api, bad):
    lesson_id = ids(api)[0]
    assert api.post(f"/api/academy/lessons/{lesson_id}/quiz", json={"answers": bad}).status_code == 422
    assert api.get(f"/api/academy/lessons/{lesson_id}").json()["attempts"] == []
    assert api.get("/api/academy").json()["progress"]["points"] == 0


def test_practice_survives_many_quizzes_and_history_is_private_and_pageable(api, monkeypatch):
    lesson_id = ids(api)[0]
    path = f"/api/academy/lessons/{lesson_id}"
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(learning, "utc_now", lambda: now)
    saved = api.post(path + "/practice", json=practice()).json()["attempt"]
    for i in range(42):
        now += timedelta(seconds=1)
        assert api.post(path + "/quiz", json={"answers": answers()}).status_code == 200
    detail = api.get(path).json()
    assert len(detail["attempts"]) == 20
    assert detail["latest_practice"]["id"] == saved["id"]
    assert detail["attempts_has_more"]
    all_attempts = list(detail["attempts"])
    cursor = all_attempts[-1]["id"]
    while True:
        page = api.get(path + "/attempts", params={"before_id": cursor}).json()
        all_attempts.extend(page["items"])
        if not page["has_more"]:
            break
        cursor = page["items"][-1]["id"]
    assert len(all_attempts) == len({a["id"] for a in all_attempts}) == 43
    assert all_attempts[-1]["id"] == saved["id"]
    role(api, "admin")
    assert api.get(path).json()["latest_practice"] is None
    assert api.get(path + "/attempts", params={"before_id": cursor}).status_code == 404
    assert api.get(path + "/attempts").json() == {"items": [], "has_more": False}
    assert api.get("/api/academy").json()["progress"]["points"] == 0


def test_search_metadata_contains_only_published_lesson_titles(api):
    before = api.get("/api/academy").json()["courses"][0]
    assert "Testlektion" in before["search_text"]
    make_drafts()
    after = api.get("/api/academy").json()["courses"][0]
    assert after["search_text"] == ""


@pytest.mark.parametrize("changes", [{"response": "short"}, {"self_checks": [True, True]},
                                     {"self_checks": [True, True, True, True]},
                                     {"self_checks": [1, 1, 1]}, {"user_id": 1}])
def test_invalid_practice_is_rejected(api, changes):
    lesson_id = ids(api)[0]
    assert api.post(f"/api/academy/lessons/{lesson_id}/practice", json=dict(practice(), **changes)).status_code == 422
    assert api.get(f"/api/academy/lessons/{lesson_id}").json()["attempts"] == []


def test_legacy_read_and_quiz_are_synchronized_but_flags_cannot_award_practice(api):
    lesson_id = ids(api)[0]
    api.post(f"/api/learning/{lesson_id}/complete", json={})
    api.post(f"/api/learning/{lesson_id}/quiz", json={"answers": answers()})
    api.patch(f"/api/learning/{lesson_id}/state", json={"practiced": True, "bookmarked": True, "pinned": True})
    detail = api.get(f"/api/academy/lessons/{lesson_id}").json()
    assert detail["lesson"]["bookmarked"] and detail["lesson"]["pinned"]
    assert detail["state"]["read"] and detail["state"]["quiz_passed"]
    assert detail["state"]["practice_completed"] is False
    assert api.get("/api/academy").json()["progress"]["points"] == 20
    api.post(f"/api/academy/lessons/{lesson_id}/complete", json={})
    assert api.get("/api/academy").json()["progress"]["points"] == 20


def test_idempotent_import_keeps_existing_content_notes_and_state(api, monkeypatch):
    lesson_id = ids(api)[0]
    api.post(f"/api/learning/{lesson_id}/complete", json={})
    note = api.post("/api/learning/notebook", json={"lesson_id": lesson_id, "title": "Meine Notiz", "body": "Privat und unverändert."}).json()
    with get_db() as conn:
        before = [dict(row) for row in conn.execute("SELECT * FROM learning_lessons ORDER BY id")]
        academy.init_academy(conn)
        after = [dict(row) for row in conn.execute("SELECT * FROM learning_lessons ORDER BY id")]
    assert before == after
    assert api.get("/api/learning/notebook").json()[0]["id"] == note["id"]
    assert api.get(f"/api/academy/lessons/{lesson_id}").json()["state"]["read"] is True


def test_hosted_import_is_draft_and_repeated_import_cannot_publish(api, monkeypatch):
    make_drafts()
    monkeypatch.setenv("SENSE_AND_STARS_DEMO", "1")
    with get_db() as conn:
        academy.init_academy(conn)
    assert api.get("/api/academy/courses/grundlagen").json()["lessons"] == []


def test_package_approval_requires_exact_current_hash_and_is_atomic(api):
    make_drafts()
    assert api.get("/api/admin/academy/release").status_code == 403
    role(api, "admin")
    state = api.get("/api/admin/academy/release").json()
    assert state["ready"] and state["draft_count"] == 2
    assert api.post("/api/admin/academy/release", json={"manifest_sha256": "0" * 64, "acknowledged": True}).status_code == 409
    assert api.post("/api/admin/academy/release", json={"manifest_sha256": state["manifest_sha256"], "acknowledged": False}).status_code == 422
    assert api.get("/api/admin/academy/release").json()["published_count"] == 0
    approved = api.post("/api/admin/academy/release", json={"manifest_sha256": state["manifest_sha256"], "acknowledged": True})
    assert approved.status_code == 200 and approved.json()["published_count"] == 2
    assert approved.json()["manifest_sha256"] == state["manifest_sha256"]
    assert api.post("/api/admin/academy/release", json={"manifest_sha256": state["manifest_sha256"], "acknowledged": True}).status_code == 200
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM learning_audit WHERE action='academy_package_published'").fetchone()[0] == 1


def test_partial_package_changed_source_and_edited_base_cannot_publish(api, content, monkeypatch):
    make_drafts()
    role(api, "admin")
    state = api.get("/api/admin/academy/release").json()
    monkeypatch.setattr(academy, "EXPECTED_LESSONS", 120)
    assert api.get("/api/admin/academy/release").json()["ready"] is False
    monkeypatch.setattr(academy, "EXPECTED_LESSONS", 2)
    path = content / "01_grundlagen.json"
    value = json.loads(path.read_text())
    value["lessons"][0]["body"] += " Redaktionell geändert."
    path.write_text(json.dumps(value))
    assert api.get("/api/admin/academy/release").json()["ready"] is False
    value["lessons"][0]["body"] = value["lessons"][0]["body"].removesuffix(" Redaktionell geändert.")
    path.write_text(json.dumps(value))
    with get_db() as conn:
        conn.execute("UPDATE learning_lessons SET body='Unerwartet geändert' WHERE academy_key='academy-grundlagen-01'")
    assert api.get("/api/admin/academy/release").json()["ready"] is False
    assert api.post("/api/admin/academy/release", json={"manifest_sha256": state["manifest_sha256"], "acknowledged": True}).status_code == 409
    assert api.get("/api/admin/academy/release").json()["published_count"] == 0



def test_practice_success_does_not_postpone_failed_quiz_review(api, monkeypatch):
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(learning, "utc_now", lambda: now)
    lesson_id = ids(api)[0]
    wrong = {key: 1 - value for key, value in answers().items()}
    api.post(f"/api/academy/lessons/{lesson_id}/quiz", json={"answers": wrong})
    result = api.post(f"/api/academy/lessons/{lesson_id}/practice", json=practice()).json()
    assert result["review_due_at"] == (now + timedelta(days=1)).isoformat()


def test_duplicate_sort_positions_refuse_release_without_partial_changes(api):
    first, second = ids(api)
    make_drafts()
    role(api, "admin")
    with get_db() as conn:
        week = conn.execute("SELECT week FROM learning_lessons WHERE id=?", (first,)).fetchone()[0]
        conn.execute("UPDATE learning_lessons SET week=? WHERE id=?", (week, second))
    state = api.get("/api/admin/academy/release").json()
    assert not state["ready"]
    assert api.post("/api/admin/academy/release", json={"manifest_sha256": state["manifest_sha256"], "acknowledged": True}).status_code == 409
    assert api.get("/api/admin/academy/release").json()["published_count"] == 0

def test_concurrent_completion_awards_once(api):
    lesson_id = ids(api)[0]
    def finish(_):
        with TestClient(api.app) as separate:
            separate.cookies.set("sense_and_stars_session", "practitioner")
            result = separate.post(f"/api/academy/lessons/{lesson_id}/complete", json={})
            assert result.status_code == 200
            return result.json()["points_awarded"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(finish, range(12))) == 5
    assert api.get("/api/academy").json()["progress"]["points"] == 5


def test_full_expected_120_lesson_12_course_release(tmp_path, monkeypatch):
    folder = tmp_path / "full"
    folder.mkdir()
    monkeypatch.setattr(academy, "CONTENT_DIR", folder)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(tmp_path / "full.sqlite3"))
    monkeypatch.setenv("SENSE_AND_STARS_DEMO", "0")
    for index, (slug, count) in enumerate(academy.COURSE_COUNTS.items()):
        (folder / f"{index:02d}_{slug}.json").write_text(json.dumps(authored_course(slug, count)))
    with get_db() as conn:
        init_schema(conn)
        learning.init_learning(conn)
        academy.init_academy(conn)
        state = academy.release_status(conn)
        assert state["ready"] and state["lesson_count"] == 120 and state["course_count"] == 12
        assert state["draft_count"] == 120 and state["published_count"] == 0
        assert len({row[0] for row in conn.execute("SELECT week FROM learning_lessons WHERE academy_key IS NOT NULL")}) == 120


def test_content_rejects_invalid_source_and_insubstantial_lesson():
    invalid = authored_course()
    invalid["lessons"][0]["sources"][0]["url"] = "http://localhost/private"
    with pytest.raises(ValueError):
        academy.AuthoredCourse.model_validate(invalid)
    invalid = authored_course()
    invalid["lessons"][0]["body"] = "Unzureichend."
    with pytest.raises(ValueError):
        academy.AuthoredCourse.model_validate(invalid)


# Uses a separate schema in an explicitly configured synthetic PostgreSQL DB.
from test_cloud_database import pg_api


def test_postgres_academy_release_progress_and_persistence(content, pg_api):
    with get_db() as conn:
        academy.init_academy(conn)
    headers = {"X-Sense-And-Stars": "1"}
    login = pg_api.post("/api/auth/login", json={"email": "pg-admin@example.org", "password": "Test-Postgres-Passphrase"}, headers=headers)
    assert login.status_code == 200
    assert pg_api.get("/api/academy").status_code == 200
    state = pg_api.get("/api/admin/academy/release").json()
    assert state["ready"] and state["draft_count"] == 2
    assert pg_api.post("/api/admin/academy/release", json={"manifest_sha256": state["manifest_sha256"], "acknowledged": True}, headers=headers).status_code == 200
    lesson_id = ids(pg_api)[0]
    for suffix, payload, points in (("complete", {}, 5), ("quiz", {"answers": answers()}, 15), ("practice", practice(), 20)):
        response = pg_api.post(f"/api/academy/lessons/{lesson_id}/{suffix}", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["points_awarded"] == points
        assert pg_api.post(f"/api/academy/lessons/{lesson_id}/{suffix}", json=payload, headers=headers).json()["points_awarded"] == 0
    assert pg_api.get("/api/academy").json()["progress"]["points"] == 40
    assert len(pg_api.get(f"/api/academy/lessons/{lesson_id}").json()["attempts"]) == 4
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM academy_attempts").fetchone()[0] == 4
        academy.init_academy(conn)
    assert pg_api.get("/api/academy").json()["progress"]["points"] == 40
