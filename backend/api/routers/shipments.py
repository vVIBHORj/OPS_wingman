"""
Shipment API Router.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_db
from backend.api.schemas import (
    ShipmentStatusUpdateRequest,
    ShipmentDelayRequest,
    ShipmentDeliverRequest,
    ShipmentResponse,
)
import simulator

router = APIRouter(prefix="/shipments", tags=["Shipments"])


@router.get("", response_model=ShipmentResponse)
def get_shipment_by_query(
    tracking_number: Optional[str] = Query(default=None, description="Search shipment by tracking number"),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Retrieve a shipment by query parameter."""
    if not tracking_number:
        raise ValueError("tracking_number query parameter is required.")
    shipment = simulator.get_shipment(session=db, tracking_number=tracking_number)
    return ShipmentResponse.model_validate(shipment)


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment_by_id(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Retrieve shipment details by UUID."""
    shipment = simulator.get_shipment(session=db, shipment_id=shipment_id)
    return ShipmentResponse.model_validate(shipment)


@router.post("/{shipment_id}/status", response_model=ShipmentResponse)
def update_shipment_status(
    shipment_id: uuid.UUID,
    payload: ShipmentStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Update shipment transit status."""
    shipment = simulator.update_shipment_status(
        session=db,
        shipment_id=shipment_id,
        new_status=payload.status,
        location=payload.location,
    )
    return ShipmentResponse.model_validate(shipment)


@router.post("/{shipment_id}/delay", response_model=ShipmentResponse)
def delay_shipment(
    shipment_id: uuid.UUID,
    payload: ShipmentDelayRequest,
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Record a logistics delay event with updated ETA and location."""
    shipment = simulator.delay_shipment(
        session=db,
        shipment_id=shipment_id,
        delay_reason=payload.delay_reason,
        updated_eta=payload.updated_eta,
        current_location=payload.current_location,
    )
    return ShipmentResponse.model_validate(shipment)


@router.post("/{shipment_id}/deliver", response_model=ShipmentResponse)
def deliver_shipment(
    shipment_id: uuid.UUID,
    payload: ShipmentDeliverRequest = ShipmentDeliverRequest(),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Record successful shipment delivery and advance order status."""
    shipment = simulator.deliver_shipment(
        session=db,
        shipment_id=shipment_id,
        actual_delivery_date=payload.actual_delivery_date,
        recipient_notes=payload.recipient_notes,
    )
    return ShipmentResponse.model_validate(shipment)

