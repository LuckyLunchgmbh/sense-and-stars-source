#!/usr/bin/env python3
"""Install only into this project's .venv and frontend/node_modules."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
if sys.version_info < (3,11):
    bundled=Path.home()/".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
    if bundled.exists():
        os.execv(str(bundled),[str(bundled),str(Path(__file__).resolve())])
    sys.exit("SoulFlow benötigt Python 3.11 oder neuer. Keine globale Installation wurde vorgenommen.")
if not shutil.which("npm"):
    sys.exit("Node.js mit npm wird benötigt. Keine globale Installation wurde vorgenommen.")
venv=root/".venv"
if not (venv/"bin/python").exists():
    subprocess.run([sys.executable,"-m","venv",str(venv)],check=True)
subprocess.run([str(venv/"bin/python"),"-m","pip","install","-r",str(root/"backend/requirements.lock")],check=True,cwd=root)
subprocess.run(["npm","ci","--no-fund","--no-audit"],check=True,cwd=root/"frontend")
subprocess.run(["npm","run","build"],check=True,cwd=root/"frontend")
print("Einrichtung geprüft. Start: .venv/bin/python scripts/run.py --demo --open")
