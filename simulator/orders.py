"""
Order simulation operations and deterministic state transitions.
Records domain events synchronously within the active transaction.
"""

import uuid
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Order,
    OrderItem,
    Customer,
    Product,
    OrderStatus,
    EventType,
)
from simulator.exceptions import (
    EntityNotFoundError,
    InvalidStateTransitionError,
    BusinessRuleViolationError,
)
from simulator.events import record_event

# Valid deterministic state transitions for OrderStatus
ORDER_TRANSITIONS = {
    OrderStatus.PENDING: {
        OrderStatus.CONFIRMED,
        OrderStatus.CANCELLED,
        OrderStatus.ON_HOLD,
    },
    OrderStatus.CONFIRMED: {
        OrderStatus.PROCESSING,
        OrderStatus.CANCELLED,
        OrderStatus.ON_HOLD,
    },
    OrderStatus.PROCESSING: {
        OrderStatus.SHIPPED,
        OrderStatus.CANCELLED,
        OrderStatus.ON_HOLD,
    },
    OrderStatus.SHIPPED: {
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.ON_HOLD,
    },
    OrderStatus.ON_HOLD: {
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
        OrderStatus.PROCESSING,
        OrderStatus.SHIPPED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.DELIVERED: set(),  # Terminal state
    OrderStatus.CANCELLED: set(),  # Terminal state
}


def create_order(
    session: Session,
    customer_id: uuid.UUID,
    items: List[Dict[str, Any]],
    order_number: Optional[str] = None,
    shipping_address: Optional[Dict[str, str]] = None,
    tax_rate: Decimal = Decimal("0.18"),
    shipping_amount: Decimal = Decimal("0.00"),
    discount_amount: Decimal = Decimal("0.00"),
    order_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[str] = None,
) -> Order:
    """
    Creates and persists a new Order with OrderItems in PENDING state.
    Calculates subtotal, tax, and total deterministically.
    Records ORDER_CREATED domain event in the same transaction.
    """
    customer = session.get(Customer, customer_id)
    if not customer:
        raise EntityNotFoundError(f"Customer with id {customer_id} not found.")

    if not items:
        raise BusinessRuleViolationError("Cannot create an order with no items.")

    auto_order_number = order_number or f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    subtotal = Decimal("0.00")
    order_items: List[OrderItem] = []

    target_order_id = order_id or uuid.uuid4()

    for item_data in items:
        product_id = item_data.get("product_id")
        sku = item_data.get("sku")

        product = None
        if product_id:
            product = session.get(Product, product_id)
        elif sku:
            product = session.scalar(select(Product).where(Product.sku == sku))

        if not product:
            raise EntityNotFoundError(f"Product not found (product_id={product_id}, sku={sku}).")

        if not product.is_active:
            raise BusinessRuleViolationError(f"Product {product.sku} is not active.")

        qty = int(item_data.get("quantity", 1))
        if qty <= 0:
            raise BusinessRuleViolationError("Item quantity must be greater than zero.")

        unit_price = item_data.get("unit_price")
        if unit_price is not None:
            price = Decimal(str(unit_price))
        else:
            price = product.unit_price

        line_total = (price * qty).quantize(Decimal("0.01"))
        subtotal += line_total

        order_item = OrderItem(
            id=uuid.uuid4(),
            order_id=target_order_id,
            product_id=product.id,
            sku=product.sku,
            product_name=product.name,
            quantity=qty,
            unit_price=price,
            total_price=line_total,
        )
        order_items.append(order_item)

    tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"))
    total_amount = (subtotal + tax_amount + shipping_amount - discount_amount).quantize(Decimal("0.01"))

    if total_amount < Decimal("0.00"):
        total_amount = Decimal("0.00")

    addr = shipping_address or {}

    order = Order(
        id=target_order_id,
        order_number=auto_order_number,
        customer_id=customer.id,
        status=OrderStatus.PENDING,
        currency="INR",
        subtotal_amount=subtotal,
        tax_amount=tax_amount,
        shipping_amount=shipping_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        shipping_address_line1=addr.get("line1", customer.city),
        shipping_address_line2=addr.get("line2"),
        shipping_city=addr.get("city", customer.city),
        shipping_state=addr.get("state", customer.state),
        shipping_pincode=addr.get("pincode", customer.pincode),
        shipping_country=addr.get("country", "IN"),
    )
    order.items = order_items

    session.add(order)

    # Record Domain Event
    record_event(
        session=session,
        event_type=EventType.ORDER_CREATED,
        entity_type="Order",
        entity_id=order.id,
        payload={
            "order_number": order.order_number,
            "customer_id": str(order.customer_id),
            "status": order.status.value,
            "subtotal_amount": str(order.subtotal_amount),
            "tax_amount": str(order.tax_amount),
            "total_amount": str(order.total_amount),
            "currency": order.currency,
            "item_count": len(order.items),
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(order)
    return order


def get_order(
    session: Session,
    order_id: Optional[uuid.UUID] = None,
    order_number: Optional[str] = None,
) -> Order:
    """Retrieves an order by UUID or order_number. Raises EntityNotFoundError if missing."""
    if order_id:
        order = session.get(Order, order_id)
    elif order_number:
        order = session.scalar(select(Order).where(Order.order_number == order_number))
    else:
        raise ValueError("Must provide either order_id or order_number.")

    if not order:
        identifier = str(order_id) if order_id else str(order_number)
        raise EntityNotFoundError(f"Order {identifier} not found.")

    return order


def update_order_status(
    session: Session,
    order_id: uuid.UUID,
    new_status: OrderStatus,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Order:
    """
    Validates and executes a state transition for an Order.
    Records ORDER_STATUS_CHANGED or ORDER_CANCELLED domain event.
    """
    order = get_order(session, order_id=order_id)

    if order.status == new_status:
        return order

    allowed_targets = ORDER_TRANSITIONS.get(order.status, set())
    if new_status not in allowed_targets:
        raise InvalidStateTransitionError(
            entity_type="Order",
            entity_id=str(order.id),
            current_status=order.status.value,
            target_status=new_status.value,
        )

    prev_status = order.status
    order.status = new_status
    if reason and new_status == OrderStatus.CANCELLED:
        order.cancellation_reason = reason

    # Record Domain Event
    event_type = EventType.ORDER_CANCELLED if new_status == OrderStatus.CANCELLED else EventType.ORDER_STATUS_CHANGED
    record_event(
        session=session,
        event_type=event_type,
        entity_type="Order",
        entity_id=order.id,
        payload={
            "order_number": order.order_number,
            "previous_status": prev_status.value,
            "new_status": new_status.value,
            "reason": reason,
        },
        correlation_id=correlation_id,
    )

    session.commit()
    session.refresh(order)
    return order


def cancel_order(
    session: Session,
    order_id: uuid.UUID,
    reason: str,
    correlation_id: Optional[str] = None,
) -> Order:
    """
    Cancels an active order if allowed by lifecycle rules.
    """
    if not reason or not reason.strip():
        raise BusinessRuleViolationError("Cancellation reason must be provided.")

    return update_order_status(
        session=session,
        order_id=order_id,
        new_status=OrderStatus.CANCELLED,
        reason=reason.strip(),
        correlation_id=correlation_id,
    )
