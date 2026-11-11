"""
Order API Router.
Reuses deterministic business simulator operations without duplicating rules.
"""

import uuid
from decimal import Decimal
from typing import Optional, Union

import simulator
from database.models import Customer, Order, OrderStatus
from database.session import get_db
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.api.schemas import (
    OrderCancelRequest,
    OrderCreateRequest,
    OrderDetailResponse,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdateRequest,
    PaymentCreateRequest,
    PaymentResponse,
    ShipmentCreateRequest,
    ShipmentResponse,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Create a new order with line items."""
    items_data = [item.model_dump() for item in payload.items]
    order = simulator.create_order(
        session=db,
        customer_id=payload.customer_id,
        items=items_data,
        order_number=payload.order_number,
        shipping_address=payload.shipping_address,
        tax_rate=payload.tax_rate,
        shipping_amount=payload.shipping_amount,
        discount_amount=payload.discount_amount,
    )
    return OrderResponse.model_validate(order)


@router.get("", response_model=Union[OrderResponse, OrderListResponse])
def get_orders(
    order_number: Optional[str] = Query(default=None, description="Exact order number search"),
    status: Optional[OrderStatus] = Query(default=None, description="Filter by status"),
    customer_id: Optional[uuid.UUID] = Query(default=None, description="Filter by customer ID"),
    search: Optional[str] = Query(default=None, description="Search order number or customer"),
    min_amount: Optional[Decimal] = Query(default=None, description="Filter by min total amount"),
    max_amount: Optional[Decimal] = Query(default=None, description="Filter by max total amount"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Union[OrderResponse, OrderListResponse]:
    """Retrieve orders with pagination and filtering, or single order by exact order_number."""
    # Backward-compatible exact order_number single lookup
    if order_number and not search and not status and not customer_id and offset == 0:
        order = simulator.get_order(session=db, order_number=order_number)
        return OrderResponse.model_validate(order)

    query = select(Order)
    count_query = select(func.count(Order.id))

    if status:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)
    if customer_id:
        query = query.where(Order.customer_id == customer_id)
        count_query = count_query.where(Order.customer_id == customer_id)
    if min_amount is not None:
        query = query.where(Order.total_amount >= min_amount)
        count_query = count_query.where(Order.total_amount >= min_amount)
    if max_amount is not None:
        query = query.where(Order.total_amount <= max_amount)
        count_query = count_query.where(Order.total_amount <= max_amount)

    if search:
        search_filter = or_(
            Order.order_number.ilike(f"%{search}%"),
            Order.customer_id.in_(
                select(Customer.id).where(
                    or_(
                        Customer.email.ilike(f"%{search}%"),
                        Customer.first_name.ilike(f"%{search}%"),
                        Customer.last_name.ilike(f"%{search}%"),
                        Customer.phone.ilike(f"%{search}%"),
                    )
                )
            ),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.scalar(count_query) or 0
    orders = db.scalars(query.order_by(desc(Order.created_at)).offset(offset).limit(limit)).all()

    return OrderListResponse(
        total=total,
        items=[OrderResponse.model_validate(o) for o in orders],
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order_by_id(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrderDetailResponse:
    """Retrieve order details by UUID, including payments, shipments, and customer."""
    order = simulator.get_order(session=db, order_id=order_id)
    return OrderDetailResponse.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: uuid.UUID,
    payload: OrderCancelRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Cancel an active order."""
    order = simulator.cancel_order(
        session=db,
        order_id=order_id,
        reason=payload.reason,
    )
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Update order status according to validated transition rules."""
    order = simulator.update_order_status(
        session=db,
        order_id=order_id,
        new_status=payload.status,
        reason=payload.reason,
    )
    return OrderResponse.model_validate(order)


@router.post(
    "/{order_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED
)
def create_order_payment(
    order_id: uuid.UUID,
    payload: PaymentCreateRequest,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Create an initiated payment for an order."""
    payment = simulator.create_payment(
        session=db,
        order_id=order_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
    )
    return PaymentResponse.model_validate(payment)


@router.post(
    "/{order_id}/shipments", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED
)
def create_order_shipment(
    order_id: uuid.UUID,
    payload: ShipmentCreateRequest,
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Create and dispatch a shipment for an order."""
    shipment = simulator.create_shipment(
        session=db,
        order_id=order_id,
        carrier=payload.carrier,
        tracking_number=payload.tracking_number,
        estimated_days=payload.estimated_days,
        status=payload.status,
    )
    return ShipmentResponse.model_validate(shipment)
