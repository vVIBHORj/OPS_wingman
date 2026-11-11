"""
Unit and Integration Tests for Support Tickets API Router (backend/api/routers/tickets.py).
Exercises ticket creation, retrieval, filtering, pagination, search, status updates, and 404 errors.
"""

import os
import tempfile
import uuid
from decimal import Decimal
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.main import app
from database.base import Base
from database.models import Customer, Order, OrderStatus, Product
from database.session import get_db

TEST_CUSTOMER_ID = uuid.UUID("11111111-2222-4333-8444-555555555555")
TEST_ORDER_ID = uuid.UUID("66666666-7777-4888-8999-aaaaaaaaaaaa")


@pytest.fixture(scope="function")
def ticket_client() -> Generator[TestClient, None, None]:
    """Provides a TestClient with an isolated temporary SQLite database session."""
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

    with TestingSessionLocal() as session:
        cust = Customer(
            id=TEST_CUSTOMER_ID,
            email="ticket.customer@example.com",
            first_name="Pooja",
            last_name="Sharma",
            city="Bengaluru",
            state="Karnataka",
            pincode="560001",
        )
        prod = Product(
            id=uuid.uuid4(),
            sku="SKU-TCK-01",
            name="Ergonomic Mouse",
            unit_price=Decimal("1299.00"),
            currency="INR",
            inventory_count=50,
            is_active=True,
        )
        order = Order(
            id=TEST_ORDER_ID,
            order_number="ORD-2026-TCK-01",
            customer_id=TEST_CUSTOMER_ID,
            status=OrderStatus.DELIVERED,
            currency="INR",
            total_amount=Decimal("1299.00"),
        )
        session.add_all([cust, prod, order])
        session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    try:
        os.remove(temp_db_path)
    except OSError:
        pass


def test_list_tickets_empty(ticket_client: TestClient):
    """GET /tickets initially returns an empty items list with total=0."""
    res = ticket_client.get("/tickets")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_create_ticket_success(ticket_client: TestClient):
    """POST /tickets successfully creates a ticket for a known customer."""
    payload = {
        "customer_id": str(TEST_CUSTOMER_ID),
        "order_id": str(TEST_ORDER_ID),
        "title": "Package delayed at hub",
        "description": "Shipment is stationary for more than 48 hours.",
        "priority": "HIGH",
        "channel": "PORTAL",
        "category": "DELIVERY_DELAY",
    }
    res = ticket_client.post("/tickets", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Package delayed at hub"
    assert data["status"] == "OPEN"
    assert data["priority"] == "HIGH"
    assert data["channel"] == "PORTAL"
    assert data["category"] == "DELIVERY_DELAY"
    assert data["ticket_number"].startswith("TCK-")
    assert data["customer_id"] == str(TEST_CUSTOMER_ID)


def test_create_ticket_customer_not_found(ticket_client: TestClient):
    """POST /tickets with a non-existent customer UUID returns 404."""
    unknown_id = str(uuid.uuid4())
    payload = {
        "customer_id": unknown_id,
        "title": "Unknown customer ticket",
        "description": "Should fail 404",
        "priority": "MEDIUM",
        "channel": "EMAIL",
    }
    res = ticket_client.post("/tickets", json=payload)
    assert res.status_code == 404
    assert f"Customer {unknown_id} not found" in res.json()["detail"]


def test_get_ticket_by_id(ticket_client: TestClient):
    """GET /tickets/{ticket_id} retrieves a created ticket by its UUID."""
    create_res = ticket_client.post(
        "/tickets",
        json={
            "customer_id": str(TEST_CUSTOMER_ID),
            "title": "Query regarding warranty",
            "description": "How do I claim a replacement?",
            "priority": "LOW",
            "channel": "WHATSAPP",
        },
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    get_res = ticket_client.get(f"/tickets/{ticket_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == ticket_id
    assert get_res.json()["title"] == "Query regarding warranty"


def test_get_ticket_by_id_not_found(ticket_client: TestClient):
    """GET /tickets/{ticket_id} with unknown UUID returns 404."""
    res = ticket_client.get(f"/tickets/{uuid.uuid4()}")
    assert res.status_code == 404


def test_list_tickets_with_filters_and_search(ticket_client: TestClient):
    """GET /tickets supports filtering by status, priority, channel, and free-text search."""
    # Create 3 tickets with varied attributes
    ticket_client.post(
        "/tickets",
        json={
            "customer_id": str(TEST_CUSTOMER_ID),
            "title": "Urgent Damaged Item on Arrival",
            "description": "Outer box crushed and glass broken.",
            "priority": "URGENT",
            "channel": "PHONE",
        },
    )
    t2_res = ticket_client.post(
        "/tickets",
        json={
            "customer_id": str(TEST_CUSTOMER_ID),
            "title": "Refund inquiry for returned order",
            "description": "Return delivered yesterday.",
            "priority": "LOW",
            "channel": "EMAIL",
        },
    )
    t2_id = t2_res.json()["id"]

    # Mark second ticket in progress
    ticket_client.post(f"/tickets/{t2_id}/status", json={"status": "IN_PROGRESS"})

    # Filter by priority=URGENT
    res_urgent = ticket_client.get("/tickets?priority=URGENT")
    assert res_urgent.status_code == 200
    assert res_urgent.json()["total"] == 1
    assert res_urgent.json()["items"][0]["priority"] == "URGENT"

    # Filter by status=IN_PROGRESS
    res_prog = ticket_client.get("/tickets?status=IN_PROGRESS")
    assert res_prog.status_code == 200
    assert res_prog.json()["total"] == 1
    assert res_prog.json()["items"][0]["status"] == "IN_PROGRESS"

    # Filter by channel=EMAIL
    res_email = ticket_client.get("/tickets?channel=EMAIL")
    assert res_email.status_code == 200
    assert res_email.json()["total"] == 1

    # Search by text "Damaged"
    res_search = ticket_client.get("/tickets?search=Damaged")
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 1
    assert "Damaged" in res_search.json()["items"][0]["title"]


def test_update_ticket_status_resolved(ticket_client: TestClient):
    """POST /tickets/{id}/status updates status and populates resolved_at when RESOLVED."""
    create_res = ticket_client.post(
        "/tickets",
        json={
            "customer_id": str(TEST_CUSTOMER_ID),
            "title": "Invoice GSTIN correction",
            "description": "Please add company GST number.",
            "priority": "MEDIUM",
            "channel": "PORTAL",
        },
    )
    ticket_id = create_res.json()["id"]

    # Resolve ticket
    res = ticket_client.post(
        f"/tickets/{ticket_id}/status",
        json={
            "status": "RESOLVED",
            "resolution_notes": "Updated tax invoice generated with GSTIN and sent via email.",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "RESOLVED"
    assert data["resolved_at"] is not None
    assert "[Resolution Note]: Updated tax invoice" in data["description"]


def test_update_ticket_status_not_found(ticket_client: TestClient):
    """POST /tickets/{id}/status with unknown UUID returns 404."""
    res = ticket_client.post(
        f"/tickets/{uuid.uuid4()}/status",
        json={"status": "RESOLVED"},
    )
    assert res.status_code == 404
