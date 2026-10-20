#!/usr/bin/env python3
"""Exercise the actual curriculum end to end in disposable synthetic SQLite.

Never touches the hosted database, existing local accounts or network sources.
Completion records in this proof are automated test data, not learning claims.
"""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def verify():
    from fastapi.testclient import TestClient
    from app import academy
    from app.main import app
    from app.db import get_db
    from app.security import hash_password, now_iso
    courses = academy.load_content()
    expected = sum(len(c.lessons) for c in courses)
    if len(courses) != 12 or expected != 120:
        raise RuntimeError("Die Gesamtabnahme benötigt den tatsächlichen vollständigen120er-Bestand.")
    content = {lesson.key:lesson for course in courses for lesson in course.lessons}
    checks = 0

    def check(condition, description):
        nonlocal checks
        if not condition:
            raise AssertionError(description)
        checks += 1

    keys = ("DATABASE_URL", "SENSE_AND_STARS_DB", "SENSE_AND_STARS_DEMO", "SENSE_AND_STARS_HOSTED")
    previous = {key:os.environ.get(key) for key in keys}
    try:
        with TemporaryDirectory(prefix="sense-stars-academy-proof-") as folder:
            os.environ.pop("DATABASE_URL", None)
            os.environ.update(SENSE_AND_STARS_DB=str(Path(folder)/"proof.sqlite3"),
                              SENSE_AND_STARS_DEMO="1", SENSE_AND_STARS_HOSTED="0")
            with TestClient(app) as client:
                def mutate(method, path, payload=None):
                    return client.request(method,path,json=payload or {},headers={"X-Sense-And-Stars":"1"})

                accounts = client.get("/api/demo").json()["accounts"]

                def login(role):
                    account = next(a for a in accounts if a["role"] == role)
                    result = mutate("POST","/api/auth/login",{k:account[k] for k in ("email","password")})
                    check(result.status_code == 200,"synthetic login " + role)

                login("practitioner")
                overview = client.get("/api/academy").json()
                check(len(overview["courses"]) == 12,"twelve courses visible")
                check(sum(c["published_count"] for c in overview["courses"]) == 120,"all120open in explicit demo")
                check(overview["progress"]["points"] == 0,"new account zero points")
                # Start with the advanced last course, before any recommended prerequisites.
                lessons = []
                for course in reversed(courses):
                    result = client.get("/api/academy/courses/" + course.id)
                    check(result.status_code == 200,"free course entry " + course.id)
                    items = result.json()["lessons"]
                    check(len(items) == len(course.lessons),"complete course " + course.id)
                    lessons.extend(items)
                first = lessons[0]
                note = mutate("POST","/api/learning/notebook",{
                    "lesson_id":first["id"],"title":"Synthetische Akademie-Abnahme",
                    "body":"Eigene synthetische Notiz zum Konten- und Persistenztest."})
                check(note.status_code == 200,"notebook link")
                check(mutate("PATCH",f'/api/learning/{first["id"]}/state',{"bookmarked":True,"pinned":True}).status_code == 200,"bookmark and pin")
                for item in lessons:
                    identifier = item["id"]
                    authored = content[item["academy_key"]]
                    route = f"/api/academy/lessons/{identifier}"
                    detail = client.get(route)
                    check(detail.status_code == 200,"actual lesson readable " + authored.key)
                    check("correct_index" not in json.dumps(detail.json()),"quiz key hidden before answer " + authored.key)
                    completed = mutate("POST",route + "/complete").json()
                    check(completed["points_awarded"] == 5,"read credit " + authored.key)
                    check(mutate("POST",route + "/complete").json()["points_awarded"] == 0,"read idempotent " + authored.key)
                    answers = {q.id:q.correct_index for q in authored.quiz}
                    quiz = mutate("POST",route + "/quiz",{"answers":answers}).json()
                    check(quiz["passed"] and quiz["score"] == 100,"quiz " + authored.key)
                    check(len(quiz["feedback"]) == 3 and all(f["explanation"] for f in quiz["feedback"]),"explained feedback " + authored.key)
                    check(quiz["points_awarded"] == 15,"quiz credit " + authored.key)
                    check(mutate("POST",route + "/quiz",{"answers":answers}).json()["points_awarded"] == 0,"quiz idempotent " + authored.key)
                    payload = {"response":"Synthetische technische Abgabe: " + authored.practice.model_answer,
                               "self_checks":[True]*len(authored.practice.rubric)}
                    practice = mutate("POST",route + "/practice",payload).json()
                    check(practice["points_awarded"] == 20,"practice credit " + authored.key)
                    check(practice["attempt"]["assessment"] == "self_assessment","honest practice feedback " + authored.key)
                    check(mutate("POST",route + "/practice",payload).json()["points_awarded"] == 0,"practice idempotent " + authored.key)
                summary = client.get("/api/academy").json()
                check(summary["progress"] == {"points":4800,"read_count":120,"passed_count":120,"practice_count":120},"exact totals")
                check(len(summary["badges"]) == 12,"all12learning badges")
                check(len(summary["reviews"]) == 120,"review schedules")
                login("admin")
                check(client.get("/api/academy").json()["progress"]["points"] == 0,"other staff has no points")
                check(client.get(f'/api/academy/lessons/{first["id"]}').json()["attempts"] == [],"other staff has no attempts")
                check(client.get("/api/learning/notebook").json() == [],"other staff has no notes")
                check(mutate("PATCH",f'/api/learning/notebook/{note.json()["id"]}',{"body":"fremd"}).status_code == 404,"foreign note denied")
                login("practitioner")
            # A fresh application lifecycle must preserve the complete stored result.
            with TestClient(app) as client:
                check(mutate("POST","/api/auth/login",{k:next(a for a in accounts if a["role"] == "practitioner")[k] for k in ("email","password")}).status_code == 200,"login after restart")
                check(client.get("/api/academy").json()["progress"] == summary["progress"],"persisted progress")
                check(len(client.get("/api/academy").json()["badges"]) == 12,"persisted badges")
                saved = client.get(f'/api/academy/lessons/{first["id"]}').json()
                check(saved["lesson"]["bookmarked"] and saved["lesson"]["pinned"],"persisted bookmark and pin")
                check(len(saved["attempts"]) == 4,"persistent separate attempts")
                check(client.get("/api/learning/notebook").json()[0]["id"] == note.json()["id"],"persistent notebook")
            # A distinct non-demo database must keep the very same real package
            # private until exact-hash acknowledgement. All writes remain here.
            os.environ.update(SENSE_AND_STARS_DB=str(Path(folder)/"draft-gate.sqlite3"),
                              SENSE_AND_STARS_DEMO="0")
            with TestClient(app) as client:
                password = "Synthetic-local-package-proof-2026"
                with get_db() as conn:
                    for role_name in ("admin", "practitioner"):
                        conn.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                                     (role_name, role_name+"@academy.example.org", hash_password(password), role_name, now_iso()))
                def gate_login(role_name):
                    check(mutate("POST","/api/auth/login",{"email":role_name+"@academy.example.org", "password":password}).status_code == 200,
                          "draft gate login " + role_name)
                gate_login("practitioner")
                check(sum(c["published_count"] for c in client.get("/api/academy").json()["courses"]) == 0,
                      "non-demo actual120lessons remain unpublished")
                check(client.get("/api/admin/academy/release").status_code == 403, "practitioner cannot approve package")
                check(client.get("/api/academy/courses/grundlagen?preview=true").status_code == 403,
                      "practitioner cannot preview unpublished contents")
                gate_login("admin")
                release = client.get("/api/admin/academy/release").json()
                check(release["ready"] and release["draft_count"] == 120 and release["published_count"] == 0,
                      "actual full package ready but not approved")
                preview = client.get("/api/academy/courses/grundlagen?preview=true").json()["lessons"]
                preview_id = preview[0]["id"]
                check(client.get(f"/api/academy/lessons/{preview_id}?preview=true").status_code == 200,
                      "admin can inspect original draft")
                check(mutate("POST", f"/api/academy/lessons/{preview_id}/complete?preview=true").status_code == 409,
                      "preview earns no points")
                check(mutate("POST", "/api/admin/academy/release", {"acknowledged":False,
                      "manifest_sha256":release["manifest_sha256"]}).status_code == 422, "approval acknowledgement required")
                check(mutate("POST", "/api/admin/academy/release", {"acknowledged":True,
                      "manifest_sha256":"0"*64}).status_code == 409, "approval stale hash rejected")
                published = mutate("POST", "/api/admin/academy/release", {"acknowledged":True,
                      "manifest_sha256":release["manifest_sha256"]})
                check(published.status_code == 200 and published.json()["published_count"] == 120,
                      "synthetic exact-package approval atomic")
                check(mutate("POST", "/api/admin/academy/release", {"acknowledged":True,
                      "manifest_sha256":release["manifest_sha256"]}).status_code == 200, "package approval idempotent")
                gate_login("practitioner")
                check(sum(c["published_count"] for c in client.get("/api/academy").json()["courses"]) == 120,
                      "all actual lessons accessible after synthetic approval")
    finally:
        for key,value in previous.items():
            if value is None:
                os.environ.pop(key,None)
            else:
                os.environ[key] = value
    report = {"status":"passed","checks":checks,"courses":12,"lessons":120,"points":4800,
              "badges":12,"environment":"disposable synthetic SQLite; actual authored curriculum",
              "human_learning_claim":False,"hosted_data_touched":False,"published":False,
              "synthetic_package_approval_tested":True}
    destination = ROOT / "artifacts/academy-flow-proof.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))


if __name__ == "__main__":
    verify()
