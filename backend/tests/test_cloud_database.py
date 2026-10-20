"""The hosted runtime must never silently store data in an ephemeral file."""
import os
import pytest
from app import db


@pytest.fixture
def pg_api(monkeypatch):
    url = os.environ.get("SOULFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("explicit isolated PostgreSQL database required")
    import uuid
    from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qsl
    import psycopg
    from psycopg import sql
    schema = "qa_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as raw:
        raw.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    parts = urlsplit(url)
    scoped = urlunsplit(parts._replace(query=urlencode([*parse_qsl(parts.query), ("options", "-csearch_path=" + schema + ",public")])))
    monkeypatch.setenv("DATABASE_URL", scoped)
    monkeypatch.setenv("SOULFLOW_DEMO", "0")
    from app.main import app
    from app.security import hash_password, now_iso
    from fastapi.testclient import TestClient
    try:
        with TestClient(app) as client:
            with db.get_db() as conn:
                for email, role in (("pg-admin@example.org", "admin"), ("pg-practice@example.org", "practitioner")):
                    conn.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)", ("TEST", email, hash_password("Test-Postgres-Passphrase"), role, now_iso()))
            yield client
    finally:
        with psycopg.connect(url, autocommit=True) as raw:
            raw.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_postgres_real_login_quiz_notebook_and_practice_flow(pg_api):
    def mutate(method, path, body=None):
        return pg_api.request(method, path, json=body or {}, headers={"X-SoulFlow": "1"})
    assert mutate("POST", "/api/auth/login", {"email": "pg-admin@example.org", "password": "wrong"}).status_code == 401
    assert mutate("POST", "/api/auth/login", {"email": "pg-admin@example.org", "password": "wrong"}).status_code == 401
    assert mutate("POST", "/api/auth/login", {"email": "pg-admin@example.org", "password": "Test-Postgres-Passphrase"}).status_code == 200
    scan = mutate("POST", "/api/admin/scan", {"simulate":True})
    assert scan.status_code == 200, scan.text
    assert scan.json()["created"] == 1
    lesson = pg_api.get("/api/learning").json()["lessons"][0]
    assert mutate("POST", f"/api/learning/{lesson['id']}/complete").status_code == 200
    answers = {q["id"]: 0 for q in lesson["quiz"]}
    assert mutate("POST", f"/api/learning/{lesson['id']}/quiz", {"answers": answers}).status_code == 200
    assert mutate("POST", f"/api/learning/{lesson['id']}/quiz", {"answers": answers}).status_code == 200
    assert mutate("POST", "/api/learning/notebook", {"lesson_id":lesson["id"],"title":"TEST · PostgreSQL","body":"Persistent test note"}).status_code == 200
    created = mutate("POST", "/api/practice/clients/examples")
    assert created.status_code == 200, created.text
    assert len(created.json()) == 3
    assert pg_api.get("/api/clients").json() == []
    assert len(pg_api.get("/api/clients?practice=1").json()) == 3
    places = pg_api.get("/api/astro/places", params={"q":"Berlin"})
    assert places.status_code == 200, places.text
    place_id = places.json()[0]["id"]
    computed = mutate("POST", f"/api/clients/{created.json()[0]['id']}/chart", {"place_id":place_id})
    assert computed.status_code == 200, computed.text
    assert computed.json()["planets"]
    assert mutate("POST", "/api/practice/reset").status_code == 200
    assert pg_api.get("/api/clients?practice=1").json() == []
    assert len(pg_api.get("/api/clients?practice=1&archived=1").json()) == 3


def test_hosted_api_has_no_demo_and_requires_session_and_same_origin(pg_api, monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    monkeypatch.setenv("SOULFLOW_HOSTED", "1")
    monkeypatch.setenv("SOULFLOW_PUBLIC_ORIGIN", "https://testserver")
    monkeypatch.setenv("SOULFLOW_SWISS_LICENSE", "agpl-3.0")
    monkeypatch.setenv("SOULFLOW_SOURCE_URL", "https://example.org/test-source")
    monkeypatch.setenv("CRON_SECRET", "synthetic-test-only-cron-secret-123")
    with TestClient(app, base_url="https://testserver", client=("203.0.113.8", 41000)) as remote:
        assert remote.get("/api/demo").status_code == 404
        assert remote.get("/api/clients").status_code == 401
        payload={"email":"pg-admin@example.org","password":"Test-Postgres-Passphrase"}
        bad=remote.post("/api/auth/login",json=payload,headers={"X-SoulFlow":"1","Origin":"https://other.example.org"})
        assert bad.status_code == 403
        login=remote.post("/api/auth/login",json=payload,headers={"X-SoulFlow":"1","Origin":"https://testserver"})
        assert login.status_code == 200, login.text
        assert "Secure" in login.headers["set-cookie"]
        assert "HttpOnly" in login.headers["set-cookie"]
        response=remote.get("/api/learning/notebook")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["strict-transport-security"]
        assert remote.get("/api/internal/learning-updates").status_code == 401
        assert remote.get("/api/health").json()["mode"] == "hosted"


def test_hosted_database_fails_closed_without_persistent_url(monkeypatch):
    monkeypatch.setenv("SOULFLOW_HOSTED", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db.get_db()


def test_sql_translation_keeps_question_marks_inside_strings():
    from app.postgres import translate_sql
    assert translate_sql("SELECT '?' AS label, ? AS value") == "SELECT '?' AS label, %s AS value"


@pytest.mark.skipif(not os.environ.get("SOULFLOW_TEST_POSTGRES_URL"), reason="explicit isolated PostgreSQL database required")
def test_postgres_real_persistence_transaction_and_constraints(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["SOULFLOW_TEST_POSTGRES_URL"])
    with db.get_db() as conn:
        db.init_schema(conn)
        stamp = 1792522800.123456
        conn.execute("INSERT INTO login_attempts(key,first_at) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET first_at=excluded.first_at", ("cloud-test-clock",stamp))
        assert conn.execute("SELECT first_at FROM login_attempts WHERE key=?", ("cloud-test-clock",)).fetchone()[0] == pytest.approx(stamp, abs=0.000001, rel=0)
        conn.execute("DELETE FROM clients WHERE email LIKE 'cloud-test-%@example.org'")
        cursor = conn.execute("INSERT INTO clients(name,email,created_at) VALUES(?,?,?)", ("TEST", "cloud-test-one@example.org", "2026-10-20"))
        assert cursor.lastrowid > 0
        identifier = cursor.lastrowid
    with db.get_db() as conn:
        assert conn.execute("SELECT name FROM clients WHERE id=?", (identifier,)).fetchone()[0] == "TEST"
        assert "email" in {r["name"] for r in conn.execute("PRAGMA table_info(clients)")}
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        with db.get_db() as conn:
            conn.execute("INSERT INTO clients(name,email,created_at) VALUES(?,?,?)", ("TEST", "CLOUD-TEST-ONE@example.org", "2026-10-20"))
    with pytest.raises(ValueError):
        with db.get_db() as conn:
            conn.execute("UPDATE clients SET name='SHOULD ROLLBACK' WHERE id=?", (identifier,))
            raise ValueError("TEST rollback")
    with db.get_db() as conn:
        assert conn.execute("SELECT name FROM clients WHERE id=?", (identifier,)).fetchone()["name"] == "TEST"
        conn.execute("DELETE FROM clients WHERE id=?", (identifier,))


@pytest.mark.skipif(not os.environ.get("SOULFLOW_TEST_POSTGRES_URL"), reason="explicit isolated PostgreSQL database required")
def test_postgres_timeouts_are_transaction_local_and_reapplied_after_boundaries(monkeypatch):
    import psycopg

    url = os.environ["SOULFLOW_TEST_POSTGRES_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    query = """SELECT current_setting('statement_timeout') AS statement_timeout,
                      current_setting('lock_timeout') AS lock_timeout"""
    with psycopg.connect(url) as baseline_conn:
        baseline = tuple(baseline_conn.execute(query).fetchone())

    conn = db.get_db()
    try:
        assert tuple(conn.execute(query).fetchone().values()) == ("15s", "10s")
        conn.commit()
        assert tuple(conn._conn.execute(query).fetchone()) == baseline
        conn._conn.rollback()

        assert tuple(conn.execute(query).fetchone().values()) == ("15s", "10s")
        conn.rollback()
        assert tuple(conn._conn.execute(query).fetchone()) == baseline
        conn._conn.rollback()

        assert tuple(conn.execute(query).fetchone().values()) == ("15s", "10s")
    finally:
        conn.close()


@pytest.mark.skipif(not os.environ.get("SOULFLOW_TEST_POSTGRES_URL"), reason="explicit isolated PostgreSQL database required")
def test_postgres_commit_connection_loss_is_normalized(monkeypatch):
    import psycopg, sqlite3
    url = os.environ["SOULFLOW_TEST_POSTGRES_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    conn = db.get_db()
    try:
        pid = conn.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
        with psycopg.connect(url, autocommit=True) as control:
            assert control.execute("SELECT pg_terminate_backend(%s)", (pid,)).fetchone()[0] is True
        with pytest.raises(sqlite3.OperationalError):
            conn.commit()
    finally:
        conn.close()
