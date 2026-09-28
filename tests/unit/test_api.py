"""
Comprehensive API Integration & Unit Tests for OpsWingman Operational REST API (Phase 1.3).
Exercises all endpoints via FastAPI TestClient over HTTP.
"""

import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os
import tempfile
from database.base import Base
from database.session import get_db
from database.models import Customer, Product, OrderStatus, PaymentStatus, ShipmentStatus
from backend.main import app


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

    # Pre-populate sample customer and product
    with TestingSessionLocal() as session:
        cust = Customer(
            id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
            email="api.user@example.com",
            first_name="Aarav",
            last_name="Mehta",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
        )
        prod1 = Product(
            id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            sku="SKU-API-01",
            name="Smart Wireless Speaker",
            unit_price=Decimal("1999.00"),
            currency="INR",
            inventory_count=80,
            is_active=True,
        )
        prod2 = Product(
            id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            sku="SKU-API-02",
            name="Bluetooth Smart Tag",
            unit_price=Decimal("499.00"),
            currency="INR",
            inventory_count=200,
            is_active=True,
        )
        session.add_all([cust, prod1, prod2])
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
    engine.dispose()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass


# ==============================================================================
# 1. Base & Health Endpoints
# ==============================================================================

def test_api_health_and_root(api_client: TestClient):
    """Verify health check and root endpoints."""
    res_health = api_client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_root = api_client.get("/")
    assert res_root.status_code == 200
    assert "OpsWingman API" in res_root.json()["name"]


# ==============================================================================
# 2. Customer & Product Endpoints
# ==============================================================================

def test_get_customer_by_id(api_client: TestClient):
    """Verify customer lookup endpoint."""
    cust_id = "11111111-1111-4111-8111-111111111111"
    res = api_client.get(f"/customers/{cust_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "api.user@example.com"
    assert data["first_name"] == "Aarav"


def test_get_products_and_sku_filter(api_client: TestClient):
    """Verify product lookup and SKU query."""
    res_all = api_client.get("/products")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 2

    res_sku = api_client.get("/products?sku=SKU-API-01")
    assert res_sku.status_code == 200
    assert res_sku.json()["name"] == "Smart Wireless Speaker"


# ==============================================================================
# 3. Order Endpoints & Validations
# ==============================================================================

def test_create_and_retrieve_order(api_client: TestClient):
    """Verify order creation and lookup by ID and order_number."""
    payload = {
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [
            {"sku": "SKU-API-01", "quantity": 1},
            {"sku": "SKU-API-02", "quantity": 2},
        ],
        "shipping_amount": "50.00",
        "discount_amount": "0.00",
    }
    res = api_client.post("/orders", json=payload)
    assert res.status_code == 201
    order_data = res.json()
    assert order_data["status"] == "PENDING"
    assert order_data["subtotal_amount"] == "2997.00"  # 1999 + 499*2 = 2997
    assert order_data["tax_amount"] == "539.46"        # 18% of 2997
    assert order_data["total_amount"] == "3586.46"     # 2997 + 539.46 + 50
    order_id = order_data["id"]
    order_number = order_data["order_number"]

    # Lookup by ID
    res_id = api_client.get(f"/orders/{order_id}")
    assert res_id.status_code == 200
    assert res_id.json()["id"] == order_id

    # Lookup by order_number
    res_num = api_client.get(f"/orders?order_number={order_number}")
    assert res_num.status_code == 200
    assert res_num.json()["order_number"] == order_number


def test_cancel_order_via_api(api_client: TestClient):
    """Verify active order cancellation."""
    payload = {
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 1}],
    }
    create_res = api_client.post("/orders", json=payload)
    order_id = create_res.json()["id"]

    cancel_res = api_client.post(
        f"/orders/{order_id}/cancel",
        json={"reason": "Customer requested order cancellation before processing."},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"
    assert cancel_res.json()["cancellation_reason"] == "Customer requested order cancellation before processing."


def test_invalid_order_transition_returns_409(api_client: TestClient):
    """Verify illegal state transition returns HTTP 409 Conflict."""
    payload = {
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 1}],
    }
    create_res = api_client.post("/orders", json=payload)
    order_id = create_res.json()["id"]

    # Attempt illegal jump PENDING -> DELIVERED
    status_res = api_client.post(
        f"/orders/{order_id}/status",
        json={"status": "DELIVERED"},
    )
    assert status_res.status_code == 409
    assert status_res.json()["error"] == "InvalidStateTransitionError"


# ==============================================================================
# 4. Payment Endpoints
# ==============================================================================

def test_payment_creation_and_capture_flow(api_client: TestClient):
    """Verify creating and capturing a payment advances order to CONFIRMED."""
    order_res = api_client.post("/orders", json={
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 1}],
    })
    order_id = order_res.json()["id"]

    # Create Payment
    pay_res = api_client.post(f"/orders/{order_id}/payments", json={
        "payment_method": "UPI",
    })
    assert pay_res.status_code == 201
    payment_id = pay_res.json()["id"]
    assert pay_res.json()["status"] == "INITIATED"

    # Capture Payment
    cap_res = api_client.post(f"/payments/{payment_id}/capture", json={
        "gateway_transaction_id": "rzp_api_test_555",
    })
    assert cap_res.status_code == 200
    assert cap_res.json()["status"] == "SUCCESSFUL"
    assert cap_res.json()["gateway_transaction_id"] == "rzp_api_test_555"
    assert cap_res.json()["paid_at"] is not None

    # Check order status is now CONFIRMED
    refreshed_order = api_client.get(f"/orders/{order_id}").json()
    assert refreshed_order["status"] == "CONFIRMED"


def test_payment_failure_flow(api_client: TestClient):
    """Verify recording payment failure with error details."""
    order_res = api_client.post("/orders", json={
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 1}],
    })
    order_id = order_res.json()["id"]

    pay_res = api_client.post(f"/orders/{order_id}/payments", json={"payment_method": "CARD"})
    payment_id = pay_res.json()["id"]

    fail_res = api_client.post(f"/payments/{payment_id}/fail", json={
        "error_code": "GATEWAY_TIMEOUT",
        "error_message": "Issuer bank timed out.",
    })
    assert fail_res.status_code == 200
    assert fail_res.json()["status"] == "FAILED"
    assert fail_res.json()["error_code"] == "GATEWAY_TIMEOUT"


# ==============================================================================
# 5. Shipment Endpoints
# ==============================================================================

def test_shipment_delay_flow(api_client: TestClient):
    """Verify creating a shipment and recording a delay."""
    order_res = api_client.post("/orders", json={
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 1}],
    })
    order_id = order_res.json()["id"]

    ship_res = api_client.post(f"/orders/{order_id}/shipments", json={
        "carrier": "BlueDart",
        "estimated_days": 4,
    })
    assert ship_res.status_code == 201
    shipment_id = ship_res.json()["id"]
    tracking_number = ship_res.json()["tracking_number"]

    # Delay shipment
    delay_res = api_client.post(f"/shipments/{shipment_id}/delay", json={
        "delay_reason": "Severe rainfall at Hubli Hub",
        "current_location": "BlueDart Hubli Transit Facility",
    })
    assert delay_res.status_code == 200
    assert delay_res.json()["status"] == "DELAYED"
    assert delay_res.json()["delay_reason"] == "Severe rainfall at Hubli Hub"

    # Query by tracking number
    track_res = api_client.get(f"/shipments?tracking_number={tracking_number}")
    assert track_res.status_code == 200
    assert track_res.json()["id"] == shipment_id


def test_shipment_delivery_flow(api_client: TestClient):
    """Verify shipment delivery advances order to DELIVERED."""
    order_res = api_client.post("/orders", json={
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 1}],
    })
    order_id = order_res.json()["id"]

    ship_res = api_client.post(f"/orders/{order_id}/shipments", json={"carrier": "Delhivery"})
    shipment_id = ship_res.json()["id"]

    # Move to IN_TRANSIT
    api_client.post(f"/shipments/{shipment_id}/status", json={"status": "IN_TRANSIT"})

    # Deliver
    deliv_res = api_client.post(f"/shipments/{shipment_id}/deliver", json={
        "recipient_notes": "Delivered and signed by Aarav Mehta",
    })
    assert deliv_res.status_code == 200
    assert deliv_res.json()["status"] == "DELIVERED"
    assert deliv_res.json()["actual_delivery_date"] is not None

    # Check Order status
    order_data = api_client.get(f"/orders/{order_id}").json()
    assert order_data["status"] == "DELIVERED"


# ==============================================================================
# 6. Error Mappings (404, 409, 422)
# ==============================================================================

def test_entity_not_found_returns_404(api_client: TestClient):
    """Verify querying non-existent entities returns HTTP 404."""
    fake_id = str(uuid.uuid4())
    res_cust = api_client.get(f"/customers/{fake_id}")
    assert res_cust.status_code == 404
    assert res_cust.json()["error"] == "EntityNotFoundError"

    res_order = api_client.get(f"/orders/{fake_id}")
    assert res_order.status_code == 404

    res_payment = api_client.get(f"/payments/{fake_id}")
    assert res_payment.status_code == 404

    res_shipment = api_client.get(f"/shipments/{fake_id}")
    assert res_shipment.status_code == 404


def test_business_rule_violation_returns_422(api_client: TestClient):
    """Verify business rule violations return HTTP 422."""
    order_res = api_client.post("/orders", json={
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 1}],
    })
    order_id = order_res.json()["id"]

    # Cancel order
    api_client.post(f"/orders/{order_id}/cancel", json={"reason": "Customer cancellation."})

    # Attempt to create shipment on cancelled order -> 422 BusinessRuleViolationError
    ship_res = api_client.post(f"/orders/{order_id}/shipments", json={"carrier": "Delhivery"})
    assert ship_res.status_code == 422
    assert ship_res.json()["error"] == "BusinessRuleViolationError"


# ==============================================================================
# 7. Complete Canonical Scenario End-to-End API Flow
# ==============================================================================

def test_full_canonical_api_flow(api_client: TestClient):
    """
    Executes the complete canonical operations lifecycle via HTTP API:
    1. Place Order
    2. Initiate & Capture Payment
    3. Dispatch Shipment
    4. Confirm Delivery
    5. Verify Order reaches DELIVERED terminal status
    """
    # 1. Place Order
    order_payload = {
        "customer_id": "11111111-1111-4111-8111-111111111111",
        "items": [{"sku": "SKU-API-01", "quantity": 2}],
        "shipping_amount": "100.00",
    }
    r1 = api_client.post("/orders", json=order_payload)
    assert r1.status_code == 201
    order_id = r1.json()["id"]
    assert r1.json()["status"] == "PENDING"

    # 2. Payment
    r2 = api_client.post(f"/orders/{order_id}/payments", json={"payment_method": "UPI"})
    assert r2.status_code == 201
    payment_id = r2.json()["id"]

    r3 = api_client.post(f"/payments/{payment_id}/capture", json={"gateway_transaction_id": "rzp_flow_101"})
    assert r3.status_code == 200
    assert r3.json()["status"] == "SUCCESSFUL"

    # 3. Dispatch Shipment
    r4 = api_client.post(f"/orders/{order_id}/shipments", json={"carrier": "Delhivery"})
    assert r4.status_code == 201
    shipment_id = r4.json()["id"]

    r5 = api_client.post(f"/shipments/{shipment_id}/status", json={"status": "IN_TRANSIT"})
    assert r5.status_code == 200

    # 4. Deliver Shipment
    r6 = api_client.post(f"/shipments/{shipment_id}/deliver", json={"recipient_notes": "Delivered successfully"})
    assert r6.status_code == 200
    assert r6.json()["status"] == "DELIVERED"

    # 5. Verify Final Order State
    r7 = api_client.get(f"/orders/{order_id}")
    assert r7.status_code == 200
    assert r7.json()["status"] == "DELIVERED"
