"""
Payment database model.
"""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Text, Numeric, ForeignKey, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, GUID
from database.models.enums import PaymentStatus, PaymentMethod

if TYPE_CHECKING:
    from database.models.order import Order


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Represents a payment transaction attempt or execution.
    Ground truth entity for payment reconciliation and settlement.
    """
    __tablename__ = "payments"

    payment_reference: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod, native_enum=False, length=50),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus, native_enum=False, length=50),
        default=PaymentStatus.INITIATED,
        index=True,
        nullable=False,
    )
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_order_status", "order_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, ref='{self.payment_reference}', status='{self.status.value}', amount={self.amount} {self.currency})>"
