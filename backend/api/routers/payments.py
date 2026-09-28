"""
Payment API Router.
"""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.session import get_db
from backend.api.schemas import (
    PaymentCaptureRequest,
    PaymentFailRequest,
    PaymentResponse,
)
import simulator

router = APIRouter(prefix="/payments", tags=["Payments"])


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

