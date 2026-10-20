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


def test_hosted_includes_only_exact_platform_deployment_host(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("VERCEL_URL", "soulflow-qa-deployment.vercel.app")
    from app.runtime import allowed_hosts
    assert allowed_hosts() == ["soulflow.example.org", "soulflow-qa-deployment.vercel.app"]


@pytest.mark.parametrize("value", ["*.vercel.app", "https://soulflow.vercel.app", "user@soulflow.vercel.app", "other.example.org", "soulflow.vercel.app:443"])
def test_platform_host_rejects_wildcards_urls_and_other_domains(monkeypatch, value):
    configured(monkeypatch)
    monkeypatch.setenv("VERCEL_URL", value)
    from app.runtime import allowed_hosts
    assert allowed_hosts() == ["soulflow.example.org"]


def test_deployment_host_is_restricted_to_authenticated_cron_route(monkeypatch):
    import asyncio
    from starlette.requests import Request
    from starlette.responses import Response
    from app.main import guard
    configured(monkeypatch)
    monkeypatch.setenv("VERCEL_URL", "soulflow-qa-deployment.vercel.app")
    async def endpoint(_request):
        return Response(status_code=204)
    def request(path, method="GET"):
        return Request({"type":"http", "method":method, "scheme":"https", "path":path,
                        "headers":[(b"host",b"soulflow-qa-deployment.vercel.app")],
                        "client":("203.0.113.7",1234), "server":("soulflow-qa-deployment.vercel.app",443)})
    # The endpoint itself still requires its bearer secret; this checks routing.
    assert asyncio.run(guard(request("/api/internal/learning-updates"),endpoint)).status_code == 204
    assert asyncio.run(guard(request("/api/auth/me"),endpoint)).status_code == 400
    assert asyncio.run(guard(request("/"),endpoint)).status_code == 400
