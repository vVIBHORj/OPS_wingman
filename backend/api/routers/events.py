"""
Domain Events API Router (Read-only).
Exposes the query services for domain events recorded by the business simulator.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_db
from backend.api.schemas import EventResponse
import simulator

router = APIRouter(prefix="/events", tags=["Domain Events"])


@router.get("", response_model=List[EventResponse])
def list_events(
    entity_type: Optional[str] = Query(default=None, description="Filter events by entity type (e.g. order, payment, shipment)"),
    entity_id: Optional[uuid.UUID] = Query(default=None, description="Filter events by entity UUID"),
    event_type: Optional[str] = Query(default=None, description="Filter events by event type (e.g. ORDER_CREATED, PAYMENT_SUCCESSFUL)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max number of events to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> List[EventResponse]:
    """
    List domain events in chronological order with optional filtering by entity_type, entity_id, or event_type.
    """
    events = simulator.list_events(
        session=db,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return [EventResponse.model_validate(e) for e in events]


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventResponse:
    """
    Retrieve a specific domain event by its UUID.
    """
    event = simulator.get_event(session=db, event_id=event_id)
    return EventResponse.model_validate(event)
