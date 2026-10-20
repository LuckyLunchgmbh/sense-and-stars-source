#!/usr/bin/env python3
"""Exercise a real HTTPS SoulFlow pilot using dedicated synthetic accounts.

This script performs mutations only when explicitly invoked. It never creates
accounts, publishes lessons, invokes cron, or prints credentials/response bodies.
The full run resets ALL practice cases belonging to its two QA practitioners;
use dedicated test accounts, never the practitioner's working account.

Private credential JSON (owner-readable only)::

    {"url":"https://your-project.vercel.app", "accounts":[
      {"role":"practitioner", "email":"qa-a@example.org", "password":"..."},
      {"role":"practitioner", "email":"qa-b@example.org", "password":"..."}
    ]}

Only practitioners whose email local part is exactly qa-a or qa-b are selected.
An account outside example.org additionally requires "synthetic": true.
An optional admin account is checked without publishing or changing any lesson.

    python scripts/verify_hosted.py --credentials /private/accounts.json \
      --state /private/qa-state.json
    # After a second deployment/cold start, verify the SAME persisted markers:
    python scripts/verify_hosted.py --credentials /private/accounts.json \
      --state /private/qa-state.json --verify-state-only

JSON on stdout contains safe check names, status codes, counts and record IDs.
There is no retry of mutations: a timeout requires inspecting the saved state.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
import stat
import sys
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import httpx


class VerificationFailed(Exception):
    """Already recorded; never include potentially sensitive exception text."""


class Report:
    def __init__(self, mode: str):
        self.data = {"mode": mode, "started_at": datetime.now(timezone.utc).isoformat(),
                     "checks": [], "requests": 0, "passed": False}

    def check(self, name: str, condition: bool, **safe_details):
        self.data["checks"].append({"check": name, "ok": bool(condition), **safe_details})
        if not condition:
            raise VerificationFailed


def https_url(value: str, *, origin: bool = False) -> bool:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or (origin and parsed.path not in ("", "/"))):
            return False
        host = parsed.hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local")):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        return True
    except (ValueError, TypeError):
        return False


def private_json(path: Path) -> dict:
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Private JSON must not be readable by group or others")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def save_state(path: Path | None, state: dict):
    if path is None:
        return
    # O_EXCL avoids following an existing temporary symlink. Atomic replace also
    # keeps an earlier successful marker available if this process is interrupted.
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class API:
    def __init__(self, client: httpx.Client, report: Report, account: dict | None = None):
        self.client, self.report, self.account = client, report, account
        self.user = None

    def request(self, method: str, path: str, name: str, body=None, *, status=200,
                origin: str | None = None, headers_check=True) -> httpx.Response:
        headers = {}
        if method != "GET":
            headers = {"X-SoulFlow": "1", "Origin": origin or str(self.client.base_url).rstrip("/"),
                       "Sec-Fetch-Site": "same-origin"}
        self.report.data["requests"] += 1
        response = self.client.request(method, path, json=body, headers=headers)
        self.report.check(name + ".http", response.status_code == status,
                          expected=status, actual=response.status_code)
        if headers_check:
            self.report.check(name + ".privacy_headers",
                              "no-store" in response.headers.get("cache-control", "").lower()
                              and "max-age=" in response.headers.get("strict-transport-security", "").lower()
                              and "frame-ancestors 'none'" in response.headers.get("content-security-policy", "")
                              and response.headers.get("x-content-type-options") == "nosniff")
        return response

    def get(self, path: str, name: str, **kwargs):
        return self.request("GET", path, name, **kwargs).json()

    def mutate(self, method: str, path: str, body, name: str, **kwargs):
        return self.request(method, path, name, body, **kwargs).json()

    def login(self, name: str):
        response = self.request("POST", "/api/auth/login", name,
                                {"email": self.account["email"], "password": self.account["password"]})
        cookie = SimpleCookie()
        for header in response.headers.get_list("set-cookie"):
            cookie.load(header)
        session = cookie.get("soulflow_session")
        self.report.check(name + ".secure_cookie", session is not None and bool(session["secure"])
                          and bool(session["httponly"]) and session["samesite"].lower() == "strict"
                          and session["path"] == "/")
        self.user = response.json()
        self.report.check(name + ".role", self.user["role"] == self.account["role"])
        return self.user

    def logout(self, name: str):
        self.mutate("POST", "/api/auth/logout", {}, name)
        self.request("GET", "/api/auth/me", name + ".revoked", status=401)


def check_public_source(report: Report, source: str):
    report.check("source.https_url", https_url(source))
    # A separate client carries no SoulFlow cookies or authentication.
    with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as public:
        current = source
        for _ in range(6):
            report.check("source.redirect_is_https", https_url(current))
            report.data["requests"] += 1
            response = public.get(current)
            if response.is_redirect:
                current = urljoin(current, response.headers.get("location", ""))
                continue
            report.check("source.public_without_auth", response.status_code == 200,
                         actual=response.status_code)
            return
    report.check("source.redirect_limit", False)


def verify_persisted(owner: API, other: API, state: dict, report: Report):
    report.check("persistence.same_owner", owner.user["id"] == state["owner_id"])
    notes = owner.get("/api/learning/notebook", "persistence.notebook")
    note = next((n for n in notes if n["id"] == state["note_id"]), None)
    report.check("persistence.note_exact", note is not None and note["body"] == state["note_body"])
    lessons = owner.get("/api/learning", "persistence.learning")["lessons"]
    lesson = next((item for item in lessons if item["id"] == state["lesson_id"]), None)
    report.check("persistence.bookmark_and_pin", lesson is not None
                 and lesson["bookmarked"] and lesson["pinned"])
    case = owner.get(f"/api/clients/{state['case_id']}", "persistence.practice_case")
    report.check("persistence.case_identity", case["is_test"] is True
                 and case["test_owner_id"] == state["owner_id"] and case["name"] == state["case_name"])
    foreign = other.get("/api/learning/notebook", "persistence.other_notebook")
    report.check("persistence.notebook_private", state["note_id"] not in [n["id"] for n in foreign])
    other.request("GET", f"/api/clients/{state['case_id']}", "persistence.case_private", status=404)


def full_run(owner: API, other: API, report: Report, state: dict, state_path: Path | None):
    token = uuid.uuid4().hex[:12]
    real_before = owner.get("/api/clients", "practice.real_before")
    owner.mutate("POST", "/api/practice/reset", {}, "practice.clean_dedicated_qa_account")
    other.mutate("POST", "/api/practice/reset", {}, "isolation.clean_second_qa_account")
    examples = owner.mutate("POST", "/api/practice/clients/examples", {}, "practice.examples")
    repeated = owner.mutate("POST", "/api/practice/clients/examples", {}, "practice.examples_repeat")
    report.check("practice.three_idempotent_charts", len(examples) == 3 and examples == repeated
                 and all(c["is_test"] and c["test_owner_id"] == owner.user["id"]
                         and len(c["chart"]["planets"]) == 10 for c in examples))
    # The built-in fictional examples are labelled again for the QA archive.
    for case in examples:
        owner.mutate("PATCH", f"/api/clients/{case['id']}",
                     {"name": "QA/SYNTHETISCH " + case["name"]}, "practice.label_example")
    payload = {"name": f"QA/SYNTHETISCH Radix {token}", "email": f"qa-{token}@example.org",
               "birth_date": "2000-01-01", "birth_time": "13:00", "birth_place": "Berlin",
               "themes": ["QA/SYNTHETISCH – technischer Test, keine Beratung"]}
    case = owner.mutate("POST", "/api/practice/clients", payload, "practice.create", status=201)
    case_id = case["id"]
    places = owner.get("/api/astro/places?q=Berlin", "astro.place_name_only")
    report.check("astro.berlin_selected", bool(places) and places[0]["timezone"] == "Europe/Berlin")
    chart = owner.mutate("POST", f"/api/clients/{case_id}/chart", {"place_id": places[0]["id"]}, "astro.chart")
    longitudes = {p["name"]: p["longitude"] for p in chart["planets"]}
    # The same independent NASA/JPL J2000 reference used by test_astro.py.
    reference = {"Sonne": 280.3689092, "Mond": 223.3237860, "Mars": 327.9632921, "Jupiter": 25.2530685}
    report.check("astro.j2000_reference", all(math.isclose(longitudes.get(k, -999), v, abs_tol=0.01)
                 for k, v in reference.items()) and len(chart["planets"]) == 10
                 and len(chart["houses"]) == 12 and chart["utc_datetime"] == "2000-01-01T12:00:00+00:00"
                 and bool(chart["source"]["actual_ephemerides"]))
    resource = owner.mutate("POST", f"/api/clients/{case_id}/resources",
                            {"kind": "note", "title": "QA/SYNTHETISCH Fallnotiz",
                             "body": "QA/SYNTHETISCH – nur Testdaten", "shared": False}, "practice.resource", status=201)
    start = (datetime.now(ZoneInfo("Europe/Berlin")) + timedelta(days=21)).replace(
        hour=10, minute=0, second=0, microsecond=0).isoformat()
    appointment = owner.mutate("POST", "/api/appointments",
                               {"client_id": case_id, "start_at": start, "title": "QA/SYNTHETISCH Übung"},
                               "practice.appointment", status=201)
    for method, path, body in (
        ("GET", f"/api/clients/{case_id}", None),
        ("PATCH", f"/api/clients/{case_id}", {"name": "QA/SYNTHETISCH fremder Schreibversuch"}),
        ("GET", f"/api/clients/{case_id}/resources", None),
        ("PATCH", f"/api/resources/{resource['id']}", {"shared": True}),
        ("POST", f"/api/clients/{case_id}/chart", {"place_id": places[0]["id"]}),
        ("DELETE", f"/api/practice/clients/{case_id}", {}),
        ("POST", f"/api/practice/clients/{case_id}/restore", {}),
        ("PATCH", f"/api/appointments/{appointment['id']}", {"status": "cancelled"}),
    ):
        other.request(method, path, "isolation.foreign_" + method.lower(), body, status=404)
    other_case = other.mutate("POST", "/api/practice/clients",
                              {"name": "QA/SYNTHETISCH zweites Konto", "email": f"qa-second-{token}@example.org"},
                              "isolation.second_case", status=201)
    owner.mutate("DELETE", f"/api/practice/clients/{case_id}", {}, "practice.archive")
    owner.request("GET", f"/api/clients/{case_id}", "practice.archive_hidden", status=404)
    archived = owner.get("/api/clients?practice=1&archived=1", "practice.archive_list")
    report.check("practice.archive_recoverable", any(c["id"] == case_id and c["archived_at"] for c in archived))
    restored = owner.mutate("POST", f"/api/practice/clients/{case_id}/restore", {}, "practice.restore")
    resources = owner.get(f"/api/clients/{case_id}/resources", "practice.restored_resource")
    appointments = owner.get("/api/appointments?practice=1", "practice.restored_appointment")
    report.check("practice.restore_preserves_data", restored["chart"] == chart
                 and resource in resources and appointment in appointments)
    owner.mutate("POST", "/api/practice/reset", {}, "practice.reset")
    report.check("practice.reset_empty", owner.get("/api/clients?practice=1", "practice.after_reset") == [])
    report.check("practice.real_clients_unchanged", owner.get("/api/clients", "practice.real_after") == real_before)
    report.check("practice.reset_isolated", other.get(f"/api/clients/{other_case['id']}", "isolation.second_case_survives")["id"] == other_case["id"])
    replacement = owner.mutate("POST", "/api/practice/clients", payload, "practice.same_email_after_reset", status=201)
    report.check("practice.fresh_start", replacement["id"] != case_id and replacement["email"] == payload["email"])
    lessons = owner.get("/api/learning", "learning.open_library")["lessons"]
    report.check("learning.all_published_open", bool(lessons) and all(l["available"] and l["status"] == "published" for l in lessons))
    lesson_id = lessons[0]["id"]
    owner.mutate("PATCH", f"/api/learning/{lesson_id}/state", {"bookmarked": True, "pinned": True}, "learning.bookmark_pin")
    body = f"QA/SYNTHETISCH Persistenzmarker {token}; keine persönlichen Daten."
    note = owner.mutate("POST", "/api/learning/notebook",
                        {"lesson_id": lesson_id, "title": f"QA/SYNTHETISCH {token}", "body": body}, "notebook.create")
    body += " Zweite Fassung gespeichert."
    owner.mutate("PATCH", f"/api/learning/notebook/{note['id']}", {"body": body}, "notebook.edit")
    export = owner.get("/api/learning/notebook/export", "notebook.export")
    report.check("notebook.export_exact", body in export["content"] and export["filename"].endswith(".md"))
    other.request("PATCH", f"/api/learning/notebook/{note['id']}", "notebook.foreign_edit",
                  {"body": "QA/SYNTHETISCH unzulässiger Fremdzugriff"}, status=404)
    updates = owner.get("/api/learning/updates/status", "updates.review_policy")
    report.check("updates.fortnightly_drafts_only", updates["interval_days"] == 14
                 and updates["review_required"] is True and updates["publication_automatic"] is False)
    state.update({"owner_id": owner.user["id"], "note_id": note["id"], "note_body": body,
                  "lesson_id": lesson_id, "case_id": replacement["id"], "case_name": payload["name"],
                  "created_at": datetime.now(timezone.utc).isoformat()})
    save_state(state_path, state)
    owner.logout("auth.logout")
    owner.login("auth.relogin")
    verify_persisted(owner, other, state, report)
    report.data["markers"] = {k: state[k] for k in ("owner_id", "note_id", "lesson_id", "case_id")}


def run(args, report: Report):
    config = private_json(args.credentials)
    url = config["url"].rstrip("/")
    report.check("config.public_https_origin", https_url(url, origin=True))
    accounts = config["accounts"]
    practitioners = [a for a in accounts if a.get("role") == "practitioner"
                     and a.get("email", "").split("@", 1)[0].lower() in ("qa-a", "qa-b")]
    report.check("config.two_distinct_qa_practitioners", len(practitioners) == 2
                 and {a["email"].split("@", 1)[0].lower() for a in practitioners} == {"qa-a", "qa-b"})
    selected = sorted(practitioners, key=lambda a: a["email"].lower())
    report.check("config.dedicated_synthetic_accounts", all(
        a.get("synthetic") is True or a["email"].lower().endswith("@example.org") for a in selected))
    if args.state:
        report.check("config.state_separate_from_credentials", args.state.resolve() != args.credentials.resolve())
    state = private_json(args.state) if args.verify_state_only else {"url": url}
    if args.verify_state_only:
        report.check("config.state_same_origin", state["url"] == url)
    elif args.state and args.state.exists():
        report.check("config.preserve_existing_state_use_new_path", False)
    with ExitStack() as stack:
        def client(account=None):
            transport = stack.enter_context(httpx.Client(base_url=url, timeout=60,
                follow_redirects=False, trust_env=False))
            return API(transport, report, account)
        public = client()
        health = public.get("/api/health", "health")
        report.check("health.hosted_agpl", health["status"] == "ok" and health["mode"] == "hosted"
                     and health["license"] == "AGPL-3.0-only")
        report.data["version"] = health["version"]
        check_public_source(report, health["source_url"])
        public.request("GET", "/api/auth/me", "auth.unauthenticated", status=401)
        public.request("GET", "/api/clients", "clients.unauthenticated", status=401)
        public.request("GET", "/api/demo", "demo.disabled", status=404)
        public.request("GET", "/api/internal/learning-updates", "cron.requires_secret", status=401)
        owner, other = (client(a) for a in selected)
        owner.login("auth.owner_login")
        other.login("auth.second_login")
        owner.request("POST", "/api/auth/logout", "csrf.foreign_origin", {},
                      origin="https://qa-invalid-origin.example.org", status=403, headers_check=False)
        owner.get("/api/auth/me", "csrf.session_preserved")
        if args.verify_state_only:
            verify_persisted(owner, other, state, report)
            report.data["markers"] = {k: state[k] for k in ("owner_id", "note_id", "lesson_id", "case_id")}
        else:
            full_run(owner, other, report, state, args.state)
        owner.request("GET", "/api/admin/lessons", "roles.practitioner_no_editor", status=403)
        admin_account = next((a for a in accounts if a.get("role") == "admin"), None)
        if admin_account is not None:
            admin = client(admin_account)
            admin.login("auth.admin_login")
            lessons = admin.get("/api/admin/lessons", "admin.drafts_visible")
            report.check("admin.has_drafts_to_review", any(l["status"] == "draft" for l in lessons))
            admin.logout("auth.admin_logout")
        owner.logout("auth.owner_final_logout")
        other.logout("auth.second_logout")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--credentials", required=True, type=Path, help="Private JSON; never prints its contents")
    parser.add_argument("--state", type=Path, help="Private persistence marker file; full run requires a new filename")
    parser.add_argument("--verify-state-only", action="store_true", help="Read existing markers after redeploy; no practice mutations")
    args = parser.parse_args()
    if args.verify_state_only and args.state is None:
        parser.error("--verify-state-only requires --state")
    report = Report("persistence_after_redeploy" if args.verify_state_only else "hosted_full_flow")
    try:
        run(args, report)
        report.data["passed"] = True
    except VerificationFailed:
        pass
    except Exception as exc:
        # Exception messages may contain URLs, usernames or request bodies.
        report.data["error_type"] = type(exc).__name__
        report.data["checks"].append({"check": "execution.completed", "ok": False})
    report.data["finished_at"] = datetime.now(timezone.utc).isoformat()
    report.data["checks_passed"] = sum(c["ok"] for c in report.data["checks"])
    print(json.dumps(report.data, ensure_ascii=False, separators=(",", ":")))
    return 0 if report.data["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
