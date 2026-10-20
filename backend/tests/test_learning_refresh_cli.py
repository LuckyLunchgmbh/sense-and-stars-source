"""Status is observation only, even when deployed schema predates local code."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys

import pytest

from app.learning_updates import init_learning_updates


@pytest.fixture
def cli(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(("SENSE_AND_STARS_", "SOULFLOW_")) or name == "DATABASE_URL":
            monkeypatch.delenv(name)
    # main() intentionally sets these; register restoration even when absent initially.
    for suffix in ("DB", "DEMO", "HOSTED"):
        monkeypatch.setenv("SENSE_AND_STARS_" + suffix, "")
        monkeypatch.delenv("SENSE_AND_STARS_" + suffix)
    script = Path(__file__).resolve().parents[2] / "scripts/learning_refresh.py"
    spec = importlib.util.spec_from_file_location("learning_refresh_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", [str(script), "--demo", "--status"])
    return module


def create_status_database(root):
    path = root / "data/demo/sense-and-stars.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as conn:
        init_learning_updates(conn)
        conn.execute("UPDATE learning_update_state SET enabled=1,next_due_at='2099-01-01T00:00:00+00:00',last_success_at='2026-10-20T12:00:00+00:00' WHERE id=1")
    path.chmod(0o640)
    return path


def test_status_does_not_initialize_schema_import_academy_or_change_permissions(cli, capsys):
    path = create_status_database(cli.ROOT)
    before, mode = path.read_bytes(), path.stat().st_mode
    assert cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["target"] == "demo" and output["result"] is None
    assert output["status"]["next_due_at"] == "2099-01-01T00:00:00+00:00"
    assert output["status"]["enabled"] is True
    assert output["status"]["review_required"] is True
    assert output["status"]["publication_automatic"] is False
    assert path.read_bytes() == before
    assert path.stat().st_mode == mode
    assert list(path.parent.iterdir()) == [path]


def test_status_missing_database_does_not_create_files_and_hides_path(cli, capsys):
    assert cli.main() == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] is None and payload["error"]
    assert str(cli.ROOT) not in captured.out + captured.err
    assert captured.err == ""
    assert not (cli.ROOT / "data").exists()


@pytest.mark.parametrize("missing", ["tables", "state_row"])
def test_status_incomplete_database_stays_unchanged_and_hides_details(cli, capsys, missing):
    path = create_status_database(cli.ROOT)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE learning_source_findings" if missing == "tables" else "DELETE FROM learning_update_state")
    before = path.read_bytes()
    assert cli.main() == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] is None and payload["error"]
    assert str(cli.ROOT) not in captured.out + captured.err
    assert captured.err == ""
    assert path.read_bytes() == before


def test_status_rejects_writes_at_sqlite_connection_boundary(cli, monkeypatch):
    path = create_status_database(cli.ROOT)
    before = path.read_bytes()
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(path))
    with cli.status_connection() as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("UPDATE learning_update_state SET enabled=0")
    assert path.read_bytes() == before


def test_status_does_not_import_application_startup(cli, monkeypatch, capsys):
    create_status_database(cli.ROOT)
    monkeypatch.setitem(sys.modules, "app.main", None)
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out)["status"]["interval_days"] == 14


def test_hosted_status_reads_existing_schema_in_server_read_only_transaction(cli, monkeypatch, capsys):
    import psycopg
    from psycopg.rows import dict_row

    path = create_status_database(cli.ROOT)
    before = path.read_bytes()
    synthetic_url = "postgresql://synthetic.invalid/status-test"

    class PostgreSQLBoundary:
        """Replace external transport only; execute the actual status SQL on SQLite."""
        def __init__(self):
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row
            self.read_only = False

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.conn.rollback()
            self.conn.close()

        def execute(self, query):
            assert self.read_only, "Hosted status issued a query before enabling read-only mode"
            self.conn.execute("PRAGMA query_only = ON")
            return self.conn.execute(query)

    def connect(url, *, connect_timeout, prepare_threshold, row_factory):
        assert url == synthetic_url
        assert connect_timeout == 10 and prepare_threshold is None and row_factory is dict_row
        return PostgreSQLBoundary()

    monkeypatch.setenv("DATABASE_URL", synthetic_url)
    monkeypatch.setattr(psycopg, "connect", connect)
    monkeypatch.setitem(sys.modules, "app.main", None)
    monkeypatch.setattr(sys, "argv", ["learning_refresh.py", "--hosted", "--status"])
    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["target"] == "hosted" and payload["result"] is None
    assert payload["status"]["last_success_at"] == "2026-10-20T12:00:00+00:00"
    assert payload["status"]["next_due_at"] == "2099-01-01T00:00:00+00:00"
    assert path.read_bytes() == before


def test_hosted_status_connection_error_never_exposes_url_or_server_message(cli, monkeypatch, capsys):
    import psycopg

    private_detail = "postgresql://user:private-password@synthetic.invalid/private-database"
    monkeypatch.setenv("DATABASE_URL", private_detail)
    def unavailable(*_args, **_kwargs):
        raise psycopg.OperationalError("cannot connect " + private_detail)
    monkeypatch.setattr(psycopg, "connect", unavailable)
    monkeypatch.setattr(sys, "argv", ["learning_refresh.py", "--hosted", "--status"])
    assert cli.main() == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] is None
    assert "private-password" not in captured.out + captured.err
    assert "synthetic.invalid" not in captured.out + captured.err
    assert captured.err == ""


def test_normal_refresh_keeps_initialization_and_respects_existing_due_gate(cli, monkeypatch, capsys):
    from app import learning_updates

    path = create_status_database(cli.ROOT)
    def no_fetch(_url):
        raise AssertionError("A non-due refresh must not fetch sources")
    monkeypatch.setattr(learning_updates, "fetch_public_html", no_fetch)
    monkeypatch.setattr(sys, "argv", ["learning_refresh.py", "--demo"])
    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"]["status"] == "not_due"
    assert payload["result"]["created"] == 0
    assert payload["status"]["next_due_at"] == "2099-01-01T00:00:00+00:00"
    assert payload["status"]["recent_runs"] == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM academy_lessons").fetchone()[0] == 120
