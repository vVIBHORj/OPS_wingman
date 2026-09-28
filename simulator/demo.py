"""
Example Demonstration of OpsWingman Business Simulator Scenarios.
Demonstrates deterministic state transitions for orders, payments, and shipments.
"""

import uuid
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import Customer, Product, OrderStatus, PaymentStatus, ShipmentStatus
from simulator.service import BusinessSimulator


def run_demo():
    print("=================================================================")
    print("  OpsWingman Business Simulator - Scenario Execution Demo")
    print("=================================================================")

    # Initialize in-memory session for clean demo execution
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    sim = BusinessSimulator(session=session)

    # 1. Setup sample buyer & catalog product
    customer = Customer(
        id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        email="rahul.verma@example.com",
        first_name="Rahul",
        last_name="Verma",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
    )
    product = Product(
        id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        sku="SKU-PROD-DEMO",
        name="Noise-Cancelling Wireless Headphones",
        unit_price=Decimal("4999.00"),
        currency="INR",
        inventory_count=100,
        is_active=True,
    )
    session.add_all([customer, product])
    session.commit()

    print(f"\n[1/4] Customer: {customer.first_name} {customer.last_name} ({customer.email})")
    print(f"      Product:  {product.name} (SKU: {product.sku}, Price: INR {product.unit_price})")

    # 2. Scenario: Normal Order Lifecycle
    print("\n--- Executing Scenario 1: Normal Order Flow ---")
    order, payment, shipment = sim.run_normal_order_flow(
        customer_id=customer.id,
        items=[{"sku": product.sku, "quantity": 1}],
        carrier="Delhivery",
    )
    print(f"  [+] Order Placed:    Number={order.order_number}, Total=INR {order.total_amount}")
    print(f"  [+] Payment Captured: Ref={payment.payment_reference}, Status={payment.status.value}, PaidAt={payment.paid_at}")
    print(f"  [+] Shipment Dispatched: Carrier={shipment.carrier}, Tracking={shipment.tracking_number}")
    print(f"  [+] Shipment Delivered: Status={shipment.status.value}, DeliveredAt={shipment.actual_delivery_date}")
    print(f"  [+] Final Order Status: {order.status.value}")

    # 3. Scenario: Delayed Order Flow
    print("\n--- Executing Scenario 2: Delayed Order Flow ---")
    d_order, d_payment, d_shipment = sim.run_delayed_order_flow(
        customer_id=customer.id,
        items=[{"sku": product.sku, "quantity": 2}],
        carrier="BlueDart",
        delay_reason="Regional transit network disruption at Hubli Hub",
    )
    print(f"  [+] Order Placed:    Number={d_order.order_number}, Total=INR {d_order.total_amount}")
    print(f"  [+] Payment Status:  {d_payment.status.value}")
    print(f"  [+] Shipment State:  Status={d_shipment.status.value}, Carrier={d_shipment.carrier}")
    print(f"  [+] Delay Reason:    '{d_shipment.delay_reason}'")
    print(f"  [+] Current Loc:     '{d_shipment.current_location}'")
    print(f"  [+] Revised ETA:     {d_shipment.estimated_delivery_date}")

    print("\n=================================================================")
    print("  Simulator Scenarios Executed Successfully.")
    print("=================================================================")


if __name__ == "__main__":
    run_demo()
