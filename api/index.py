"""Vercel ASGI entrypoint; configuration fails closed before public startup."""
import os

from backend.app.config import setting

os.environ.setdefault("SENSE_AND_STARS_HOSTED", setting("HOSTED", "1"))
from backend.app.main import app
