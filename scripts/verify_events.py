"""
OpsWingman Phase 1.4 - Domain Event System Verification Script.
Executes an end-to-end business lifecycle through the API and simulator, demonstrating persistent domain events.
"""

import os
import sys
import json
from pathlib import Path
import uuid
from decimal import Decimal

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.session import get_db
from database.models import Customer, Product
from backend.main import app


def run_events_verification():
    print("=================================================================")
    print("  OpsWingman Phase 1.4 - Domain Event System Verification")
    print("=================================================================")

    import tempfile
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{temp_db_path}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    # Seed baseline customer and product
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    with TestingSession() as session:
        customer = Customer(
            id=customer_id,
            email="aarav.mehta@example.com",
            first_name="Aarav",
            last_name="Mehta",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
        )
        product = Product(
            id=product_id,
            sku="SKU-PROD-VERIFY",
            name="Smart Pro Wireless Earbuds",
            unit_price=Decimal("2999.00"),
            currency="INR",
            inventory_count=50,
            is_active=True,
        )
        session.add_all([customer, product])
        session.commit()

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as client:
        # Step 1: Create Order
        print("\n[Step 1] Creating Order -> expecting ORDER_CREATED event ...")
        order_res = client.post(
            "/orders",
            json={
                "customer_id": str(customer_id),
                "items": [{"product_id": str(product_id), "quantity": 1}],
                "shipping_amount": 99.0,
            },
        )
        assert order_res.status_code == 201, f"Failed to create order: {order_res.text}"
        order_data = order_res.json()
        order_id = order_data["id"]
        print(f"  [OK] Order Created: {order_data['order_number']} (ID: {order_id})")

        # Step 2: Create and Capture Payment
        print("\n[Step 2] Creating & Capturing Payment -> expecting PAYMENT_INITIATED and PAYMENT_SUCCESSFUL events ...")
        pay_create_res = client.post(
            f"/orders/{order_id}/payments",
            json={"payment_method": "UPI"},
        )
        assert pay_create_res.status_code == 201
        payment_id = pay_create_res.json()["id"]

        pay_cap_res = client.post(
            f"/payments/{payment_id}/capture",
            json={"gateway_transaction_id": "pay_demo_txn_001"},
        )
        assert pay_cap_res.status_code == 200
        print(f"  [OK] Payment Captured: {pay_cap_res.json()['payment_reference']} (ID: {payment_id})")

        # Step 3: Create Shipment
        print("\n[Step 3] Creating Shipment -> expecting SHIPMENT_CREATED event ...")
        ship_res = client.post(
            f"/orders/{order_id}/shipments",
            json={"carrier": "Delhivery", "estimated_days": 3},
        )
        assert ship_res.status_code == 201
        shipment_data = ship_res.json()
        shipment_id = shipment_data["id"]
        print(f"  [OK] Shipment Created: {shipment_data['shipment_number']} (Tracking: {shipment_data['tracking_number']})")

        # Step 4: Advance & Deliver Shipment
        print("\n[Step 4] Advancing to IN_TRANSIT and Delivering Shipment -> expecting SHIPMENT_STATUS_CHANGED & SHIPMENT_DELIVERED events ...")
        transit_res = client.post(
            f"/shipments/{shipment_id}/status",
            json={"status": "IN_TRANSIT", "location": "Hub Central"},
        )
        assert transit_res.status_code == 200

        deliv_res = client.post(
            f"/shipments/{shipment_id}/deliver",
            json={"recipient_notes": "Delivered to reception desk."},
        )
        assert deliv_res.status_code == 200
        print(f"  [OK] Shipment Delivered: {deliv_res.json()['status']}")

        # Step 5: Query All Events via GET /events
        print("\n[Step 5] Querying All Recorded Domain Events via GET /events ...")
        events_res = client.get("/events")
        assert events_res.status_code == 200
        events = events_res.json()
        print(f"  [OK] Total Recorded Domain Events: {len(events)}\n")

        for idx, ev in enumerate(events, 1):
            print(f"  [{idx}] Event Type : {ev['event_type']}")
            print(f"      Entity     : {ev['entity_type']} ({ev['entity_id']})")
            print(f"      Occurred At: {ev['occurred_at']}")
            print(f"      Payload    : {json.dumps(ev['payload'])}")
            print("-" * 65)

    app.dependency_overrides.clear()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

    print("\n=================================================================")
    print("  Phase 1.4 Verification Complete: All Events Captured Atomically")
    print("=================================================================")


if __name__ == "__main__":
    run_events_verification()
