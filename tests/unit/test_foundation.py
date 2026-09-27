"""
Unit tests for Phase 0 Foundation verification.
"""

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify that root endpoint responds with Phase 0 status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "OpsWingman API"
    assert "Phase 0" in data["phase"]
    assert data["status"] == "operational"


def test_health_endpoint():
    """Verify that health check endpoint returns healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["api"] == "ok"


def test_package_structure():
    """Verify that core package namespaces are importable."""
    import backend
    import backend.api
    import backend.agents
    import backend.workflows
    import backend.tools
    import backend.policies
    import backend.rag
    import backend.ml
    import backend.approvals
    import backend.audit
    import backend.security
    import backend.evaluation
    import database
    import simulator
    import workers
    import integrations
    import evals

    assert backend is not None
    assert database is not None
    assert simulator is not None
    assert workers is not None
    assert integrations is not None
    assert evals is not None
