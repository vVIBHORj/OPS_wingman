"""
Shipment API Router.
"""

import uuid
from typing import Optional, Union

import simulator
from database.models import Shipment, ShipmentStatus
from database.session import get_db
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.api.schemas import (
    ShipmentDelayRequest,
    ShipmentDeliverRequest,
    ShipmentListResponse,
    ShipmentResponse,
    ShipmentStatusUpdateRequest,
)

router = APIRouter(prefix="/shipments", tags=["Shipments"])


@router.get("", response_model=Union[ShipmentResponse, ShipmentListResponse])
def get_shipments(
    tracking_number: Optional[str] = Query(
        default=None, description="Exact shipment tracking number"
    ),
    status: Optional[ShipmentStatus] = Query(default=None, description="Filter by status"),
    carrier: Optional[str] = Query(default=None, description="Filter by carrier"),
    is_delayed: Optional[bool] = Query(default=None, description="Filter delayed shipments"),
    order_id: Optional[uuid.UUID] = Query(default=None, description="Filter by order ID"),
    search: Optional[str] = Query(default=None, description="Search tracking or shipment number"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Union[ShipmentResponse, ShipmentListResponse]:
    """Retrieve shipment list with filters and pagination, or single shipment by tracking_number."""
    # Backward compatible single lookup by tracking_number
    if tracking_number and not search and not status and not carrier and offset == 0:
        shipment = simulator.get_shipment(session=db, tracking_number=tracking_number)
        return ShipmentResponse.model_validate(shipment)

    query = select(Shipment)
    count_query = select(func.count(Shipment.id))

    if status:
        query = query.where(Shipment.status == status)
        count_query = count_query.where(Shipment.status == status)
    if carrier:
        query = query.where(Shipment.carrier.ilike(f"%{carrier}%"))
        count_query = count_query.where(Shipment.carrier.ilike(f"%{carrier}%"))
    if order_id:
        query = query.where(Shipment.order_id == order_id)
        count_query = count_query.where(Shipment.order_id == order_id)
    if is_delayed is True:
        query = query.where(Shipment.status == ShipmentStatus.DELAYED)
        count_query = count_query.where(Shipment.status == ShipmentStatus.DELAYED)
    elif is_delayed is False:
        query = query.where(Shipment.status != ShipmentStatus.DELAYED)
        count_query = count_query.where(Shipment.status != ShipmentStatus.DELAYED)

    if search:
        search_filter = or_(
            Shipment.tracking_number.ilike(f"%{search}%"),
            Shipment.shipment_number.ilike(f"%{search}%"),
            Shipment.current_location.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.scalar(count_query) or 0
    shipments = db.scalars(
        query.order_by(desc(Shipment.created_at)).offset(offset).limit(limit)
    ).all()

    return ShipmentListResponse(
        total=total,
        items=[ShipmentResponse.model_validate(s) for s in shipments],
        limit=limit,
        offset=offset,
    )


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
