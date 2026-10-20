"""Freely selectable academy with private attempts and deliberate package release.

Authored material is validated locally, never fetched at request time. Completion
and self-assessment are learning records, not professional qualifications.
"""
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from .config import setting
from .db import get_db
from . import learning
from .security import require_admin, require_staff

router = APIRouter()
CONTENT_DIR = Path(__file__).with_name("academy_content")
COURSE_COUNTS = {
    "grundlagen": 8, "zeichen": 12, "planeten": 12, "haeuser": 12,
    "aspekte": 12, "radixsynthese": 8, "transite": 10,
    "psychologisch-evolutionaer": 12, "mondknoten-asteroiden": 8,
    "hellenistisch": 8, "jyotish": 6, "beratung-feldarbeit": 12,
}
EXPECTED_LESSONS = 120
XP_VALUES = {"read": 5, "quiz": 15, "practice": 20}
Text = Annotated[str, Field(strict=True, min_length=1, max_length=16000)]
Level = Literal["foundation", "deepening", "practice"]


class Example(learning.StrictModel):
    title: Annotated[str, Field(strict=True, min_length=1, max_length=200)]
    body: Text

    @field_validator("body")
    @classmethod
    def substantial(cls, value):
        if len(value.split()) < 60:
            raise ValueError("Ein erläutertes Beispiel benötigt mindestens 60 Wörter.")
        return learning._clean(value)


class Practice(learning.StrictModel):
    prompt: Annotated[str, Field(strict=True, min_length=1, max_length=3000)]
    model_answer: Text
    rubric: Annotated[list[Annotated[str, Field(strict=True, min_length=1, max_length=600)]], Field(min_length=3, max_length=5)]

    @field_validator("model_answer")
    @classmethod
    def substantial(cls, value):
        if len(value.split()) < 120:
            raise ValueError("Eine Musterbearbeitung benötigt mindestens 120 Wörter.")
        return learning._clean(value)

    @field_validator("rubric")
    @classmethod
    def distinct_criteria(cls, values):
        values = [learning._clean(value) for value in values]
        if len(set(values)) != len(values):
            raise ValueError("Prüfkriterien müssen unterschiedlich sein.")
        return values


class Question(learning.QuizQuestion):
    explanation: Annotated[str, Field(strict=True, min_length=1, max_length=2000)]


class Source(learning.StrictModel):
    url: Annotated[str, Field(strict=True, min_length=1, max_length=2048)]
    title: Annotated[str, Field(strict=True, min_length=1, max_length=200)]
    author: Annotated[str, Field(strict=True, min_length=1, max_length=200)]
    note: Annotated[str, Field(strict=True, min_length=1, max_length=2000)]
    checked_at: Annotated[str, Field(strict=True, pattern=r"^\d{4}-\d{2}-\d{2}$")]

    @field_validator("url")
    @classmethod
    def public_url(cls, value):
        return learning._source_url(value)

    @field_validator("checked_at")
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value


class AuthoredLesson(learning.StrictModel):
    key: Annotated[str, Field(strict=True, pattern=r"^academy-[a-z0-9-]+-\d{2}$", max_length=100)]
    title: Annotated[str, Field(strict=True, min_length=1, max_length=160)]
    summary: Annotated[str, Field(strict=True, min_length=1, max_length=600)]
    objective: Annotated[str, Field(strict=True, min_length=1, max_length=1000)]
    level: Level
    minutes: Annotated[StrictInt, Field(ge=5, le=180)]
    body: Text
    examples: Annotated[list[Example], Field(min_length=2, max_length=2)]
    practice: Practice
    quiz: Annotated[list[Question], Field(min_length=3, max_length=3)]
    sources: Annotated[list[Source], Field(min_length=1, max_length=10)]

    @field_validator("body")
    @classmethod
    def substantial(cls, value):
        if len(value.split()) < 450:
            raise ValueError("Ein Lehrtext benötigt mindestens 450 Wörter.")
        return learning._clean(value)

    @model_validator(mode="after")
    def unique_questions(self):
        if len({q.id for q in self.quiz}) != len(self.quiz):
            raise ValueError("Wissensfragen benötigen eindeutige Kennungen.")
        return self


class AuthoredCourse(learning.StrictModel):
    id: Annotated[str, Field(strict=True, pattern=r"^[a-z0-9-]+$", max_length=80)]
    title: Annotated[str, Field(strict=True, min_length=1, max_length=60)]
    summary: Annotated[str, Field(strict=True, min_length=1, max_length=1000)]
    tradition: Annotated[str, Field(strict=True, min_length=1, max_length=400)]
    level: Level
    prerequisites: Annotated[list[Annotated[str, Field(strict=True, min_length=1, max_length=400)]], Field(max_length=12)]
    lessons: Annotated[list[AuthoredLesson], Field(min_length=1, max_length=12)]

    @model_validator(mode="after")
    def known_course(self):
        if self.id not in COURSE_COUNTS:
            raise ValueError("Unbekannter Kurs im Akademie-Erstbestand.")
        keys = [lesson.key for lesson in self.lessons]
        if len(set(keys)) != len(keys) or any(not key.startswith(f"academy-{self.id}-") for key in keys):
            raise ValueError("Lektionen benötigen eindeutige zum Kurs gehörende Kennungen.")
        return self


class PracticeSubmission(learning.StrictModel):
    response: Annotated[str, Field(strict=True, min_length=40, max_length=12000)]
    self_checks: Annotated[list[StrictBool], Field(min_length=3, max_length=5)]

    @field_validator("response")
    @classmethod
    def readable(cls, value):
        return learning._clean(value)


class ReleaseSubmission(learning.StrictModel):
    manifest_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
    acknowledged: StrictBool


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def load_content():
    """Allow a partial set of complete course files during local authoring."""
    courses = [AuthoredCourse.model_validate_json(path.read_text(encoding="utf-8"))
               for path in sorted(CONTENT_DIR.glob("*.json"))]
    if len({course.id for course in courses}) != len(courses):
        raise ValueError("Kurskennungen dürfen im Erstbestand nicht doppelt vorkommen.")
    return courses


def _base_lesson(course, lesson, week):
    source = lesson.sources[0]
    return learning.LessonCreate(
        title=lesson.title, category=course.title, summary=lesson.summary,
        body=lesson.body, week=week, source_url=source.url, source_title=source.title,
        quiz=[q.model_dump(exclude={"explanation"}) for q in lesson.quiz],
        track=course.title, level=lesson.level, learning_objective=lesson.objective,
        exercise=lesson.practice.prompt, source_note=source.note,
    )


def init_academy(conn):
    """Idempotent, non-destructive import; call after init_learning in one transaction."""
    courses = load_content()  # validate all files before writing anything
    for statement in (
        """CREATE TABLE IF NOT EXISTS academy_courses(
            id TEXT PRIMARY KEY, position INTEGER NOT NULL, payload TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS academy_lessons(
            key TEXT PRIMARY KEY, lesson_id INTEGER NOT NULL UNIQUE REFERENCES learning_lessons(id),
            course_id TEXT NOT NULL REFERENCES academy_courses(id),
            position INTEGER NOT NULL, payload TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS academy_attempts(
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            lesson_id INTEGER NOT NULL REFERENCES learning_lessons(id),
            kind TEXT NOT NULL CHECK(kind IN ('quiz','practice')), payload TEXT NOT NULL,
            created_at TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS academy_attempt_owner ON academy_attempts(user_id,lesson_id,created_at)",
        """CREATE TABLE IF NOT EXISTS academy_xp(
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            lesson_id INTEGER NOT NULL REFERENCES learning_lessons(id),
            event TEXT NOT NULL CHECK(event IN ('read','quiz','practice')),
            points INTEGER NOT NULL CHECK(points IN (5,15,20)), earned_at TEXT NOT NULL,
            PRIMARY KEY(user_id,lesson_id,event))""",
        """CREATE TABLE IF NOT EXISTS academy_reviews(
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            lesson_id INTEGER NOT NULL REFERENCES learning_lessons(id), due_at TEXT NOT NULL,
            PRIMARY KEY(user_id,lesson_id))""",
        """CREATE TABLE IF NOT EXISTS academy_badges(
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            course_id TEXT NOT NULL REFERENCES academy_courses(id), title TEXT NOT NULL,
            earned_at TEXT NOT NULL, PRIMARY KEY(user_id,course_id))""",
    ):
        conn.execute(statement)
    present = {row["name"] for row in conn.execute("PRAGMA table_info(learning_lessons)")}
    for column in ("academy_course_id", "academy_key"):
        if column not in present:
            conn.execute(f"ALTER TABLE learning_lessons ADD COLUMN {column} TEXT")
    # Serialize with other initializers and publication, without committing the caller.
    # SQLite callers already performing writes own their transaction; a no-op
    # update acquires the same database write lock without nested BEGIN.
    conn.execute("UPDATE academy_courses SET position=position WHERE id='__lock__'")
    # One inventory avoids thousands of network round trips during hosted seeding.
    # The caller's write transaction keeps these reserved sort slots stable.
    imported_keys = {row["key"] for row in conn.execute("SELECT key FROM academy_lessons")}
    existing_rows = conn.execute("SELECT seed_key,week FROM learning_lessons").fetchall()
    existing_seeds = {row["seed_key"] for row in existing_rows if row["seed_key"]}
    used_weeks = {row["week"] for row in existing_rows}
    free_weeks = iter(week for week in range(1, learning.MAX_WEEK + 1) if week not in used_weeks)
    for course in courses:
        position = list(COURSE_COUNTS).index(course.id)
        conn.execute("INSERT OR IGNORE INTO academy_courses(id,position,payload) VALUES(?,?,?)",
                     (course.id, position, _canonical(course.model_dump(exclude={"lessons"}))))
        for lesson_position, lesson in enumerate(course.lessons):
            if lesson.key in imported_keys:
                continue
            if lesson.key in existing_seeds:
                raise ValueError("Eine Akademie-Kennung ist bereits außerhalb des zugehörigen Imports belegt.")
            week = next(free_weeks, None)
            if week is None:
                raise ValueError("Nicht genug freie Sortierplätze für die Akademie; vorhandene Inhalte bleiben erhalten.")
            cursor = learning._insert_editorial(conn, _base_lesson(course, lesson, week),
                status="published" if setting("DEMO") == "1" else "draft", seed_key=lesson.key)
            lesson_id = cursor.lastrowid
            conn.execute("UPDATE learning_lessons SET academy_course_id=?,academy_key=? WHERE id=?",
                         (course.id, lesson.key, lesson_id))
            conn.execute("INSERT INTO academy_lessons(key,lesson_id,course_id,position,payload) VALUES(?,?,?,?,?)",
                         (lesson.key, lesson_id, course.id, lesson_position, _canonical(lesson.model_dump())))
            imported_keys.add(lesson.key)


def _rows(conn, course_id=None, *, summary=False):
    columns = "l.id,l.status,l.title,l.summary,a.course_id,a.position" if summary else "l.*,a.course_id,a.position,a.payload"
    clause = " WHERE a.course_id=?" if course_id else ""
    return conn.execute("SELECT " + columns + " FROM academy_lessons a "
        "JOIN learning_lessons l ON l.id=a.lesson_id" + clause + " ORDER BY a.course_id,a.position",
        (course_id,) if course_id else ()).fetchall()


def _require_lesson(conn, lesson_id, user, preview=False):
    if preview and user["role"] != "admin":
        raise HTTPException(403, "Die redaktionelle Vorschau ist nur für den Betreiber zugänglich.")
    row = conn.execute("SELECT l.*,a.course_id,a.position,a.payload FROM academy_lessons a "
        "JOIN learning_lessons l ON l.id=a.lesson_id WHERE l.id=?", (lesson_id,)).fetchone()
    if row is None or (row["status"] != "published" and not preview):
        raise HTTPException(404, "Diese veröffentlichte Akademie-Lektion wurde nicht gefunden.")
    return row


def _personal_progress(conn, user_id):
    return learning._progress(conn, user_id)


def _progress_summary(conn, user_id):
    rows = conn.execute("SELECT event,COUNT(*) AS count,SUM(points) AS points FROM academy_xp "
                        "WHERE user_id=? GROUP BY event", (user_id,)).fetchall()
    events = {row["event"]: dict(row) for row in rows}
    # Existing read acknowledgements remain visible even when made through the
    # legacy library before the academy was opened. No practice credit is inferred.
    read_count = conn.execute("SELECT COUNT(*) FROM learning_progress p JOIN academy_lessons a "
        "ON a.lesson_id=p.lesson_id WHERE p.user_id=? AND p.completed_at IS NOT NULL", (user_id,)).fetchone()[0]
    passed_count = conn.execute("SELECT COUNT(*) FROM learning_progress p JOIN academy_lessons a "
        "ON a.lesson_id=p.lesson_id WHERE p.user_id=? AND p.quiz_passed=1", (user_id,)).fetchone()[0]
    return {"points": sum(row["points"] for row in rows), "read_count": read_count,
            "passed_count": passed_count, "practice_count": events.get("practice", {}).get("count", 0)}


def _course_summary(conn, course, user_id, rows=None, progress=None, badges=None):
    data = json.loads(course["payload"])
    rows = _rows(conn, course["id"], summary=True) if rows is None else rows
    progress = _personal_progress(conn, user_id) if progress is None else progress
    published = [row for row in rows if row["status"] == "published"]
    if badges is None:
        badges = {row["course_id"] for row in conn.execute("SELECT course_id FROM academy_badges WHERE user_id=?", (user_id,))}
    return {**data, "lesson_count": len(rows), "published_count": len(published),
            "search_text": " ".join(row["title"] + " " + row["summary"] for row in published),
            "completed_count": sum(bool(progress.get(row["id"], {}).get("completed_at")) for row in published),
            "passed_count": sum(bool(progress.get(row["id"], {}).get("quiz_passed")) for row in published),
            "badge_earned": course["id"] in badges}


def _course(conn, course_id):
    row = conn.execute("SELECT * FROM academy_courses WHERE id=?", (course_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Dieser Kurs wurde nicht gefunden.")
    return row


def _lesson_json(row, progress, preview=False):
    state = learning._lesson_state(row, progress)
    # Admin preview may expose lesson text but never embeds the solution key.
    visible_state = dict(state, available=True) if preview else state
    result = learning._lesson_json(row, visible_state)
    result["available"] = state["available"]
    result.update(academy_course_id=row["course_id"], academy_key=row["academy_key"],
                  minutes=json.loads(row["payload"])["minutes"])
    return result


def _attempt_page(conn, user_id, lesson_id, before_id=None):
    params = [user_id, lesson_id]
    before = ""
    if before_id:
        cursor = conn.execute("SELECT created_at,id FROM academy_attempts WHERE id=? AND user_id=? AND lesson_id=?",
                              (before_id, user_id, lesson_id)).fetchone()
        if cursor is None:
            raise HTTPException(404, "Dieser Verlaufspunkt wurde nicht gefunden.")
        before = " AND (created_at<? OR (created_at=? AND id<?))"
        params.extend([cursor["created_at"], cursor["created_at"], cursor["id"]])
    rows = conn.execute("SELECT payload FROM academy_attempts WHERE user_id=? AND lesson_id=?" + before +
                        " ORDER BY created_at DESC,id DESC LIMIT 21", params).fetchall()
    return {"items": [json.loads(row["payload"]) for row in rows[:20]], "has_more": len(rows) > 20}


def _save_attempt(conn, user_id, lesson_id, kind, **values):
    attempt = {"id": str(uuid4()), "kind": kind, "created_at": learning._iso(learning.utc_now()),
               "score": None, "passed": False, "response": None, "self_checks": [], "feedback": [], **values}
    conn.execute("INSERT INTO academy_attempts(id,user_id,lesson_id,kind,payload,created_at) VALUES(?,?,?,?,?,?)",
                 (attempt["id"], user_id, lesson_id, kind, _canonical(attempt), attempt["created_at"]))
    return attempt


def _award(conn, user_id, lesson_id, event):
    cursor = conn.execute("INSERT OR IGNORE INTO academy_xp(user_id,lesson_id,event,points,earned_at) VALUES(?,?,?,?,?)",
                         (user_id, lesson_id, event, XP_VALUES[event], learning._iso(learning.utc_now())))
    return XP_VALUES[event] if cursor.rowcount else 0


def _schedule_review(conn, user_id, lesson_id, days, *, keep_earlier=False):
    due = learning._iso(learning.utc_now() + timedelta(days=days))
    if keep_earlier:
        previous = conn.execute("SELECT due_at FROM academy_reviews WHERE user_id=? AND lesson_id=?", (user_id, lesson_id)).fetchone()
        if previous and previous["due_at"] < due:
            due = previous["due_at"]
    conn.execute("INSERT INTO academy_reviews(user_id,lesson_id,due_at) VALUES(?,?,?) "
                 "ON CONFLICT(user_id,lesson_id) DO UPDATE SET due_at=excluded.due_at", (user_id, lesson_id, due))
    return due


def _check_badge(conn, user_id, course_id):
    rows = _rows(conn, course_id, summary=True)
    if len(rows) != COURSE_COUNTS[course_id] or any(row["status"] != "published" for row in rows):
        return
    progress = _personal_progress(conn, user_id)
    practiced = {row["lesson_id"] for row in conn.execute(
        "SELECT lesson_id FROM academy_xp WHERE user_id=? AND event='practice'", (user_id,))}
    if all(progress.get(row["id"], {}).get("quiz_passed") and row["id"] in practiced for row in rows):
        title = "Lernabzeichen · " + json.loads(_course(conn, course_id)["payload"])["title"]
        conn.execute("INSERT OR IGNORE INTO academy_badges(user_id,course_id,title,earned_at) VALUES(?,?,?,?)",
                     (user_id, course_id, title, learning._iso(learning.utc_now())))


@router.get("/api/academy")
def overview(request: Request):
    user = require_staff(request)
    with get_db() as conn:
        progress = _personal_progress(conn, user["id"])
        badges = [{"id": row["course_id"], "title": row["title"], "earned_at": row["earned_at"]}
                  for row in conn.execute("SELECT * FROM academy_badges WHERE user_id=? ORDER BY earned_at,course_id", (user["id"],))]
        all_rows = _rows(conn, summary=True)
        courses = [_course_summary(conn, course, user["id"],
                    [row for row in all_rows if row["course_id"] == course["id"]], progress,
                    {badge["id"] for badge in badges})
                   for course in conn.execute("SELECT * FROM academy_courses ORDER BY position,id")]
        reviews = [dict(row) for row in conn.execute("SELECT r.lesson_id,l.title,r.due_at FROM academy_reviews r "
            "JOIN learning_lessons l ON l.id=r.lesson_id WHERE r.user_id=? AND l.status='published' ORDER BY r.due_at,r.lesson_id", (user["id"],))]
        return {"courses": courses, "progress": _progress_summary(conn, user["id"]), "badges": badges,
                "reviews": reviews, "preview_available": user["role"] == "admin"}


@router.get("/api/academy/courses/{course_id}")
def course_detail(course_id: str, request: Request, preview: bool = False):
    user = require_staff(request)
    if preview and user["role"] != "admin":
        raise HTTPException(403, "Die redaktionelle Vorschau ist nur für den Betreiber zugänglich.")
    with get_db() as conn:
        course = _course(conn, course_id)
        progress = _personal_progress(conn, user["id"])
        rows = _rows(conn, course_id)
        return {"course": _course_summary(conn, course, user["id"], rows, progress),
                "lessons": [_lesson_json(row, progress.get(row["id"], {}), preview)
                            for row in rows if preview or row["status"] == "published"]}


@router.get("/api/academy/lessons/{lesson_id}")
def lesson_detail(lesson_id: int, request: Request, preview: bool = False):
    user = require_staff(request)
    with get_db() as conn:
        row = _require_lesson(conn, lesson_id, user, preview)
        content = json.loads(row["payload"])
        progress = _personal_progress(conn, user["id"]).get(lesson_id, {})
        practiced = conn.execute("SELECT 1 FROM academy_xp WHERE user_id=? AND lesson_id=? AND event='practice'", (user["id"], lesson_id)).fetchone()
        review = conn.execute("SELECT due_at FROM academy_reviews WHERE user_id=? AND lesson_id=?", (user["id"], lesson_id)).fetchone()
        history = _attempt_page(conn, user["id"], lesson_id)
        latest_practice = conn.execute("SELECT payload FROM academy_attempts WHERE user_id=? AND lesson_id=? AND kind='practice' "
                                       "ORDER BY created_at DESC,id DESC LIMIT 1", (user["id"], lesson_id)).fetchone()
        return {"lesson": _lesson_json(row, progress, preview),
                "course": _course_summary(conn, _course(conn, row["course_id"]), user["id"]),
                "examples": content["examples"], "practice": content["practice"], "sources": content["sources"],
                "quiz": [{"id": q["id"], "question": q["question"], "options": q["options"]} for q in content["quiz"]],
                "attempts": history["items"], "attempts_has_more": history["has_more"],
                "latest_practice": json.loads(latest_practice["payload"]) if latest_practice else None,
                "state": {"read": bool(progress.get("completed_at")), "quiz_passed": bool(progress.get("quiz_passed")),
                          "practice_completed": bool(practiced), "review_due_at": review["due_at"] if review else None}}


@router.get("/api/academy/lessons/{lesson_id}/attempts")
def attempt_history(lesson_id: int, request: Request, preview: bool = False,
                    before_id: str | None = Query(default=None, max_length=36)):
    user = require_staff(request)
    with get_db() as conn:
        _require_lesson(conn, lesson_id, user, preview)
        return _attempt_page(conn, user["id"], lesson_id, before_id)


@router.post("/api/academy/lessons/{lesson_id}/complete")
def complete(lesson_id: int, payload: learning.EmptyRequest, request: Request, preview: bool = False):
    user = require_staff(request)
    if preview:
        raise HTTPException(409, "Die redaktionelle Vorschau ist schreibgeschützt.")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _require_lesson(conn, lesson_id, user)
        conn.execute("INSERT INTO learning_progress(user_id,lesson_id,completed_at) VALUES(?,?,?) "
            "ON CONFLICT(user_id,lesson_id) DO UPDATE SET completed_at=COALESCE(learning_progress.completed_at,excluded.completed_at)",
            (user["id"], lesson_id, learning._iso(learning.utc_now())))
        awarded = _award(conn, user["id"], lesson_id, "read")
        return {"points_awarded": awarded, "progress": _progress_summary(conn, user["id"])}


@router.post("/api/academy/lessons/{lesson_id}/quiz")
def submit_quiz(lesson_id: int, payload: learning.QuizSubmission, request: Request, preview: bool = False):
    user = require_staff(request)
    if preview:
        raise HTTPException(409, "Die redaktionelle Vorschau ist schreibgeschützt.")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _require_lesson(conn, lesson_id, user)
        questions = json.loads(row["payload"])["quiz"]
        if set(payload.answers) != {q["id"] for q in questions}:
            raise HTTPException(422, "Beantworte genau alle Fragen der Lektion.")
        if any(not 0 <= payload.answers[q["id"]] < len(q["options"]) for q in questions):
            raise HTTPException(422, "Wähle für jede Frage eine vorhandene Antwortmöglichkeit.")
        feedback = [{"question_id": q["id"], "correct": payload.answers[q["id"]] == q["correct_index"],
                     "correct_index": q["correct_index"], "explanation": q["explanation"]} for q in questions]
        score = round(100 * sum(item["correct"] for item in feedback) / len(questions))
        passed = score >= learning.PASS_SCORE
        conn.execute("""INSERT INTO learning_progress(user_id,lesson_id,quiz_score,quiz_passed,quiz_passed_at,quiz_attempted)
            VALUES(?,?,?,?,?,1) ON CONFLICT(user_id,lesson_id) DO UPDATE SET quiz_attempted=1,
            quiz_score=MAX(quiz_score,excluded.quiz_score),quiz_passed=MAX(quiz_passed,excluded.quiz_passed),
            quiz_passed_at=COALESCE(learning_progress.quiz_passed_at,excluded.quiz_passed_at)""",
            (user["id"], lesson_id, score, int(passed), learning._iso(learning.utc_now()) if passed else None))
        _save_attempt(conn, user["id"], lesson_id, "quiz", score=score, passed=passed, feedback=feedback,
                      answers=payload.answers)
        awarded = _award(conn, user["id"], lesson_id, "quiz") if passed else 0
        due = _schedule_review(conn, user["id"], lesson_id, 7 if passed else 1)
        _check_badge(conn, user["id"], row["course_id"])
        return {"score": score, "passed": passed, "feedback": feedback, "points_awarded": awarded,
                "progress": _progress_summary(conn, user["id"]), "review_due_at": due}


@router.post("/api/academy/lessons/{lesson_id}/practice")
def submit_practice(lesson_id: int, payload: PracticeSubmission, request: Request, preview: bool = False):
    user = require_staff(request)
    if preview:
        raise HTTPException(409, "Die redaktionelle Vorschau ist schreibgeschützt.")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _require_lesson(conn, lesson_id, user)
        practice = json.loads(row["payload"])["practice"]
        if len(payload.self_checks) != len(practice["rubric"]):
            raise HTTPException(422, "Prüfe genau alle Kriterien dieser Praxisaufgabe.")
        passed = all(payload.self_checks)
        attempt = _save_attempt(conn, user["id"], lesson_id, "practice", response=payload.response,
            self_checks=payload.self_checks, passed=passed,
            feedback=[{"criterion": criterion, "self_checked": checked}
                      for criterion, checked in zip(practice["rubric"], payload.self_checks)],
            assessment="self_assessment")
        awarded = _award(conn, user["id"], lesson_id, "practice") if passed else 0
        if passed:
            conn.execute("INSERT INTO learning_progress(user_id,lesson_id,practiced) VALUES(?,?,1) "
                         "ON CONFLICT(user_id,lesson_id) DO UPDATE SET practiced=1", (user["id"], lesson_id))
        due = _schedule_review(conn, user["id"], lesson_id, 7 if passed else 1, keep_earlier=passed)
        _check_badge(conn, user["id"], row["course_id"])
        return {"attempt": attempt, "points_awarded": awarded,
                "progress": _progress_summary(conn, user["id"]), "review_due_at": due}


def release_status(conn):
    """Hash the exact stored teaching package, excluding personal or status data.

    Approval is refused if stored base text diverges from its metadata or if the
    files delivered with this software differ from that previewed package.
    """
    courses = conn.execute("SELECT * FROM academy_courses ORDER BY position,id").fetchall()
    rows = _rows(conn)
    package = []
    coherent = len({row["week"] for row in rows}) == len(rows)
    for course in courses:
        data = json.loads(course["payload"])
        lessons = []
        for row in sorted((r for r in rows if r["course_id"] == course["id"]), key=lambda r: r["position"]):
            authored = AuthoredLesson.model_validate_json(row["payload"])
            expected_base = _base_lesson(AuthoredCourse(**data, lessons=[authored]), authored, row["week"]).model_dump()
            actual_base = {key: json.loads(row[key]) if key == "quiz" else row[key] for key in expected_base}
            coherent = coherent and expected_base == actual_base and row["source_kind"] == "editorial"
            lessons.append(authored.model_dump())
        package.append(dict(data, lessons=lessons))
    manifest = hashlib.sha256(_canonical(package).encode()).hexdigest()
    delivered = [course.model_dump() for course in load_content()]
    # File names do not confer ordering; the declared course sequence is canonical.
    delivered.sort(key=lambda course: list(COURSE_COUNTS).index(course["id"]))
    complete = (len(rows) == EXPECTED_LESSONS and len(courses) == len(COURSE_COUNTS)
                and {course["id"] for course in courses} == set(COURSE_COUNTS)
                and all(sum(row["course_id"] == slug for row in rows) == count for slug, count in COURSE_COUNTS.items()))
    published = sum(row["status"] == "published" for row in rows)
    return {"manifest_sha256": manifest, "expected_lessons": EXPECTED_LESSONS,
            "course_count": len(courses), "lesson_count": len(rows), "published_count": published,
            "draft_count": len(rows) - published, "ready": bool(complete and coherent and package == delivered)}


@router.get("/api/admin/academy/release")
def get_release(request: Request):
    require_admin(request)
    with get_db() as conn:
        return release_status(conn)


@router.post("/api/admin/academy/release")
def publish_release(payload: ReleaseSubmission, request: Request):
    user = require_admin(request)
    if not payload.acknowledged:
        raise HTTPException(422, "Die vollständige Inhaltsfreigabe muss bewusst bestätigt werden.")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = release_status(conn)
        if not state["ready"]:
            raise HTTPException(409, "Der vollständige, unveränderte Akademie-Erstbestand ist noch nicht freigabefähig.")
        if payload.manifest_sha256 != state["manifest_sha256"]:
            raise HTTPException(409, "Die Vorschau hat sich geändert. Prüfe die aktuelle Fassung vor der Freigabe.")
        if conn.execute("SELECT 1 FROM learning_lessons a JOIN academy_lessons m ON m.lesson_id=a.id "
            "JOIN learning_lessons b ON b.week=a.week AND b.id<>a.id WHERE b.status='published'").fetchone():
            raise HTTPException(409, "Ein Sortierplatz ist bereits belegt. Prüfe die Redaktion vor der Freigabe.")
        if state["draft_count"]:
            conn.execute("UPDATE learning_lessons SET status='published',published_at=? WHERE status='draft' "
                "AND id IN (SELECT lesson_id FROM academy_lessons)", (learning._iso(learning.utc_now()),))
            learning._audit(conn, user["id"], "academy_package_published")
        return release_status(conn)
