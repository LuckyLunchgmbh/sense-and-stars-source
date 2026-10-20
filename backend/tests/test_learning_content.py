"""Editorial regression checks for the offline learning-room seed collection."""
from collections import Counter
import importlib
import json
import re
import socket
from urllib.parse import urlsplit
import urllib.request

import pytest

from app import learning_content
from app.learning import LessonCreate


def _words(text):
    return re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", text, flags=re.UNICODE)


def _answer(question_id):
    matches = [question for lesson in learning_content.WORKSPACE_LESSONS
               for question in lesson["quiz"] if question["id"] == question_id]
    assert len(matches) == 1, "A content regression question needs a stable, unique identifier."
    question = matches[0]
    return question["options"][question["correct_index"]]


def test_collection_has_stable_unique_seeds_and_order_without_user_state():
    lessons = learning_content.WORKSPACE_LESSONS
    assert len(lessons) == 12
    assert [lesson["week"] for lesson in lessons] == list(range(5, 17))
    seeds = [lesson["seed_key"] for lesson in lessons]
    assert len(set(seeds)) == 12
    assert all(re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", seed) for seed in seeds)
    assert Counter(lesson["level"] for lesson in lessons) == {
        "foundation": 4, "deepening": 5, "practice": 3,
    }
    forbidden = {"bookmarked", "pinned", "practiced", "reflected", "completed",
                 "available", "status", "user_id", "unlock_at"}
    assert all(not forbidden.intersection(lesson) for lesson in lessons)


@pytest.mark.parametrize("lesson", learning_content.WORKSPACE_LESSONS,
                         ids=lambda lesson: lesson["seed_key"])
def test_every_lesson_meets_the_create_contract_and_editorial_depth(lesson):
    payload = {key: value for key, value in lesson.items() if key != "seed_key"}
    validated = LessonCreate.model_validate(payload)
    assert validated.title == lesson["title"]
    total_words = sum(len(_words(lesson[field]))
                      for field in ("body", "exercise", "reflection_prompt"))
    assert 350 <= total_words <= 550, (lesson["seed_key"], total_words)
    assert len(lesson["body"].split("\n\n")) >= 3
    assert len(_words(lesson["exercise"])) >= 70  # An executable activity, beyond a prompt label.
    assert len(_words(lesson["reflection_prompt"])) >= 15
    assert all(lesson[field].strip() for field in (
        "track", "learning_objective", "exercise", "reflection_prompt", "source_note"))
    assert not re.search(r"<[/!A-Za-z]|^\s*#{1,6}\s", lesson["body"], re.MULTILINE)
    assert lesson["content_version"] == 1


def test_sources_are_public_attributed_and_have_bounded_editorial_roles():
    domains = set()
    for lesson in learning_content.WORKSPACE_LESSONS:
        parsed = urlsplit(lesson["source_url"])
        assert parsed.scheme == "https" and parsed.hostname
        assert not parsed.username and not parsed.password and not parsed.fragment
        domains.add(parsed.hostname)
        note = lesson["source_note"]
        assert lesson["source_url"] in note and lesson["source_title"] in note
        assert "Quelle belegt" in note
        assert "eigene Redaktion" in note
        assert "20.10.2026" in note
    assert {"www.astro.com", "markjonesastrology.com", "www.silkeschaefer.com"} <= domains
    assert any(domain.endswith("who.int") or domain.endswith("paho.org") for domain in domains)


def test_quizzes_are_short_optional_understanding_checks_with_valid_backend_answers():
    question_ids = []
    correct_positions = set()
    for lesson in learning_content.WORKSPACE_LESSONS:
        assert 2 <= len(lesson["quiz"]) <= 3
        for question in lesson["quiz"]:
            assert 2 <= len(question["options"]) <= 4
            assert len(set(question["options"])) == len(question["options"])
            assert type(question["correct_index"]) is int
            assert 0 <= question["correct_index"] < len(question["options"])
            correct_positions.add(question["correct_index"])
            question_ids.append(question["id"])
        # The text must never embed a quiz key or solicit a compulsory passing grade.
        public_text = " ".join(lesson[key] for key in ("body", "exercise", "reflection_prompt"))
        assert "correct_index" not in public_text and "Quiz bestehen" not in public_text
    assert len(question_ids) == len(set(question_ids))
    assert len(correct_positions) > 1
    assert "correct_index" in json.dumps(learning_content.WORKSPACE_LESSONS)


def test_fundamental_geometry_and_element_classification_answers_are_correct():
    # These are subject-matter checks, independent of narrative phrasing.
    assert _answer("symbols_function") == "Planet"
    assert set(_answer("elements_water").split(", ")) == {"Krebs", "Skorpion", "Fische"}
    assert set(_answer("qualities_fixed").split(", ")) == {
        "Stier", "Löwe", "Skorpion", "Wassermann",
    }
    assert "östlichem Horizont" in _answer("asc_geometry")
    assert _answer("aspects_orb") == "2°"
    assert _answer("aspects_trine") == "120°"


def test_spiritual_examples_keep_authority_with_the_participant():
    # Correct responses must model consent, epistemic limits and acceptance of a no.
    assert "Selbstaussage" in _answer("field_evidence")
    assert "eigene" in _answer("intuition_origin").lower()
    assert "verwerfen" in _answer("feedback_no").lower()
    assert "Zustimmung" in _answer("phone_consent")
    assert "Keine" in _answer("journal_proof")
    assert "Quellenrolle" in _answer("sources_roles")


def test_importing_editorial_content_performs_no_network_calls(monkeypatch):
    def offline(*args, **kwargs):
        pytest.fail("Importing bundled lessons must remain offline.")

    monkeypatch.setattr(socket, "create_connection", offline)
    monkeypatch.setattr(urllib.request, "urlopen", offline)
    reloaded = importlib.reload(learning_content)
    assert len(reloaded.WORKSPACE_LESSONS) == 12
