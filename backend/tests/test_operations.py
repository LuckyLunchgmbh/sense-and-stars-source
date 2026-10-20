"""Subprocess proof of backup and non-overwriting restore, using test records."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def test_backup_and_restore_revoke_sessions_without_overwriting(tmp_path):
    source=tmp_path/"source.sqlite3"
    with sqlite3.connect(source) as conn:
        conn.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT); INSERT INTO meta VALUES('mode','demo'); CREATE TABLE sessions(token TEXT); INSERT INTO sessions VALUES('TEST'); CREATE TABLE records(id INTEGER); INSERT INTO records VALUES(42);")
    env={**os.environ,"SOULFLOW_DB":str(source)}
    backup=subprocess.run([sys.executable,str(ROOT/"scripts/backup.py"),"--demo"],env=env,capture_output=True,text=True)
    assert backup.returncode==0,backup.stderr
    saved=next((tmp_path/"backups").glob("*.sqlite3"))
    target=tmp_path/"restored.sqlite3"
    command=[sys.executable,str(ROOT/"scripts/restore.py"),str(saved),str(target)]
    restored=subprocess.run(command,capture_output=True,text=True)
    assert restored.returncode==0,restored.stderr
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT id FROM records").fetchone()[0]==42
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]==0
        assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    before=target.read_bytes()
    assert subprocess.run(command,capture_output=True).returncode!=0
    assert target.read_bytes()==before
