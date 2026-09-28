"""
Unit tests for the OpsWingman Business Simulator (Phase 1.2).
Tests deterministic operations, state validation, and transition enforcement.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database.base import Base
from database.models import (
    Customer,
    Product,
    Order,
    Payment,
    Shipment,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    ShipmentStatus,
)
from simulator import (
    BusinessSimulator,
    create_order,
    get_order,
    update_order_status,
    cancel_order,
    create_payment,
    get_payment,
    capture_payment,
    fail_payment,
    create_shipment,
    get_shipment,
    update_shipment_status,
    delay_shipment,
    deliver_shipment,
    InvalidStateTransitionError,
    EntityNotFoundError,
    BusinessRuleViolationError,
)


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
        email="sim.user@example.com",
        first_name="Sim",
        last_name="User",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
    )
    p1 = Product(
        id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        sku="SKU-SIM-01",
        name="Simulator Widget",
        unit_price=Decimal("1000.00"),
        currency="INR",
        inventory_count=100,
        is_active=True,
    )
    p2 = Product(
        id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        sku="SKU-SIM-02",
        name="Simulator Gadget",
        unit_price=Decimal("2500.00"),
        currency="INR",
        inventory_count=50,
        is_active=True,
    )
    session.add_all([cust, p1, p2])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# 1. Normal Order Lifecycle Tests
# ==============================================================================

def test_order_creation_and_calculation(test_db: Session):
    """Verify order creation and deterministic monetary calculations."""
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    items = [
        {"sku": "SKU-SIM-01", "quantity": 2},            # 2000.00
        {"sku": "SKU-SIM-02", "quantity": 1},            # 2500.00
    ]
    order = create_order(
        session=test_db,
        customer_id=cust_id,
        items=items,
        shipping_amount=Decimal("100.00"),
        discount_amount=Decimal("50.00"),
    )

    assert order is not None
    assert order.status == OrderStatus.PENDING
    assert order.subtotal_amount == Decimal("4500.00")
    assert order.tax_amount == Decimal("810.00")  # 18% of 4500
    assert order.shipping_amount == Decimal("100.00")
    assert order.discount_amount == Decimal("50.00")
    assert order.total_amount == Decimal("5360.00")  # 4500 + 810 + 100 - 50
    assert len(order.items) == 2


def test_full_normal_order_lifecycle(test_db: Session):
    """Verify standard happy path: Create -> Pay -> Ship -> Deliver."""
    sim = BusinessSimulator(session=test_db)
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    items = [{"sku": "SKU-SIM-01", "quantity": 1}]

    order, payment, shipment = sim.run_normal_order_flow(customer_id=cust_id, items=items)

    assert order.status == OrderStatus.DELIVERED
    assert payment.status == PaymentStatus.SUCCESSFUL
    assert payment.paid_at is not None
    assert shipment.status == ShipmentStatus.DELIVERED
    assert shipment.actual_delivery_date is not None


# ==============================================================================
# 2. Payment Operations & Failures
# ==============================================================================

def test_successful_payment_capture(test_db: Session):
    """Verify creating and capturing a payment advances order to CONFIRMED."""
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    order = create_order(test_db, customer_id=cust_id, items=[{"sku": "SKU-SIM-01", "quantity": 1}])
    assert order.status == OrderStatus.PENDING

    payment = create_payment(test_db, order_id=order.id, payment_method=PaymentMethod.UPI)
    assert payment.status == PaymentStatus.INITIATED
    assert payment.amount == order.total_amount

    captured = capture_payment(test_db, payment_id=payment.id, gateway_transaction_id="rzp_tx_9999")
    assert captured.status == PaymentStatus.SUCCESSFUL
    assert captured.gateway_transaction_id == "rzp_tx_9999"
    assert captured.paid_at is not None

    # Check order auto-advanced to CONFIRMED
    refreshed_order = get_order(test_db, order_id=order.id)
    assert refreshed_order.status == OrderStatus.CONFIRMED


def test_failed_payment_operation(test_db: Session):
    """Verify failing a payment records error code and leaves order PENDING."""
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    order = create_order(test_db, customer_id=cust_id, items=[{"sku": "SKU-SIM-01", "quantity": 1}])

    payment = create_payment(test_db, order_id=order.id, payment_method=PaymentMethod.CARD)
    failed = fail_payment(
        test_db,
        payment_id=payment.id,
        error_code="INSUFFICIENT_FUNDS",
        error_message="Card issuer declined transaction.",
    )

    assert failed.status == PaymentStatus.FAILED
    assert failed.error_code == "INSUFFICIENT_FUNDS"
    assert failed.error_message == "Card issuer declined transaction."
    assert failed.paid_at is None

    # Failed payment cannot be captured
    with pytest.raises(InvalidStateTransitionError):
        capture_payment(test_db, payment_id=payment.id)


# ==============================================================================
# 3. Shipment Delay & Delivery Operations
# ==============================================================================

def test_shipment_delay_scenario(test_db: Session):
    """Verify delaying a shipment records reason, revised ETA, and location."""
    sim = BusinessSimulator(session=test_db)
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    items = [{"sku": "SKU-SIM-02", "quantity": 1}]

    order, payment, shipment = sim.run_delayed_order_flow(
        customer_id=cust_id,
        items=items,
        carrier="BlueDart",
        delay_reason="Regional transit network flood alert",
    )

    assert shipment.status == ShipmentStatus.DELAYED
    assert shipment.delay_reason == "Regional transit network flood alert"
    assert shipment.current_location is not None
    assert "Transit Hub - Delayed" in shipment.current_location
    assert order.status == OrderStatus.SHIPPED



def test_shipment_delivery_advances_order(test_db: Session):
    """Verify delivering shipment advances order to DELIVERED."""
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    order = create_order(test_db, customer_id=cust_id, items=[{"sku": "SKU-SIM-01", "quantity": 1}])
    payment = create_payment(test_db, order_id=order.id)
    capture_payment(test_db, payment_id=payment.id)

    shipment = create_shipment(test_db, order_id=order.id, carrier="Delhivery")
    assert shipment.status == ShipmentStatus.MANIFESTED

    # Advance through transit
    update_shipment_status(test_db, shipment_id=shipment.id, new_status=ShipmentStatus.IN_TRANSIT)
    update_shipment_status(test_db, shipment_id=shipment.id, new_status=ShipmentStatus.OUT_FOR_DELIVERY)

    delivered = deliver_shipment(test_db, shipment_id=shipment.id, recipient_notes="Signed by Sim User")
    assert delivered.status == ShipmentStatus.DELIVERED
    assert delivered.actual_delivery_date is not None

    refreshed_order = get_order(test_db, order_id=order.id)
    assert refreshed_order.status == OrderStatus.DELIVERED


# ==============================================================================
# 4. Cancellation & Invalid State Transitions
# ==============================================================================

def test_cancel_active_order(test_db: Session):
    """Verify order cancellation records reason and prevents shipment."""
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    order = create_order(test_db, customer_id=cust_id, items=[{"sku": "SKU-SIM-01", "quantity": 1}])

    cancelled = cancel_order(test_db, order_id=order.id, reason="Customer found item cheaper elsewhere.")
    assert cancelled.status == OrderStatus.CANCELLED
    assert cancelled.cancellation_reason == "Customer found item cheaper elsewhere."

    # Cannot create shipment for cancelled order
    with pytest.raises(BusinessRuleViolationError):
        create_shipment(test_db, order_id=order.id)

    # Cannot create payment for cancelled order
    with pytest.raises(BusinessRuleViolationError):
        create_payment(test_db, order_id=order.id)


def test_invalid_order_state_transitions(test_db: Session):
    """Verify illegal order transitions are rejected."""
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    order = create_order(test_db, customer_id=cust_id, items=[{"sku": "SKU-SIM-01", "quantity": 1}])

    # Cannot jump directly from PENDING to DELIVERED
    with pytest.raises(InvalidStateTransitionError):
        update_order_status(test_db, order_id=order.id, new_status=OrderStatus.DELIVERED)

    # Move to SHIPPED
    update_order_status(test_db, order_id=order.id, new_status=OrderStatus.CONFIRMED)
    update_order_status(test_db, order_id=order.id, new_status=OrderStatus.PROCESSING)
    update_order_status(test_db, order_id=order.id, new_status=OrderStatus.SHIPPED)
    update_order_status(test_db, order_id=order.id, new_status=OrderStatus.DELIVERED)

    # DELIVERED is terminal: cannot go back to PENDING or SHIPPED
    with pytest.raises(InvalidStateTransitionError):
        update_order_status(test_db, order_id=order.id, new_status=OrderStatus.PENDING)

    with pytest.raises(InvalidStateTransitionError):
        update_order_status(test_db, order_id=order.id, new_status=OrderStatus.SHIPPED)


def test_invalid_shipment_state_transitions(test_db: Session):
    """Verify illegal shipment transitions are rejected."""
    cust_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    order = create_order(test_db, customer_id=cust_id, items=[{"sku": "SKU-SIM-01", "quantity": 1}])
    shipment = create_shipment(test_db, order_id=order.id)

    # Cannot jump MANIFESTED directly to DELIVERED without delivery call or transition
    with pytest.raises(InvalidStateTransitionError):
        update_shipment_status(test_db, shipment_id=shipment.id, new_status=ShipmentStatus.DELIVERED)

    # Advance to IN_TRANSIT, then deliver shipment
    update_shipment_status(test_db, shipment_id=shipment.id, new_status=ShipmentStatus.IN_TRANSIT)
    deliver_shipment(test_db, shipment_id=shipment.id)

    # DELIVERED is terminal: cannot return to IN_TRANSIT or MANIFESTED
    with pytest.raises(InvalidStateTransitionError):
        update_shipment_status(test_db, shipment_id=shipment.id, new_status=ShipmentStatus.IN_TRANSIT)


def test_entity_not_found_handling(test_db: Session):
    """Verify proper exceptions when non-existent IDs are queried."""
    fake_id = uuid.uuid4()
    with pytest.raises(EntityNotFoundError):
        get_order(test_db, order_id=fake_id)

    with pytest.raises(EntityNotFoundError):
        get_payment(test_db, payment_id=fake_id)

    with pytest.raises(EntityNotFoundError):
        get_shipment(test_db, shipment_id=fake_id)
