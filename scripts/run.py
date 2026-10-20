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

ROOT = Path(__file__).resolve().parents[1]
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
    if health.get("version") not in ("1.0.0", "1.1.0") or health.get("mode")!=("demo" if args.demo else "local"):
        sys.exit("Dieser Port wird bereits von einem anderen Modus oder Dienst verwendet.")
    print("Sense & Stars läuft bereits: "+url,flush=True)
    if args.open: webbrowser.open(url)
    sys.exit(0)
except (urllib.error.URLError,TimeoutError,ConnectionError):
    pass
env=os.environ.copy()
env["SOULFLOW_DEMO"]="1" if args.demo else "0"
env.setdefault("SOULFLOW_DB",str(ROOT/"data"/("demo" if args.demo else "local")/"soulflow.sqlite3"))
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
