"""
Domain Event recording and query services for OpsWingman Simulator.
"""

import uuid
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import DomainEvent, EventType
from simulator.exceptions import EntityNotFoundError


def record_event(
    session: Session,
    event_type: Union[EventType, str],
    entity_type: str,
    entity_id: uuid.UUID,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
    causation_id: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> DomainEvent:
    """
    Records a domain event within the active session transaction.
    Does not commit independently, ensuring atomic transaction participation.
    """
    ev_type_str = event_type.value if isinstance(event_type, EventType) else str(event_type)

    event = DomainEvent(
        id=uuid.uuid4(),
        event_type=ev_type_str,
        entity_type=entity_type.lower(),
        entity_id=entity_id,
        payload=payload,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    session.add(event)
    return event


def get_event(
    session: Session,
    event_id: uuid.UUID,
) -> DomainEvent:
    """Retrieves an event by UUID or raises EntityNotFoundError."""
    event = session.get(DomainEvent, event_id)
    if not event:
        raise EntityNotFoundError(f"DomainEvent {event_id} not found.")
    return event


def list_events(
    session: Session,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    event_type: Optional[Union[EventType, str]] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[DomainEvent]:
    """Queries domain events chronologically with optional filters."""
    from sqlalchemy import func
    query = select(DomainEvent)

    if entity_type:
        query = query.where(func.lower(DomainEvent.entity_type) == entity_type.lower())
    if entity_id:
        query = query.where(DomainEvent.entity_id == entity_id)
    if event_type:
        ev_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
        query = query.where(func.upper(DomainEvent.event_type) == ev_str.upper())

    query = query.order_by(DomainEvent.occurred_at.asc(), DomainEvent.created_at.asc()).limit(limit).offset(offset)
    return list(session.scalars(query).all())


def list_events_for_entity(
    session: Session,
    entity_type: str,
    entity_id: uuid.UUID,
    limit: int = 100,
) -> List[DomainEvent]:
    """Retrieves chronological event trail for a specific entity."""
    return list_events(session, entity_type=entity_type, entity_id=entity_id, limit=limit)


def list_events_by_type(
    session: Session,
    event_type: Union[EventType, str],
    limit: int = 100,
) -> List[DomainEvent]:
    """Retrieves events matching a specific event_type."""
    return list_events(session, event_type=event_type, limit=limit)
