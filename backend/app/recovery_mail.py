"""Transactional recovery email through an explicitly configured SMTP server.

No credentials, SMTP replies, message bodies or tokens are written to logs.
The transport always verifies TLS, including local mode; tests replace it.
"""
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
import ipaddress
import json
import os
from pathlib import Path
import smtplib
import ssl
import subprocess
import sys
from threading import BoundedSemaphore
from urllib.parse import urlsplit

from email_validator import EmailNotValidError, validate_email

from .config import setting
from .mailbudget import reserve_mail_attempt
from .runtime import hosted, public_origin


@dataclass(frozen=True, repr=False)
class MailSettings:
    host: str
    port: int
    security: str
    username: str
    password: str
    sender: str
    origin: str


def recovery_origin():
    if hosted():
        return public_origin()
    value = setting("RECOVERY_LOCAL_ORIGIN", "")
    try:
        parsed = urlsplit(value)
        loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname or "").is_loopback
        valid = (loopback and parsed.scheme in ("http", "https") and not parsed.username
                 and not parsed.password and parsed.path in ("", "/") and not parsed.query
                 and not parsed.fragment and parsed.port is not None)
    except ValueError:
        valid = False
    return value.rstrip("/") if valid else None


def mail_settings():
    """Missing/invalid configuration disables recovery for every account alike."""
    host = setting("SMTP_HOST", "").strip()
    security = setting("SMTP_SECURITY", "").strip().lower()
    username = setting("SMTP_USERNAME", "")
    password = setting("SMTP_PASSWORD", "")
    sender = setting("MAIL_FROM", "").strip()
    try:
        port = int(setting("SMTP_PORT", "0"))
        sender = validate_email(sender, check_deliverability=False).normalized
        origin = recovery_origin()
    except (ValueError, EmailNotValidError, RuntimeError):
        return None
    if (not host or any(c.isspace() for c in host) or any(c in host for c in "/@\\?#")
            or not 1 <= port <= 65535 or security not in ("ssl", "starttls")
            or not username or not password or not origin):
        return None
    return MailSettings(host, port, security, username, password, sender, origin)


SEND_TIMEOUT = 6
_SEND_SLOTS = BoundedSemaphore(2)


def _worker_environment():
    # Hosted launchers may add uv/dependency bundles directly to sys.path rather
    # than PYTHONPATH. A fresh interpreter otherwise loses those imports. Resolve
    # parent-relative paths before the worker switches to the backend directory.
    environment = os.environ.copy()
    paths = [str(Path(__file__).resolve().parent.parent)]
    paths.extend(str(Path(path or os.getcwd()).resolve()) for path in sys.path if isinstance(path, str))
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    return environment


def send_message(settings: MailSettings, recipient: str, subject: str, text: str):
    """Await delivery acceptance with a hard deadline, including DNS resolution.

    smtplib's socket timeout alone only bounds individual network operations. A
    short-lived worker also bounds a slow DNS lookup or a drip-fed SMTP reply.
    Secrets travel only through stdin, never process arguments, files or logs.
    subprocess.run kills and reaps the worker on timeout before returning.
    """
    from dataclasses import asdict
    # One reserved slot means one recipient. Reject address lists and headers
    # even for internal test/administrative calls to this shared send function.
    recipient = validate_email(recipient, check_deliverability=False).normalized
    payload = json.dumps({"settings": asdict(settings), "recipient": recipient,
                          "subject": subject, "text": text}).encode("utf-8")
    if not _SEND_SLOTS.acquire(blocking=False):
        raise RuntimeError("Mail transport busy")
    try:
        reserve_mail_attempt()
        subprocess.run([sys.executable, "-m", "app.recovery_mail"], input=payload,
                       cwd=Path(__file__).resolve().parent.parent,
                       env=_worker_environment(),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=SEND_TIMEOUT, check=True)
    finally:
        _SEND_SLOTS.release()


def _send_message(settings: MailSettings, recipient: str, subject: str, text: str):
    message = EmailMessage()
    message["From"] = formataddr(("Sense & Stars", settings.sender))
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text)
    context = ssl.create_default_context()
    if settings.security == "ssl":
        with smtplib.SMTP_SSL(settings.host, settings.port, timeout=SEND_TIMEOUT, context=context) as smtp:
            smtp.login(settings.username, settings.password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.host, settings.port, timeout=SEND_TIMEOUT) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(settings.username, settings.password)
            smtp.send_message(message)


def send_reset(settings: MailSettings, recipient: str, token: str):
    url = settings.origin + "/#reset-password?token=" + token
    send_message(settings, recipient, "Dein Rücksetzlink für Sense & Stars", (
        "Hallo,\n\nüber diesen Link kannst du ein neues Passwort für Sense & Stars festlegen:\n\n"
        + url + "\n\nDer Link ist 30 Minuten gültig und kann genau einmal verwendet werden. "
        "Bitte gib ihn nicht weiter.\n\nFalls du diese Anfrage nicht gestellt hast, "
        "kannst du diese Nachricht ignorieren. Dein Passwort wurde noch nicht geändert.\n\n"
        "Sense & Stars\n"
    ))


def send_changed(settings: MailSettings, recipient: str):
    send_message(settings, recipient, "Dein Sense & Stars Passwort wurde geändert", (
        "Hallo,\n\ndein Passwort für Sense & Stars wurde soeben zurückgesetzt. "
        "Alle bisherigen Anmeldungen und Rücksetzlinks sind jetzt ungültig.\n\n"
        "Du kannst dich mit deinem neuen Passwort hier anmelden:\n"
        + settings.origin + "/\n\nFalls du diese Änderung nicht selbst veranlasst hast, "
        "wende dich bitte sofort an die Person, die deinen Zugang eingerichtet hat. "
        "Du kannst über „Passwort vergessen?“ erneut einen Rücksetzlink anfordern.\n\n"
        "Sense & Stars\n"
    ))


if __name__ == "__main__":
    try:
        payload = json.loads(sys.stdin.buffer.read())
        _send_message(MailSettings(**payload["settings"]), payload["recipient"],
                      payload["subject"], payload["text"])
    except Exception:
        # No exception details: SMTP libraries can include credentials/addresses.
        sys.exit(1)
