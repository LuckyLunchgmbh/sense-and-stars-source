"""Bounded public-source discovery with a durable fourteen-day review queue.

Only configured public hosts can be contacted. No client context, prompts,
cookies or credentials leave this module. Article text is parsed transiently
and hashed, never copied into a lesson. All output is private editorial work.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import os
import queue
import re
import secrets
import socket
import ssl
import threading
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .db import get_db
from .security import require_admin, require_staff

router = APIRouter()
INTERVAL_DAYS = 14
MAX_HTML_BYTES = 750_000
FETCH_TIMEOUT = 4.0
RUN_BUDGET = 55.0
LEASE_SECONDS = 300
MAX_NEW_PER_SOURCE = 2


@dataclass(frozen=True)
class Source:
    key: str
    title: str
    url: str
    article_path: str


# Primary websites checked on 20 October 2026. External video, newsletter,
# login, shop, CDN and community hosts intentionally receive no request.
SOURCES = (
    Source("silke", "Silke Schäfer", "https://www.silkeschaefer.com/astrologie/aktuelles", r"^/blog/[^/]+/?$"),
    Source("mark", "Mark Jones", "https://markjonesastrology.com/blog/", r"^/blog/[^/]+/?$"),
    Source("kaypacha", "Kaypacha · New Paradigm Astrology", "https://newparadigmastrology.com/pele-reports/", r"^/[a-z]+-\d{1,2}-\d{4}-astrology-forecast/?$"),
    Source("maurice", "Maurice Fernandez", "https://mauricefernandez.com/category/videos/", r"^/(?!category/|learn-astrology/|astrology-readings/|contact|about|events|shop|cart|my-account|videos|articles|privacy|terms|donate|join)[a-z0-9][a-z0-9-]+/?$"),
    Source("pam", "Pam Gregory", "https://www.thenextstep.uk.com/blog/", r"^/newsletters/[^/]+/?$"),
)
ALLOWED_HOSTS = frozenset(urlsplit(source.url).hostname for source in SOURCES)


def utc_now():
    return datetime.now(timezone.utc)


def _iso(moment):
    return moment.astimezone(timezone.utc).isoformat()


def _date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def init_learning_updates(conn):
    for statement in (
        """CREATE TABLE IF NOT EXISTS learning_update_state(
        id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
        next_due_at TEXT, last_success_at TEXT, last_error TEXT,
        lock_token TEXT, lock_expires_at TEXT)""",
        """CREATE TABLE IF NOT EXISTS learning_update_runs(
        id INTEGER PRIMARY KEY, token TEXT NOT NULL UNIQUE, trigger TEXT NOT NULL,
        user_id INTEGER REFERENCES users(id), started_at TEXT NOT NULL, finished_at TEXT,
        status TEXT NOT NULL, created INTEGER NOT NULL DEFAULT 0, error TEXT,
        sources TEXT NOT NULL DEFAULT '[]')""",
        """CREATE TABLE IF NOT EXISTS learning_source_findings(
        id INTEGER PRIMARY KEY, source_key TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL, published_at TEXT, discovered_at TEXT NOT NULL,
        fetched_at TEXT NOT NULL, fetch_status TEXT NOT NULL,
        text_chars INTEGER NOT NULL DEFAULT 0, text_sha256 TEXT,
        lesson_id INTEGER REFERENCES learning_lessons(id), run_id INTEGER REFERENCES learning_update_runs(id))""",
        "INSERT OR IGNORE INTO learning_update_state(id,enabled) VALUES(1,0)",
    ):
        conn.execute(statement)


def configure_updates(conn, *, enabled: bool, now=None):
    """Explicit operator setup; repeated startup does not reset the due date."""
    if type(enabled) is not bool:
        raise ValueError("enabled muss ein Boolean sein.")
    moment = _iso(now or utc_now())
    conn.execute("UPDATE learning_update_state SET enabled=?,next_due_at=COALESCE(next_due_at,?) WHERE id=1", (int(enabled), moment))


def validate_public_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("Unzulässige Quellenadresse.")
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.query:
            raise ValueError("Die Quelle liegt außerhalb der freigegebenen HTTPS-Hosts.")
    except ValueError:
        raise ValueError("Die Quelle liegt außerhalb der freigegebenen HTTPS-Hosts.") from None
    return urlunsplit(("https", parsed.hostname, parsed.path or "/", "", ""))


def resolve_public_address(host):
    """Bound DNS time and reject mixed/private answers, then pin one public IP."""
    if host not in ALLOWED_HOSTS:
        raise ValueError("Nicht freigegebener Quellenhost.")
    resolved = queue.Queue(maxsize=1)
    def lookup():
        try:
            resolved.put(socket.getaddrinfo(host,443,type=socket.SOCK_STREAM))
        except OSError:
            resolved.put(None)
    threading.Thread(target=lookup, daemon=True).start()
    try:
        answers = resolved.get(timeout=min(2.0,FETCH_TIMEOUT))
    except queue.Empty:
        raise TimeoutError("Die DNS-Zeitgrenze ist erreicht.") from None
    if not answers:
        raise ValueError("Der Quellenhost ist nicht erreichbar.")
    addresses = [answer[4][0] for answer in answers]
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Private oder reservierte Netzwerkadressen sind gesperrt.")
    return addresses[0]


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host,443,timeout=timeout,context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Connect to the already checked IP; TLS still authenticates the host.
        raw = socket.create_connection((self.address,443),self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
            self._source_socket = self.sock
        except BaseException:
            raw.close()
            raise


def fetch_public_html(url):
    canonical = validate_public_url(url)
    started = time.monotonic()
    host = urlsplit(canonical).hostname
    address = resolve_public_address(host)
    connection = _PinnedHTTPS(host,address,max(0.1,FETCH_TIMEOUT-(time.monotonic()-started)))
    try:
        connection.request("GET",urlsplit(canonical).path,headers={"User-Agent":"Sense-And-Stars-source-review/1.1", "Accept":"text/html", "Accept-Encoding":"identity"})
        remaining=FETCH_TIMEOUT-(time.monotonic()-started)
        if remaining<=0:
            raise TimeoutError("Die Quellen-Zeitgrenze ist erreicht.")
        if getattr(connection,"sock",None):
            connection.sock.settimeout(remaining)
        response = connection.getresponse()
        # Do not follow any Location. No proxy or environment credential support.
        if response.status != 200 or "text/html" not in response.getheader("Content-Type", "").lower() or response.getheader("Content-Encoding", "identity").lower() not in ("identity", ""):
            raise ValueError("Die Quelle liefert keinen direkt zugänglichen HTML-Text.")
        length = response.getheader("Content-Length")
        if length and (not length.isdecimal() or int(length) > MAX_HTML_BYTES):
            raise ValueError("Die Quelle überschreitet die zulässige Größe.")
        data = bytearray()
        while True:
            remaining = FETCH_TIMEOUT-(time.monotonic()-started)
            if remaining <= 0:
                raise TimeoutError("Die Quellen-Zeitgrenze ist erreicht.")
            source_socket=getattr(connection,"_source_socket",None) or getattr(connection,"sock",None)
            if source_socket:
                source_socket.settimeout(remaining)
            chunk = response.read1(min(16_384,MAX_HTML_BYTES+1-len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_HTML_BYTES:
                raise ValueError("Die Quelle überschreitet die zulässige Größe.")
        return bytes(data)
    finally:
        connection.close()


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.links=[]
        self.text=[]
        self.title=[]
        self.document_title=[]
        self.published_at=None
        self.anchor=None

    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        classes=set(data.get("class", "").split())
        excluded=tag in ("script","style","nav","header","footer","noscript","form","aside") or bool(classes & {"menu","navigation","sidebar"})
        content=tag in ("article","main") or bool(classes & {"entry-content","post-content","blog-content","w-richtext"})
        self.stack.append((tag,excluded,content))
        if tag=="meta" and (data.get("property") or data.get("name")) in ("article:published_time","date","datePublished"):
            value=data.get("content", "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T[0-9:.+Z-]+)?",value):
                self.published_at=value[:64]
        if tag=="time" and data.get("datetime") and not self.published_at:
            value=data["datetime"]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T[0-9:.+Z-]+)?",value):
                self.published_at=value[:64]
        if tag=="a" and data.get("href"):
            self.anchor=[data["href"],[]]
        # HTML void elements never wait for an end tag.
        if tag in ("area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"):
            self.stack.pop()

    def handle_endtag(self,tag):
        if tag=="a" and self.anchor:
            self.links.append((self.anchor[0]," ".join(self.anchor[1]).strip()))
            self.anchor=None
        for index in range(len(self.stack)-1,-1,-1):
            if self.stack[index][0]==tag:
                del self.stack[index:]
                break

    def handle_data(self,data):
        if any(item[1] for item in self.stack):
            return
        text=re.sub(r"\s+"," ",data).strip()
        if not text:
            return
        tags={item[0] for item in self.stack}
        if "h1" in tags:
            self.title.append(text)
        if "title" in tags:
            self.document_title.append(text)
        if self.anchor:
            self.anchor[1].append(text)
        # Only paragraphs in a content region qualify as article text. Navigation,
        # captions, headings and link/video-only pages cannot become a full read.
        if "p" in tags and not self.anchor and any(item[2] for item in self.stack):
            self.text.append(text)


def parse_page(data):
    if len(data)>MAX_HTML_BYTES:
        raise ValueError("Zu großer HTML-Text.")
    parser=_Page()
    parser.feed(data.decode("utf-8",errors="replace"))
    return {"title":" ".join(parser.title or parser.document_title)[:200], "published_at":parser.published_at,
            "text":"\n".join(parser.text),"links":parser.links}


def _discover(source, data):
    found=[]
    seen=set()
    for href,title in parse_page(data)["links"]:
        try:
            url=validate_public_url(urljoin(source.url,href))
        except ValueError:
            continue
        if urlsplit(url).hostname != urlsplit(source.url).hostname or not re.fullmatch(source.article_path,urlsplit(url).path) or not title:
            continue
        # Ignore alternate fragment/slash spellings of the same source.
        url=url.rstrip("/")+"/"
        if url in seen:
            continue
        seen.add(url)
        found.append({"url":url,"title":title[:200]})
        if len(found)>=40:
            break
    return found


def _read_candidate(source, candidate):
    finding={**candidate,"source_key":source.key,"source_title":source.title,"fetch_status":"unavailable",
             "published_at":None,"text_chars":0,"text_sha256":None,"fetched_at":_iso(utc_now())}
    try:
        page=parse_page(fetch_public_html(candidate["url"]))
        finding["title"]=page["title"] or finding["title"]
        finding["published_at"]=page["published_at"]
        finding["text_chars"]=len(page["text"])
        if len(page["text"])>=400:
            finding["fetch_status"]="text_accessible"
            finding["text_sha256"]=hashlib.sha256(page["text"].encode()).hexdigest()
        else:
            finding["fetch_status"]="metadata_only"
    except (OSError,ValueError,http.client.HTTPException):
        pass
    return finding


def _reading_draft(conn,finding,run_id):
    from .learning import _insert_editorial,LessonCreate,MAX_WEEK
    previous=conn.execute("SELECT * FROM learning_source_findings WHERE url=?",(finding["url"],)).fetchone()
    lesson_id=previous["lesson_id"] if previous else None
    created=0
    if not previous:
        occupied={row["week"] for row in conn.execute("SELECT week FROM learning_lessons")}
        week=next((i for i in range(1,MAX_WEEK+1) if i not in occupied),None)
        if week is None:
            raise ValueError("Alle Sortierplätze sind belegt; keine automatische Veröffentlichung.")
        access=("Automatisiert zugänglicher Webtext, fachlich noch ungeprüft. Videos und Audios wurden nicht angesehen oder transkribiert."
                if finding["fetch_status"]=="text_accessible" else
                "Die Quelle ist nicht als Artikeltext zugänglich oder noch nicht vollständig abrufbar. Bisher liegen nur Fundmetadaten vor; Video-/Audioinhalte wurden nicht geprüft.")
        lesson=LessonCreate(title=f"Rechercheentwurf · {finding['title']}"[:160],category="Quellen-Leseübung",
            summary=f"Unveröffentlichter Rechercheentwurf zur eigenen Lektüre bei {finding['source_title']}. Fachliche Prüfung und eigener Lehrtext stehen aus."[:600],
            body=(f"Rechercheentwurf · Sense & Stars · {_iso(utc_now())[:10]}\n\nQuelle: {finding['source_title']}\nOriginaltitel: {finding['title']}\n"
                  f"Originaladresse: {finding['url']}\nVeröffentlichungsdatum laut Website-Metadaten: {finding['published_at'] or 'nicht angegeben'}\n\n{access}\n\n"
                  "Dies ist eine eigene Quellen-Leseübung, keine Zusammenfassung des Originalinhalts und keine fertige Fachlektion. "
                  "Die Überschrift und technische Erreichbarkeit belegen weder die Richtigkeit einer Aussage noch eine spirituelle Fähigkeit. "
                  "Öffne das öffentliche Original. Notiere in eigenen Worten, welche konkrete Frage du dort untersuchen möchtest. "
                  "Ist nur ein Video oder eine Anmeldung sichtbar, kennzeichne den Inhalt als noch nicht gelesen und überspringe kostenpflichtige Zugänge.\n\n"
                  "Halte drei Spalten auseinander: genaue Aussage der Autorin oder des Autors, eigene Deutung und eine offene Rückfrage. "
                  "Ordne Behauptungen zu Energiefeldern oder Fernwahrnehmung als spirituelle Modellannahmen oder persönliche Erfahrungsberichte ein, sofern keine geeigneten Belege vorliegen. "
                  "Leite daraus keine Diagnose, Heilzusage oder Aussage über eine reale Person ab. "
                  "Verwende für eine spätere Übung eine ausdrücklich fiktive Situation und formuliere eine Einladung, die ein Nein erlaubt.\n\n"
                  "Vor Veröffentlichung: Originalzugang, Datum, Urheberschaft, inhaltliche Grenzen und zulässige eigene Formulierungen prüfen. "
                  "Anschließend einen eigenen zusammenhängenden Lerntext und einen passenden freiwilligen Verständnischeck ausarbeiten, redaktionell speichern und separat freigeben."),
            week=week,source_url=finding["url"],source_title=finding["source_title"],
            quiz=[{"id":"source-review","question":"Was ist vor einer Veröffentlichung dieses Rechercheentwurfs erforderlich?", "options":["Original prüfen, eigenen Lehrtext ausarbeiten und bewusst freigeben","Die Überschrift automatisch als gesichertes Wissen übernehmen"],"correct_index":0}],
            track="Quellenarbeit",level="practice",learning_objective="Eine öffentliche Originalquelle prüfen und Autorenaussage, eigene Deutung und offene Fragen getrennt erfassen.",
            exercise="Öffne die Quelle und lege eine Notiz mit drei Spalten an: Autorenaussage, eigene Deutung, offene Frage. Schreibe dann für eine fiktive Beratungssituation eine freiwillige Reflexionsfrage. Kennzeichne nicht zugängliche Abschnitte, statt deren Inhalt zu ergänzen.",
            reflection_prompt="Welche Aussage habe ich tatsächlich im Original gesehen, welche stammt von mir, und was müsste ich noch prüfen?",
            source_note=f"{access} Abrufstatus: {finding['fetch_status']}. Abruf: {finding['fetched_at']}. URL: {finding['url']}. Kein fremder Artikel- oder Kurstext übernommen.")
        cursor=_insert_editorial(conn,lesson,status="draft")
        lesson_id=cursor.lastrowid
        conn.execute("UPDATE learning_lessons SET source_kind='source_reading_draft',scan_key=? WHERE id=?",("scheduled:"+hashlib.sha256(finding["url"].encode()).hexdigest(),lesson_id))
        created=1
    conn.execute("""INSERT INTO learning_source_findings(source_key,url,title,published_at,discovered_at,fetched_at,fetch_status,text_chars,text_sha256,lesson_id,run_id)
        VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET title=excluded.title,published_at=excluded.published_at,
        fetched_at=excluded.fetched_at,fetch_status=excluded.fetch_status,text_chars=excluded.text_chars,text_sha256=excluded.text_sha256,run_id=excluded.run_id""",
        (finding["source_key"],finding["url"],finding["title"],finding["published_at"],_iso(utc_now()),finding["fetched_at"],finding["fetch_status"],finding["text_chars"],finding["text_sha256"],lesson_id,run_id))
    return created


def updates_status(*, connection_factory=None):
    now=utc_now()
    with (connection_factory or get_db)() as conn:
        state_row=conn.execute("SELECT * FROM learning_update_state WHERE id=1").fetchone()
        if state_row is None:
            raise RuntimeError("Der Quellenstatus ist noch nicht eingerichtet.")
        state=dict(state_row)
        runs=[]
        for row in conn.execute("SELECT id,trigger,started_at,finished_at,status,created,error,sources FROM learning_update_runs ORDER BY id DESC LIMIT 10"):
            item=dict(row); item["sources"]=json.loads(item["sources"]); runs.append(item)
        findings=[dict(row) for row in conn.execute("SELECT source_key,url,title,published_at,discovered_at,fetched_at,fetch_status,text_chars,lesson_id FROM learning_source_findings ORDER BY fetched_at DESC,id DESC LIMIT 30")]
    stale=bool(state["lock_token"] and state["lock_expires_at"] and _date(state["lock_expires_at"])<=now)
    return {"enabled":bool(state["enabled"]),"interval_days":INTERVAL_DAYS,"next_due_at":state["next_due_at"],
            "last_success_at":state["last_success_at"],"last_error":state["last_error"],"stale":stale,
            "last_run_at":(runs[0]["finished_at"] or runs[0]["started_at"]) if runs else None,
            "last_run_status":runs[0]["status"] if runs else None,
            "active_run":next((item for item in runs if item["status"]=="running"),None) if state["lock_token"] else None,
            "recent_runs":runs,"findings":findings,"sources":[{"key":s.key,"title":s.title,"url":s.url} for s in SOURCES],
            "review_required":True,"publication_automatic":False}


def run_updates(*,trigger,user_id=None):
    # Admit network work against one clock from function entry, including the
    # initial DB/lease phase. Final persistence has separate hosting headroom;
    # this is not a hard upper bound on database or total invocation duration.
    deadline=time.monotonic()+RUN_BUDGET
    if trigger not in ("manual","cron"):
        raise ValueError("Unbekannter Auslöser.")
    started=utc_now(); started_iso=_iso(started); token=secrets.token_urlsafe(24)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state=conn.execute("SELECT * FROM learning_update_state WHERE id=1").fetchone()
        if not state["enabled"]:
            return {"status":"disabled","created":0}
        if state["lock_token"]:
            if state["lock_expires_at"] and _date(state["lock_expires_at"])>started:
                return {"status":"running","created":0}
            conn.execute("UPDATE learning_update_runs SET status='stale',finished_at=?,error=? WHERE token=? AND status='running'",(started_iso,"Ein früherer Lauf wurde unterbrochen; seine Sperre ist abgelaufen.",state["lock_token"]))
            conn.execute("UPDATE learning_update_state SET lock_token=NULL,lock_expires_at=NULL WHERE id=1")
        if state["next_due_at"] and _date(state["next_due_at"])>started:
            return {"status":"not_due","created":0,"next_due_at":state["next_due_at"]}
        conn.execute("UPDATE learning_update_state SET lock_token=?,lock_expires_at=? WHERE id=1",(token,_iso(started+timedelta(seconds=LEASE_SECONDS))))
        cursor=conn.execute("INSERT INTO learning_update_runs(token,trigger,user_id,started_at,status,sources) VALUES(?,?,?,?,'running','[]')",(token,trigger,user_id,started_iso))
        run_id=cursor.lastrowid
        known={row["url"]:row["fetch_status"] for row in conn.execute("SELECT url,fetch_status FROM learning_source_findings")}
    findings=[]; sources=[]
    try:
        for source in SOURCES:
            report={"key":source.key,"title":source.title,"url":source.url,"fetched_at":_iso(utc_now()),"fetch_status":"unavailable","candidates":0}
            try:
                if time.monotonic()+FETCH_TIMEOUT>deadline:
                    raise TimeoutError()
                candidates=_discover(source,fetch_public_html(source.url))
                if not candidates:
                    raise ValueError("Der Quellenindex enthält keine erkennbaren Beitragsverweise; manuelle Prüfung erforderlich.")
                report.update(fetch_status="index_accessible",candidates=len(candidates))
                pending=[item for item in candidates if known.get(item["url"]) not in ("text_accessible","metadata_only")][:MAX_NEW_PER_SOURCE]
                for candidate in pending:
                    if time.monotonic()+FETCH_TIMEOUT>deadline:
                        raise TimeoutError()
                    findings.append(_read_candidate(source,candidate))
            except (OSError,ValueError,http.client.HTTPException):
                report["fetch_status"]="unavailable"
            sources.append(report)
        any_index=any(item["fetch_status"]=="index_accessible" for item in sources)
        errors=any(item["fetch_status"]=="unavailable" for item in sources+findings)
        status="partial" if errors and any_index else "failed" if errors else "succeeded"
        error="Einige öffentliche Quellen sind nicht vollständig abrufbar. Der Lauf wird als unvollständig geführt; erneuter Versuch bleibt möglich." if errors else None
        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            state=conn.execute("SELECT lock_token FROM learning_update_state WHERE id=1").fetchone()
            if state["lock_token"]!=token:
                return {"status":"stale","created":0}
            created=sum(_reading_draft(conn,finding,run_id) for finding in findings)
            finished=_iso(utc_now())
            conn.execute("UPDATE learning_update_runs SET status=?,created=?,finished_at=?,error=?,sources=? WHERE id=?",(status,created,finished,error,json.dumps(sources,ensure_ascii=False),run_id))
            if status=="succeeded":
                conn.execute("UPDATE learning_update_state SET last_success_at=?,next_due_at=?,last_error=NULL,lock_token=NULL,lock_expires_at=NULL WHERE id=1",(finished,_iso(utc_now()+timedelta(days=INTERVAL_DAYS))))
            else:
                # A partial review cycle still has the regular fourteen-day
                # cadence. Total outage retries at most daily, never as success.
                delay=INTERVAL_DAYS if status=="partial" else 1
                conn.execute("UPDATE learning_update_state SET last_error=?,next_due_at=?,lock_token=NULL,lock_expires_at=NULL WHERE id=1",(error,_iso(utc_now()+timedelta(days=delay))))
        return {"status":status,"created":created,"run_id":run_id,"sources":sources,"error":error}
    except Exception:
        # DB writes above roll back together. A retry cannot duplicate drafts;
        # no exception, HTML or host credentials are returned to the browser.
        error="Der Aktualisierungslauf konnte nicht sicher abgeschlossen werden. Vorhandene Inhalte bleiben erhalten; bitte den Lauf erneut prüfen."
        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE learning_update_runs SET status='failed',finished_at=?,error=? WHERE token=? AND status='running'",(_iso(utc_now()),error,token))
            conn.execute("UPDATE learning_update_state SET last_error=?,next_due_at=?,lock_token=NULL,lock_expires_at=NULL WHERE id=1 AND lock_token=?",(error,_iso(utc_now()+timedelta(days=1)),token))
        return {"status":"failed","created":0,"run_id":run_id,"error":error}


class _Empty(BaseModel):
    model_config=ConfigDict(extra="forbid")


@router.get("/api/learning/updates/status")
def get_updates_status(request: Request):
    require_staff(request)
    return updates_status()


@router.post("/api/admin/learning-updates/run")
def manual_updates(payload: _Empty,request: Request):
    user=require_admin(request)
    result=run_updates(trigger="manual",user_id=user["id"])
    return JSONResponse(result,status_code=503 if result["status"] in ("partial","failed","stale") else 200)


@router.get("/api/internal/learning-updates")
def cron_updates(request: Request):
    secret=os.environ.get("CRON_SECRET", "")
    if len(secret)<24:
        raise HTTPException(503,"Der geschützte Zeitplan ist noch nicht eingerichtet.")
    supplied=request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(),("Bearer "+secret).encode()):
        raise HTTPException(401,"Der Zeitplanaufruf ist nicht autorisiert.")
    result=run_updates(trigger="cron")
    return JSONResponse(result,status_code=503 if result["status"] in ("partial","failed","stale") else 200)
