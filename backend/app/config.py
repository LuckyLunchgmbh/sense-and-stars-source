"""Sense & Stars configuration with bounded SoulFlow compatibility aliases."""
import os
from pathlib import Path


PRIMARY_PREFIX = "SENSE_AND_STARS_"
LEGACY_PREFIX = "SOULFLOW_"


def setting(suffix: str, default=None, *, environ=None):
    values = os.environ if environ is None else environ
    return values.get(PRIMARY_PREFIX + suffix, values.get(LEGACY_PREFIX + suffix, default))


def set_setting(suffix: str, value: str, *, environ=None) -> None:
    values = os.environ if environ is None else environ
    values[PRIMARY_PREFIX + suffix] = value


def compatible_database_path(directory: Path) -> Path:
    """Use the new default unless an existing legacy database holds user data."""
    primary = directory / "sense-and-stars.sqlite3"
    legacy = directory / "soulflow.sqlite3"
    return legacy if legacy.exists() and not primary.exists() else primary
