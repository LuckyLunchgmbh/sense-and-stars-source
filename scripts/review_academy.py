#!/usr/bin/env python3
"""Build a private, offline-readable editorial review package from the actual lessons.

No network calls and no publication. The report describes mechanical checks;
source relevance and teaching quality still need a separate editorial review.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = dict(zip(("grundlagen", "zeichen", "planeten", "haeuser", "aspekte",
    "radixsynthese", "transite", "psychologisch-evolutionaer", "mondknoten-asteroiden",
    "hellenistisch", "jyotish", "beratung-feldarbeit"), (8,12,12,12,12,8,10,12,8,8,6,12)))


def words(text):
    return len(re.findall(r"\b[\wÄÖÜäöüß]+(?:[-’'][\wÄÖÜäöüß]+)*\b", text))


def prose(value):
    """Render deliberately small safe Markdown vocabulary, without raw HTML."""
    blocks = []
    for paragraph in value.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if paragraph.startswith(("## ", "### ")):
            heading, _, rest = paragraph.partition("\n")
            tag, prefix = ("h4", 4) if heading.startswith("### ") else ("h3", 3)
            blocks.append(f"<{tag}>" + escape(heading[prefix:]) + f"</{tag}>")
            if rest.strip():
                blocks.append("<p>" + escape(rest.strip()).replace("\n", "<br>") + "</p>")
        else:
            blocks.append("<p>" + escape(paragraph).replace("\n", "<br>") + "</p>")
    return "\n".join(blocks)


def build():
    files = sorted((ROOT / "backend/app/academy_content").glob("*.json"))
    courses = [json.loads(p.read_text()) for p in files]
    lessons = [lesson for course in courses for lesson in course["lessons"]]
    issues, paragraphs, source_urls = [], defaultdict(list), set()
    course_counts = {c["id"]: len(c["lessons"]) for c in courses}
    if course_counts != EXPECTED:
        issues.append({"kind":"catalog", "expected": EXPECTED, "actual":course_counts})
    for field in ("key", "title"):
        for value, count in Counter(l[field] for l in lessons).items():
            if count > 1:
                issues.append({"kind":"duplicate_" + field, "value":value, "count":count})
    for lesson in lessons:
        key = lesson["key"]
        counts = {"body": words(lesson["body"]),
                  "model_answer": words(lesson["practice"]["model_answer"])}
        for field, minimum in (("body",450), ("model_answer",120)):
            if counts[field] < minimum:
                issues.append({"key":key,"kind":"short_" + field,"words":counts[field]})
        if len(lesson["examples"]) < 2 or any(words(e["body"]) < 60 for e in lesson["examples"]):
            issues.append({"key":key,"kind":"examples"})
        if len(lesson["quiz"]) != 3 or not 3 <= len(lesson["practice"]["rubric"]) <= 5:
            issues.append({"key":key,"kind":"assessment_structure"})
        if not lesson["sources"]:
            issues.append({"key":key,"kind":"missing_sources"})
        for source in lesson["sources"]:
            source_urls.add(source["url"])
            if not source["url"].startswith("https://") or not source.get("note") or not source.get("checked_at"):
                issues.append({"key":key,"kind":"source_metadata"})
        for question in lesson["quiz"]:
            if not (0 <= question["correct_index"] < len(question["options"])) or not question["explanation"]:
                issues.append({"key":key,"kind":"quiz_answer"})
        for paragraph in lesson["body"].split("\n\n"):
            if words(paragraph) >= 35:
                paragraphs[re.sub(r"\s+", " ", paragraph.strip()).casefold()].append(key)
    repeats = [{"lessons": keys,"excerpt": p[:160]} for p,keys in paragraphs.items() if len(set(keys)) > 1]
    manifest = {p.name:sha256(p.read_bytes()).hexdigest() for p in files}
    report = {"status":"draft_review_only", "course_count":len(courses),"lesson_count":len(lessons),
              "teaching_words":sum(words(l["body"]) for l in lessons),
              "source_count":len(source_urls),"sources":sorted(source_urls),
              "mechanical_issues":issues,"repeated_paragraphs":repeats,"files":manifest,
              "note":"Wortzahlen und Struktur sind keine fachliche Qualitätsfreigabe."}
    out = ROOT / "artifacts/academy-review"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2) + "\n")
    sections = []
    for course in courses:
        rows = []
        for lesson in course["lessons"]:
            examples = "".join(f'<h3>{escape(e["title"])}</h3>{prose(e["body"])}' for e in lesson["examples"])
            rubric = "".join(f'<li>{escape(r)}</li>' for r in lesson["practice"]["rubric"])
            quiz = "".join(f'<li><strong>{escape(q["question"])}</strong><ol>' +
                "".join(f'<li>{escape(o)}</li>' for o in q["options"]) +
                f'</ol><details><summary>Lösung und Begründung</summary><p>Antwort {q["correct_index"]+1}: {escape(q["explanation"])}</p></details></li>' for q in lesson["quiz"])
            sources = "".join(f'<li><a href="{escape(s["url"],quote=True)}" target="_blank" rel="noopener noreferrer">{escape(s["title"])}</a> · {escape(s["author"])}<p>{escape(s["note"])}</p><small>Geprüft: {escape(s["checked_at"])}</small></li>' for s in lesson["sources"])
            rows.append(f'''<details class="lesson" id="{escape(lesson["key"],quote=True)}"><summary>{escape(lesson["title"])} <small>{lesson["minutes"]} Min.</small></summary>
<div class="reading"><p class="objective"><strong>Lernziel</strong><br>{escape(lesson["objective"])}</p>{prose(lesson["body"])}
<h2>Eigene Beispiele</h2>{examples}<h2>Deine Praxisaufgabe</h2>{prose(lesson["practice"]["prompt"])}<ol>{rubric}</ol>
<details><summary>Musterbearbeitung lesen</summary>{prose(lesson["practice"]["model_answer"])}</details><h2>Wissensfragen</h2><ol>{quiz}</ol>
<h2>Quellen und ihre Rolle</h2><ul>{sources}</ul></div></details>''')
        sections.append(f'<section class="course" id="{escape(course["id"],quote=True)}"><h2>{escape(course["title"])}</h2><p>{escape(course["summary"])}</p><p class="meta">{escape(course["tradition"])} · {len(course["lessons"])} Lektionen</p>{"".join(rows)}</section>')
    navigation = "".join(f'<a href="#{escape(c["id"],quote=True)}">{escape(c["title"])}</a>' for c in courses)
    html = '''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sense &amp; Stars · Akademie zur Freigabe</title>
<style> :root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f5f2f8;color:#302638;font:17px/1.65 system-ui,sans-serif}header,main,footer{max-width:1100px;margin:auto;padding:2rem}header{padding-top:4rem}h1{font:clamp(2.4rem,6vw,4.4rem)/1.1 Georgia,serif;margin:.6em 0}h2,h3,h4{line-height:1.3}h2{font-family:Georgia,serif}.eyebrow,.meta,small{color:#75657f}.tag{display:inline-block;background:#ebe0f3;border-radius:30px;padding:.35em 1em}nav{display:flex;flex-wrap:wrap;gap:.5rem;margin:2rem 0}a{color:#754093;text-underline-offset:3px}nav a{padding:.4rem .8rem;border:1px solid #d8cde1;border-radius:8px}.course{scroll-margin-top:1rem;border-top:1px solid #d8cde1;padding:1.5rem 0 3rem}.lesson{margin:.65rem 0;border:1px solid #ded4e6;border-radius:12px;background:white}.lesson>summary{padding:1rem;cursor:pointer;font-weight:600}.lesson>summary small{float:right}.reading{padding:0 clamp(1rem,4vw,3rem) 2rem;max-width:850px}.reading p{white-space:normal}.reading details{border-left:3px solid #9b59b6;padding:.7rem 1rem;background:#f5f2f8;margin:1rem 0}.objective{background:#f1eaf6;padding:1rem;border-radius:8px}summary:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #754093;outline-offset:4px}input{width:100%;padding:1rem;font:inherit;border:1px solid #a895b4;border-radius:10px}li{margin:.5rem 0}.empty{display:none}@media(max-width:600px){header,main,footer{padding:1.2rem}.lesson>summary small{float:none;display:block}header{padding-top:2rem}}</style>
<header><p class="eyebrow">SENSE &amp; STARS · REDAKTIONELLE GESAMTPRÜFUNG</p><h1>Deine Akademie.<br>Dein eigener Weg.</h1><span class="tag">Entwurf · noch keine Veröffentlichung</span>
<p>ALLE_COUNT eigenständige Lektionen in COURSE_COUNT Kursen. Jedes Thema bleibt frei wählbar. Die folgenden Texte sind der konkrete Erstbestand zur bewussten Freigabe.</p><p>Astrologische Schulen und spirituelle Annahmen werden kenntlich gemacht. Lernabzeichen dokumentieren Lernleistungen. Diese Vorschau speichert keine Lernpunkte.</p><label for="search">Lektionen nach Titel oder Inhalt finden</label><input id="search" type="search" placeholder="Zum Beispiel Saturn, Gespräch oder Häuser"><nav>NAVIGATION</nav></header><main>SECTIONS</main><footer>Strukturbericht: <a href="report.json">report.json</a> · Diese Datei veröffentlicht keine Inhalte und lädt keine externen Skripte.</footer>
<script>document.querySelector('#search').addEventListener('input',function(){const term=this.value.toLocaleLowerCase('de');document.querySelectorAll('.lesson').forEach(el=>el.hidden=!el.textContent.toLocaleLowerCase('de').includes(term));document.querySelectorAll('.course').forEach(el=>el.hidden=![...el.querySelectorAll('.lesson')].some(item=>!item.hidden));});</script></html>'''
    html = html.replace("ALLE_COUNT",str(len(lessons))).replace("COURSE_COUNT",str(len(courses))).replace("NAVIGATION",navigation).replace("SECTIONS","".join(sections))
    (out / "index.html").write_text(html)
    print(json.dumps({k:report[k] for k in ("course_count","lesson_count","teaching_words","source_count")},ensure_ascii=False))
    print(f"Mechanical issues: {len(issues)}; repeated paragraphs: {len(repeats)}; review: {out}")
    return report


if __name__ == "__main__":
    result = build()
    if "--check" in sys.argv and (result["mechanical_issues"] or result["repeated_paragraphs"]):
        raise SystemExit("Academy structure requires correction; inspect report.json.")
