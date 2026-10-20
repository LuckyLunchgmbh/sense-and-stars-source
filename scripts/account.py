#!/usr/bin/env python3
"""Local administrative entry. Passwords are entered privately, never via arguments."""
import argparse
import getpass
import os
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"backend"))
from app.config import compatible_database_path, set_setting, setting
set_setting("DEMO", "0")
if not setting("DB"):
    set_setting("DB", str(compatible_database_path(root / "data/local")))
from app.main import initialize
from app.db import get_db
from app.security import hash_password,now_iso
from email_validator import validate_email,EmailNotValidError

parser=argparse.ArgumentParser(description="Lokales Betreiber-/Beraterkonto anlegen oder Passwort ändern")
parser.add_argument("action",choices=["create","reset-password"])
parser.add_argument("--role",choices=["admin","practitioner"],default="admin")
args=parser.parse_args()
initialize()
try:
    email=validate_email(input("E-Mail: ").strip(),check_deliverability=False).normalized
except EmailNotValidError as exc:
    sys.exit(str(exc))
name=input("Anzeigename: ").strip() if args.action=="create" else None
if args.action=="create" and (not name or len(name)>150): sys.exit("Anzeigename benötigt 1 bis 150 Zeichen.")
password=getpass.getpass("Passwort (mindestens 12 Zeichen): ")
if len(password)<12 or len(password)>256: sys.exit("Passwort benötigt 12 bis 256 Zeichen.")
if password!=getpass.getpass("Passwort wiederholen: "): sys.exit("Die Passwörter stimmen nicht überein.")
with get_db() as conn:
    existing=conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
    if args.action=="create":
        if existing: sys.exit("Konto existiert bereits; es wurde nichts überschrieben.")
        conn.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",(name,email,hash_password(password),args.role,now_iso()))
    else:
        if not existing: sys.exit("Konto nicht gefunden.")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(password),existing["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?",(existing["id"],))
print("Konto lokal angelegt." if args.action=="create" else "Passwort geändert; vorhandene Sitzungen widerrufen.")
