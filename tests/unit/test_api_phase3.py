"""API integration tests for Phase 3 Knowledge and Approval endpoints."""

import os
import tempfile
import uuid
from decimal import Decimal
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base
from database.session import get_db
from database.models import (
    ApprovalRecord,
    Customer,
    DomainEvent,
    KnowledgeChunk,
    KnowledgeDocument,
    Order,
    OrderItem,
    Payment,
    Product,
    Shipment,
    Ticket,
)
from backend.main import app
from backend.approvals.service import ApprovalService
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.tools.schemas import StructuredAction
from database.models.enums import ApprovalStatus, DocumentType, OrderStatus, PaymentMethod


@pytest.fixture(scope="function")
def api_test_db() -> Generator[Session, None, None]:
    """Provides an isolated SQLite file DB session for API tests."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{temp_db_path}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    seed_default_knowledge(session)

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


@pytest.fixture(scope="function")
def client(api_test_db: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield api_test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_api_ingest_and_get_document(client: TestClient):
    payload = {
        "document_id": "POL-API-001",
        "title": "API Ingested Policy",
        "doc_type": "POLICY",
        "source": "api://test/ingest.md",
        "version": "1.0.0",
        "content": "All requests through API are validated strictly against domain schemas.",
        "metadata": {"test": True},
    }
    res = client.post("/knowledge/documents", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["document_id"] == "POL-API-001"
    assert data["title"] == "API Ingested Policy"

    # Get single
    res_get = client.get("/knowledge/documents/POL-API-001")
    assert res_get.status_code == 200
    assert res_get.json()["document_id"] == "POL-API-001"

    # List
    res_list = client.get("/knowledge/documents?doc_type=POLICY")
    assert res_list.status_code == 200
    assert any(d["document_id"] == "POL-API-001" for d in res_list.json())


def test_api_retrieve_knowledge(client: TestClient):
    payload = {
        "query": "cancellation policy before shipping",
        "top_k": 3,
        "min_similarity": 0.0,
    }
    res = client.post("/knowledge/retrieve", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] > 0
    assert len(data["results"]) > 0
    assert any("POL-CAN-001" in r["document_id"] for r in data["results"])


def test_api_approval_lifecycle(client: TestClient, api_test_db: Session):
    service = ApprovalService(api_test_db)
    action = StructuredAction(
        action_name="cancel_order",
        parameters={"order_id": str(uuid.uuid4())},
        reason="Customer cancellation",
        risk="HIGH",
    )
    record = service.create_approval(
        workflow_id="wf-api-test-001",
        action=action,
        risk_level="HIGH",
        reason="Supervisor review",
    )

    # 1. List approvals
    res_list = client.get("/approvals?status=PENDING")
    assert res_list.status_code == 200
    assert any(a["id"] == str(record.id) for a in res_list.json())

    # 2. Get approval by ID
    res_get = client.get(f"/approvals/{record.id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == str(record.id)

    # 3. Approve
    res_approve = client.post(
        f"/approvals/{record.id}/approve",
        json={"approver_identity": "manager@opswingman.local"},
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "APPROVED"
    assert res_approve.json()["approver_identity"] == "manager@opswingman.local"


def test_api_reject_approval(client: TestClient, api_test_db: Session):
    service = ApprovalService(api_test_db)
    action = StructuredAction(
        action_name="request_refund",
        parameters={"amount": 9000},
        reason="Customer refund",
        risk="HIGH",
    )
    record = service.create_approval(
        workflow_id="wf-api-test-002",
        action=action,
        risk_level="HIGH",
        reason="Supervisor review",
    )

    # Reject
    res_reject = client.post(
        f"/approvals/{record.id}/reject",
        json={
            "approver_identity": "supervisor@opswingman.local",
            "rejection_reason": "Suspected fraudulent transaction",
        },
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "REJECTED"
    assert res_reject.json()["rejection_reason"] == "Suspected fraudulent transaction"
