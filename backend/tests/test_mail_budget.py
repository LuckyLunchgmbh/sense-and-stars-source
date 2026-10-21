"""Shared attempt caps: synthetic mail only, intercepting the transport boundary."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
import subprocess
from threading import BoundedSemaphore
from types import SimpleNamespace

import pytest

from app import mailbudget, recovery_mail
from app.db import get_db, init_schema
from test_cloud_database import pg_api  # isolated PostgreSQL schema when configured


SETTINGS = recovery_mail.MailSettings("smtp.example.org", 587, "starttls", "synthetic-user",
                                     "synthetic-secret", "sender@example.org", "https://app.example.org")


@pytest.fixture
def transport(monkeypatch):
    clock = SimpleNamespace(now=datetime(2026, 10, 20, 12, tzinfo=timezone.utc))
    monkeypatch.setattr(mailbudget, "utc_now", lambda: clock.now)
    calls = []
    monkeypatch.setattr(recovery_mail.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    return SimpleNamespace(clock=clock, calls=calls)


@pytest.fixture
def budget(tmp_path, monkeypatch, transport):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENSE_AND_STARS_HOSTED", "0")
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(tmp_path / "mail-budget.sqlite3"))
    with get_db() as conn:
        init_schema(conn)
    return transport


def counts():
    with get_db() as conn:
        return {row["period"]: row["attempts"] for row in conn.execute("SELECT * FROM mail_send_budget")}


def set_count(period, attempts):
    with get_db() as conn:
        conn.execute("INSERT INTO mail_send_budget VALUES(?,?) ON CONFLICT(period) DO UPDATE SET attempts=excluded.attempts", (period, attempts))


def send_test():
    recovery_mail.send_message(SETTINGS, "recipient@example.org", "Synthetic test", "No real mail")


def test_daily_cap_shared_by_reset_notice_and_test_mail(budget):
    for _ in range(38):
        recovery_mail.send_reset(SETTINGS, "recipient@example.org", "synthetic-token")
    recovery_mail.send_changed(SETTINGS, "recipient@example.org")
    send_test()
    assert len(budget.calls) == 40
    assert counts() == {"day:2026-10-20": 40, "month:2026-10": 40}
    for send in (send_test, lambda: recovery_mail.send_reset(SETTINGS, "recipient@example.org", "another-token"),
                 lambda: recovery_mail.send_changed(SETTINGS, "recipient@example.org")):
        with pytest.raises(mailbudget.MailBudgetExceeded):
            send()
    assert len(budget.calls) == 40
    assert counts() == {"day:2026-10-20": 40, "month:2026-10": 40}


def test_monthly_cap_does_not_partially_charge_daily_budget(budget):
    set_count("month:2026-10", 999)
    send_test()
    assert counts() == {"month:2026-10": 1000, "day:2026-10-20": 1}
    with pytest.raises(mailbudget.MailBudgetExceeded):
        send_test()
    assert len(budget.calls) == 1
    assert counts() == {"month:2026-10": 1000, "day:2026-10-20": 1}


def test_day_rollover_is_utc_and_does_not_reset_monthly_counter(budget):
    budget.clock.now = datetime(2026, 10, 21, 1, 59, 59, tzinfo=timezone(timedelta(hours=2)))
    set_count("day:2026-10-20", 39)
    set_count("month:2026-10", 39)
    send_test()
    budget.clock.now += timedelta(seconds=1)
    send_test()
    assert counts() == {"day:2026-10-20": 40, "day:2026-10-21": 1, "month:2026-10": 41}


def test_calendar_month_rollover_keeps_previous_usage(budget):
    set_count("month:2026-10", 1000)
    budget.clock.now = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    with pytest.raises(mailbudget.MailBudgetExceeded):
        send_test()
    budget.clock.now += timedelta(seconds=1)
    send_test()
    assert counts() == {"month:2026-10": 1000, "month:2026-11": 1, "day:2026-11-01": 1}


def _reserve_concurrently(total=70):
    def attempt(_):
        try:
            mailbudget.reserve_mail_attempt()
            return True
        except mailbudget.MailBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(attempt, range(total)))
    assert sum(results) == 40
    assert counts() == {"day:2026-10-20": 40, "month:2026-10": 40}


def test_concurrent_connections_cannot_overspend_daily_cap(budget):
    _reserve_concurrently()


def test_postgres_workers_share_atomic_mail_budget(pg_api, transport):
    _reserve_concurrently()


def test_budget_survives_schema_reinitialization_and_reconnect(budget):
    send_test()
    with get_db() as conn:
        init_schema(conn)
    send_test()
    assert counts() == {"day:2026-10-20": 2, "month:2026-10": 2}


@pytest.mark.parametrize("error", [subprocess.CalledProcessError(1, ["synthetic"]),
    subprocess.TimeoutExpired(["synthetic"], 6), OSError("synthetic process failure")])
def test_smtp_error_timeout_and_launch_failure_never_refund(budget, monkeypatch, error):
    def failure(*args, **kwargs):
        raise error
    monkeypatch.setattr(recovery_mail.subprocess, "run", failure)
    with pytest.raises(type(error)):
        send_test()
    assert counts() == {"day:2026-10-20": 1, "month:2026-10": 1}


def test_database_unavailable_prevents_any_smtp_process(budget, monkeypatch):
    def unavailable():
        raise sqlite3.OperationalError("synthetic outage")
    monkeypatch.setattr(mailbudget, "get_db", unavailable)
    with pytest.raises(sqlite3.OperationalError):
        send_test()
    assert budget.calls == []
    assert counts() == {}


def test_uncertain_database_commit_prevents_smtp_and_keeps_reservation(budget, monkeypatch):
    real_get_db = mailbudget.get_db
    class CommitFailure:
        def __enter__(self):
            self.conn = real_get_db()
            return self.conn.__enter__()
        def __exit__(self, exc_type, exc, traceback):
            result = self.conn.__exit__(exc_type, exc, traceback)
            if exc_type is None:
                # Simulate an acknowledgement lost after the server committed.
                raise sqlite3.OperationalError("synthetic uncertain commit")
            return result
    monkeypatch.setattr(mailbudget, "get_db", CommitFailure)
    with pytest.raises(sqlite3.OperationalError):
        send_test()
    assert budget.calls == []
    assert counts() == {"day:2026-10-20": 1, "month:2026-10": 1}


def test_missing_budget_table_prevents_any_smtp_process(budget):
    with get_db() as conn:
        conn.execute("DROP TABLE mail_send_budget")
    with pytest.raises(sqlite3.OperationalError):
        send_test()
    assert budget.calls == []


def test_busy_local_transport_does_not_reserve_budget(budget, monkeypatch):
    semaphore = BoundedSemaphore(1)
    assert semaphore.acquire(blocking=False)
    monkeypatch.setattr(recovery_mail, "_SEND_SLOTS", semaphore)
    with pytest.raises(RuntimeError, match="transport busy"):
        send_test()
    assert counts() == {} and budget.calls == []
    semaphore.release()
    send_test()
    assert counts() == {"day:2026-10-20": 1, "month:2026-10": 1}


@pytest.mark.parametrize("recipient", ["a@example.org,b@example.org", "a@example.org\r\nBcc: b@example.org"])
def test_one_reserved_slot_cannot_expand_to_multiple_recipients(budget, recipient):
    with pytest.raises(ValueError):
        recovery_mail.send_message(SETTINGS, recipient, "Synthetic test", "No real mail")
    assert counts() == {} and budget.calls == []
