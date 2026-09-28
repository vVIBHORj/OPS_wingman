"""
Ticket database model for customer service and operational exceptions.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, GUID
from database.models.enums import TicketStatus, TicketPriority, TicketChannel

if TYPE_CHECKING:
    from database.models.customer import Customer
    from database.models.order import Order


class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Represents an inbound support ticket, customer issue, or operational inquiry.
    Ground truth entity for customer interactions and workflow ticket resolution.
    """
    __tablename__ = "tickets"

    ticket_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("customers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("orders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[TicketChannel] = mapped_column(
        SQLEnum(TicketChannel, native_enum=False, length=50),
        default=TicketChannel.EMAIL,
        nullable=False,
    )
    status: Mapped[TicketStatus] = mapped_column(
        SQLEnum(TicketStatus, native_enum=False, length=50),
        default=TicketStatus.OPEN,
        index=True,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SQLEnum(TicketPriority, native_enum=False, length=50),
        default=TicketPriority.MEDIUM,
        index=True,
        nullable=False,
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="tickets")
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="tickets")

    __table_args__ = (
        Index("ix_tickets_customer_status", "customer_id", "status"),
        Index("ix_tickets_order_status", "order_id", "status"),
        Index("ix_tickets_created_status", "created_at", "status"),
    )

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, number='{self.ticket_number}', status='{self.status.value}', priority='{self.priority.value}')>"
