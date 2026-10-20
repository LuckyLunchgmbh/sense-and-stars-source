#!/usr/bin/env python3
"""Restore into a NEW path only. Never overwrites or touches a running database."""
import argparse
from pathlib import Path
import sqlite3
import sys

parser=argparse.ArgumentParser(description="Sicherung in eine neue Datenbank wiederherstellen")
parser.add_argument("backup",type=Path)
parser.add_argument("destination",type=Path)
args=parser.parse_args()
source=args.backup.resolve()
target=args.destination.resolve()
if not source.is_file(): sys.exit("Sicherungsdatei nicht gefunden.")
if target.exists(): sys.exit("Ziel existiert bereits; nichts wurde überschrieben.")
target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
with sqlite3.connect(source.as_uri()+"?mode=ro",uri=True) as original:
    if original.execute("PRAGMA integrity_check").fetchone()[0]!="ok": sys.exit("Sicherung ist beschädigt.")
    try:
        mode=original.execute("SELECT value FROM meta WHERE key='mode'").fetchone()[0]
    except (sqlite3.DatabaseError,TypeError): sys.exit("Keine SoulFlow-Sicherung.")
    if mode not in ("local","demo"): sys.exit("Unbekannter Datenbankmodus.")
    # Exclusive filesystem creation also closes a time-of-check/time-of-use gap.
    with target.open("xb"):
        pass
    target.chmod(0o600)
    with sqlite3.connect(target) as restored:
        original.backup(restored)
        restored.execute("DELETE FROM sessions")
        if restored.execute("PRAGMA integrity_check").fetchone()[0]!="ok": sys.exit("Wiederherstellung nicht gültig.")
print("Neue Datenbank geprüft, alte Sitzungen widerrufen: "+str(target))
print("Modus: "+mode+". Start über SOULFLOW_DB mit diesem Pfad; vorhandenen Server vorher stoppen.")
