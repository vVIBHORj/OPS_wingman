"""
Order API Router.
Reuses deterministic business simulator operations without duplicating rules.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database.session import get_db
from backend.api.schemas import (
    OrderCreateRequest,
    OrderStatusUpdateRequest,
    OrderCancelRequest,
    OrderResponse,
    PaymentCreateRequest,
    PaymentResponse,
    ShipmentCreateRequest,
    ShipmentResponse,
)
import simulator

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


@router.get("", response_model=OrderResponse)
def get_order_by_query(
    order_number: Optional[str] = Query(default=None, description="Search order by order number"),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Retrieve an order by query parameter."""
    if not order_number:
        raise ValueError("order_number query parameter is required.")
    order = simulator.get_order(session=db, order_number=order_number)
    return OrderResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_by_id(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Retrieve an order by UUID."""
    order = simulator.get_order(session=db, order_id=order_id)
    return OrderResponse.model_validate(order)


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


@router.post("/{order_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/{order_id}/shipments", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
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

