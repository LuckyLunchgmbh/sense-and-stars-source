"""SQLite connections are short lived; request writes use explicit transactions."""
import os
import sqlite3
from pathlib import Path

from .config import compatible_database_path, setting


ROOT = Path(__file__).resolve().parents[2]


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def db_path() -> Path:
    explicit = setting("DB")
    return Path(explicit or compatible_database_path(ROOT / "data")).resolve()


def get_db(*, cache=False) -> sqlite3.Connection:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if not database_url.startswith(("postgres://", "postgresql://")):
            raise RuntimeError("DATABASE_URL benötigt eine PostgreSQL-Verbindung.")
        from .postgres import Connection
        return Connection(database_url, write_lock=831746206) if cache else Connection(database_url)
    if setting("HOSTED") == "1":
        raise RuntimeError("SENSE_AND_STARS_HOSTED benötigt eine dauerhafte DATABASE_URL.")
    path = db_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, factory=ClosingConnection)
    path.chmod(0o600)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_schema(conn):
    conn.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS clients(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
      birth_date TEXT, birth_time TEXT, birth_place TEXT, themes TEXT NOT NULL DEFAULT '[]',
      chart TEXT, chart_shared INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
      password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','practitioner','client')),
      client_id INTEGER UNIQUE REFERENCES clients(id), tour_completed INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(
      token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS login_attempts(
      key TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, first_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS appointments(
      id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id), start_at TEXT NOT NULL,
      duration_minutes INTEGER NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'scheduled',
      prepared INTEGER NOT NULL DEFAULT 0, price_cents INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS appointment_start ON appointments(start_at);
    CREATE TABLE IF NOT EXISTS resources(
      id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id), kind TEXT NOT NULL,
      title TEXT NOT NULL, body TEXT NOT NULL, shared INTEGER NOT NULL DEFAULT 0,
      audio_url TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(
      id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT NOT NULL,
      resource_id INTEGER, created_at TEXT NOT NULL);
    """)
    # Additive migration: existing appointments retain their agreed price.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "hourly_rate_cents" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN hourly_rate_cents INTEGER CHECK(hourly_rate_cents >= 0 AND hourly_rate_cents <= 1000000)")
    login_columns = {row["name"] for row in conn.execute("PRAGMA table_info(login_attempts)")}
    if "account_key" not in login_columns:
        conn.execute("ALTER TABLE login_attempts ADD COLUMN account_key TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS login_attempts_account ON login_attempts(account_key)")
    conn.execute("""CREATE TABLE IF NOT EXISTS password_reset_tokens(
      token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      credential_fingerprint TEXT NOT NULL, expires_at REAL NOT NULL, created_at REAL NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS password_reset_user ON password_reset_tokens(user_id)")
    conn.execute("""CREATE TABLE IF NOT EXISTS password_reset_limits(
      key TEXT PRIMARY KEY, count INTEGER NOT NULL, first_at REAL NOT NULL, last_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mail_send_budget(
      period TEXT PRIMARY KEY, attempts INTEGER NOT NULL CHECK(attempts >= 0))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS personal_dedications(
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
      title TEXT NOT NULL, salutation TEXT NOT NULL, paragraphs_json TEXT NOT NULL,
      closing TEXT NOT NULL, sender TEXT NOT NULL,
      content_version INTEGER NOT NULL DEFAULT 1 CHECK(content_version >= 1), created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS personal_dedication_views(
      dedication_id INTEGER NOT NULL REFERENCES personal_dedications(id) ON DELETE CASCADE,
      session_token_hash TEXT NOT NULL REFERENCES sessions(token_hash) ON DELETE CASCADE,
      content_version INTEGER NOT NULL CHECK(content_version >= 1), dismissed_at TEXT NOT NULL,
      PRIMARY KEY(dedication_id,session_token_hash,content_version))""")
