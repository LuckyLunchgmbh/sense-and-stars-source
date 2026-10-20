"""Small DB-API bridge for Sense & Stars' explicitly tested SQL vocabulary.

PostgreSQL is the durable hosted store; SQLite remains the local store. This
module does not pretend to translate arbitrary SQLite. Parameters stay bound,
the app's immediate write transactions use one transaction-scoped advisory lock,
and original SQL errors are converted without disclosing connection strings.
"""
import re
import sqlite3

import psycopg

_SERIAL_TABLES = {
    "clients", "users", "appointments", "resources", "audit",
    "learning_lessons", "learning_scans", "learning_audit", "learning_notebook",
    "learning_update_runs", "learning_source_findings",
}
_WRITE_LOCK = 831746205


def translate_sql(sql: str) -> str:
    if re.match(r"\s*(CREATE|ALTER)\b", sql, flags=re.I):
        sql = re.sub(r"\bINTEGER PRIMARY KEY\b", "BIGSERIAL PRIMARY KEY", sql, flags=re.I)
        sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.I)
        sql = re.sub(r"TEXT(\s+NOT NULL)?\s+COLLATE NOCASE", lambda m: "CITEXT" + (m[1] or ""), sql, flags=re.I)
    # SQLite scalar MAX is PostgreSQL GREATEST. Qualify the existing value in
    # ON CONFLICT so PostgreSQL cannot confuse it with the excluded row.
    sql = re.sub(r"MAX\((quiz_score|quiz_passed),excluded\.\1\)", lambda m: f"GREATEST(learning_progress.{m[1]},excluded.{m[1]})", sql)
    ignore = bool(re.search(r"\bINSERT OR IGNORE\b", sql, flags=re.I))
    sql = re.sub(r"\bINSERT OR IGNORE\b", "INSERT", sql, flags=re.I).rstrip().rstrip(";")
    if ignore:
        sql += " ON CONFLICT DO NOTHING"
    # Only placeholders outside SQL literals/quoted identifiers are converted.
    output, quote, i = [], None, 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            output.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    output.append(sql[i + 1]); i += 1
                else:
                    quote = None
        elif ch in ("'", '"'):
            quote = ch; output.append(ch)
        else:
            output.append("%s" if ch == "?" else ch)
        i += 1
    return "".join(output)


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, (int, slice)) else super().__getitem__(key)


class Result:
    def __init__(self, cursor, *, lastrowid=None):
        names = [col.name for col in cursor.description] if cursor.description else []
        self._rows = [Row(zip(names, values)) for values in cursor.fetchall()] if names else []
        self.rowcount = cursor.rowcount
        self.lastrowid = lastrowid
        self._position = 0
        cursor.close()

    def fetchone(self):
        if self._position >= len(self._rows):
            return None
        row = self._rows[self._position]; self._position += 1
        return row

    def fetchall(self):
        rows = self._rows[self._position:]; self._position = len(self._rows)
        return rows

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row


class Connection:
    def __init__(self, url, *, write_lock=_WRITE_LOCK):
        self._write_lock = write_lock
        self._transaction_configured = False
        try:
            self._conn = psycopg.connect(url, connect_timeout=10, prepare_threshold=None)
        except psycopg.Error as exc:
            raise sqlite3.OperationalError("Dauerhafte Datenbank nicht erreichbar.") from exc

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.rollback() if exc_type else self.commit()
        finally:
            self.close()

    def execute(self, sql, params=()):
        sql = sql.strip()
        table_info = re.fullmatch(r"PRAGMA table_info\(([A-Za-z_][A-Za-z_0-9]*)\)", sql, re.I)
        if table_info:
            return self.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position", (table_info[1],))
        if sql.upper() == "BEGIN IMMEDIATE":
            sql, params = "SELECT pg_advisory_xact_lock(?)", (self._write_lock,)
        elif sql.upper().startswith("PRAGMA "):
            return self.execute("SELECT 1 WHERE false")
        translated = translate_sql(sql)
        insert = re.match(r"INSERT\s+INTO\s+([a-z_]+)\s*\(", translated, re.I)
        return_id = bool(insert and insert[1] in _SERIAL_TABLES and "RETURNING" not in translated.upper())
        if return_id:
            translated += " RETURNING id"
        try:
            if not self._transaction_configured:
                self._conn.execute("SET LOCAL statement_timeout = '15000ms'")
                self._conn.execute("SET LOCAL lock_timeout = '10000ms'")
                self._transaction_configured = True
            cursor = self._conn.execute(translated, tuple(params) if params else None)
            result = Result(cursor)
            if return_id and result._rows:
                result.lastrowid = result._rows[0]["id"]
            return result
        except psycopg.IntegrityError as exc:
            raise sqlite3.IntegrityError("Datenbankbedingung verletzt.") from exc
        except psycopg.Error as exc:
            raise sqlite3.OperationalError("Datenbankanfrage fehlgeschlagen.") from exc

    def executescript(self, script):
        # Schema creation must serialize across parallel cold starts.
        self.execute("BEGIN IMMEDIATE")
        self.execute("CREATE EXTENSION IF NOT EXISTS citext")
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)
        old_clock = self.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='login_attempts' AND column_name='first_at' AND data_type='real'").fetchone()
        if old_clock:
            self.execute("ALTER TABLE login_attempts ALTER COLUMN first_at TYPE DOUBLE PRECISION")

    def commit(self):
        try:
            self._conn.commit()
        except psycopg.Error as exc:
            raise sqlite3.OperationalError("Datenbanktransaktion konnte nicht bestätigt werden.") from exc
        finally:
            self._transaction_configured = False

    def rollback(self):
        try:
            self._conn.rollback()
        except psycopg.Error as exc:
            raise sqlite3.OperationalError("Datenbankverbindung wurde unterbrochen.") from exc
        finally:
            self._transaction_configured = False

    def close(self):
        self._conn.close()
