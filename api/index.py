"""Vercel ASGI entrypoint; configuration fails closed before public startup."""
import os

os.environ.setdefault("SOULFLOW_HOSTED", "1")
from backend.app.main import app
