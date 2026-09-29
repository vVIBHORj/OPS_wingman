"""
Payment simulation operations and deterministic state transitions.
Records domain events synchronously within the active transaction.
"""

import uuid
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Order,
    Payment,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    EventType,
)
from simulator.exceptions import (
    EntityNotFoundError,
    InvalidStateTransitionError,
    BusinessRuleViolationError,
)
from simulator.events import record_event

PAYMENT_TRANSITIONS = {
    PaymentStatus.INITIATED: {
        PaymentStatus.AUTHORIZED,
        PaymentStatus.SUCCESSFUL,
        PaymentStatus.FAILED,
    },
    PaymentStatus.AUTHORIZED: {
        PaymentStatus.SUCCESSFUL,
        PaymentStatus.FAILED,
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.SUCCESSFUL: {
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.FAILED: set(),    # Terminal state for this attempt
    PaymentStatus.REFUNDED: set(),  # Terminal state
}


def create_payment(
    session: Session,
    order_id: uuid.UUID,
    amount: Optional[Decimal] = None,
    payment_method: PaymentMethod = PaymentMethod.UPI,
    payment_reference: Optional[str] = None,
    payment_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[str] = None,
) -> Payment:
    """
    Creates an INITIATED payment record linked to an existing order.
    Records PAYMENT_INITIATED domain event in the same transaction.
    """
    order = session.get(Order, order_id)
    if not order:
        raise EntityNotFoundError(f"Order {order_id} not found.")

    if order.status == OrderStatus.CANCELLED:
        raise BusinessRuleViolationError(f"Cannot create payment for cancelled order {order.order_number}.")

    pay_amount = amount if amount is not None else order.total_amount
    if pay_amount <= Decimal("0.00"):
        raise BusinessRuleViolationError("Payment amount must be greater than zero.")

    ref = payment_reference or f"PAY-{payment_method.value}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    payment = Payment(
        id=payment_id or uuid.uuid4(),
        payment_reference=ref,
        order_id=order.id,
        amount=pay_amount,
        currency=order.currency,
        payment_method=payment_method,
        status=PaymentStatus.INITIATED,
    )
    session.add(payment)

    # Record Domain Event
    record_event(
        session=session,
        event_type=EventType.PAYMENT_INITIATED,
        entity_type="Payment",
        entity_id=payment.id,
        payload={
            "payment_reference": payment.payment_reference,
            "order_id": str(payment.order_id),
            "amount": str(payment.amount),
            "currency": payment.currency,
            "payment_method": payment.payment_method.value,
            "status": payment.status.value,
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(payment)
    return payment


def get_payment(
    session: Session,
    payment_id: Optional[uuid.UUID] = None,
    payment_reference: Optional[str] = None,
) -> Payment:
    """Retrieves a payment by UUID or payment_reference."""
    if payment_id:
        payment = session.get(Payment, payment_id)
    elif payment_reference:
        payment = session.scalar(select(Payment).where(Payment.payment_reference == payment_reference))
    else:
        raise ValueError("Must provide either payment_id or payment_reference.")

    if not payment:
        identifier = str(payment_id) if payment_id else str(payment_reference)
        raise EntityNotFoundError(f"Payment {identifier} not found.")

    return payment


def capture_payment(
    session: Session,
    payment_id: uuid.UUID,
    gateway_transaction_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Payment:
    """
    Captures an initiated or authorized payment, transitioning it to SUCCESSFUL.
    Also advances order status to CONFIRMED if currently PENDING.
    Records PAYMENT_SUCCESSFUL domain event in the same transaction.
    """
    payment = get_payment(session, payment_id=payment_id)

    allowed_targets = PAYMENT_TRANSITIONS.get(payment.status, set())
    if PaymentStatus.SUCCESSFUL not in allowed_targets:
        raise InvalidStateTransitionError(
            entity_type="Payment",
            entity_id=str(payment.id),
            current_status=payment.status.value,
            target_status=PaymentStatus.SUCCESSFUL.value,
        )

    prev_status = payment.status
    payment.status = PaymentStatus.SUCCESSFUL
    payment.gateway_transaction_id = gateway_transaction_id or f"gtw_{uuid.uuid4().hex[:12]}"
    payment.paid_at = datetime.now(timezone.utc)

    # Sync order status if PENDING
    order = session.get(Order, payment.order_id)
    if order and order.status == OrderStatus.PENDING:
        prev_order_status = order.status
        order.status = OrderStatus.CONFIRMED
        record_event(
            session=session,
            event_type=EventType.ORDER_STATUS_CHANGED,
            entity_type="Order",
            entity_id=order.id,
            payload={
                "order_number": order.order_number,
                "previous_status": prev_order_status.value,
                "new_status": OrderStatus.CONFIRMED.value,
                "reason": f"Payment {payment.payment_reference} captured successfully",
            },
            correlation_id=correlation_id,
        )

    # Record Payment Domain Event
    paid_at_val: Optional[datetime] = payment.paid_at
    record_event(
        session=session,
        event_type=EventType.PAYMENT_SUCCESSFUL,
        entity_type="Payment",
        entity_id=payment.id,
        payload={
            "payment_reference": payment.payment_reference,
            "order_id": str(payment.order_id),
            "amount": str(payment.amount),
            "currency": payment.currency,
            "previous_status": prev_status.value,
            "new_status": PaymentStatus.SUCCESSFUL.value,
            "gateway_transaction_id": payment.gateway_transaction_id,
            "paid_at": paid_at_val.isoformat() if paid_at_val is not None else None,
        },
        correlation_id=correlation_id,
    )



    session.commit()
    session.refresh(payment)
    return payment


def fail_payment(
    session: Session,
    payment_id: uuid.UUID,
    error_code: str,
    error_message: str,
    correlation_id: Optional[str] = None,
) -> Payment:
    """
    Marks an initiated payment as FAILED with error provenance.
    Records PAYMENT_FAILED domain event in the same transaction.
    """
    payment = get_payment(session, payment_id=payment_id)

    allowed_targets = PAYMENT_TRANSITIONS.get(payment.status, set())
    if PaymentStatus.FAILED not in allowed_targets:
        raise InvalidStateTransitionError(
            entity_type="Payment",
            entity_id=str(payment.id),
            current_status=payment.status.value,
            target_status=PaymentStatus.FAILED.value,
        )

    prev_status = payment.status
    payment.status = PaymentStatus.FAILED
    payment.error_code = error_code
    payment.error_message = error_message

    # Record Domain Event
    record_event(
        session=session,
        event_type=EventType.PAYMENT_FAILED,
        entity_type="Payment",
        entity_id=payment.id,
        payload={
            "payment_reference": payment.payment_reference,
            "order_id": str(payment.order_id),
            "amount": str(payment.amount),
            "previous_status": prev_status.value,
            "new_status": PaymentStatus.FAILED.value,
            "error_code": error_code,
            "error_message": error_message,
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(payment)
    return payment


def refund_payment(
    session: Session,
    payment_id: uuid.UUID,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Payment:
    """Refunds a successful payment, transitioning it to REFUNDED.

    Records PAYMENT_REFUNDED domain event in the same transaction.
    """
    payment = get_payment(session, payment_id=payment_id)

    allowed_targets = PAYMENT_TRANSITIONS.get(payment.status, set())
    if PaymentStatus.REFUNDED not in allowed_targets:
        raise InvalidStateTransitionError(
            entity_type="Payment",
            entity_id=str(payment.id),
            current_status=payment.status.value,
            target_status=PaymentStatus.REFUNDED.value,
        )

    prev_status = payment.status
    payment.status = PaymentStatus.REFUNDED

    record_event(
        session=session,
        event_type=EventType.PAYMENT_REFUNDED,
        entity_type="Payment",
        entity_id=payment.id,
        payload={
            "payment_reference": payment.payment_reference,
            "order_id": str(payment.order_id),
            "amount": str(payment.amount),
            "currency": payment.currency,
            "previous_status": prev_status.value,
            "new_status": PaymentStatus.REFUNDED.value,
            "reason": reason or "Customer refund processed",
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(payment)
    return payment

