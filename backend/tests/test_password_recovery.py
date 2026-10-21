"""Recovery uses synthetic identities and intercepted mail only; no real sends."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import re
import ssl
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import password_recovery as recovery, recovery_mail
from app.db import get_db
from app.security import hash_password, token_hash
from test_cloud_database import pg_api  # existing isolated PostgreSQL fixture


NEW_PASSWORD = "Morgen Blume Wiese"
HEADERS = {"X-Sense-And-Stars": "1"}


@pytest.fixture
def mail(monkeypatch):
    for key, value in {
        "SMTP_HOST": "smtp.example.org", "SMTP_PORT": "587", "SMTP_SECURITY": "starttls",
        "SMTP_USERNAME": "synthetic-user", "SMTP_PASSWORD": "synthetic-smtp-secret",
        "MAIL_FROM": "noreply@example.org", "RECOVERY_LOCAL_ORIGIN": "http://127.0.0.1:8768",
    }.items():
        monkeypatch.setenv("SENSE_AND_STARS_" + key, value)
    sent = []
    monkeypatch.setattr(recovery_mail, "send_message", lambda settings, recipient, subject, text: sent.append({
        "recipient": recipient, "subject": subject, "text": text,
    }))
    clock = SimpleNamespace(now=1_800_000_000.0, elapsed=0.0, sleeps=[])
    def sleep(seconds):
        clock.sleeps.append(seconds)
        clock.elapsed += seconds
    monkeypatch.setattr(recovery, "time", SimpleNamespace(time=lambda: clock.now,
                        monotonic=lambda: clock.elapsed, sleep=sleep))
    return SimpleNamespace(sent=sent, clock=clock)


@pytest.fixture
def api(tmp_path, monkeypatch, mail):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENSE_AND_STARS_HOSTED", "0")
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(tmp_path / "recovery.sqlite3"))
    monkeypatch.setenv("SENSE_AND_STARS_DEMO", "1")
    from app.main import app
    with TestClient(app) as client:
        yield client


def post(api, path, data, **headers):
    return api.post("/api/auth/" + path, json=data, headers={**HEADERS, **headers})


def account(api, role="practitioner"):
    return next(a for a in api.get("/api/demo").json()["accounts"] if a["role"] == role)


def request_token(api, mail, email):
    response = post(api, "password-reset/request", {"email": email})
    assert response.status_code == 202, response.text
    return re.search(r"token=([A-Za-z0-9_-]{43})", mail.sent[-1]["text"])[1]


def confirm(api, token, password=NEW_PASSWORD):
    return post(api, "password-reset/confirm", {"token": token, "password": password, "password_confirm": password})


def test_unconfigured_is_honest_and_identical_for_all_accounts(api, mail, monkeypatch):
    monkeypatch.setenv("SENSE_AND_STARS_SMTP_PASSWORD", "")
    assert api.get("/api/auth/recovery").json() == {"available": False}
    responses = [post(api, "password-reset/request", {"email": email}) for email in
                 (account(api)["email"], "unknown@example.org")]
    assert [r.status_code for r in responses] == [503, 503]
    assert responses[0].json() == responses[1].json()
    assert mail.sent == []
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[0] == 0


def test_request_is_neutral_hash_only_and_does_not_change_password(api, mail):
    target = account(api)
    with get_db() as conn:
        before = dict(conn.execute("SELECT * FROM users WHERE email=?", (target["email"],)).fetchone())
    known = post(api, "password-reset/request", {"email": target["email"]})
    unknown = post(api, "password-reset/request", {"email": "unknown@example.org"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"message": recovery.REQUEST_MESSAGE}
    assert api.get("/api/auth/recovery").json() == {"available": True}
    assert known.headers["cache-control"] == "no-store"
    assert known.headers["referrer-policy"] == "no-referrer"
    assert mail.clock.sleeps == [7, 7]
    assert len(mail.sent) == 1 and mail.sent[0]["recipient"] == target["email"]
    token = re.search(r"token=([A-Za-z0-9_-]{43})", mail.sent[0]["text"])[1]
    assert "http://127.0.0.1:8768/#reset-password?token=" in mail.sent[0]["text"]
    assert token not in known.text and token not in unknown.text
    with get_db() as conn:
        row = dict(conn.execute("SELECT * FROM password_reset_tokens").fetchone())
        assert row["token_hash"] == token_hash(token)
        assert token not in str(row)
        assert row["expires_at"] - row["created_at"] == 1800
        assert row["credential_fingerprint"] == token_hash(before["password_hash"])
        assert dict(conn.execute("SELECT * FROM users WHERE id=?", (before["id"],)).fetchone()) == before


def test_response_window_also_covers_slow_smtp_acceptance(api, mail, monkeypatch):
    def slow_mail(*args):
        mail.clock.elapsed += 5
    monkeypatch.setattr(recovery_mail, "send_message", slow_mail)
    target = account(api)
    assert post(api, "password-reset/request", {"email": target["email"]}).status_code == 202
    assert mail.clock.elapsed == 7 and mail.clock.sleeps == [2]
    assert post(api, "password-reset/request", {"email": "unknown@example.org"}).status_code == 202
    assert mail.clock.elapsed == 14 and mail.clock.sleeps == [2, 7]


def _exercise_recovery(api, mail, target, other):
    assert post(api, "login", target).status_code == 200
    old_cookie = api.cookies.get("sense_and_stars_session")
    assert api.patch("/api/auth/me", json={"name": "TEST Name bleibt", "hourly_rate_cents": 7350}, headers=HEADERS).status_code == 200
    note = api.post("/api/learning/notebook", json={"title": "TEST Notiz", "body": "Bleibt erhalten"}, headers=HEADERS)
    assert note.status_code == 200, note.text
    for _ in range(5):
        assert post(api, "login", {**target, "password": "wrong"}).status_code == 401
    assert post(api, "login", target).status_code == 429
    assert post(api, "login", {**other, "password": "wrong"}).status_code == 401
    with get_db() as conn:
        user = dict(conn.execute("SELECT * FROM users WHERE email=?", (target["email"],)).fetchone())
        other_user = dict(conn.execute("SELECT * FROM users WHERE email=?", (other["email"],)).fetchone())
        conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", ("other-session", other_user["id"], "2099-01-01T00:00:00+00:00"))
        # A second peer's failures belong to the same target and must also clear.
        conn.execute("INSERT INTO login_attempts(key,failures,first_at,account_key) VALUES(?,5,?,?)", ("second-peer", mail.clock.now, token_hash(target["email"])))
    token = request_token(api, mail, target["email"])
    response = confirm(api, token)
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert "set-cookie" not in response.headers
    assert api.get("/api/auth/me").status_code == 401
    assert confirm(api, token).status_code == 400
    assert post(api, "login", target).status_code == 401
    assert post(api, "login", {**target, "password": NEW_PASSWORD}).status_code == 200
    assert api.get("/api/learning/notebook").json() == [note.json()]
    profile = api.get("/api/auth/me").json()
    assert profile["name"] == "TEST Name bleibt" and profile["hourly_rate_cents"] == 7350
    with get_db() as conn:
        after = dict(conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone())
        assert {k: v for k, v in after.items() if k != "password_hash"} == {k: v for k, v in user.items() if k != "password_hash"}
        assert dict(conn.execute("SELECT * FROM users WHERE id=?", (other_user["id"],)).fetchone()) == other_user
        assert conn.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash(old_cookie),)).fetchone() is None
        assert conn.execute("SELECT * FROM sessions WHERE token_hash='other-session'").fetchone()
        assert conn.execute("SELECT * FROM login_attempts WHERE account_key=?", (token_hash(other["email"]),)).fetchone()
        assert not conn.execute("SELECT * FROM login_attempts WHERE account_key=?", (token_hash(target["email"]),)).fetchone()
        assert not conn.execute("SELECT * FROM password_reset_tokens WHERE user_id=?", (user["id"],)).fetchone()
    assert len(mail.sent) == 2
    assert NEW_PASSWORD not in mail.sent[-1]["text"] and token not in mail.sent[-1]["text"]


def test_recovery_unlocks_only_target_revokes_sessions_and_preserves_work(api, mail):
    target, other = account(api), account(api, "admin")
    _exercise_recovery(api, mail, {k: target[k] for k in ("email", "password")}, {k: other[k] for k in ("email", "password")})


def test_postgres_recovery_unlocks_and_preserves_work(pg_api, mail):
    _exercise_recovery(pg_api, mail, {"email": "pg-practice@example.org", "password": "Test-Postgres-Passphrase"},
                       {"email": "pg-admin@example.org", "password": "Test-Postgres-Passphrase"})


def test_postgres_concurrent_confirm_has_one_winner(pg_api, mail):
    token = request_token(pg_api, mail, "pg-practice@example.org")
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: confirm(pg_api, token), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 400]


def test_invalid_expired_and_password_rotated_tokens_fail(api, mail):
    target = account(api)
    token = request_token(api, mail, target["email"])
    wrong = confirm(api, "x" * 43)
    mail.clock.now += 1800
    expired = confirm(api, token)
    assert wrong.status_code == expired.status_code == 400 and wrong.json() == expired.json()
    token = request_token(api, mail, target["email"])
    with get_db() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_password("Manually Rotated Passphrase"), target["email"]))
    assert confirm(api, token).status_code == 400
    assert post(api, "login", {"email": target["email"], "password": "Manually Rotated Passphrase"}).status_code == 200


def test_token_expiring_while_waiting_for_lock_is_rejected(api, mail, monkeypatch):
    target = account(api)
    token = request_token(api, mail, target["email"])
    real_get_db = recovery.get_db
    @contextmanager
    def delayed_lock():
        with real_get_db() as conn:
            class DelayedConnection:
                def __getattr__(self, name): return getattr(conn, name)
                def execute(self, sql, *args):
                    if sql == "BEGIN IMMEDIATE":
                        mail.clock.now += recovery.TOKEN_LIFETIME
                    return conn.execute(sql, *args)
            yield DelayedConnection()
    monkeypatch.setattr(recovery, "get_db", delayed_lock)
    assert confirm(api, token).status_code == 400
    assert post(api, "login", {"email": target["email"], "password": target["password"]}).status_code == 200


def test_new_request_and_failed_send_leave_previous_link_working(api, mail, monkeypatch):
    target = account(api)
    token = request_token(api, mail, target["email"])
    mail.clock.now += 61
    def failed(*args):
        raise RuntimeError("SMTP PRIVATE exception must never be reflected")
    monkeypatch.setattr(recovery_mail, "send_message", failed)
    response = post(api, "password-reset/request", {"email": target["email"]})
    assert response.status_code == 202 and "PRIVATE" not in response.text
    with get_db() as conn:
        tokens = conn.execute("SELECT token_hash FROM password_reset_tokens").fetchall()
        assert [r[0] for r in tokens] == [token_hash(token)]
        assert conn.execute("SELECT COUNT(*) FROM audit WHERE action='password_reset.mail_failed'").fetchone()[0] == 1
    # Notification delivery also fails; the completed reset still succeeds.
    assert confirm(api, token).status_code == 200
    assert post(api, "login", {"email": target["email"], "password": NEW_PASSWORD}).status_code == 200


def test_mail_audit_failure_does_not_change_neutral_request_or_committed_reset(api, mail, monkeypatch, caplog):
    real_audit = recovery._audit
    def audit_failure(conn, user_id, action):
        if action != "password_reset.completed":
            raise sqlite3.OperationalError("PRIVATE database connection detail")
        return real_audit(conn, user_id, action)
    monkeypatch.setattr(recovery, "_audit", audit_failure)
    target = account(api)
    token = request_token(api, mail, target["email"])
    unknown = post(api, "password-reset/request", {"email": "unknown@example.org"})
    assert unknown.status_code == 202 and unknown.json() == {"message": recovery.REQUEST_MESSAGE}
    assert confirm(api, token).status_code == 200
    assert post(api, "login", {"email": target["email"], "password": NEW_PASSWORD}).status_code == 200
    assert "PRIVATE" not in caplog.text and token not in caplog.text and target["email"] not in caplog.text
    assert "Recovery mail result could not be persisted." in caplog.text


def test_smtp_failure_followed_by_cleanup_database_failure_still_returns_neutral_response(api, mail, monkeypatch):
    real_get_db = recovery.get_db
    calls = []
    def fail_mail_reconnect():
        calls.append(1)
        if len(calls) == 2:
            raise sqlite3.OperationalError("PRIVATE reconnect detail")
        return real_get_db()
    def send_failure(*args):
        raise RuntimeError("PRIVATE transport detail")
    monkeypatch.setattr(recovery, "get_db", fail_mail_reconnect)
    monkeypatch.setattr(recovery_mail, "send_message", send_failure)
    response = post(api, "password-reset/request", {"email": account(api)["email"]})
    assert response.status_code == 202 and response.json() == {"message": recovery.REQUEST_MESSAGE}
    assert mail.clock.sleeps == [7]


def test_all_outstanding_links_revoked_and_concurrent_confirm_has_one_winner(api, mail):
    target = account(api)
    first = request_token(api, mail, target["email"])
    mail.clock.now += 61
    second = request_token(api, mail, target["email"])
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: confirm(api, first), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 400]
    assert confirm(api, second).status_code == 400


@pytest.mark.parametrize("changes", [{"password": "short", "password_confirm": "short"},
    {"password": "a" * 257, "password_confirm": "a" * 257}, {"password_confirm": "Other Private Secret"},
    {"token": "PRIVATE invalid token"}, {"unexpected": "PRIVATE extra"}])
def test_validation_never_reflects_credentials_or_tokens(api, changes):
    payload = {"token": "t" * 43, "password": NEW_PASSWORD, "password_confirm": NEW_PASSWORD, **changes}
    response = post(api, "password-reset/confirm", payload)
    assert response.status_code == 422
    assert "input" not in response.text and "ctx" not in response.text
    for value in payload.values():
        assert value not in response.text


def test_request_validation_and_cross_origin_are_rejected(api):
    response = post(api, "password-reset/request", {"email": "PRIVATE not an email"})
    assert response.status_code == 422 and "PRIVATE" not in response.text
    assert post(api, "password-reset/request", {"email": "x@example.org"}, Origin="https://evil.example").status_code == 403
    assert api.post("/api/auth/password-reset/request", json={"email": "x@example.org"}).status_code == 403


def test_password_whitespace_is_not_silently_changed(api, mail):
    target = account(api)
    token = request_token(api, mail, target["email"])
    password = "  Drei einfache Worte  "
    assert confirm(api, token, password=password).status_code == 200
    assert post(api, "login", {"email": target["email"], "password": password.strip()}).status_code == 401
    assert post(api, "login", {"email": target["email"], "password": password}).status_code == 200


def test_rate_limit_durable_account_peer_and_global_without_forwarded_header_trust(api, mail):
    target = account(api)
    for email in (target["email"], "unknown@example.org"):
        assert post(api, "password-reset/request", {"email": email}).status_code == 202
        assert post(api, "password-reset/request", {"email": email}, **{"X-Forwarded-For": "198.51.100.31"}).status_code == 429
        for _ in range(2):
            mail.clock.now += 61
            assert post(api, "password-reset/request", {"email": email}).status_code == 202
        mail.clock.now += 61
        assert post(api, "password-reset/request", {"email": email}).status_code == 429
    # Six accepted requests above; a single peer may send at most twenty/hour.
    for i in range(14):
        assert post(api, "password-reset/request", {"email": f"other{i}@example.org"}).status_code == 202
    assert post(api, "password-reset/request", {"email": "peer-capped@example.org"}, **{"X-Forwarded-For": "203.0.113.5"}).status_code == 429
    with get_db() as conn:
        conn.execute("DELETE FROM password_reset_limits")
        conn.execute("INSERT INTO password_reset_limits VALUES(?,100,?,?)", (token_hash("request.global"), mail.clock.now, mail.clock.now))
    assert post(api, "password-reset/request", {"email": "global-capped@example.org"}).status_code == 429


def test_confirm_limiter_is_separate_and_invalid_attempts_persist(api):
    for _ in range(10):
        assert confirm(api, "x" * 43).status_code == 400
    assert confirm(api, "x" * 43).status_code == 429
    assert post(api, "password-reset/request", {"email": "unknown@example.org"}).status_code == 202


def test_legacy_login_failure_attribution_and_reset(api, mail):
    import time
    target = account(api)
    with get_db() as conn:
        key = token_hash("testclient:" + target["email"].lower())
        conn.execute("INSERT INTO login_attempts(key,failures,first_at) VALUES(?,5,?)", (key, time.time()))
    assert post(api, "login", {"email": target["email"], "password": target["password"]}).status_code == 429
    with get_db() as conn:
        assert conn.execute("SELECT account_key FROM login_attempts WHERE key=?", (key,)).fetchone()[0] == token_hash(target["email"])
    token = request_token(api, mail, target["email"])
    assert confirm(api, token).status_code == 200
    assert post(api, "login", {"email": target["email"], "password": NEW_PASSWORD}).status_code == 200


@pytest.mark.parametrize("key,value", [("SMTP_SECURITY", "plain"), ("SMTP_PORT", "0"),
    ("MAIL_FROM", "sender@example.org\r\nBcc: evil@example.org"), ("SMTP_HOST", "smtp.example.org/evil"),
    ("RECOVERY_LOCAL_ORIGIN", "https://evil.example.org"), ("RECOVERY_LOCAL_ORIGIN", "http://localhost"),
    ("RECOVERY_LOCAL_ORIGIN", "http://user:pass@localhost:8768"), ("RECOVERY_LOCAL_ORIGIN", "http://127.0.0.1:8768/#evil")])
def test_invalid_mail_configuration_is_disabled(api, monkeypatch, key, value):
    monkeypatch.setenv("SENSE_AND_STARS_" + key, value)
    assert api.get("/api/auth/recovery").json() == {"available": False}


def test_hosted_mail_uses_only_canonical_origin(mail, monkeypatch):
    monkeypatch.setenv("SENSE_AND_STARS_HOSTED", "1")
    monkeypatch.setenv("SENSE_AND_STARS_PUBLIC_ORIGIN", "https://app.example.org")
    assert recovery_mail.mail_settings().origin == "https://app.example.org"
    monkeypatch.setenv("SENSE_AND_STARS_PUBLIC_ORIGIN", "http://app.example.org")
    assert recovery_mail.mail_settings() is None


@pytest.mark.parametrize("security", ["ssl", "starttls"])
def test_smtp_transport_requires_verified_tls_before_credentials(mail, monkeypatch, security):
    calls = []
    class FakeSMTP:
        def __init__(self, host, port, **kwargs):
            calls.append(("connect", kwargs))
        def __enter__(self): return self
        def __exit__(self, *args): calls.append(("close", None))
        def ehlo(self): calls.append(("ehlo", None))
        def starttls(self, **kwargs): calls.append(("tls", kwargs))
        def login(self, *args): calls.append(("login", None))
        def send_message(self, message): calls.append(("send", message))
    monkeypatch.setattr(recovery_mail.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(recovery_mail.smtplib, "SMTP", FakeSMTP)
    settings = replace(recovery_mail.mail_settings(), security=security)
    recovery_mail._send_message(settings, "synthetic@example.org", "TEST", "Synthetic only")
    context = next(value["context"] for _, value in calls if isinstance(value, dict) and "context" in value)
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    names = [name for name, _ in calls]
    if security == "starttls":
        assert names.index("tls") < names.index("login") < names.index("send")
    message = next(value for name, value in calls if name == "send")
    assert message["To"] == "synthetic@example.org" and "noreply@example.org" in message["From"]
