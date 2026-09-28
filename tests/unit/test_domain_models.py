"""
Unit and domain model tests for OpsWingman Phase 1.1.
Tests SQLAlchemy 2.0 entities, relationships, constraints, CRUD operations,
and all 6 deterministic seed scenarios.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from database.base import Base
from database.models import (
    Customer,
    Product,
    Order,
    OrderItem,
    Payment,
    Shipment,
    Ticket,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    ShipmentStatus,
    TicketStatus,
    TicketPriority,
    TicketChannel,
)
from database.seed import (
    create_seed_data,
    CUSTOMER_ROHAN_ID,
    CUSTOMER_AMIT_ID,
    ORDER_DELAYED_ID,
    ORDER_NORMAL_ID,
    ORDER_CANCELLED_ID,
    ORDER_FAILED_PAYMENT_ID,
    ORDER_DELIVERED_ID,
)


@pytest.fixture(scope="function")
def test_db():
    """In-memory SQLite database session fixture for isolated fast testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# 1. Model Creation & CRUD Tests
# ==============================================================================

def test_create_customer(test_db: Session):
    """Verify Customer creation with UUID, timestamps, and fields."""
    customer = Customer(
        email="test.user@example.com",
        first_name="Test",
        last_name="User",
        phone="+919999988888",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
    )
    test_db.add(customer)
    test_db.commit()

    retrieved = test_db.scalar(select(Customer).where(Customer.email == "test.user@example.com"))
    assert retrieved is not None
    assert isinstance(retrieved.id, uuid.UUID)
    assert retrieved.first_name == "Test"
    assert retrieved.last_name == "User"
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


def test_create_product_with_decimal_price(test_db: Session):
    """Verify Product creation and strict Decimal money handling."""
    product = Product(
        sku="SKU-TEST-99",
        name="Test Item Pro",
        unit_price=Decimal("1499.50"),
        currency="INR",
        inventory_count=50,
    )
    test_db.add(product)
    test_db.commit()

    retrieved = test_db.scalar(select(Product).where(Product.sku == "SKU-TEST-99"))
    assert retrieved is not None
    assert retrieved.unit_price == Decimal("1499.50")
    assert isinstance(retrieved.unit_price, Decimal)
    assert retrieved.inventory_count == 50


def test_order_and_items_relationship(test_db: Session):
    """Verify Order creation with line items and cascade persistence."""
    customer = Customer(
        email="buyer@example.com",
        first_name="Rajesh",
        last_name="Kumar",
    )
    product = Product(
        sku="SKU-PROD-10",
        name="Wireless Mouse",
        unit_price=Decimal("799.00"),
        currency="INR",
        inventory_count=20,
    )
    test_db.add_all([customer, product])
    test_db.commit()

    order = Order(
        order_number="ORD-TEST-0001",
        customer_id=customer.id,
        status=OrderStatus.PENDING,
        subtotal_amount=Decimal("1598.00"),
        total_amount=Decimal("1598.00"),
    )
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        sku=product.sku,
        product_name=product.name,
        quantity=2,
        unit_price=Decimal("799.00"),
        total_price=Decimal("1598.00"),
    )
    order.items.append(item)
    test_db.add(order)
    test_db.commit()

    retrieved_order = test_db.scalar(select(Order).where(Order.order_number == "ORD-TEST-0001"))
    assert retrieved_order is not None
    assert len(retrieved_order.items) == 1
    assert retrieved_order.items[0].sku == "SKU-PROD-10"
    assert retrieved_order.items[0].quantity == 2
    assert retrieved_order.items[0].total_price == Decimal("1598.00")
    assert retrieved_order.customer.email == "buyer@example.com"


# ==============================================================================
# 2. Database Constraints & Uniqueness Tests
# ==============================================================================

def test_unique_customer_email_constraint(test_db: Session):
    """Verify unique constraint on customer email."""
    c1 = Customer(email="duplicate@example.com", first_name="A", last_name="B")
    test_db.add(c1)
    test_db.commit()

    c2 = Customer(email="duplicate@example.com", first_name="C", last_name="D")
    test_db.add(c2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_unique_product_sku_constraint(test_db: Session):
    """Verify unique constraint on product SKU."""
    p1 = Product(sku="SKU-DUP-1", name="Product 1", unit_price=Decimal("100.00"))
    test_db.add(p1)
    test_db.commit()

    p2 = Product(sku="SKU-DUP-1", name="Product 2", unit_price=Decimal("200.00"))
    test_db.add(p2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_unique_order_number_constraint(test_db: Session):
    """Verify unique constraint on order number."""
    customer = Customer(email="order.unique@example.com", first_name="U", last_name="O")
    test_db.add(customer)
    test_db.commit()

    o1 = Order(order_number="ORD-DUP-01", customer_id=customer.id, total_amount=Decimal("500.00"))
    test_db.add(o1)
    test_db.commit()

    o2 = Order(order_number="ORD-DUP-01", customer_id=customer.id, total_amount=Decimal("600.00"))
    test_db.add(o2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


# ==============================================================================
# 3. Deterministic Seed Data & Scenarios Tests
# ==============================================================================

def test_seed_data_generation_and_counts(test_db: Session):
    """Verify that seed generation populates all models with expected counts."""
    c_count, p_count, o_count, oi_count, pay_count, s_count = create_seed_data(test_db)
    assert c_count == 5
    assert p_count == 5
    assert o_count == 6
    assert test_db.query(Customer).count() == 5
    assert test_db.query(Product).count() == 5
    assert test_db.query(Order).count() == 6
    assert test_db.query(Ticket).count() == 4


def test_scenario_1_normal_order(test_db: Session):
    """Verify Scenario 1: Normal Order (shipped, paid via UPI, on schedule)."""
    create_seed_data(test_db)
    order = test_db.get(Order, ORDER_NORMAL_ID)
    assert order is not None
    assert order.status == OrderStatus.SHIPPED
    assert len(order.payments) == 1
    assert order.payments[0].status == PaymentStatus.SUCCESSFUL
    assert order.payments[0].payment_method == PaymentMethod.UPI
    assert len(order.shipments) == 1
    assert order.shipments[0].status == ShipmentStatus.IN_TRANSIT
    assert order.shipments[0].carrier == "Delhivery"


def test_scenario_2_delayed_order_and_support_ticket(test_db: Session):
    """
    Verify Scenario 2: Delayed Order (shipment delayed past ETA, open ticket attached).
    Crucial for OpsWingman delay detection and customer communication workflows.
    """
    create_seed_data(test_db)
    order = test_db.get(Order, ORDER_DELAYED_ID)
    assert order is not None
    assert order.status == OrderStatus.SHIPPED
    assert len(order.shipments) == 1

    shipment = order.shipments[0]
    assert shipment.status == ShipmentStatus.DELAYED
    assert shipment.delay_reason is not None
    assert "transit network disruption" in shipment.delay_reason
    assert shipment.current_location is not None
    assert "Hubli" in shipment.current_location


    # Verify linked support ticket
    assert len(order.tickets) == 1
    ticket = order.tickets[0]
    assert ticket.status == TicketStatus.OPEN
    assert ticket.priority == TicketPriority.HIGH
    assert ticket.category == "ORDER_DELAY"
    assert ticket.customer_id == CUSTOMER_AMIT_ID


def test_scenario_3_cancelled_order(test_db: Session):
    """Verify Scenario 3: Cancelled Order with recorded reason and in-progress ticket."""
    create_seed_data(test_db)
    order = test_db.get(Order, ORDER_CANCELLED_ID)
    assert order is not None
    assert order.status == OrderStatus.CANCELLED
    assert order.cancellation_reason is not None
    assert "cancellation before dispatch" in order.cancellation_reason
    assert len(order.tickets) == 1
    assert order.tickets[0].category == "CANCELLATION_REQUEST"


def test_scenario_4_failed_payment(test_db: Session):
    """Verify Scenario 4: Failed Payment with gateway timeout error and urgent ticket."""
    create_seed_data(test_db)
    order = test_db.get(Order, ORDER_FAILED_PAYMENT_ID)
    assert order is not None
    assert order.status == OrderStatus.PENDING
    assert len(order.payments) == 1
    payment = order.payments[0]
    assert payment.status == PaymentStatus.FAILED
    assert payment.error_code == "BAD_REQUEST_PAYMENT_TIMED_OUT"
    assert payment.paid_at is None
    assert len(order.tickets) == 1
    assert order.tickets[0].priority == TicketPriority.URGENT


def test_scenario_5_delivered_order(test_db: Session):
    """Verify Scenario 5: Delivered Order completed lifecycle with confirmed date."""
    create_seed_data(test_db)
    order = test_db.get(Order, ORDER_DELIVERED_ID)
    assert order is not None
    assert order.status == OrderStatus.DELIVERED
    assert len(order.shipments) == 1
    shipment = order.shipments[0]
    assert shipment.status == ShipmentStatus.DELIVERED
    assert shipment.actual_delivery_date is not None


def test_scenario_6_customer_with_multiple_orders(test_db: Session):
    """Verify Scenario 6: Customer with multiple orders in different lifecycle stages."""
    create_seed_data(test_db)
    customer = test_db.get(Customer, CUSTOMER_ROHAN_ID)
    assert customer is not None
    assert len(customer.orders) == 2
    order_statuses = {o.status for o in customer.orders}
    assert OrderStatus.DELIVERED in order_statuses
    assert OrderStatus.PROCESSING in order_statuses
