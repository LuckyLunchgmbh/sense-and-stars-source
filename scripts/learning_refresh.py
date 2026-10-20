#!/usr/bin/env python3
"""Explicit scheduled draft discovery; never publishes or sends client data."""
import argparse
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import compatible_database_path, set_setting


@contextmanager
def status_connection():
    """Observe the installed database without creating files or running migrations."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if not database_url.startswith(("postgres://", "postgresql://")):
            raise sqlite3.OperationalError("Ungültige Datenbankkonfiguration.")
        import psycopg
        from psycopg.rows import dict_row
        try:
            with psycopg.connect(database_url, connect_timeout=10, prepare_threshold=None,
                                  row_factory=dict_row) as conn:
                # Set before the first statement: the server rejects accidental writes.
                conn.read_only = True
                yield conn
        except psycopg.Error:
            raise sqlite3.OperationalError("Quellenstatus nicht lesbar.") from None
    else:
        from app.db import db_path
        # get_db() would create missing directories/files and chmod an existing file.
        with closing(sqlite3.connect(db_path().as_uri() + "?mode=ro", uri=True,
                                     timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            yield conn


def main():
    parser = argparse.ArgumentParser(description="Sense & Stars Quellenentwürfe aktualisieren")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--demo", action="store_true", help="Nur synthetische lokale Demodatenbank")
    target.add_argument("--hosted", action="store_true", help="Explizit konfigurierte persistente Hosting-Datenbank")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.demo:
        if os.environ.get("DATABASE_URL"):
            parser.error("Demo darf keine DATABASE_URL übernehmen.")
        set_setting("HOSTED", "0")
        set_setting("DEMO", "1")
        set_setting("DB", str(compatible_database_path(ROOT / "data/demo")))
    elif not os.environ.get("DATABASE_URL"):
        parser.error("Hosted benötigt eine sicher gesetzte DATABASE_URL; kein lokaler Fallback.")
    else:
        set_setting("HOSTED", "1")
        set_setting("DEMO", "0")
    from app.learning_updates import configure_updates, run_updates, updates_status
    if args.status:
        try:
            status = updates_status(connection_factory=status_connection)
        except (sqlite3.Error, OSError, RuntimeError):
            print(json.dumps({"target": "demo" if args.demo else "hosted", "result": None,
                              "status": None, "error": "Quellenstatus nicht verfügbar: Die Datenbank oder Aktualisierungstabellen fehlen oder sind nicht lesbar."},
                             ensure_ascii=False, indent=2))
            return 1
        result = None
    else:
        from app.main import initialize
        from app.db import get_db
        initialize()
        with get_db() as conn:
            configure_updates(conn, enabled=True)
        result = run_updates(trigger="cron")
        status = updates_status()
    print(json.dumps({"target":"demo" if args.demo else "hosted", "result":result, "status":status}, ensure_ascii=False, indent=2))
    return 1 if result and result["status"] in ("failed", "stale") else 0


if __name__ == "__main__":
    raise SystemExit(main())
