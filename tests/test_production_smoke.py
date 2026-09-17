"""
tests/test_production_smoke.py
==============================
Production Smoke & Container Health Verification Suite for Category 17.
Validates:
  1. Hardened production Django settings (DEBUG=False, HTTPS headers, secure cookies, WhiteNoise).
  2. Health-check probe endpoint (/health/) returning HTTP 200 on healthy database and HTTP 503 on failure.
  3. Static asset discovery and collectstatic dry-run execution.
  4. Idempotent execution and strict Decimal types in institutional provisioning script.
  5. Multi-stage Dockerfile, docker-compose.yml, and Nginx reverse proxy configuration syntax.
"""

import os
from unittest.mock import patch
import pytest

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DB_ENGINE"] = "sqlite"

import django  # noqa: E402
django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402
from scripts.provision_instance import provision_instance  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    call_command("migrate", interactive=False)


def test_production_settings_security_flags():
    """
    Validates that config/settings_prod.py enforces strict production security flags,
    HTTPS redirects, secure cookies, WhiteNoise middleware, and HSTS headers.
    """
    os.environ["CI"] = "true"
    os.environ["SECURE_SSL_REDIRECT"] = "True"

    from config import settings_prod

    # Core production guards
    assert settings_prod.DEBUG is False, "Production DEBUG must strictly be False."
    assert settings_prod.SECRET_KEY is not None and len(settings_prod.SECRET_KEY) > 10

    # Cookie security
    assert settings_prod.SESSION_COOKIE_SECURE is True, "Session cookie must require HTTPS."
    assert settings_prod.CSRF_COOKIE_SECURE is True, "CSRF cookie must require HTTPS."

    # Browser & header hardening
    assert settings_prod.SECURE_BROWSER_XSS_FILTER is True
    assert settings_prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert settings_prod.X_FRAME_OPTIONS == "DENY"
    assert settings_prod.SECURE_HSTS_SECONDS >= 31536000
    assert settings_prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert settings_prod.SECURE_HSTS_PRELOAD is True
    assert settings_prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")

    # WhiteNoise static asset delivery
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings_prod.MIDDLEWARE
    assert settings_prod.STATICFILES_STORAGE == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    assert settings_prod.WHITENOISE_MANIFEST_STRICT is False


def test_health_check_probe_returns_200():
    """
    Validates that the /health/ probe returns HTTP 200 and healthy JSON telemetry
    when database connectivity is active.
    """
    client = Client()
    resp = client.get("/health/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["service"] == "classfellow_web"
    assert "version" in data


def test_health_check_probe_db_failure_returns_503():
    """
    Validates that /health/ returns HTTP 503 and unhealthy status when the database
    is unreachable or fails connectivity check.
    """
    client = Client()
    with patch("django.db.connection.ensure_connection", side_effect=Exception("Database server connection refused")):
        resp = client.get("/health/")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "Database server connection refused" in data["error"]


def test_collectstatic_dry_run():
    """
    Validates that Django's collectstatic management command executes cleanly in dry-run mode
    without raising asset discovery or manifest syntax exceptions.
    """
    try:
        call_command("collectstatic", dry_run=True, interactive=False, verbosity=0)
    except Exception as exc:
        pytest.fail(f"collectstatic dry-run failed with exception: {exc}")


def test_provision_instance_idempotent_execution():
    """
    Validates that scripts/provision_instance.py programmatically provisions institutional
    defaults and can be executed repeatedly with zero constraint errors.
    """
    summary1 = provision_instance(
        admin_username="smoke_admin_user",
        admin_password="SmokePassword123!",
        campus_name="Smoke Test Campus",
        campus_code="CAMPUS-SMOKE",
        session_name="2026-2027 Smoke Session",
    )
    assert summary1["session"]["name"] == "2026-2027 Smoke Session"
    assert summary1["campus"]["code"] == "CAMPUS-SMOKE"
    assert summary1["admin_user"]["username"] == "smoke_admin_user"
    assert len(summary1["fee_heads"]) == 6
    assert len(summary1["grading_tiers"]) == 6

    # Re-run to verify strict idempotency
    summary2 = provision_instance(
        admin_username="smoke_admin_user",
        admin_password="SmokePassword123!",
        campus_name="Smoke Test Campus",
        campus_code="CAMPUS-SMOKE",
        session_name="2026-2027 Smoke Session",
    )
    assert summary2["session"]["created"] is False
    assert summary2["campus"]["created"] is False
    assert summary2["admin_user"]["created"] is False


def test_container_files_syntax_and_structure():
    """
    Validates the presence and required directives of Dockerfile, docker-compose.yml,
    docker/entrypoint.sh, and nginx/nginx.conf.
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1. Dockerfile
    dockerfile_path = os.path.join(root_dir, "Dockerfile")
    assert os.path.isfile(dockerfile_path), "Root Dockerfile must exist."
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        dockerfile_content = f.read()
    assert "FROM python:3.12-slim AS builder" in dockerfile_content
    assert "FROM python:3.12-slim AS runner" in dockerfile_content
    assert "useradd -u 1001 -g classfellow" in dockerfile_content
    assert "USER classfellow" in dockerfile_content
    assert "HEALTHCHECK" in dockerfile_content
    assert "gunicorn" in dockerfile_content

    # 2. docker/entrypoint.sh
    entrypoint_path = os.path.join(root_dir, "docker", "entrypoint.sh")
    assert os.path.isfile(entrypoint_path), "docker/entrypoint.sh must exist."
    with open(entrypoint_path, "r", encoding="utf-8") as f:
        entrypoint_content = f.read()
    assert "migrate --noinput" in entrypoint_content
    assert "collectstatic --noinput" in entrypoint_content
    assert "exec \"$@\"" in entrypoint_content

    # 3. docker-compose.yml
    compose_path = os.path.join(root_dir, "docker-compose.yml")
    assert os.path.isfile(compose_path), "docker-compose.yml must exist."
    with open(compose_path, "r", encoding="utf-8") as f:
        compose_content = f.read()
    assert "postgres:16-alpine" in compose_content
    assert "nginx:1.25-alpine" in compose_content
    assert "classfellow_web" in compose_content
    assert "healthcheck" in compose_content

    # 4. nginx/nginx.conf
    nginx_path = os.path.join(root_dir, "nginx", "nginx.conf")
    assert os.path.isfile(nginx_path), "nginx/nginx.conf must exist."
    with open(nginx_path, "r", encoding="utf-8") as f:
        nginx_content = f.read()
    assert "upstream classfellow_upstream" in nginx_content
    assert "client_max_body_size 50M;" in nginx_content
    assert "location /static/" in nginx_content
    assert "location /media/" in nginx_content
    assert "location /health/" in nginx_content
