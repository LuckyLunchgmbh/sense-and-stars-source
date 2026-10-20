#!/usr/bin/env python3
"""Consistent SQLite backup. Contains sensitive data; no cloud transfer occurs."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.config import compatible_database_path, setting

parser=argparse.ArgumentParser(description="Konsistente lokale Sicherung")
parser.add_argument("--demo",action="store_true")
args=parser.parse_args()
source=Path(setting("DB") or compatible_database_path(root / "data" / ("demo" if args.demo else "local"))).resolve()
if not source.exists(): sys.exit("Datenbank nicht vorhanden.")
folder=source.parent/"backups"
folder.mkdir(mode=0o700,parents=True,exist_ok=True)
target=folder/("sense-and-stars-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".sqlite3")
with sqlite3.connect(source.as_uri()+"?mode=ro",uri=True) as original, sqlite3.connect(target) as backup:
    original.backup(backup)
    if backup.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
        sys.exit("Sicherung hat Integritätsprüfung nicht bestanden: "+str(target))
target.chmod(0o600)
print("Sicherung mit Integritätsprüfung erstellt: "+str(target))
