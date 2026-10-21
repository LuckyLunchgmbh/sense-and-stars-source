"""Shared, conservative send-attempt limits for the approved free mail service.

Every SMTP attempt consumes a daily and a monthly slot before it starts. Slots
are never refunded: the provider may have accepted a message before a timeout or
disconnect. Missing/broken storage prevents sending rather than bypassing caps.
"""
from datetime import datetime, timezone

from .db import get_db


DAILY_LIMIT = 40
MONTHLY_LIMIT = 1000


class MailBudgetExceeded(RuntimeError):
    """The fixed shared free-service allowance has been exhausted."""


def utc_now():
    return datetime.now(timezone.utc)


def reserve_mail_attempt():
    """Commit both budget counters atomically before any SMTP process starts."""
    with get_db() as conn:
        # SQLite write lock / PostgreSQL transaction advisory lock: all workers
        # sharing the configured application database reserve serially.
        conn.execute("BEGIN IMMEDIATE")
        now = utc_now().astimezone(timezone.utc)
        periods = (("day:" + now.strftime("%Y-%m-%d"), DAILY_LIMIT),
                   ("month:" + now.strftime("%Y-%m"), MONTHLY_LIMIT))
        for period, limit in periods:
            row = conn.execute("SELECT attempts FROM mail_send_budget WHERE period=?", (period,)).fetchone()
            if row and row["attempts"] >= limit:
                raise MailBudgetExceeded("Mail send allowance exhausted")
        for period, _ in periods:
            conn.execute("""INSERT INTO mail_send_budget(period,attempts) VALUES(?,1)
                         ON CONFLICT(period) DO UPDATE SET attempts=mail_send_budget.attempts+1""", (period,))
