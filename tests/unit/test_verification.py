"""Unit tests for Post-Action State Verification Subsystem (Phase 4 - Deliverable D-14)."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
import uuid
import pytest
from sqlalchemy.orm import Session

from database.models import (
    Customer,
    DomainEvent,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Product,
    Shipment,
    ShipmentStatus,
    Ticket,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from backend.verification.schemas import (
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)
from backend.verification.service import StateVerificationService


@pytest.fixture
def service() -> StateVerificationService:
    return StateVerificationService()


@pytest.fixture
def sample_customer(db_session: Session) -> Customer:
    cust = Customer(
        id=uuid.uuid4(),
        email=f"verify.{uuid.uuid4().hex[:6]}@example.com",
        first_name="Ananya",
        last_name="Roy",
        city="Kolkata",
        state="West Bengal",
        pincode="700001",
        phone="+919830012345",
    )
    db_session.add(cust)
    db_session.commit()
    return cust


# ==============================================================================
# Order Cancellation Verification Tests
# ==============================================================================

def test_verify_order_cancellation_success(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """1. Verifies successful order cancellation state matching CANCELLED and expected reason."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-VFY-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.CANCELLED,
        cancellation_reason="customer_requested_cancellation",
        total_amount=Decimal("1500.00"),
    )
    db_session.add(order)
    db_session.commit()

    result = service.verify_order_cancellation(
        db_session,
        order_id=order.id,
        expected_reason="customer_requested_cancellation",
    )

    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED
    assert result.target_state == "CANCELLED"
    assert result.actual_state == "CANCELLED"
    assert len(result.discrepancies) == 0
    assert result.details["cancellation_reason"] == "customer_requested_cancellation"
    assert isinstance(result.timestamp, datetime)


def test_verify_order_cancellation_divergence(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """2. Verifies state divergence when order is still CONFIRMED instead of CANCELLED."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-VFY-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.CONFIRMED,
        total_amount=Decimal("2000.00"),
    )
    db_session.add(order)
    db_session.commit()

    result = service.verify_order_cancellation(db_session, order_id=order.id)

    assert result.verified is False
    assert result.status == VerificationStatus.DIVERGENT
    assert result.target_state == "CANCELLED"
    assert result.actual_state == "CONFIRMED"
    assert len(result.discrepancies) >= 1
    assert "status mismatch" in result.discrepancies[0]


def test_verify_order_cancellation_missing_record(db_session: Session, service: StateVerificationService):
    """3. Verifies missing order produces NOT_FOUND status with clear discrepancies."""
    missing_id = str(uuid.uuid4())
    result = service.verify_order_cancellation(db_session, order_id=missing_id)

    assert result.verified is False
    assert result.status == VerificationStatus.NOT_FOUND
    assert result.actual_state == "NOT_FOUND"
    assert len(result.discrepancies) == 1
    assert "not found" in result.discrepancies[0]


def test_verify_order_cancellation_multiple_discrepancies(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """4. Verifies multiple discrepancies are recorded when status AND reason both mismatch."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-VFY-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.PROCESSING,
        cancellation_reason="wrong_item",
        total_amount=Decimal("3500.00"),
    )
    db_session.add(order)
    db_session.commit()

    result = service.verify_order_cancellation(
        db_session,
        order_id=order.id,
        expected_reason="customer_duplicate_order",
    )

    assert result.verified is False
    assert result.status == VerificationStatus.DIVERGENT
    assert len(result.discrepancies) == 2
    assert any("status mismatch" in d for d in result.discrepancies)
    assert any("reason mismatch" in d for d in result.discrepancies)


# ==============================================================================
# Payment Refund Verification Tests
# ==============================================================================

def test_verify_payment_refund_success(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """5. Verifies successful refund verification when payment status is REFUNDED with matching amount."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-PAY-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.CANCELLED,
        total_amount=Decimal("4500.00"),
    )
    db_session.add(order)
    payment = Payment(
        id=uuid.uuid4(),
        payment_reference=f"PAY-REF-{uuid.uuid4().hex[:6].upper()}",
        order_id=order.id,
        amount=Decimal("4500.00"),
        currency="INR",
        payment_method=PaymentMethod.UPI,
        status=PaymentStatus.REFUNDED,
    )
    db_session.add(payment)
    db_session.commit()

    result = service.verify_payment_refund(
        db_session,
        order_id_or_payment_id=payment.id,
        expected_amount=4500.00,
    )

    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED
    assert result.target_state == "REFUNDED"
    assert result.actual_state == "REFUNDED"
    assert len(result.discrepancies) == 0


def test_verify_payment_refund_divergence(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """6. Verifies divergence when payment is SUCCESSFUL but not yet REFUNDED."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-PAY-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.CONFIRMED,
        total_amount=Decimal("1200.00"),
    )
    db_session.add(order)
    payment = Payment(
        id=uuid.uuid4(),
        payment_reference=f"PAY-SUCCESS-{uuid.uuid4().hex[:6].upper()}",
        order_id=order.id,
        amount=Decimal("1200.00"),
        currency="INR",
        payment_method=PaymentMethod.CARD,
        status=PaymentStatus.SUCCESSFUL,
    )
    db_session.add(payment)
    db_session.commit()

    result = service.verify_payment_refund(db_session, order_id_or_payment_id=payment.id)

    assert result.verified is False
    assert result.status == VerificationStatus.DIVERGENT
    assert result.actual_state == "SUCCESSFUL"
    assert "Payment status mismatch" in result.discrepancies[0]


def test_verify_payment_refund_amount_discrepancy(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """7. Verifies discrepancy when payment is REFUNDED but amount differs from expectation."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-PAY-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.CANCELLED,
        total_amount=Decimal("1000.00"),
    )
    db_session.add(order)
    payment = Payment(
        id=uuid.uuid4(),
        payment_reference=f"PAY-PARTIAL-{uuid.uuid4().hex[:6].upper()}",
        order_id=order.id,
        amount=Decimal("1000.00"),
        currency="INR",
        payment_method=PaymentMethod.UPI,
        status=PaymentStatus.REFUNDED,
    )
    db_session.add(payment)
    db_session.commit()

    result = service.verify_payment_refund(
        db_session,
        order_id_or_payment_id=order.id,  # Lookup by order_id
        expected_amount=2000.00,          # Mismatching expected amount
    )

    assert result.verified is False
    assert result.status == VerificationStatus.DIVERGENT
    assert any("amount mismatch" in d for d in result.discrepancies)


# ==============================================================================
# Ticket Verification Tests
# ==============================================================================

def test_verify_ticket_status_success(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """8. Verifies ticket creation and status verification."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="TCK-20261001-A1B2C3",
        customer_id=sample_customer.id,
        title="Delivery Delay Inquiry",
        description="Customer asking where their shipment is.",
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
        channel=TicketChannel.EMAIL,
    )
    db_session.add(ticket)
    db_session.commit()

    result = service.verify_ticket_status(
        db_session,
        ticket_id_or_number=ticket.id,
        expected_status=TicketStatus.OPEN,
        expected_priority=TicketPriority.HIGH,
    )

    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED
    assert result.target_state == "OPEN"
    assert result.actual_state == "OPEN"
    assert len(result.discrepancies) == 0


def test_verify_ticket_status_priority_mismatch(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """9. Verifies discrepancy when ticket status matches but priority differs."""
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number="TCK-20261001-X9Y8Z7",
        customer_id=sample_customer.id,
        title="Return Request",
        description="Return requested.",
        status=TicketStatus.OPEN,
        priority=TicketPriority.LOW,
        channel=TicketChannel.PORTAL,
    )
    db_session.add(ticket)
    db_session.commit()

    result = service.verify_ticket_status(
        db_session,
        ticket_id_or_number="TCK-20261001-X9Y8Z7",
        expected_status=TicketStatus.OPEN,
        expected_priority=TicketPriority.URGENT,
    )

    assert result.verified is False
    assert result.status == VerificationStatus.DIVERGENT
    assert any("priority mismatch" in d for d in result.discrepancies)


def test_verify_ticket_missing_record(db_session: Session, service: StateVerificationService):
    """10. Verifies missing ticket record produces NOT_FOUND."""
    result = service.verify_ticket_status(db_session, ticket_id_or_number="TCK-DOES-NOT-EXIST")

    assert result.verified is False
    assert result.status == VerificationStatus.NOT_FOUND
    assert result.actual_state == "NOT_FOUND"


# ==============================================================================
# Shipment Verification Tests
# ==============================================================================

def test_verify_shipment_status_success(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """11. Verifies shipment status matches DELIVERED."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-SHP-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.DELIVERED,
        total_amount=Decimal("3000.00"),
    )
    db_session.add(order)
    shipment = Shipment(
        id=uuid.uuid4(),
        shipment_number=f"SHP-{uuid.uuid4().hex[:6].upper()}",
        order_id=order.id,
        carrier="BlueDart",
        tracking_number=f"TRK-{uuid.uuid4().hex[:8].upper()}",
        status=ShipmentStatus.DELIVERED,
        actual_delivery_date=datetime.now(timezone.utc),
    )
    db_session.add(shipment)
    db_session.commit()

    result = service.verify_shipment_status(
        db_session,
        shipment_id_or_tracking=shipment.tracking_number,
        expected_status=ShipmentStatus.DELIVERED,
    )

    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED
    assert result.target_state == "DELIVERED"
    assert result.actual_state == "DELIVERED"


def test_verify_shipment_status_mismatch(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """12. Verifies shipment status divergence when shipment is still IN_TRANSIT."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-SHP-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.SHIPPED,
        total_amount=Decimal("2500.00"),
    )
    db_session.add(order)
    shipment = Shipment(
        id=uuid.uuid4(),
        shipment_number=f"SHP-{uuid.uuid4().hex[:6].upper()}",
        order_id=order.id,
        carrier="Delhivery",
        tracking_number=f"TRK-{uuid.uuid4().hex[:8].upper()}",
        status=ShipmentStatus.IN_TRANSIT,
    )
    db_session.add(shipment)
    db_session.commit()

    result = service.verify_shipment_status(
        db_session,
        shipment_id_or_tracking=shipment.id,
        expected_status=ShipmentStatus.DELIVERED,
    )

    assert result.verified is False
    assert result.status == VerificationStatus.DIVERGENT
    assert result.actual_state == "IN_TRANSIT"
    assert "Shipment status mismatch" in result.discrepancies[0]


# ==============================================================================
# Domain Event Verification Tests
# ==============================================================================

def test_verify_domain_event_dispatch(db_session: Session, service: StateVerificationService):
    """13. Verifies that an expected immutable domain event was persisted."""
    entity_id = uuid.uuid4()
    event = DomainEvent(
        id=uuid.uuid4(),
        event_type="ORDER_CANCELLED",
        entity_type="Order",
        entity_id=entity_id,
        payload={"reason": "customer_request"},
    )
    db_session.add(event)
    db_session.commit()

    result = service.verify_domain_event(
        db_session,
        entity_id=entity_id,
        expected_event_type="ORDER_CANCELLED",
    )

    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED
    assert result.target_state == "ORDER_CANCELLED"
    assert result.actual_state == "ORDER_CANCELLED"


# ==============================================================================
# Non-Mutation & Failure Path Tests
# ==============================================================================

def test_verification_does_not_mutate_database(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """14. Verifies that state verification is purely read-only and leaves no dirty/new objects."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-CLEAN-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.CONFIRMED,
        total_amount=Decimal("1000.00"),
    )
    db_session.add(order)
    db_session.commit()

    # Pre-condition: session is clean
    assert len(db_session.dirty) == 0
    assert len(db_session.new) == 0

    # Perform verification
    result = service.verify_order_cancellation(db_session, order_id=order.id)

    # Post-condition: session must still be completely clean
    assert len(db_session.dirty) == 0
    assert len(db_session.new) == 0
    assert result.verified is False  # Confirmed order is not cancelled


def test_database_error_reported_as_unverified(service: StateVerificationService):
    """15. Verifies database query exceptions are never reported as verified."""
    broken_session = MagicMock(spec=Session)
    broken_session.get.side_effect = RuntimeError("Database connection dropped unexpectedly")

    result = service.verify_order_cancellation(
        broken_session,
        order_id=uuid.uuid4(),
    )

    assert result.verified is False
    assert result.status == VerificationStatus.ERROR
    assert result.error is not None
    assert "Database connection dropped" in result.error
    assert len(result.discrepancies) >= 1


def test_verification_request_generic_dispatch(db_session: Session, service: StateVerificationService, sample_customer: Customer):
    """16. & 17. Verifies unified verify(VerificationRequest) router and timestamp presence."""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-GEN-{uuid.uuid4().hex[:6].upper()}",
        customer_id=sample_customer.id,
        status=OrderStatus.CANCELLED,
        cancellation_reason="item_out_of_stock",
        total_amount=Decimal("500.00"),
    )
    db_session.add(order)
    db_session.commit()

    req = VerificationRequest(
        entity_type="order",
        entity_id=str(order.id),
        target_state="CANCELLED",
        operation="cancel_order",
        expected_attributes={"cancellation_reason": "item_out_of_stock"},
    )

    result = service.verify(db_session, req)

    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED
    assert result.entity_type == "order"
    assert result.operation == "cancel_order"
    assert result.timestamp is not None
    assert isinstance(result.timestamp, datetime)
