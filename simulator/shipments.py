"""
Shipment simulation operations and logistics state transitions.
Records domain events synchronously within the active transaction.
"""

import uuid
from typing import Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Order,
    Shipment,
    OrderStatus,
    ShipmentStatus,
    EventType,
)
from simulator.exceptions import (
    EntityNotFoundError,
    InvalidStateTransitionError,
    BusinessRuleViolationError,
)
from simulator.events import record_event

SHIPMENT_TRANSITIONS = {
    ShipmentStatus.MANIFESTED: {
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.DELAYED,
    },
    ShipmentStatus.IN_TRANSIT: {
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.DELAYED,
        ShipmentStatus.FAILED_ATTEMPT,
        ShipmentStatus.DELIVERED,
    },
    ShipmentStatus.DELAYED: {
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.RETURNED,
    },
    ShipmentStatus.OUT_FOR_DELIVERY: {
        ShipmentStatus.DELIVERED,
        ShipmentStatus.FAILED_ATTEMPT,
        ShipmentStatus.DELAYED,
    },
    ShipmentStatus.FAILED_ATTEMPT: {
        ShipmentStatus.OUT_FOR_DELIVERY,
        ShipmentStatus.RETURNED,
    },
    ShipmentStatus.DELIVERED: set(),  # Terminal state
    ShipmentStatus.RETURNED: set(),   # Terminal state
}


def create_shipment(
    session: Session,
    order_id: uuid.UUID,
    carrier: str = "Delhivery",
    tracking_number: Optional[str] = None,
    estimated_days: int = 3,
    status: ShipmentStatus = ShipmentStatus.MANIFESTED,
    shipment_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[str] = None,
) -> Shipment:
    """
    Creates and dispatches a shipment for an active, paid Order.
    Advances order status to SHIPPED if currently PROCESSING or CONFIRMED.
    Records SHIPMENT_CREATED domain event in the same transaction.
    """
    order = session.get(Order, order_id)
    if not order:
        raise EntityNotFoundError(f"Order {order_id} not found.")

    if order.status == OrderStatus.CANCELLED:
        raise BusinessRuleViolationError(f"Cannot create shipment for cancelled order {order.order_number}.")

    if order.status == OrderStatus.DELIVERED:
        raise BusinessRuleViolationError(f"Order {order.order_number} is already delivered.")

    now = datetime.now(timezone.utc)
    track_num = tracking_number or f"{carrier[:3].upper()}{uuid.uuid4().hex[:9].upper()}IN"
    ship_num = f"SHP-{carrier[:3].upper()}-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    shipment = Shipment(
        id=shipment_id or uuid.uuid4(),
        shipment_number=ship_num,
        order_id=order.id,
        carrier=carrier,
        tracking_number=track_num,
        status=status,
        estimated_delivery_date=now + timedelta(days=estimated_days),
        current_location=f"{carrier} Origin Facility",
        shipped_at=now,
    )

    session.add(shipment)

    # Sync order status to SHIPPED if appropriate
    if order.status in (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING):
        prev_order_status = order.status
        order.status = OrderStatus.SHIPPED
        record_event(
            session=session,
            event_type=EventType.ORDER_STATUS_CHANGED,
            entity_type="Order",
            entity_id=order.id,
            payload={
                "order_number": order.order_number,
                "previous_status": prev_order_status.value,
                "new_status": OrderStatus.SHIPPED.value,
                "reason": f"Shipment {shipment.shipment_number} created ({carrier})",
            },
            correlation_id=correlation_id,
        )

    # Record Shipment Domain Event
    record_event(
        session=session,
        event_type=EventType.SHIPMENT_CREATED,
        entity_type="Shipment",
        entity_id=shipment.id,
        payload={
            "shipment_number": shipment.shipment_number,
            "order_id": str(shipment.order_id),
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "status": shipment.status.value,
            "estimated_delivery_date": shipment.estimated_delivery_date.isoformat() if shipment.estimated_delivery_date else None,
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(shipment)
    return shipment


def get_shipment(
    session: Session,
    shipment_id: Optional[uuid.UUID] = None,
    tracking_number: Optional[str] = None,
) -> Shipment:
    """Retrieves a shipment by UUID or tracking_number."""
    if shipment_id:
        shipment = session.get(Shipment, shipment_id)
    elif tracking_number:
        shipment = session.scalar(select(Shipment).where(Shipment.tracking_number == tracking_number))
    else:
        raise ValueError("Must provide either shipment_id or tracking_number.")

    if not shipment:
        identifier = str(shipment_id) if shipment_id else str(tracking_number)
        raise EntityNotFoundError(f"Shipment {identifier} not found.")

    return shipment


def update_shipment_status(
    session: Session,
    shipment_id: uuid.UUID,
    new_status: ShipmentStatus,
    location: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Shipment:
    """
    Executes a validated shipment state transition.
    Records SHIPMENT_STATUS_CHANGED domain event.
    """
    shipment = get_shipment(session, shipment_id=shipment_id)

    if shipment.status == new_status:
        if location:
            shipment.current_location = location
            session.commit()
            session.refresh(shipment)
        return shipment

    allowed_targets = SHIPMENT_TRANSITIONS.get(shipment.status, set())
    if new_status not in allowed_targets:
        raise InvalidStateTransitionError(
            entity_type="Shipment",
            entity_id=str(shipment.id),
            current_status=shipment.status.value,
            target_status=new_status.value,
        )

    prev_status = shipment.status
    shipment.status = new_status
    if location:
        shipment.current_location = location

    # Record Domain Event
    record_event(
        session=session,
        event_type=EventType.SHIPMENT_STATUS_CHANGED,
        entity_type="Shipment",
        entity_id=shipment.id,
        payload={
            "shipment_number": shipment.shipment_number,
            "order_id": str(shipment.order_id),
            "carrier": shipment.carrier,
            "previous_status": prev_status.value,
            "new_status": new_status.value,
            "current_location": shipment.current_location,
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(shipment)
    return shipment


def delay_shipment(
    session: Session,
    shipment_id: uuid.UUID,
    delay_reason: str,
    updated_eta: Optional[datetime] = None,
    current_location: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Shipment:
    """
    Marks a shipment as DELAYED with reason, revised ETA, and location.
    Records SHIPMENT_DELAYED domain event.
    """
    if not delay_reason or not delay_reason.strip():
        raise BusinessRuleViolationError("Delay reason must be specified.")

    shipment = get_shipment(session, shipment_id=shipment_id)

    allowed_targets = SHIPMENT_TRANSITIONS.get(shipment.status, set())
    if ShipmentStatus.DELAYED not in allowed_targets and shipment.status != ShipmentStatus.DELAYED:
        raise InvalidStateTransitionError(
            entity_type="Shipment",
            entity_id=str(shipment.id),
            current_status=shipment.status.value,
            target_status=ShipmentStatus.DELAYED.value,
        )

    prev_status = shipment.status
    shipment.status = ShipmentStatus.DELAYED
    shipment.delay_reason = delay_reason.strip()
    if updated_eta:
        shipment.estimated_delivery_date = updated_eta
    if current_location:
        shipment.current_location = current_location

    # Record Domain Event
    record_event(
        session=session,
        event_type=EventType.SHIPMENT_DELAYED,
        entity_type="Shipment",
        entity_id=shipment.id,
        payload={
            "shipment_number": shipment.shipment_number,
            "order_id": str(shipment.order_id),
            "carrier": shipment.carrier,
            "previous_status": prev_status.value,
            "new_status": ShipmentStatus.DELAYED.value,
            "delay_reason": shipment.delay_reason,
            "revised_eta": shipment.estimated_delivery_date.isoformat() if shipment.estimated_delivery_date else None,
            "current_location": shipment.current_location,
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(shipment)
    return shipment


def deliver_shipment(
    session: Session,
    shipment_id: uuid.UUID,
    actual_delivery_date: Optional[datetime] = None,
    recipient_notes: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Shipment:
    """
    Marks a shipment as DELIVERED and advances Order to DELIVERED.
    Records SHIPMENT_DELIVERED and ORDER_STATUS_CHANGED domain events.
    """
    shipment = get_shipment(session, shipment_id=shipment_id)

    allowed_targets = SHIPMENT_TRANSITIONS.get(shipment.status, set())
    if ShipmentStatus.DELIVERED not in allowed_targets:
        raise InvalidStateTransitionError(
            entity_type="Shipment",
            entity_id=str(shipment.id),
            current_status=shipment.status.value,
            target_status=ShipmentStatus.DELIVERED.value,
        )

    prev_status = shipment.status
    deliv_time = actual_delivery_date or datetime.now(timezone.utc)
    shipment.status = ShipmentStatus.DELIVERED
    shipment.actual_delivery_date = deliv_time
    if recipient_notes:
        shipment.current_location = f"Delivered - {recipient_notes}"

    # Sync Order status to DELIVERED
    order = session.get(Order, shipment.order_id)
    if order and order.status != OrderStatus.DELIVERED:
        prev_order_status = order.status
        order.status = OrderStatus.DELIVERED
        record_event(
            session=session,
            event_type=EventType.ORDER_STATUS_CHANGED,
            entity_type="Order",
            entity_id=order.id,
            payload={
                "order_number": order.order_number,
                "previous_status": prev_order_status.value,
                "new_status": OrderStatus.DELIVERED.value,
                "reason": f"Shipment {shipment.shipment_number} marked as delivered",
            },
            correlation_id=correlation_id,
        )

    # Record Shipment Domain Event
    actual_delivery_val: Optional[datetime] = shipment.actual_delivery_date
    record_event(
        session=session,
        event_type=EventType.SHIPMENT_DELIVERED,
        entity_type="Shipment",
        entity_id=shipment.id,
        payload={
            "shipment_number": shipment.shipment_number,
            "order_id": str(shipment.order_id),
            "carrier": shipment.carrier,
            "previous_status": prev_status.value,
            "new_status": ShipmentStatus.DELIVERED.value,
            "actual_delivery_date": actual_delivery_val.isoformat() if actual_delivery_val is not None else None,
            "recipient_notes": recipient_notes,
        },
        correlation_id=correlation_id,
    )


    session.commit()
    session.refresh(shipment)
    return shipment
