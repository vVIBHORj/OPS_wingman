"""
Payment API Router.
"""

import uuid
from typing import Optional

import simulator
from database.models import Payment, PaymentMethod, PaymentStatus
from database.session import get_db
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.api.schemas import (
    PaymentCaptureRequest,
    PaymentFailRequest,
    PaymentListResponse,
    PaymentRefundRequest,
    PaymentResponse,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("", response_model=PaymentListResponse)
def list_payments(
    status: Optional[PaymentStatus] = Query(default=None, description="Filter by payment status"),
    payment_method: Optional[PaymentMethod] = Query(
        default=None, description="Filter by payment method"
    ),
    order_id: Optional[uuid.UUID] = Query(default=None, description="Filter by order ID"),
    search: Optional[str] = Query(
        default=None, description="Search reference or gateway transaction ID"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PaymentListResponse:
    """List payment transactions with filters and pagination."""
    query = select(Payment)
    count_query = select(func.count(Payment.id))

    if status:
        query = query.where(Payment.status == status)
        count_query = count_query.where(Payment.status == status)
    if payment_method:
        query = query.where(Payment.payment_method == payment_method)
        count_query = count_query.where(Payment.payment_method == payment_method)
    if order_id:
        query = query.where(Payment.order_id == order_id)
        count_query = count_query.where(Payment.order_id == order_id)

    if search:
        search_filter = or_(
            Payment.payment_reference.ilike(f"%{search}%"),
            Payment.gateway_transaction_id.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.scalar(count_query) or 0
    payments = db.scalars(
        query.order_by(desc(Payment.created_at)).offset(offset).limit(limit)
    ).all()

    return PaymentListResponse(
        total=total,
        items=[PaymentResponse.model_validate(p) for p in payments],
        limit=limit,
        offset=offset,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment_by_id(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Retrieve payment details by UUID."""
    payment = simulator.get_payment(session=db, payment_id=payment_id)
    return PaymentResponse.model_validate(payment)


@router.post("/{payment_id}/capture", response_model=PaymentResponse)
def capture_payment(
    payment_id: uuid.UUID,
    payload: PaymentCaptureRequest = PaymentCaptureRequest(),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Capture an initiated or authorized payment."""
    payment = simulator.capture_payment(
        session=db,
        payment_id=payment_id,
        gateway_transaction_id=payload.gateway_transaction_id,
    )
    return PaymentResponse.model_validate(payment)


@router.post("/{payment_id}/fail", response_model=PaymentResponse)
def fail_payment(
    payment_id: uuid.UUID,
    payload: PaymentFailRequest,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Record a failed payment attempt with error details."""
    payment = simulator.fail_payment(
        session=db,
        payment_id=payment_id,
        error_code=payload.error_code,
        error_message=payload.error_message,
    )
    return PaymentResponse.model_validate(payment)


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
def refund_payment(
    payment_id: uuid.UUID,
    payload: PaymentRefundRequest = PaymentRefundRequest(),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """Process a refund against a captured payment."""
    payment = simulator.refund_payment(
        session=db,
        payment_id=payment_id,
        reason=payload.reason,
    )
    return PaymentResponse.model_validate(payment)
