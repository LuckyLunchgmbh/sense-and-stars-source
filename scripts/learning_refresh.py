#!/usr/bin/env python3
"""Explicit scheduled draft discovery; never publishes or sends client data."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser(description="SoulFlow Quellenentwürfe aktualisieren")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--demo", action="store_true", help="Nur synthetische lokale Demodatenbank")
    target.add_argument("--hosted", action="store_true", help="Explizit konfigurierte persistente Hosting-Datenbank")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.demo:
        if os.environ.get("DATABASE_URL"):
            parser.error("Demo darf keine DATABASE_URL übernehmen.")
        os.environ["SOULFLOW_HOSTED"] = "0"
        os.environ["SOULFLOW_DEMO"] = "1"
        os.environ["SOULFLOW_DB"] = str(ROOT / "data/demo/soulflow.sqlite3")
    elif not os.environ.get("DATABASE_URL"):
        parser.error("Hosted benötigt eine sicher gesetzte DATABASE_URL; kein lokaler Fallback.")
    else:
        os.environ["SOULFLOW_HOSTED"] = "1"
        os.environ["SOULFLOW_DEMO"] = "0"
    from app.main import initialize
    from app.db import get_db
    from app.learning_updates import configure_updates, run_updates, updates_status
    initialize()
    if not args.status:
        with get_db() as conn:
            configure_updates(conn, enabled=True)
        result = run_updates(trigger="cron")
    else:
        result = None
    status = updates_status()
    print(json.dumps({"target":"demo" if args.demo else "hosted", "result":result, "status":status}, ensure_ascii=False, indent=2))
    return 1 if result and result["status"] in ("failed", "stale") else 0


if __name__ == "__main__":
    raise SystemExit(main())
