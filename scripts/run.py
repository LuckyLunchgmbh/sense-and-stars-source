#!/usr/bin/env python3
"""Launch the loopback-only app, keeping demo and non-demo databases separate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import compatible_database_path, set_setting, setting

parser=argparse.ArgumentParser(description="Sense & Stars lokal starten")
parser.add_argument("--demo",action="store_true",help="Nur synthetische Beispieldaten")
parser.add_argument("--port",type=int,default=8768)
parser.add_argument("--open",action="store_true")
args=parser.parse_args()
if not 1024 <= args.port <= 65535:
    parser.error("Port muss zwischen 1024 und 65535 liegen.")
python=ROOT/".venv"/"bin"/"python"
if not python.exists() or not (ROOT/"frontend"/"dist"/"index.html").exists():
    sys.exit("Zuerst die projektlokale Einrichtung ausführen: python3 scripts/setup.py")
url=f"http://127.0.0.1:{args.port}"
try:
    with urllib.request.urlopen(url+"/api/health",timeout=1) as response:
        health=json.load(response)
    current_version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if health.get("version") != current_version or health.get("mode")!=("demo" if args.demo else "local"):
        sys.exit("Dieser Port wird bereits von einem anderen Modus oder Dienst verwendet.")
    print("Sense & Stars läuft bereits: "+url,flush=True)
    if args.open: webbrowser.open(url)
    sys.exit(0)
except (urllib.error.URLError,TimeoutError,ConnectionError):
    pass
env=os.environ.copy()
set_setting("DEMO", "1" if args.demo else "0", environ=env)
if not setting("DB", environ=env):
    set_setting("DB", str(compatible_database_path(ROOT / "data" / ("demo" if args.demo else "local"))), environ=env)
print("Sense & Stars "+("DEMO · nur erfundene Daten" if args.demo else "lokaler Kontobetrieb")+" · "+url,flush=True)
if args.open:
    # Browser can load while uvicorn starts; the launcher remains the foreground process.
    import threading
    threading.Timer(1.5,lambda:webbrowser.open(url)).start()
try:
    result=subprocess.run([str(python),"-m","uvicorn","app.main:app","--app-dir",str(ROOT/"backend"),"--host","127.0.0.1","--port",str(args.port),"--no-access-log"],cwd=ROOT,env=env)
    sys.exit(result.returncode)
except KeyboardInterrupt:
    pass
