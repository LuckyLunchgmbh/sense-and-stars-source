import pytest


def configured(monkeypatch):
    monkeypatch.setenv("SOULFLOW_HOSTED", "1")
    monkeypatch.setenv("SOULFLOW_DEMO", "0")
    monkeypatch.setenv("SOULFLOW_PUBLIC_ORIGIN", "https://soulflow.example.org")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test@db.example.org/soulflow?sslmode=require")


def test_hosted_requires_explicit_license_and_persistence(monkeypatch):
    configured(monkeypatch)
    from app.runtime import validate_hosted_settings
    monkeypatch.delenv("SOULFLOW_SWISS_LICENSE", raising=False)
    with pytest.raises(RuntimeError, match="Lizenz"):
        validate_hosted_settings()
    monkeypatch.setenv("SOULFLOW_SWISS_LICENSE", "agpl-3.0")
    monkeypatch.delenv("SOULFLOW_SOURCE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Quellcode"):
        validate_hosted_settings()
    monkeypatch.setenv("SOULFLOW_SOURCE_URL", "https://github.com/example/soulflow")
    validate_hosted_settings()
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        validate_hosted_settings()


@pytest.mark.parametrize("origin", ["http://example.org", "https://user:password@example.org", "https://example.org/other", "https://example.org?token=test"])
def test_hosted_origin_is_exact_https_without_credentials(monkeypatch, origin):
    configured(monkeypatch)
    monkeypatch.setenv("SOULFLOW_PUBLIC_ORIGIN", origin)
    from app.runtime import public_origin
    with pytest.raises(RuntimeError):
        public_origin()


def test_hosted_never_exposes_local_demo_accounts(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("SOULFLOW_DEMO", "1")
    from app.runtime import validate_hosted_settings
    with pytest.raises(RuntimeError, match="Demo"):
        validate_hosted_settings()


def test_public_health_exposes_source_offer_without_secrets(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("SOULFLOW_SWISS_LICENSE", "agpl-3.0")
    monkeypatch.setenv("SOULFLOW_SOURCE_URL", "https://github.com/example/source/tree/v1.1.0")
    monkeypatch.setenv("CRON_SECRET", "private-test-only-secret-not-for-response")
    from app.main import health
    result = health()
    assert result["source_url"] == "https://github.com/example/source/tree/v1.1.0"
    assert result["license"] == "AGPL-3.0-only"
    assert set(result) == {"status", "mode", "version", "source_url", "license"}
