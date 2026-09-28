"""
Unit and Integration Tests for Domain Events (Phase 1.4).
Verifies deterministic event capture, transactional integrity, payload richness, and read-only API query endpoints.
"""

import uuid
import os
import tempfile
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database.base import Base
from database.session import get_db
from database.models import (
    Customer,
    Product,
    Order,
    Payment,
    Shipment,
    DomainEvent,
    EventType,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    ShipmentStatus,
)
from backend.main import app
import simulator


@pytest.fixture(scope="function")
def test_db():
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Pre-populate sample customer & products
    cust = Customer(
        id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        email="events.user@example.com",
        first_name="Rohan",
        last_name="Verma",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
    )
    prod = Product(
        id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        sku="SKU-EVT-01",
        name="Noise Cancelling Earbuds",
        unit_price=Decimal("2499.00"),
        currency="INR",
        inventory_count=50,
        is_active=True,
    )
    session.add(cust)
    session.add(prod)
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def api_client():
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
            id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
            email="events.api@example.com",
            first_name="Pooja",
            last_name="Sharma",
            city="Delhi",
            state="Delhi",
            pincode="110001",
        )
        prod = Product(
            id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
            sku="SKU-EVT-API",
            name="Ergonomic Mouse",
            unit_price=Decimal("1200.00"),
            currency="INR",
            inventory_count=30,
            is_active=True,
        )
        session.add(cust)
        session.add(prod)
        session.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass


# ==============================================================================
# Simulator Domain Event Unit Tests
# ==============================================================================

def test_event_created_on_order_created(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 2, "unit_price": Decimal("2499.00")}],
    )

    events = simulator.list_events_for_entity(test_db, entity_type="order", entity_id=order.id)
    assert len(events) == 1
    event = events[0]

    assert event.event_type == EventType.ORDER_CREATED.value
    assert event.entity_type == "order"
    assert event.entity_id == order.id
    assert event.payload["order_number"] == order.order_number
    assert event.payload["customer_id"] == str(customer_id)
    assert Decimal(str(event.payload["total_amount"])) == order.total_amount
    assert event.payload["status"] == OrderStatus.PENDING.value
    assert event.payload["item_count"] == 1


def test_event_created_on_order_status_changed(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    simulator.update_order_status(
        session=test_db,
        order_id=order.id,
        new_status=OrderStatus.CONFIRMED,
    )

    events = simulator.list_events_for_entity(test_db, entity_type="order", entity_id=order.id)
    assert len(events) == 2

    status_event = events[1]
    assert status_event.event_type == EventType.ORDER_STATUS_CHANGED.value
    assert status_event.payload["previous_status"] == OrderStatus.PENDING.value
    assert status_event.payload["new_status"] == OrderStatus.CONFIRMED.value


def test_event_created_on_order_cancelled(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    simulator.cancel_order(
        session=test_db,
        order_id=order.id,
        reason="Customer requested cancellation before dispatch",
    )

    events = simulator.list_events_for_entity(test_db, entity_type="order", entity_id=order.id)
    assert len(events) == 2

    cancel_event = events[1]
    assert cancel_event.event_type == EventType.ORDER_CANCELLED.value
    assert cancel_event.payload["previous_status"] == OrderStatus.PENDING.value
    assert cancel_event.payload["new_status"] == OrderStatus.CANCELLED.value
    assert cancel_event.payload["reason"] == "Customer requested cancellation before dispatch"


def test_event_created_on_payment_lifecycle(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    # 1. Payment Initiated
    payment = simulator.create_payment(
        session=test_db,
        order_id=order.id,
        payment_method=PaymentMethod.UPI,
    )
    p_events = simulator.list_events_for_entity(test_db, entity_type="payment", entity_id=payment.id)
    assert len(p_events) == 1
    assert p_events[0].event_type == EventType.PAYMENT_INITIATED.value
    assert p_events[0].payload["status"] == PaymentStatus.INITIATED.value
    assert p_events[0].payload["payment_method"] == PaymentMethod.UPI.value

    # 2. Payment Captured / Successful
    simulator.capture_payment(
        session=test_db,
        payment_id=payment.id,
        gateway_transaction_id="pay_upi_success_12345",
    )
    p_events = simulator.list_events_for_entity(test_db, entity_type="payment", entity_id=payment.id)
    assert len(p_events) == 2
    assert p_events[1].event_type == EventType.PAYMENT_SUCCESSFUL.value
    assert p_events[1].payload["previous_status"] == PaymentStatus.INITIATED.value
    assert p_events[1].payload["new_status"] == PaymentStatus.SUCCESSFUL.value
    assert p_events[1].payload["gateway_transaction_id"] == "pay_upi_success_12345"


def test_event_created_on_payment_failed(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    payment = simulator.create_payment(
        session=test_db,
        order_id=order.id,
        payment_method=PaymentMethod.CARD,
    )

    simulator.fail_payment(
        session=test_db,
        payment_id=payment.id,
        error_code="CARD_DECLINED",
        error_message="Insufficient balance in card",
    )

    p_events = simulator.list_events_for_entity(test_db, entity_type="payment", entity_id=payment.id)
    assert len(p_events) == 2
    fail_event = p_events[1]
    assert fail_event.event_type == EventType.PAYMENT_FAILED.value
    assert fail_event.payload["previous_status"] == PaymentStatus.INITIATED.value
    assert fail_event.payload["new_status"] == PaymentStatus.FAILED.value
    assert fail_event.payload["error_code"] == "CARD_DECLINED"
    assert fail_event.payload["error_message"] == "Insufficient balance in card"


def test_event_created_on_shipment_lifecycle(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )
    payment = simulator.create_payment(session=test_db, order_id=order.id)
    simulator.capture_payment(session=test_db, payment_id=payment.id)

    # 1. Create Shipment
    shipment = simulator.create_shipment(
        session=test_db,
        order_id=order.id,
        carrier="BlueDart",
    )
    s_events = simulator.list_events_for_entity(test_db, entity_type="shipment", entity_id=shipment.id)
    assert len(s_events) == 1
    assert s_events[0].event_type == EventType.SHIPMENT_CREATED.value
    assert s_events[0].payload["carrier"] == "BlueDart"

    # 2. Update Shipment Status to In Transit
    simulator.update_shipment_status(
        session=test_db,
        shipment_id=shipment.id,
        new_status=ShipmentStatus.IN_TRANSIT,
        location="Bengaluru Hub",
    )
    s_events = simulator.list_events_for_entity(test_db, entity_type="shipment", entity_id=shipment.id)
    assert len(s_events) == 2
    assert s_events[1].event_type == EventType.SHIPMENT_STATUS_CHANGED.value
    assert s_events[1].payload["previous_status"] == ShipmentStatus.MANIFESTED.value
    assert s_events[1].payload["new_status"] == ShipmentStatus.IN_TRANSIT.value

    # 3. Delay Shipment
    revised_eta = datetime.now(timezone.utc) + timedelta(days=2)
    simulator.delay_shipment(
        session=test_db,
        shipment_id=shipment.id,
        delay_reason="Highway flood blockage",
        updated_eta=revised_eta,
        current_location="Hosur Transit Point",
    )
    s_events = simulator.list_events_for_entity(test_db, entity_type="shipment", entity_id=shipment.id)
    assert len(s_events) == 3
    delay_event = s_events[2]
    assert delay_event.event_type == EventType.SHIPMENT_DELAYED.value
    assert delay_event.payload["delay_reason"] == "Highway flood blockage"
    assert delay_event.payload["current_location"] == "Hosur Transit Point"
    assert "revised_eta" in delay_event.payload

    # 4. Resume to OUT_FOR_DELIVERY and Deliver Shipment
    simulator.update_shipment_status(
        session=test_db,
        shipment_id=shipment.id,
        new_status=ShipmentStatus.OUT_FOR_DELIVERY,
        location="Local Delivery Hub",
    )
    deliv_time = datetime.now(timezone.utc)
    simulator.deliver_shipment(
        session=test_db,
        shipment_id=shipment.id,
        actual_delivery_date=deliv_time,
        recipient_notes="Signed by Security Guard",
    )
    s_events = simulator.list_events_for_entity(test_db, entity_type="shipment", entity_id=shipment.id)
    assert len(s_events) == 5
    deliv_event = s_events[4]
    assert deliv_event.event_type == EventType.SHIPMENT_DELIVERED.value
    assert deliv_event.payload["previous_status"] == ShipmentStatus.OUT_FOR_DELIVERY.value
    assert deliv_event.payload["new_status"] == ShipmentStatus.DELIVERED.value
    assert deliv_event.payload["recipient_notes"] == "Signed by Security Guard"


def test_failed_business_operation_does_not_create_event_same_transaction(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )
    initial_event_count = len(simulator.list_events(test_db))

    # Attempt illegal transition (from PENDING directly to DELIVERED)
    with pytest.raises(simulator.InvalidStateTransitionError):
        simulator.update_order_status(
            session=test_db,
            order_id=order.id,
            new_status=OrderStatus.DELIVERED,
        )

    # Verify no new event was persisted
    post_event_count = len(simulator.list_events(test_db))
    assert post_event_count == initial_event_count


def test_multiple_events_maintain_chronological_ordering(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )
    simulator.update_order_status(session=test_db, order_id=order.id, new_status=OrderStatus.CONFIRMED)
    simulator.update_order_status(session=test_db, order_id=order.id, new_status=OrderStatus.PROCESSING)
    payment = simulator.create_payment(session=test_db, order_id=order.id)
    simulator.capture_payment(session=test_db, payment_id=payment.id)
    shipment = simulator.create_shipment(session=test_db, order_id=order.id)
    simulator.update_shipment_status(session=test_db, shipment_id=shipment.id, new_status=ShipmentStatus.IN_TRANSIT)
    simulator.deliver_shipment(session=test_db, shipment_id=shipment.id)

    all_events = simulator.list_events(test_db)
    assert len(all_events) >= 6

    # Verify timestamps are monotonically non-decreasing
    for i in range(1, len(all_events)):
        assert all_events[i].occurred_at >= all_events[i - 1].occurred_at


# ==============================================================================
# Domain Event REST API Tests
# ==============================================================================

def test_api_get_event_by_id_and_filters(api_client: TestClient):
    # 1. Create an order via API
    order_res = api_client.post(
        "/orders",
        json={
            "customer_id": "11111111-1111-4111-8111-111111111111",
            "items": [{"product_id": "22222222-2222-4222-8222-222222222222", "quantity": 1}],
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # 2. List events via GET /events
    events_res = api_client.get("/events")
    assert events_res.status_code == 200
    events_list = events_res.json()
    assert len(events_list) >= 1

    created_event = next(e for e in events_list if e["entity_id"] == order_id)
    assert created_event["event_type"] == "ORDER_CREATED"
    assert created_event["entity_type"] == "order"
    event_id = created_event["id"]

    # 3. Query event by ID: GET /events/{event_id}
    single_res = api_client.get(f"/events/{event_id}")
    assert single_res.status_code == 200
    assert single_res.json()["id"] == event_id
    assert single_res.json()["payload"]["status"] == "PENDING"

    # 4. Filter by entity_type and entity_id: GET /events?entity_type=order&entity_id=...
    filtered_res = api_client.get(f"/events?entity_type=order&entity_id={order_id}")
    assert filtered_res.status_code == 200
    filtered_events = filtered_res.json()
    assert len(filtered_events) == 1
    assert filtered_events[0]["id"] == event_id

    # 5. Filter by event_type: GET /events?event_type=ORDER_CREATED
    type_res = api_client.get("/events?event_type=ORDER_CREATED")
    assert type_res.status_code == 200
    type_events = type_res.json()
    assert all(e["event_type"] == "ORDER_CREATED" for e in type_events)


def test_api_get_event_not_found(api_client: TestClient):
    random_id = str(uuid.uuid4())
    res = api_client.get(f"/events/{random_id}")
    assert res.status_code == 404
    assert res.json()["error"] == "EntityNotFoundError"
