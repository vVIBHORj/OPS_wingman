"""
Unit Tests for Phase 5 Production Readiness & Packaging.

Verifies:
- Production configuration validation & secret requirements
- CORS origins parsing from JSON and comma-separated formats
- Liveness and readiness endpoints (/health, /health/live, /health/ready, /ready)
- Database unreadiness status (503 Service Unavailable on DB failure)
- Correlation ID middleware (X-Request-ID header propagation)
- CLI management commands (check-config, migration-status)
"""

import argparse
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import app
from scripts.ops import cmd_check_config, cmd_migration_status


# ==============================================================================
# 1. Configuration & Security Validation Tests
# ==============================================================================

def test_settings_development_defaults():
    """Verifies that development settings load with safe default parameters."""
    cfg = Settings(environment="development")
    assert cfg.environment == "development"
    assert cfg.backend_port == 8000
    assert cfg.backend_cors_origins == ["http://localhost:3000"]
    assert cfg.debug is False
    assert cfg.docs_enabled is True


def test_cors_origins_parsing_variants():
    """Verifies parsing of CORS origins from JSON list string, comma-separated string, or list."""
    # JSON list string
    cfg1 = Settings(backend_cors_origins='["https://app.opswingman.io", "https://admin.opswingman.io"]')
    assert cfg1.backend_cors_origins == ["https://app.opswingman.io", "https://admin.opswingman.io"]

    # Comma-separated string
    cfg2 = Settings(backend_cors_origins="https://app.opswingman.io, https://admin.opswingman.io")
    assert cfg2.backend_cors_origins == ["https://app.opswingman.io", "https://admin.opswingman.io"]

    # Native list
    cfg3 = Settings(backend_cors_origins=["https://local.test"])
    assert cfg3.backend_cors_origins == ["https://local.test"]


def test_production_settings_rejects_insecure_secrets():
    """Ensures production startup fails if default secret key is unchanged."""
    with pytest.raises(ValueError, match="APP_SECRET_KEY must be set to a secure"):
        Settings(
            environment="production",
            app_secret_key="change-this-insecure-secret-key-for-local-dev-only",
        )

    with pytest.raises(ValueError, match="APP_SECRET_KEY must be set to a secure"):
        Settings(
            environment="production",
            app_secret_key="short-secret",
        )


def test_production_settings_rejects_debug_mode():
    """Ensures production startup fails if debug mode is True."""
    with pytest.raises(ValueError, match="DEBUG must be set to False"):
        Settings(
            environment="production",
            debug=True,
            app_secret_key="a-very-long-production-grade-secret-key-12345",
        )


def test_production_settings_valid():
    """Verifies that production settings succeed with valid production secrets."""
    cfg = Settings(
        environment="production",
        debug=False,
        app_secret_key="a-very-long-production-grade-secret-key-12345",
        docs_enabled=False,
    )
    assert cfg.environment == "production"
    assert cfg.debug is False
    assert cfg.docs_enabled is False


# ==============================================================================
# 2. Health & Readiness Endpoint Tests
# ==============================================================================

def test_liveness_endpoints():
    """Tests /health and /health/live endpoints."""
    client = TestClient(app)

    res1 = client.get("/health")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "healthy"
    assert data1["services"]["api"] == "ok"

    res2 = client.get("/health/live")
    assert res2.status_code == 200
    assert res2.json() == {"status": "alive"}


def test_readiness_probe_database_healthy(db_session):
    """Verifies that /health/ready returns 200 when database connection is healthy."""
    client = TestClient(app)

    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["services"]["database"] == "ok"

    # Verify alias /ready
    res_alias = client.get("/ready")
    assert res_alias.status_code == 200


def test_readiness_probe_database_failure():
    """Verifies that /health/ready returns 503 Service Unavailable when DB is down."""
    client = TestClient(app)

    with patch("backend.main.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session.execute.side_effect = RuntimeError("Could not connect to PostgreSQL server: connection refused")
        mock_session_local.return_value.__enter__.return_value = mock_session

        res = client.get("/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "unready"
        assert data["services"]["database"] == "unavailable"
        assert "connection refused" in data["error"]


# ==============================================================================
# 3. Correlation ID & Security Headers Tests
# ==============================================================================

def test_correlation_id_middleware_generated():
    """Verifies that requests without X-Request-ID receive a generated UUID header."""
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    req_id = res.headers.get("X-Request-ID")
    assert req_id is not None
    assert len(req_id) >= 16


def test_correlation_id_middleware_preserved():
    """Verifies that an incoming X-Request-ID is preserved in the response."""
    client = TestClient(app)
    custom_id = "test-custom-request-id-998877"
    res = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_id


def test_cors_preflight_response():
    """Verifies CORS preflight headers against configured origins."""
    client = TestClient(app)
    res = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ==============================================================================
# 4. CLI Operations Tests
# ==============================================================================

def test_cli_check_config():
    """Tests that ops.py check-config returns 0 for development environment."""
    args = argparse.Namespace(env="development")
    ret = cmd_check_config(args)
    assert ret == 0


def test_cli_migration_status():
    """Tests that ops.py migration-status succeeds."""
    args = argparse.Namespace()
    ret = cmd_migration_status(args)
    assert ret == 0
