"""State Verification Service (Phase 4 - Deliverable D-14).

Performs post-action state verification against persistent PostgreSQL/SQLAlchemy
ground truth to confirm that state-changing tool executions actually produced
their intended business outcomes without silent failures or state drift.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    DomainEvent,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Shipment,
    ShipmentStatus,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from backend.verification.schemas import (
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)


class StateVerificationService:
    """Read-only verification engine confirming external actions produced intended database changes."""

    # ==========================================================================
    # Entity-Specific Verifiers
    # ==========================================================================

    def verify_order_cancellation(
        self,
        session: Session,
        order_id: Union[str, uuid.UUID],
        expected_reason: Optional[str] = None,
    ) -> VerificationResult:
        """Verifies that an order has transitioned to CANCELLED state and optional reason matches."""
        target_state = OrderStatus.CANCELLED.value
        entity_id_str = str(order_id)
        discrepancies: List[str] = []

        try:
            order: Optional[Order] = None
            try:
                val_uuid = uuid.UUID(entity_id_str)
                order = session.get(Order, val_uuid)
            except ValueError:
                pass

            if order is None:
                order = session.scalar(select(Order).where(Order.order_number == entity_id_str))

            if order is None:
                return VerificationResult(
                    verified=False,
                    status=VerificationStatus.NOT_FOUND,
                    entity_type="order",
                    entity_id=entity_id_str,
                    target_state=target_state,
                    actual_state="NOT_FOUND",
                    discrepancies=[f"Order '{entity_id_str}' was not found in the database."],
                    operation="cancel_order",
                )

            actual_status = order.status.value
            details: Dict[str, Any] = {
                "order_number": order.order_number,
                "status": actual_status,
                "cancellation_reason": order.cancellation_reason,
            }

            if actual_status != target_state:
                discrepancies.append(
                    f"Order status mismatch: expected '{target_state}', got '{actual_status}'."
                )

            if expected_reason is not None and order.cancellation_reason != expected_reason:
                discrepancies.append(
                    f"Cancellation reason mismatch: expected '{expected_reason}', got '{order.cancellation_reason}'."
                )

            verified = len(discrepancies) == 0
            return VerificationResult(
                verified=verified,
                status=VerificationStatus.VERIFIED if verified else VerificationStatus.DIVERGENT,
                entity_type="order",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state=actual_status,
                discrepancies=discrepancies,
                operation="cancel_order",
                details=details,
            )

        except Exception as exc:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.ERROR,
                entity_type="order",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state="ERROR",
                discrepancies=[f"Database inspection error: {exc}"],
                operation="cancel_order",
                error=str(exc),
            )

    def verify_payment_refund(
        self,
        session: Session,
        order_id_or_payment_id: Union[str, uuid.UUID],
        expected_amount: Optional[Union[float, Decimal]] = None,
    ) -> VerificationResult:
        """Verifies that a payment has transitioned to REFUNDED status and optional amount matches."""
        target_state = PaymentStatus.REFUNDED.value
        entity_id_str = str(order_id_or_payment_id)
        discrepancies: List[str] = []

        try:
            payment: Optional[Payment] = None
            try:
                val_uuid = uuid.UUID(entity_id_str)
                # First try by payment.id, then by payment.order_id
                payment = session.get(Payment, val_uuid)
                if payment is None:
                    payment = session.scalar(select(Payment).where(Payment.order_id == val_uuid))
            except ValueError:
                payment = session.scalar(select(Payment).where(Payment.payment_reference == entity_id_str))

            if payment is None:
                return VerificationResult(
                    verified=False,
                    status=VerificationStatus.NOT_FOUND,
                    entity_type="payment",
                    entity_id=entity_id_str,
                    target_state=target_state,
                    actual_state="NOT_FOUND",
                    discrepancies=[f"Payment record for '{entity_id_str}' was not found in the database."],
                    operation="refund_payment",
                )

            actual_status = payment.status.value
            details: Dict[str, Any] = {
                "payment_reference": payment.payment_reference,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "status": actual_status,
            }

            if actual_status != target_state:
                discrepancies.append(
                    f"Payment status mismatch: expected '{target_state}', got '{actual_status}'."
                )

            if expected_amount is not None:
                exp_dec = Decimal(str(expected_amount))
                if payment.amount != exp_dec:
                    discrepancies.append(
                        f"Refund amount mismatch: expected {exp_dec}, observed payment amount {payment.amount}."
                    )

            verified = len(discrepancies) == 0
            return VerificationResult(
                verified=verified,
                status=VerificationStatus.VERIFIED if verified else VerificationStatus.DIVERGENT,
                entity_type="payment",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state=actual_status,
                discrepancies=discrepancies,
                operation="refund_payment",
                details=details,
            )

        except Exception as exc:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.ERROR,
                entity_type="payment",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state="ERROR",
                discrepancies=[f"Database inspection error: {exc}"],
                operation="refund_payment",
                error=str(exc),
            )

    def verify_ticket_status(
        self,
        session: Session,
        ticket_id_or_number: Union[str, uuid.UUID],
        expected_status: Union[str, TicketStatus] = TicketStatus.OPEN,
        expected_priority: Optional[Union[str, TicketPriority]] = None,
    ) -> VerificationResult:
        """Verifies ticket persistence, lifecycle status, and priority attributes."""
        target_state = expected_status.value if isinstance(expected_status, TicketStatus) else str(expected_status)
        entity_id_str = str(ticket_id_or_number)
        discrepancies: List[str] = []

        try:
            ticket: Optional[Ticket] = None
            try:
                val_uuid = uuid.UUID(entity_id_str)
                ticket = session.get(Ticket, val_uuid)
                if ticket is None:
                    ticket = session.scalar(select(Ticket).where(Ticket.order_id == val_uuid))
            except ValueError:
                pass

            if ticket is None:
                ticket = session.scalar(select(Ticket).where(Ticket.ticket_number == entity_id_str))

            if ticket is None:
                return VerificationResult(
                    verified=False,
                    status=VerificationStatus.NOT_FOUND,
                    entity_type="ticket",
                    entity_id=entity_id_str,
                    target_state=target_state,
                    actual_state="NOT_FOUND",
                    discrepancies=[f"Ticket '{entity_id_str}' was not found in the database."],
                    operation="create_ticket",
                )

            actual_status = ticket.status.value
            details: Dict[str, Any] = {
                "ticket_number": ticket.ticket_number,
                "status": actual_status,
                "priority": ticket.priority.value,
                "title": ticket.title,
            }

            if actual_status != target_state:
                discrepancies.append(
                    f"Ticket status mismatch: expected '{target_state}', got '{actual_status}'."
                )

            if expected_priority is not None:
                exp_prio_val = (
                    expected_priority.value
                    if isinstance(expected_priority, TicketPriority)
                    else str(expected_priority)
                )
                if ticket.priority.value != exp_prio_val:
                    discrepancies.append(
                        f"Ticket priority mismatch: expected '{exp_prio_val}', got '{ticket.priority.value}'."
                    )

            verified = len(discrepancies) == 0
            return VerificationResult(
                verified=verified,
                status=VerificationStatus.VERIFIED if verified else VerificationStatus.DIVERGENT,
                entity_type="ticket",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state=actual_status,
                discrepancies=discrepancies,
                operation="create_ticket",
                details=details,
            )

        except Exception as exc:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.ERROR,
                entity_type="ticket",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state="ERROR",
                discrepancies=[f"Database inspection error: {exc}"],
                operation="create_ticket",
                error=str(exc),
            )

    def verify_shipment_status(
        self,
        session: Session,
        shipment_id_or_tracking: Union[str, uuid.UUID],
        expected_status: Union[str, ShipmentStatus] = ShipmentStatus.DELIVERED,
    ) -> VerificationResult:
        """Verifies shipment lifecycle state against database ground truth."""
        target_state = expected_status.value if isinstance(expected_status, ShipmentStatus) else str(expected_status)
        entity_id_str = str(shipment_id_or_tracking)
        discrepancies: List[str] = []

        try:
            shipment: Optional[Shipment] = None
            try:
                val_uuid = uuid.UUID(entity_id_str)
                shipment = session.get(Shipment, val_uuid)
                if shipment is None:
                    shipment = session.scalar(select(Shipment).where(Shipment.order_id == val_uuid))
            except ValueError:
                pass

            if shipment is None:
                shipment = session.scalar(select(Shipment).where(Shipment.tracking_number == entity_id_str))

            if shipment is None:
                return VerificationResult(
                    verified=False,
                    status=VerificationStatus.NOT_FOUND,
                    entity_type="shipment",
                    entity_id=entity_id_str,
                    target_state=target_state,
                    actual_state="NOT_FOUND",
                    discrepancies=[f"Shipment '{entity_id_str}' was not found in the database."],
                    operation="update_shipment",
                )

            actual_status = shipment.status.value
            details: Dict[str, Any] = {
                "tracking_number": shipment.tracking_number,
                "carrier": shipment.carrier,
                "status": actual_status,
                "actual_delivery_date": shipment.actual_delivery_date.isoformat() if shipment.actual_delivery_date else None,
            }

            if actual_status != target_state:
                discrepancies.append(
                    f"Shipment status mismatch: expected '{target_state}', got '{actual_status}'."
                )

            verified = len(discrepancies) == 0
            return VerificationResult(
                verified=verified,
                status=VerificationStatus.VERIFIED if verified else VerificationStatus.DIVERGENT,
                entity_type="shipment",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state=actual_status,
                discrepancies=discrepancies,
                operation="update_shipment",
                details=details,
            )

        except Exception as exc:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.ERROR,
                entity_type="shipment",
                entity_id=entity_id_str,
                target_state=target_state,
                actual_state="ERROR",
                discrepancies=[f"Database inspection error: {exc}"],
                operation="update_shipment",
                error=str(exc),
            )

    def verify_domain_event(
        self,
        session: Session,
        entity_id: Union[str, uuid.UUID],
        expected_event_type: str,
    ) -> VerificationResult:
        """Verifies that an immutable domain event was persisted for the target entity."""
        entity_id_str = str(entity_id)
        discrepancies: List[str] = []

        try:
            val_uuid: Optional[uuid.UUID] = None
            try:
                val_uuid = uuid.UUID(entity_id_str)
            except ValueError:
                pass

            if val_uuid is None:
                return VerificationResult(
                    verified=False,
                    status=VerificationStatus.DIVERGENT,
                    entity_type="event",
                    entity_id=entity_id_str,
                    target_state=expected_event_type,
                    actual_state="INVALID_UUID",
                    discrepancies=[f"Invalid UUID '{entity_id_str}' for domain event lookup."],
                    operation="dispatch_event",
                )

            events = session.scalars(
                select(DomainEvent).where(
                    DomainEvent.entity_id == val_uuid,
                    DomainEvent.event_type == expected_event_type,
                )
            ).all()

            if not events:
                discrepancies.append(
                    f"No domain event of type '{expected_event_type}' was recorded for entity '{entity_id_str}'."
                )
                return VerificationResult(
                    verified=False,
                    status=VerificationStatus.DIVERGENT,
                    entity_type="event",
                    entity_id=entity_id_str,
                    target_state=expected_event_type,
                    actual_state="NO_MATCHING_EVENT",
                    discrepancies=discrepancies,
                    operation="dispatch_event",
                )

            latest_event = events[-1]
            return VerificationResult(
                verified=True,
                status=VerificationStatus.VERIFIED,
                entity_type="event",
                entity_id=entity_id_str,
                target_state=expected_event_type,
                actual_state=latest_event.event_type,
                discrepancies=[],
                operation="dispatch_event",
                details={
                    "event_id": str(latest_event.id),
                    "occurred_at": latest_event.occurred_at.isoformat() if latest_event.occurred_at else None,
                    "payload": latest_event.payload,
                },
            )

        except Exception as exc:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.ERROR,
                entity_type="event",
                entity_id=entity_id_str,
                target_state=expected_event_type,
                actual_state="ERROR",
                discrepancies=[f"Database inspection error: {exc}"],
                operation="dispatch_event",
                error=str(exc),
            )

    # ==========================================================================
    # Unified Verification Dispatcher
    # ==========================================================================

    def verify(
        self,
        session: Session,
        request: VerificationRequest,
    ) -> VerificationResult:
        """Dispatches verification according to request.entity_type."""
        etype = request.entity_type.lower()
        if etype == "order":
            expected_reason = request.expected_attributes.get("cancellation_reason")
            return self.verify_order_cancellation(
                session=session,
                order_id=request.entity_id,
                expected_reason=expected_reason,
            )
        elif etype == "payment":
            expected_amount = request.expected_attributes.get("amount")
            return self.verify_payment_refund(
                session=session,
                order_id_or_payment_id=request.entity_id,
                expected_amount=expected_amount,
            )
        elif etype == "ticket":
            expected_priority = request.expected_attributes.get("priority")
            return self.verify_ticket_status(
                session=session,
                ticket_id_or_number=request.entity_id,
                expected_status=request.target_state,
                expected_priority=expected_priority,
            )
        elif etype == "shipment":
            return self.verify_shipment_status(
                session=session,
                shipment_id_or_tracking=request.entity_id,
                expected_status=request.target_state,
            )
        elif etype == "event":
            return self.verify_domain_event(
                session=session,
                entity_id=request.entity_id,
                expected_event_type=request.target_state,
            )
        else:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.ERROR,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                target_state=request.target_state,
                actual_state="UNSUPPORTED_ENTITY",
                discrepancies=[f"Unsupported entity type for verification: '{request.entity_type}'."],
                operation=request.operation,
            )


# Global default verification service instance
state_verification_service = StateVerificationService()
