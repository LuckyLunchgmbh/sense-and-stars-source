"""Real local TLS transport and worker tests; no mail leaves loopback.

The test certificate is trusted only inside the test process/child environment.
OpenSSL generates an ephemeral certificate; no global trust store is modified.
"""
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
import os
from pathlib import Path
import shlex
import shutil
import socketserver
import ssl
import subprocess
import threading
import time

import pytest

from app import recovery_mail
from app.db import get_db, init_schema


@pytest.fixture(autouse=True)
def isolated_mail_budget(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENSE_AND_STARS_HOSTED", "0")
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(tmp_path / "smtp-budget.sqlite3"))
    with get_db() as conn:
        init_schema(conn)


@pytest.fixture
def smtp_certificate(tmp_path):
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("OpenSSL is required for isolated real TLS SMTP tests")
    config = tmp_path / "openssl.cnf"
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    config.write_text("""[req]
distinguished_name=subject
x509_extensions=extensions
prompt=no
[subject]
CN=localhost
[extensions]
subjectAltName=DNS:localhost,IP:127.0.0.1
basicConstraints=critical,CA:TRUE
keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign
""")
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-days", "1", "-config", str(config), "-keyout", str(key),
                    "-out", str(cert)], check=True, capture_output=True)
    return cert, key


@contextmanager
def tls_smtp(certificate, security, *, stall=False):
    cert, key = certificate
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    messages = []
    stopped = threading.Event()

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            connection = self.request
            reader = None
            try:
                connection.settimeout(3)
                if stall:
                    stopped.wait(3)
                    return
                if security == "ssl":
                    connection = context.wrap_socket(connection, server_side=True)
                reader = connection.makefile("rb")
                connection.sendall(b"220 localhost isolated test SMTP\r\n")
                while True:
                    command = reader.readline()
                    if not command:
                        break
                    verb = command.split(b" ", 1)[0].strip().upper()
                    if verb in (b"EHLO", b"HELO"):
                        connection.sendall(b"250-localhost\r\n250-STARTTLS\r\n250 AUTH PLAIN\r\n")
                    elif verb == b"STARTTLS":
                        connection.sendall(b"220 Ready for TLS\r\n")
                        reader.close()
                        connection = context.wrap_socket(connection, server_side=True)
                        reader = connection.makefile("rb")
                    elif verb == b"AUTH":
                        import base64
                        provided = base64.b64decode(command.split()[2])
                        if provided != b"\x00synthetic-user\x00synthetic-mail-secret":
                            connection.sendall(b"535 Authentication failed\r\n")
                        else:
                            connection.sendall(b"235 Authenticated\r\n")
                    elif verb in (b"MAIL", b"RCPT", b"RSET"):
                        connection.sendall(b"250 OK\r\n")
                    elif verb == b"DATA":
                        connection.sendall(b"354 End with dot\r\n")
                        body = []
                        while (line := reader.readline()) not in (b".\r\n", b""):
                            body.append(line[1:] if line.startswith(b"..") else line)
                        messages.append(BytesParser(policy=policy.default).parsebytes(b"".join(body)))
                        connection.sendall(b"250 Accepted locally\r\n")
                    elif verb == b"QUIT":
                        connection.sendall(b"221 Bye\r\n")
                        break
                    else:
                        connection.sendall(b"500 Unsupported test command\r\n")
            except (ssl.SSLError, ConnectionError, TimeoutError):
                pass
            finally:
                if reader:
                    reader.close()
                connection.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    with Server(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        settings = recovery_mail.MailSettings(
            "127.0.0.1", server.server_address[1], security,
            "synthetic-user", "synthetic-mail-secret", "sender@example.org",
            "https://sense-and-stars.example.org",
        )
        try:
            yield settings, messages
        finally:
            stopped.set()
            server.shutdown()
            thread.join(timeout=3)


@pytest.mark.parametrize("security", ["ssl", "starttls"])
def test_real_tls_worker_delivers_reset_and_change_notice(smtp_certificate, monkeypatch, security):
    monkeypatch.setenv("SSL_CERT_FILE", str(smtp_certificate[0]))
    with tls_smtp(smtp_certificate, security) as (settings, messages):
        token = "synthetic-token-only-for-transport-test"
        recovery_mail.send_reset(settings, "recipient@example.org", token)
        recovery_mail.send_changed(settings, "recipient@example.org")
    assert len(messages) == 2
    assert str(messages[0]["To"]) == "recipient@example.org"
    assert str(messages[0]["From"]) == "Sense & Stars <sender@example.org>"
    body = messages[0].get_content()
    assert settings.origin + "/#reset-password?token=" + token in body
    assert "30 Minuten" in body
    assert token not in messages[1].get_content()
    assert "Alle bisherigen Anmeldungen" in messages[1].get_content()


def test_real_tls_worker_inherits_parent_only_import_paths(smtp_certificate, tmp_path, monkeypatch):
    """Model a launcher that adds dependency bundles only to parent sys.path."""
    interpreter = Path(recovery_mail.sys.executable).absolute()
    wrapper = tmp_path / "python-no-site"
    wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(str(interpreter)) + ' -S "$@"\n')
    wrapper.chmod(0o700)
    monkeypatch.setattr(recovery_mail.sys, "executable", str(wrapper))
    monkeypatch.syspath_prepend(os.path.relpath(tmp_path, Path.cwd()))
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setenv("SSL_CERT_FILE", str(smtp_certificate[0]))
    original_run = subprocess.run
    probe = original_run([str(wrapper), "-c", "import email_validator"],
                         capture_output=True, text=True, check=False)
    assert probe.returncode != 0
    assert "ModuleNotFoundError" in probe.stderr and "email_validator" in probe.stderr
    observed = []
    def run_worker(args, **kwargs):
        observed.append((args, kwargs))
        return original_run(args, **kwargs)
    monkeypatch.setattr(recovery_mail.subprocess, "run", run_worker)
    with tls_smtp(smtp_certificate, "ssl") as (settings, messages):
        token = "synthetic-parent-path-token"
        recovery_mail.send_reset(settings, "recipient@example.org", token)
    assert len(messages) == 1
    assert token in messages[0].get_content()
    args, kwargs = observed[0]
    assert args == [str(wrapper), "-m", "app.recovery_mail"]
    assert settings.password not in str(args) and token not in str(args)
    assert kwargs["timeout"] == recovery_mail.SEND_TIMEOUT
    assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs.get("shell", False) is False
    assert kwargs["env"]["SSL_CERT_FILE"] == str(smtp_certificate[0])
    assert all(Path(path).is_absolute() for path in kwargs["env"]["PYTHONPATH"].split(os.pathsep))
    assert str(tmp_path.resolve()) in kwargs["env"]["PYTHONPATH"].split(os.pathsep)
    assert "PYTHONPATH" not in os.environ  # No mutation of the parent's environment.


def test_real_worker_rejects_untrusted_certificate(smtp_certificate, monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    with tls_smtp(smtp_certificate, "ssl") as (settings, messages):
        with pytest.raises(subprocess.CalledProcessError):
            recovery_mail.send_reset(settings, "recipient@example.org", "synthetic-token")
    assert messages == []


def test_real_worker_stall_is_killed_and_reaped(smtp_certificate, monkeypatch):
    monkeypatch.setattr(recovery_mail, "SEND_TIMEOUT", 0.2)
    with tls_smtp(smtp_certificate, "ssl", stall=True) as (settings, messages):
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            recovery_mail.send_reset(settings, "recipient@example.org", "synthetic-token")
        elapsed = time.monotonic() - start
    assert elapsed < 2
    assert messages == []
