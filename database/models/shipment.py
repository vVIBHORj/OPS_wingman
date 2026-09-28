"""
Shipment database model.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, GUID
from database.models.enums import ShipmentStatus

if TYPE_CHECKING:
    from database.models.order import Order


class Shipment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Represents physical fulfillment and dispatch of an Order.
    Ground truth entity for shipment tracking, logistics delays, and delivery verification.
    """
    __tablename__ = "shipments"

    shipment_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    carrier: Mapped[str] = mapped_column(String(100), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[ShipmentStatus] = mapped_column(
        SQLEnum(ShipmentStatus, native_enum=False, length=50),
        default=ShipmentStatus.MANIFESTED,
        index=True,
        nullable=False,
    )
    estimated_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_location: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    delay_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="shipments")

    __table_args__ = (
        Index("ix_shipments_order_status", "order_id", "status"),
        Index("ix_shipments_carrier_tracking", "carrier", "tracking_number"),
    )

    def __repr__(self) -> str:
        return f"<Shipment(id={self.id}, tracking='{self.tracking_number}', carrier='{self.carrier}', status='{self.status.value}')>"
