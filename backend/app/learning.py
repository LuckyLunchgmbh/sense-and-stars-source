"""Local, editorial learning workspace. No LLM or private-data egress.

`complete` records the user's explicit read acknowledgement; quizzes are optional.
It cannot prove physical reading, professional qualification or therapeutic value.
Scanner output is source metadata, never automatically publishable instruction.
"""
from datetime import datetime, timezone
import html
import ipaddress
import json
import os
import re
import sqlite3
import time
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request as URLRequest, build_opener
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError, field_validator, model_validator

from .db import get_db
from .security import require_admin, require_staff
from .config import setting

router = APIRouter()
MAX_WEEK = 260
PASS_SCORE = 80
MAX_FEED_BYTES = 512_000
FEED_TIMEOUT = 4.0
MAX_FEED_ENTRIES = 3
RSS_SOURCES = (("NASA – Nachrichten", "https://www.nasa.gov/feed/"),)
PERSONAL_STATE_FIELDS = ("bookmarked", "pinned", "practiced", "reflected")
LESSON_METADATA = {
    "track": "TEXT NOT NULL DEFAULT ''",
    "level": "TEXT NOT NULL DEFAULT 'foundation' CHECK(level IN ('foundation','deepening','practice'))",
    "learning_objective": "TEXT NOT NULL DEFAULT ''",
    "exercise": "TEXT NOT NULL DEFAULT ''",
    "reflection_prompt": "TEXT NOT NULL DEFAULT ''",
    "content_version": "INTEGER NOT NULL DEFAULT 1 CHECK(content_version BETWEEN 1 AND 100000)",
    "source_note": "TEXT NOT NULL DEFAULT ''",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _clean(value: str) -> str:
    value = value.strip()
    if not value or any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ValueError("Bitte einen lesbaren Text ohne Steuerzeichen eingeben.")
    return value


ShortText = Annotated[str, Field(strict=True, min_length=1, max_length=400)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EmptyRequest(StrictModel):
    pass


class QuizQuestion(StrictModel):
    id: Annotated[str, Field(strict=True, pattern=r"^[A-Za-z0-9_-]{1,64}$")]
    question: ShortText
    options: Annotated[list[Annotated[str, Field(strict=True, min_length=1, max_length=300)]], Field(min_length=2, max_length=8)]
    correct_index: StrictInt

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        return _clean(value)

    @field_validator("options")
    @classmethod
    def clean_options(cls, values):
        values = [_clean(value) for value in values]
        if len(set(values)) != len(values):
            raise ValueError("Antwortmöglichkeiten müssen unterschiedlich sein.")
        return values

    @model_validator(mode="after")
    def correct_is_option(self):
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError("Die richtige Antwort muss in den Antwortmöglichkeiten vorkommen.")
        return self


def _source_url(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Quellenadressen dürfen keine Steuerzeichen enthalten.")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Quellen benötigen eine öffentliche HTTPS-Adresse ohne Zugangsdaten.")
    hostname = parsed.hostname.lower()
    if "." not in hostname or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Die Quelle muss öffentlich sein.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None or parsed.port not in (None, 443):
        raise ValueError("Quellen verwenden einen öffentlichen Hostnamen über HTTPS.")
    return value


class LessonCreate(StrictModel):
    title: Annotated[str, Field(strict=True, min_length=1, max_length=160)]
    category: Annotated[str, Field(strict=True, min_length=1, max_length=60)]
    summary: Annotated[str, Field(strict=True, min_length=1, max_length=600)]
    body: Annotated[str, Field(strict=True, min_length=1, max_length=16_000)]
    week: Annotated[StrictInt, Field(ge=1, le=MAX_WEEK)]
    source_url: Annotated[str, Field(strict=True, min_length=1, max_length=2048)]
    source_title: Annotated[str, Field(strict=True, min_length=1, max_length=200)]
    quiz: Annotated[list[QuizQuestion], Field(min_length=1, max_length=20)]
    track: Annotated[str, Field(strict=True, max_length=80)] = ""
    level: Literal["foundation", "deepening", "practice"] = "foundation"
    learning_objective: Annotated[str, Field(strict=True, max_length=1000)] = ""
    exercise: Annotated[str, Field(strict=True, max_length=3000)] = ""
    reflection_prompt: Annotated[str, Field(strict=True, max_length=1000)] = ""
    content_version: Annotated[StrictInt, Field(ge=1, le=100000)] = 1
    source_note: Annotated[str, Field(strict=True, max_length=2000)] = ""

    @field_validator("title", "category", "summary", "body", "source_title")
    @classmethod
    def clean_text(cls, value):
        return _clean(value)

    @field_validator("source_url")
    @classmethod
    def validate_source(cls, value):
        return _source_url(value)

    @field_validator("track", "learning_objective", "exercise", "reflection_prompt", "source_note")
    @classmethod
    def clean_optional_text(cls, value):
        return _clean(value) if value else value

    @model_validator(mode="after")
    def unique_questions(self):
        if len({question.id for question in self.quiz}) != len(self.quiz):
            raise ValueError("Fragen benötigen eindeutige Kennungen.")
        return self


class QuizSubmission(StrictModel):
    answers: Annotated[dict[str, StrictInt], Field(min_length=1, max_length=20)]


class ScanRequest(StrictModel):
    simulate: StrictBool = True


class PersonalStateUpdate(StrictModel):
    bookmarked: StrictBool | None = None
    pinned: StrictBool | None = None
    practiced: StrictBool | None = None
    reflected: StrictBool | None = None

    @model_validator(mode="after")
    def explicit_boolean_required(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Mindestens einen Zustand als true oder false angeben.")
        return self


NoteTitle = Annotated[str, Field(strict=True, min_length=1, max_length=160)]
NoteBody = Annotated[str, Field(strict=True, min_length=1, max_length=12000)]


class NotebookCreate(StrictModel):
    lesson_id: Annotated[StrictInt, Field(ge=1)] | None = None
    title: NoteTitle
    body: NoteBody

    @field_validator("title", "body")
    @classmethod
    def readable_text(cls, value):
        return _clean(value)


class NotebookUpdate(StrictModel):
    title: NoteTitle | None = None
    body: NoteBody | None = None

    @field_validator("title", "body")
    @classmethod
    def readable_text(cls, value):
        return _clean(value) if value is not None else value

    @model_validator(mode="after")
    def explicit_text_required(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Mindestens einen neuen Titel oder Inhalt angeben.")
        return self


# Short original editorial texts. The cited sources have bounded roles; practical
# conversation examples and spiritual associations are labeled editorial choices.
SEED_LESSONS = (
    {
        "title": "Ankommen, zuhören und Grenzen achten", "category": "Beratungspraxis", "week": 1,
        "summary": "Ein freiwilliger Einstieg, empathisches Nachfragen und ein klarer Beratungsrahmen.",
        "body": "Redaktioneller Praxisimpuls · Sense & Stars, 20.10.2026\n\n"
        "Die WHO beschreibt im Selbsthilfeleitfaden ‚Doing What Matters in Times of Stress‘ unter anderem "
        "Grounding: gegenwärtige Gedanken und Gefühle bemerken, Körperkontakt wahrnehmen und sich der Umgebung zuwenden. "
        "Der Leitfaden ist keine Quelle für Astrologie.\n\n"
        "Eigenständiges Sense-&-Stars-Alltagsbeispiel: Frage zu Beginn ‚Möchtest du erst kurz ankommen oder direkt erzählen?‘ "
        "Bei Zustimmung kann die Person einen Gegenstand im Raum betrachten, ein Geräusch bemerken und den Kontakt "
        "zur Sitzfläche oder zum Boden wahrnehmen. Augen und Atmung dürfen so bleiben, wie es angenehm ist. "
        "Ein Nein, eine Pause oder ein Themenwechsel sind jederzeit möglich. Die Einladung verspricht keine bestimmte Wirkung.\n\n"
        "Zuhören üben: Eine Person sagt ‚Ich weiß nicht, ob ich die Stelle wechseln soll.‘ Antworte zunächst "
        "‚Was macht diese Entscheidung gerade schwierig?‘ Fasse danach in eigenen Worten zusammen und frage "
        "‚Habe ich dich richtig verstanden?‘ Erkläre Gefühle nicht vorschnell aus einem Radix.\n\n"
        "Grenzen benennen: ‚Wir können deine Fragen spirituell reflektieren. Ich stelle keine Diagnose und biete "
        "hier keine medizinische oder psychotherapeutische Behandlung an.‘ Bei Anliegen außerhalb des eigenen "
        "Rahmens wird dieser offengelegt. Dieses redaktionelle Gesprächsbeispiel ist keine WHO-Empfehlung "
        "für Sense & Stars und kein Nachweis einer Beratungskompetenz; das Quiz prüft nur den Lerntext.",
        "source_url": "https://www.who.int/publications/i/item/9789240003927",
        "source_title": "WHO · Doing What Matters in Times of Stress (2020), Abschnitt Grounding",
        "quiz": [
            {"id": "q1", "question": "Wie reagierst du auf ein Nein zur Einstiegsübung?", "options": ["Das Nein achten und nach dem gewünschten Einstieg fragen", "Die Übung trotzdem durchführen"], "correct_index": 0},
            {"id": "q2", "question": "Welche Antwort lässt Raum für die eigene Sicht der Person?", "options": ["Dein Radix beweist, warum du zweifelst", "Was macht die Entscheidung gerade schwierig?"], "correct_index": 1},
        ],
    },
    {
        "title": "Häuser als offene Gesprächslandkarte", "category": "Astro-Grundlagen", "week": 2,
        "summary": "Berechnete Häuser von spirituellen Themen und persönlichen Aussagen unterscheiden.",
        "body": "Redaktioneller Grundlagenimpuls · Sense & Stars, 20.10.2026\n\n"
        "Die Swiss-Ephemeris-Dokumentation beschreibt unterschiedliche Berechnungsverfahren für Häuser. "
        "Zeitpunkt, geografischer Ort und gewähltes Häusersystem gehören zur Berechnung. Sense & Stars V1 verwendet "
        "Placidus und gibt das System im Ergebnis an. Die mathematische Dokumentation belegt keine Persönlichkeitsdeutung.\n\n"
        "Für dieses spirituelle Gesprächsbeispiel nutzt Sense & Stars folgende konventionelle Themenanker: "
        "Haus 1 – Auftreten und Selbstbild; Haus 4 – Zuhause und Zugehörigkeit; Haus 7 – Begegnung und Beziehungen; "
        "Haus 10 – öffentliche Rolle und berufliche Ausrichtung. Diese Zuordnungen sind Deutungskonventionen, "
        "keine wissenschaftlichen oder psychologischen Befunde.\n\n"
        "Praktisches Beispiel zu Haus 7: Statt ‚Du hast Beziehungsprobleme‘ fragst du ‚Welche Formen von "
        "Zusammenarbeit beschäftigen dich gerade – falls du dieses Thema aufgreifen möchtest?‘ "
        "Zurück zu Haus 4 könnte die offene Frage lauten: ‚Was bedeutet Zuhause für dich im Moment?‘ "
        "Die Person entscheidet, ob ein Anker passt, und ihre eigene Erfahrung bleibt maßgeblich.\n\n"
        "Mini-Übung: Wähle einen der vier Anker und formuliere eine offene Frage ohne Vorhersage oder Etikett. "
        "Trenne in deinen Notizen die berechnete Hausposition, deine spirituelle Frage und die tatsächliche "
        "Antwort der Person. Aus Hauspositionen werden keine Diagnosen, Behandlungen oder Heilversprechen abgeleitet.",
        "source_url": "https://www.astro.com/swisseph/swephprg.htm",
        "source_title": "Astrodienst · Swiss Ephemeris Programming Interface, Kapitel 15: House cusp calculation",
        "quiz": [
            {"id": "q1", "question": "Was belegt eine berechnete Hausposition?", "options": ["Eine psychologische Diagnose", "Eine Position innerhalb des angegebenen Berechnungsverfahrens"], "correct_index": 1},
            {"id": "q2", "question": "Wie nutzt du einen spirituellen Themenanker?", "options": ["Als freiwillige offene Frage, die auch nicht passen darf", "Als unumstößliche Aussage über die Person"], "correct_index": 0},
        ],
    },
    {
        "title": "Geburtszeit: Herkunft und Unsicherheit", "category": "Sorgfältige Praxis", "week": 3,
        "summary": "Ortszeit, Zeitzone und unbekannte Angaben nachvollziehbar festhalten.",
        "body": "Redaktioneller Grundlagenimpuls · Sense & Stars, 20.10.2026\n\n"
        "Die IANA-Zeitzonendatenbank dokumentiert die Geschichte lokaler Uhrzeiten ausgewählter Orte. "
        "Sie wird aktualisiert, wenn sich Regeln wie UTC-Abstände oder Sommerzeit ändern. "
        "Eine Ortszeit ist deshalb nicht allein durch eine heutige Zeitzonenabkürzung erklärt.\n\n"
        "In Sense & Stars hältst du den angegebenen Geburtsort und die Geburtszeit mit ihrer Herkunft fest. "
        "Bei widersprüchlichen oder fehlenden Angaben wird nicht still geraten. "
        "Die App fordert bei doppelt vorkommenden Ortszeiten eine Auswahl; eine nicht existente Ortszeit wird abgelehnt.\n\n"
        "Reflexionsfrage: Welche Angabe weiß ich sicher, welche wurde nur geschätzt? Kennzeichne die Schätzung. "
        "Eine präzise Berechnung macht eine ungesicherte Eingabe nicht verlässlich und belegt keine astrologische Wirkung.",
        "source_url": "https://www.iana.org/time-zones", "source_title": "IANA · Time Zone Database",
        "quiz": [
            {"id": "q1", "question": "Was ist bei einer geschätzten Geburtszeit sinnvoll?", "options": ["Die Unsicherheit kennzeichnen", "Die Schätzung als exakt ausgeben"], "correct_index": 0},
            {"id": "q2", "question": "Warum ist das historische Datum für Ortszeiten relevant?", "options": ["Uhrzeitregeln waren weltweit immer gleich", "UTC-Abstände und Sommerzeitregeln können sich ändern"], "correct_index": 1},
        ],
    },
)


def init_learning(conn: sqlite3.Connection):
    """Idempotent schema/seed initialization; the caller owns its transaction."""
    # Individual statements avoid executescript's implicit commit of caller writes.
    statements = (
        """CREATE TABLE IF NOT EXISTS learning_lessons(
        id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
        summary TEXT NOT NULL, body TEXT NOT NULL, week INTEGER NOT NULL CHECK(week BETWEEN 1 AND 260),
        source_url TEXT NOT NULL, source_title TEXT NOT NULL, quiz TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('draft','published')) DEFAULT 'draft',
        source_kind TEXT NOT NULL DEFAULT 'editorial', seed_key TEXT UNIQUE, scan_key TEXT UNIQUE,
        created_at TEXT NOT NULL, published_at TEXT)""",
        "CREATE UNIQUE INDEX IF NOT EXISTS learning_published_week ON learning_lessons(week) WHERE status='published'",
        """CREATE TABLE IF NOT EXISTS learning_progress(
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lesson_id INTEGER NOT NULL REFERENCES learning_lessons(id) ON DELETE CASCADE,
        quiz_score INTEGER NOT NULL DEFAULT 0 CHECK(quiz_score BETWEEN 0 AND 100),
        quiz_passed INTEGER NOT NULL DEFAULT 0 CHECK(quiz_passed IN (0,1)),
        quiz_passed_at TEXT, completed_at TEXT, PRIMARY KEY(user_id,lesson_id))""",
        """CREATE TABLE IF NOT EXISTS learning_scans(
        id INTEGER PRIMARY KEY, iso_week TEXT NOT NULL, mode TEXT NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id), created INTEGER NOT NULL,
        sources TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(iso_week,mode))""",
        """CREATE TABLE IF NOT EXISTS learning_audit(
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
        action TEXT NOT NULL, lesson_id INTEGER REFERENCES learning_lessons(id), created_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS learning_notebook(
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lesson_id INTEGER REFERENCES learning_lessons(id), lesson_title_snapshot TEXT,
        lesson_version_snapshot INTEGER, lesson_source_url_snapshot TEXT, lesson_source_title_snapshot TEXT,
        title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 160),
        body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 12000),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS learning_notebook_owner ON learning_notebook(user_id,updated_at,id)",
    )
    for statement in statements:
        conn.execute(statement)
    # ALTER only missing columns: existing IDs, editorial text and quiz history
    # remain untouched, including when upgrading a pre-workspace database.
    for table, additions in (
        ("learning_lessons", LESSON_METADATA),
        ("learning_progress", {
            **{key: f"INTEGER NOT NULL DEFAULT 0 CHECK({key} IN (0,1))" for key in PERSONAL_STATE_FIELDS},
            "quiz_attempted": "INTEGER NOT NULL DEFAULT 0 CHECK(quiz_attempted IN (0,1))",
        }),
    ):
        present = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, definition in additions.items():
            if column not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                if table == "learning_progress" and column == "quiz_attempted":
                    # Every old progress row was created by a quiz submission.
                    conn.execute("UPDATE learning_progress SET quiz_attempted=1")

    # Imported here so the existing application/module import stays independent
    # of optional content tooling. All authored content is validated before use.
    from .learning_content import WORKSPACE_LESSONS

    seeds = [(dict(lesson, seed_key=f"editorial-v1-{index}"), "published") for index, lesson in enumerate(SEED_LESSONS, 1)]
    workspace_status = "published" if setting("DEMO") == "1" else "draft"
    seeds.extend((lesson, workspace_status) for lesson in WORKSPACE_LESSONS)
    previous_seed_week = 0
    for lesson, status in seeds:
        data = dict(lesson)
        seed_key = data.pop("seed_key")
        if not isinstance(seed_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", seed_key):
            raise ValueError("Redaktionelle Startlektionen benötigen eine stabile Kennung.")
        existing = conn.execute("SELECT week FROM learning_lessons WHERE seed_key=?", (seed_key,)).fetchone()
        if existing:
            previous_seed_week = max(previous_seed_week, existing["week"])
            continue
        validated = LessonCreate.model_validate(data)
        week = max(validated.week, previous_seed_week + 1)
        # Reserve every existing editorial/scanner position, including drafts:
        # a new seed must not block a later explicit publication. Search gaps
        # rather than jumping beyond a distant published position.
        while week <= MAX_WEEK and conn.execute("SELECT 1 FROM learning_lessons WHERE week=?", (week,)).fetchone():
            week += 1
        if week > MAX_WEEK:
            raise ValueError("Nicht genug freie Sortierplätze für die Startlektionen; vorhandene Inhalte bleiben erhalten.")
        _insert_editorial(conn, validated.model_copy(update={"week": week}), status=status, seed_key=seed_key)
        previous_seed_week = week
    from .learning_updates import init_learning_updates
    init_learning_updates(conn)


def _insert_editorial(conn, lesson: LessonCreate, *, status="draft", seed_key=None):
    values = lesson.model_dump()
    values["quiz"] = _json(values["quiz"])
    values.update(status=status, seed_key=seed_key, created_at=_iso(utc_now()),
                  published_at=_iso(utc_now()) if status == "published" else None)
    columns = ",".join(values)
    placeholders = ",".join("?" for _ in values)
    return conn.execute(f"INSERT INTO learning_lessons({columns}) VALUES({placeholders})", tuple(values.values()))


def _audit(conn, user_id: int, action: str, lesson_id: int | None = None):
    conn.execute("INSERT INTO learning_audit(user_id,action,lesson_id,created_at) VALUES(?,?,?,?)",
                 (user_id, action, lesson_id, _iso(utc_now())))


def _progress(conn, user_id):
    return {row["lesson_id"]: dict(row) for row in conn.execute("SELECT * FROM learning_progress WHERE user_id=?", (user_id,))}


def _lesson_state(row, progress):
    return {
        "available": row["status"] == "published", "completed": bool(progress.get("completed_at")),
        **{key: bool(progress.get(key, 0)) for key in PERSONAL_STATE_FIELDS},
    }


def _lesson_json(row, state=None, admin=False):
    state = state or _lesson_state(row, {})
    visible = admin or state["available"]
    quiz = json.loads(row["quiz"]) if visible else []
    if not admin:
        quiz = [{key: value for key, value in question.items() if key != "correct_index"} for question in quiz]
    return {
        "id": row["id"], "title": row["title"], "category": row["category"], "summary": row["summary"],
        "body": row["body"] if visible else "", "week": row["week"],
        "source_url": row["source_url"], "source_title": row["source_title"], "status": row["status"],
        "available": state["available"], "completed": state["completed"], "quiz": quiz,
        "source_kind": row["source_kind"],
        **{key: row[key] for key in ("academy_course_id", "academy_key") if key in row.keys()},
        **{key: row[key] for key in LESSON_METADATA},
        **{key: state[key] for key in PERSONAL_STATE_FIELDS},
    }


def _published(conn):
    return conn.execute("SELECT * FROM learning_lessons WHERE status='published' ORDER BY week,id").fetchall()


def _require_available(conn, user_id, lesson_id):
    lesson = conn.execute("SELECT * FROM learning_lessons WHERE id=? AND status='published'", (lesson_id,)).fetchone()
    if lesson is None:
        raise HTTPException(404, "Diese veröffentlichte Lektion wurde nicht gefunden.")
    progress = _progress(conn, user_id)
    return lesson, progress.get(lesson_id, {})


@router.get("/api/learning")
def learning_path(request: Request):
    user = require_staff(request)
    with get_db() as conn:
        rows = _published(conn)
        progress = _progress(conn, user["id"])
        state = {row["id"]: _lesson_state(row, progress.get(row["id"], {})) for row in rows}
    return {
        "lessons": [_lesson_json(row, state[row["id"]]) for row in rows],
        "progress": {
            "completed_ids": [row["id"] for row in rows if state[row["id"]]["completed"]],
            "quiz_scores": {str(row["id"]): progress[row["id"]]["quiz_score"] for row in rows
                            if progress.get(row["id"], {}).get("quiz_attempted")},
        },
        "next_unlock_at": None,
    }


def _notebook_json(row):
    return {key: row[key] for key in (
        "id", "user_id", "lesson_id", "lesson_title_snapshot", "lesson_version_snapshot",
        "title", "body", "created_at", "updated_at",
    )}


def _own_notes(conn, user_id):
    return conn.execute("SELECT * FROM learning_notebook WHERE user_id=? ORDER BY updated_at DESC,id DESC", (user_id,)).fetchall()


# Keep the literal notebook paths ahead of all lesson-id routes.
@router.get("/api/learning/notebook")
def notebook(request: Request):
    user = require_staff(request)
    with get_db() as conn:
        return [_notebook_json(row) for row in _own_notes(conn, user["id"])]


@router.get("/api/learning/notebook/export")
def export_notebook(request: Request):
    user = require_staff(request)
    with get_db() as conn:
        rows = _own_notes(conn, user["id"])
    lines = ["# Mein Sense & Stars-Notizbuch", "", "Privater lokaler Export. Eigene Notizen sind keine Qualifikationsnachweise.", ""]
    for row in rows:
        lines.extend([f"## {' '.join(row['title'].split())}", "", f"Erstellt: {row['created_at']}", f"Bearbeitet: {row['updated_at']}", ""])
        if row["lesson_id"] is not None:
            lines.extend([
                f"Lektion {row['lesson_id']}: {' '.join(row['lesson_title_snapshot'].split())} · Version {row['lesson_version_snapshot']}",
                f"Quelle des gespeicherten Lernstands: {' '.join(row['lesson_source_title_snapshot'].split())}",
                row["lesson_source_url_snapshot"], "",
            ])
        else:
            lines.extend(["Freie Notiz ohne Lektionsverknüpfung.", ""])
        lines.extend([row["body"], "", "---", ""])
    return {"filename": f"sense-and-stars-notizbuch-{utc_now().date().isoformat()}.md", "content": "\n".join(lines)}


@router.post("/api/learning/notebook")
def create_notebook_note(payload: NotebookCreate, request: Request):
    user = require_staff(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lesson = None
        if payload.lesson_id is not None:
            lesson, _ = _require_available(conn, user["id"], payload.lesson_id)
        now = _iso(utc_now())
        cursor = conn.execute(
            """INSERT INTO learning_notebook(user_id,lesson_id,lesson_title_snapshot,lesson_version_snapshot,
            lesson_source_url_snapshot,lesson_source_title_snapshot,title,body,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (user["id"], payload.lesson_id, lesson["title"] if lesson else None,
             lesson["content_version"] if lesson else None, lesson["source_url"] if lesson else None,
             lesson["source_title"] if lesson else None, payload.title, payload.body, now, now),
        )
        _audit(conn, user["id"], "notebook_created", payload.lesson_id)
        row = conn.execute("SELECT * FROM learning_notebook WHERE id=? AND user_id=?", (cursor.lastrowid, user["id"])).fetchone()
    return _notebook_json(row)


@router.patch("/api/learning/notebook/{note_id}")
def update_notebook_note(note_id: int, payload: NotebookUpdate, request: Request):
    user = require_staff(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM learning_notebook WHERE id=? AND user_id=?", (note_id, user["id"])).fetchone()
        if row is None:
            raise HTTPException(404, "Diese Notiz wurde nicht gefunden.")
        changes = payload.model_dump(exclude_unset=True)
        changes["updated_at"] = _iso(utc_now())
        assignments = ",".join(f"{key}=?" for key in changes)
        conn.execute(f"UPDATE learning_notebook SET {assignments} WHERE id=? AND user_id=?",
                     (*changes.values(), note_id, user["id"]))
        _audit(conn, user["id"], "notebook_updated", row["lesson_id"])
        updated = conn.execute("SELECT * FROM learning_notebook WHERE id=? AND user_id=?", (note_id, user["id"])).fetchone()
    return _notebook_json(updated)


@router.patch("/api/learning/{lesson_id}/state")
def update_personal_state(lesson_id: int, payload: PersonalStateUpdate, request: Request):
    user = require_staff(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lesson, _ = _require_available(conn, user["id"], lesson_id)
        changes = payload.model_dump(exclude_unset=True)
        columns = ",".join(changes)
        placeholders = ",".join("?" for _ in changes)
        assignments = ",".join(f"{key}=excluded.{key}" for key in changes)
        conn.execute(
            f"INSERT INTO learning_progress(user_id,lesson_id,{columns}) VALUES(?,?,{placeholders}) "
            f"ON CONFLICT(user_id,lesson_id) DO UPDATE SET {assignments}",
            (user["id"], lesson_id, *(int(value) for value in changes.values())),
        )
        _audit(conn, user["id"], "personal_state_updated", lesson_id)
        progress = _progress(conn, user["id"])[lesson_id]
    return _lesson_json(lesson, _lesson_state(lesson, progress))


def _is_academy_lesson(lesson_id):
    with get_db() as conn:
        row = conn.execute("SELECT seed_key FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone()
        return bool(row and (row["seed_key"] or "").startswith("academy-"))


@router.post("/api/learning/{lesson_id}/quiz")
def submit_quiz(lesson_id: int, payload: QuizSubmission, request: Request, preview: bool = False):
    user = require_staff(request)
    if _is_academy_lesson(lesson_id):
        from .academy import submit_quiz as academy_quiz
        result = academy_quiz(lesson_id, payload, request, preview=preview)
        return {"score": result["score"], "passed": result["passed"],
                "feedback": "Quiz bestanden." if result["passed"] else "Du kannst freiwillig erneut üben oder weiterlesen."}
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lesson, _ = _require_available(conn, user["id"], lesson_id)
        quiz = json.loads(lesson["quiz"])
        if set(payload.answers) != {question["id"] for question in quiz}:
            raise HTTPException(422, "Beantworte genau alle Fragen der Lektion.")
        if any(not 0 <= payload.answers[q["id"]] < len(q["options"]) for q in quiz):
            raise HTTPException(422, "Jede Antwort muss eine vorhandene Antwortmöglichkeit auswählen.")
        correct = sum(payload.answers[q["id"]] == q["correct_index"] for q in quiz)
        score = round(100 * correct / len(quiz))
        passed = score >= PASS_SCORE
        conn.execute(
            """INSERT INTO learning_progress(user_id,lesson_id,quiz_score,quiz_passed,quiz_passed_at,quiz_attempted)
            VALUES(?,?,?,?,?,1) ON CONFLICT(user_id,lesson_id) DO UPDATE SET quiz_attempted=1,
            quiz_score=MAX(quiz_score,excluded.quiz_score), quiz_passed=MAX(quiz_passed,excluded.quiz_passed),
            quiz_passed_at=COALESCE(learning_progress.quiz_passed_at,excluded.quiz_passed_at)""",
            (user["id"], lesson_id, score, int(passed), _iso(utc_now()) if passed else None),
        )
        _audit(conn, user["id"], "quiz_passed" if passed else "quiz_attempted", lesson_id)
    feedback = ("Quiz bestanden. Es prüft nur diesen Lerntext; die Lesebestätigung ist unabhängig davon."
                if passed else f"Quiz noch nicht bestanden; die Schwelle beträgt {PASS_SCORE} %. Du kannst freiwillig erneut üben oder weiterlesen.")
    return {"score": score, "passed": passed, "feedback": feedback}


@router.post("/api/learning/{lesson_id}/complete")
def complete_lesson(lesson_id: int, payload: EmptyRequest, request: Request, preview: bool = False):
    user = require_staff(request)
    if _is_academy_lesson(lesson_id):
        from .academy import complete as academy_complete
        academy_complete(lesson_id, payload, request, preview=preview)
        return {"ok": True}
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _, progress = _require_available(conn, user["id"], lesson_id)
        if not progress.get("completed_at"):
            conn.execute("""INSERT INTO learning_progress(user_id,lesson_id,completed_at) VALUES(?,?,?)
                ON CONFLICT(user_id,lesson_id) DO UPDATE SET completed_at=excluded.completed_at""",
                         (user["id"], lesson_id, _iso(utc_now())))
            _audit(conn, user["id"], "read_and_completed", lesson_id)
    return {"ok": True}


@router.get("/api/admin/lessons")
def admin_lessons(request: Request):
    require_admin(request)
    with get_db() as conn:
        return [_lesson_json(row, admin=True) for row in conn.execute("SELECT * FROM learning_lessons ORDER BY week,id")]


@router.post("/api/admin/lessons")
def create_lesson(payload: LessonCreate, request: Request):
    user = require_admin(request)
    with get_db() as conn:
        cursor = _insert_editorial(conn, payload)
        _audit(conn, user["id"], "lesson_drafted", cursor.lastrowid)
        row = conn.execute("SELECT * FROM learning_lessons WHERE id=?", (cursor.lastrowid,)).fetchone()
    return _lesson_json(row, admin=True)


@router.post("/api/admin/lessons/{lesson_id}/publish")
def publish_lesson(lesson_id: int, payload: EmptyRequest, request: Request):
    user = require_admin(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Diese Lektion wurde nicht gefunden.")
        if (row["seed_key"] or "").startswith("academy-"):
            raise HTTPException(409, "Der Akademie-Erstbestand wird ausschließlich als geprüftes Gesamtpaket freigegeben.")
        if row["status"] == "published":
            return _lesson_json(row, admin=True)
        if row["source_kind"] != "editorial":
            raise HTTPException(409, "Dieser Scanner-Entwurf enthält nur Quellenmetadaten. Erstelle nach Quellenprüfung eine redigierte Lektion mit eigenem Text und Quiz.")
        try:
            LessonCreate.model_validate({key: json.loads(row[key]) if key == "quiz" else row[key] for key in LessonCreate.model_fields})
        except (ValidationError, ValueError, TypeError):
            raise HTTPException(409, "Der Entwurf benötigt vollständigen Text, Quelle und ein gültiges Quiz.")
        if conn.execute("SELECT 1 FROM learning_lessons WHERE status='published' AND week=?", (row["week"],)).fetchone():
            raise HTTPException(409, "Dieser Sortierplatz ist bereits durch eine veröffentlichte Lektion belegt.")
        conn.execute("UPDATE learning_lessons SET status='published',published_at=? WHERE id=?", (_iso(utc_now()), lesson_id))
        _audit(conn, user["id"], "lesson_published", lesson_id)
        row = conn.execute("SELECT * FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone()
    return _lesson_json(row, admin=True)


@router.patch("/api/admin/lessons/{lesson_id}")
def edit_lesson(lesson_id: int, payload: LessonCreate, request: Request):
    """Deliberate editorial conversion; publishing remains a separate action."""
    user = require_admin(request)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Dieser Entwurf wurde nicht gefunden.")
        if (row["seed_key"] or "").startswith("academy-"):
            raise HTTPException(409, "Akademie-Lektionen werden im zusammengehörigen Kurspaket redigiert.")
        if row["status"] != "draft":
            raise HTTPException(409, "Veröffentlichte Lektionen werden hier nicht überschrieben. Erstelle eine neue Fassung.")
        if row["source_kind"] != "editorial" and (payload.body == row["body"] or payload.title.startswith("Rechercheentwurf")):
            raise HTTPException(409, "Ersetze den Rechercheentwurf durch einen eigenen geprüften Lehrtext mit passendem Titel und Verständnischeck, bevor du ihn redaktionell speicherst.")
        values = payload.model_dump()
        values["quiz"] = _json(values["quiz"])
        conn.execute("UPDATE learning_lessons SET " + ",".join(f"{key}=?" for key in values) + ",source_kind='editorial' WHERE id=?", (*values.values(), lesson_id))
        _audit(conn, user["id"], "lesson_editorially_reviewed", lesson_id)
        row = conn.execute("SELECT * FROM learning_lessons WHERE id=?", (lesson_id,)).fetchone()
    return _lesson_json(row, admin=True)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        # Do not follow a redirect outside (or even inside) the fixed source list.
        raise ValueError("Weiterleitungen werden beim Quellenabruf nicht verfolgt.")


def _plain_text(value: str, limit: int) -> str:
    value = html.unescape(re.sub(r"<[^>]*>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _fetch_rss(source_url: str) -> list[dict]:
    """Only fixed, public feed URLs; never fetch entry links or arbitrary input."""
    if source_url not in {url for _, url in RSS_SOURCES}:
        raise ValueError("Nicht konfigurierte Quellen werden nicht abgerufen.")
    deadline = time.monotonic() + FEED_TIMEOUT
    opener = build_opener(_NoRedirect())
    request = URLRequest(source_url, headers={"User-Agent": "Sense-And-Stars-local/1.1", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with opener.open(request, timeout=FEED_TIMEOUT) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_FEED_BYTES:
            raise ValueError("Der Feed überschreitet die zulässige Größe.")
        data = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError("Die Zeitgrenze für den Quellenabruf ist erreicht.")
            chunk = response.read1(min(16_384, MAX_FEED_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_FEED_BYTES:
                raise ValueError("Der Feed überschreitet die zulässige Größe.")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML mit Dokumenttyp- oder Entitätsdefinition ist nicht zulässig.")
    return _parse_rss(bytes(data))


def _parse_rss(data: bytes) -> list[dict]:
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("Der Feed ist zu groß.")
    # Accept UTF-8 only, so UTF-16/32 byte layouts cannot hide DTD/entity tokens
    # from the pre-parser check. No untrusted XML reaches the parser first.
    text = data.decode("utf-8-sig", errors="strict")
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("Der Feed ist zu groß oder enthält unzulässige XML-Definitionen.")
    root = ET.fromstring(text)
    entries = root.findall("./channel/item")
    atom = {"atom": "http://www.w3.org/2005/Atom"}
    entries += root.findall("./atom:entry", atom)
    result = []
    seen = set()
    for entry in entries:
        title = _plain_text(entry.findtext("title") or entry.findtext("atom:title", namespaces=atom) or "", 160)
        link = entry.findtext("link")
        if not link:
            atom_links = entry.findall("atom:link", atom)
            link = next((item.get("href") for item in atom_links if item.get("rel", "alternate") == "alternate"), None)
        if not title or not link:
            continue
        try:
            link = _source_url(link.strip())
        except ValueError:
            continue
        if link in seen:
            continue
        seen.add(link)
        excerpt = _plain_text(entry.findtext("description") or entry.findtext("atom:summary", namespaces=atom) or "", 400)
        result.append({"title": title, "url": link, "excerpt": excerpt})
        if len(result) == MAX_FEED_ENTRIES:
            break
    return result


def _scanner_draft(conn, *, title, body, source_url, source_title, week, scan_key, source_kind):
    return conn.execute(
        """INSERT OR IGNORE INTO learning_lessons(title,category,summary,body,week,source_url,
        source_title,quiz,status,source_kind,scan_key,created_at)
        VALUES(?,?,?,?,?,?,?,'[]','draft',?,?,?)""",
        (title, "Quellenprüfung", "Quellenmetadaten zur redaktionellen Prüfung; keine freigegebene Lektion.",
         body, week, source_url, source_title, source_kind, scan_key, _iso(utc_now())),
    )


@router.post("/api/admin/scan")
def scan_sources(payload: ScanRequest, request: Request):
    user = require_admin(request)
    mode = "simulation" if payload.simulate else "rss"
    local_date = utc_now().astimezone(ZoneInfo("Europe/Berlin")).date()
    year, week_number, _ = local_date.isocalendar()
    iso_week = f"{year}-W{week_number:02d}"
    with get_db() as conn:
        previous = conn.execute("SELECT * FROM learning_scans WHERE iso_week=? AND mode=?", (iso_week, mode)).fetchone()
        if previous:
            return {"mode": mode, "created": 0, "message": f"{iso_week} wurde in diesem Modus bereits geprüft; keine Duplikate.", "sources": json.loads(previous["sources"])}
    sources = []
    candidates = []
    if payload.simulate:
        source_title, source_url = RSS_SOURCES[0]
        sources.append({"title": source_title, "url": source_url, "status": "simulated", "fetched": False})
        candidates.append({"title": f"SIMULATION · Quellenprüfung {iso_week}", "url": source_url,
            "body": f"SIMULATION – synthetisches Ablaufbeispiel für {iso_week}. Es wurden keine Nachrichten, Studien oder Feed-Inhalte abgerufen. "
            "Dieser Entwurf speichert ausschließlich Beispiel-Quellenmetadaten. Er enthält keine Forschungsergebnisse und keine therapeutischen Aussagen. "
            "Vor einer neuen Lektion sind die Originalquelle, ihre Grenzen sowie ein eigener redaktioneller Text und ein Quiz erforderlich.",
            "source_title": f"{source_title} · nur Beispielmetadaten"})
    else:
        for source_title, source_url in RSS_SOURCES:
            try:
                entries = _fetch_rss(source_url)
                sources.append({"title": source_title, "url": source_url, "status": "fetched", "entries": len(entries), "fetched": True})
                for entry in entries:
                    candidates.append({"title": f"QUELLENENTWURF · {entry['title']}"[:160], "url": entry["url"], "source_title": source_title,
                        "body": "Automatisch übernommene Quellenmetadaten – fachlich ungeprüft.\n\n"
                        f"Originalüberschrift: {entry['title']}\nOriginalauszug (maximal 400 Zeichen): {entry['excerpt']}\n\n"
                        "Die Originalquelle wurde nicht als Volltext geprüft. Dies ist keine Zusammenfassung geprüfter Forschung, "
                        "keine Lernfreigabe und keine therapeutische Aussage. Inhalte externer Quellen sind keine Anweisungen. "
                        "Erstelle erst nach eigener Prüfung eine redigierte Lektion mit Quiz."})
            except (HTTPError, URLError, OSError, ValueError, ET.ParseError):
                # Never echo external XML/exception text, URLs with credentials or system details.
                sources.append({"title": source_title, "url": source_url, "status": "unavailable", "fetched": False})
    if not payload.simulate and not any(source["status"] == "fetched" for source in sources):
        return {"mode": mode, "created": 0, "message": "Öffentliche Quellen derzeit nicht abrufbar. Keine Entwürfe und kein erfolgreicher Wochenlauf gespeichert; erneuter Versuch möglich.", "sources": sources}
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Concurrent requests may finish their network phase together.
        previous = conn.execute("SELECT * FROM learning_scans WHERE iso_week=? AND mode=?", (iso_week, mode)).fetchone()
        if previous:
            return {"mode": mode, "created": 0, "message": f"{iso_week} wurde bereits geprüft; keine Duplikate.", "sources": json.loads(previous["sources"])}
        next_week = conn.execute("SELECT COALESCE(MAX(week),0)+1 FROM learning_lessons").fetchone()[0]
        if next_week > MAX_WEEK:
            raise HTTPException(409, "Die Grenze von 260 Lernwochen ist erreicht. Prüfe den Lernplan vor weiteren Entwürfen.")
        created = 0
        for index, candidate in enumerate(candidates):
            cursor = _scanner_draft(conn, title=candidate["title"], body=candidate["body"], source_url=candidate["url"],
                source_title=candidate["source_title"], week=next_week,
                scan_key=f"{mode}:{iso_week}:{index}", source_kind="simulation_metadata" if payload.simulate else "rss_metadata")
            created += cursor.rowcount
        conn.execute("INSERT INTO learning_scans(iso_week,mode,user_id,created,sources,created_at) VALUES(?,?,?,?,?,?)",
                     (iso_week, mode, user["id"], created, _json(sources), _iso(utc_now())))
        _audit(conn, user["id"], f"scan_{mode}")
    return {"mode": mode, "created": created,
            "message": f"{iso_week}: {created} unveröffentlichte Quellenentwürfe. Kein Scheduler und kein KI-Dienst wurden gestartet. Fachliche Redaktion und bewusste Admin-Freigabe bleiben erforderlich.",
            "sources": sources}


from .learning_updates import router as updates_router
router.include_router(updates_router)
