from pathlib import Path


def test_primary_brand_setting_wins_and_legacy_remains_a_fallback(monkeypatch):
    from app.config import setting

    monkeypatch.setenv("SOULFLOW_DEMO", "legacy")
    monkeypatch.setenv("SENSE_AND_STARS_DEMO", "primary")
    assert setting("DEMO") == "primary"

    monkeypatch.delenv("SENSE_AND_STARS_DEMO")
    assert setting("DEMO") == "legacy"


def test_default_database_path_prefers_existing_legacy_file(monkeypatch, tmp_path):
    from app import db

    monkeypatch.delenv("SENSE_AND_STARS_DB", raising=False)
    monkeypatch.delenv("SOULFLOW_DB", raising=False)
    monkeypatch.setattr(db, "ROOT", tmp_path)
    legacy = tmp_path / "data" / "soulflow.sqlite3"
    legacy.parent.mkdir()
    legacy.touch()

    assert db.db_path() == legacy.resolve()

    legacy.unlink()
    assert db.db_path() == (tmp_path / "data" / "sense-and-stars.sqlite3").resolve()


def test_explicit_primary_database_path_wins_over_legacy(monkeypatch, tmp_path):
    from app.db import db_path

    primary = tmp_path / "primary.sqlite3"
    legacy = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(primary))
    monkeypatch.setenv("SOULFLOW_DB", str(legacy))

    assert db_path() == primary.resolve()
