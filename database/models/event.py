"""
Domain Event database model and EventType enum for OpsWingman.
Provides an immutable audit log of domain state transitions.
"""

import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, GUID, UUIDPrimaryKeyMixin


class EventType(str, Enum):
    """Canonical domain event types for OpsWingman."""
    # Order Events
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"
    ORDER_CANCELLED = "ORDER_CANCELLED"

    # Payment Events
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCESSFUL = "PAYMENT_SUCCESSFUL"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"

    # Shipment Events
    SHIPMENT_CREATED = "SHIPMENT_CREATED"
    SHIPMENT_STATUS_CHANGED = "SHIPMENT_STATUS_CHANGED"
    SHIPMENT_DELAYED = "SHIPMENT_DELAYED"
    SHIPMENT_DELIVERED = "SHIPMENT_DELIVERED"


class DomainEvent(Base, UUIDPrimaryKeyMixin):
    """
    Persistent record of a domain state change.
    Events are recorded within the same database transaction as the business operation.
    """
    __tablename__ = "domain_events"

    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID, index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    causation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_domain_events_entity", "entity_type", "entity_id"),
        Index("ix_domain_events_type_occurred", "event_type", "occurred_at"),
        Index("ix_domain_events_occurred_at", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<DomainEvent(id={self.id}, type='{self.event_type}', entity='{self.entity_type}:{self.entity_id}', occurred_at='{self.occurred_at}')>"
