import os
import sys
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


def run_api_verification():
    print("=================================================================")
    print("  OpsWingman Phase 1.3 - Operational REST API Verification")
    print("=================================================================")

    import tempfile
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{temp_db_path}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    # Seed baseline customer and product
    with TestingSession() as session:
        customer = Customer(
            id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
            email="aarav.mehta@example.com",
            first_name="Aarav",
            last_name="Mehta",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
        )
        product = Product(
            id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
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
        # 1. Verify GET /health
        print("\n[1/3] Testing GET /health ...")
        res_health = client.get("/health")
        print(f"      Status: {res_health.status_code}, Response: {res_health.json()}")
        assert res_health.status_code == 200

        # 2. Verify GET /docs
        print("\n[2/3] Testing GET /docs (OpenAPI Documentation) ...")
        res_docs = client.get("/docs")
        print(f"      Status: {res_docs.status_code} (HTML Documentation Rendered)")
        assert res_docs.status_code == 200

        # 3. Complete End-to-End API Flow
        print("\n[3/3] Executing Complete End-to-End API Flow ...")
        
        # Step A: POST /orders
        order_payload = {
            "customer_id": "11111111-1111-4111-8111-111111111111",
            "items": [{"sku": "SKU-PROD-VERIFY", "quantity": 1}],
            "shipping_amount": "50.00",
        }
        r_order = client.post("/orders", json=order_payload)
        print(f"  [A] POST /orders -> Status {r_order.status_code}")
        order_data = r_order.json()
        order_id = order_data["id"]
        print(f"      Order Number: {order_data['order_number']}, Status: {order_data['status']}, Total: INR {order_data['total_amount']}")

        # Step B: POST /orders/{order_id}/payments
        r_pay_create = client.post(f"/orders/{order_id}/payments", json={"payment_method": "UPI"})
        print(f"  [B] POST /orders/{order_id}/payments -> Status {r_pay_create.status_code}")
        payment_id = r_pay_create.json()["id"]

        # Step C: POST /payments/{payment_id}/capture
        r_pay_cap = client.post(f"/payments/{payment_id}/capture", json={"gateway_transaction_id": "rzp_test_demo_001"})
        print(f"  [C] POST /payments/{payment_id}/capture -> Status {r_pay_cap.status_code}")
        print(f"      Payment Status: {r_pay_cap.json()['status']}, TxID: {r_pay_cap.json()['gateway_transaction_id']}")

        # Step D: POST /orders/{order_id}/shipments
        r_ship_create = client.post(f"/orders/{order_id}/shipments", json={"carrier": "Delhivery", "estimated_days": 3})
        print(f"  [D] POST /orders/{order_id}/shipments -> Status {r_ship_create.status_code}")
        shipment_id = r_ship_create.json()["id"]
        print(f"      Shipment Carrier: {r_ship_create.json()['carrier']}, Tracking: {r_ship_create.json()['tracking_number']}")

        # Step E: POST /shipments/{shipment_id}/status (Advance to IN_TRANSIT)
        r_ship_transit = client.post(f"/shipments/{shipment_id}/status", json={"status": "IN_TRANSIT", "location": "Mumbai Sorting Hub"})
        print(f"  [E] POST /shipments/{shipment_id}/status -> Status {r_ship_transit.status_code}")

        # Step F: POST /shipments/{shipment_id}/deliver
        r_ship_deliv = client.post(f"/shipments/{shipment_id}/deliver", json={"recipient_notes": "Delivered and signed by Aarav Mehta"})
        print(f"  [F] POST /shipments/{shipment_id}/deliver -> Status {r_ship_deliv.status_code}")
        print(f"      Shipment Status: {r_ship_deliv.json()['status']}")

        # Step G: GET /orders/{order_id} (Verify terminal state)
        r_order_final = client.get(f"/orders/{order_id}")
        print(f"  [G] GET /orders/{order_id} -> Final Order Status: {r_order_final.json()['status']}")
        assert r_order_final.json()["status"] == "DELIVERED"

    app.dependency_overrides.clear()
    engine.dispose()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

    print("\n=================================================================")
    print("  All API Verifications Passed Successfully.")
    print("=================================================================")


if __name__ == "__main__":
    run_api_verification()
