"""Idempotency Record database model for OpsWingman Resilience & Deduplication (Phase 4 - Deliverable D-15)."""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.enums import IdempotencyStatus


class IdempotencyRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable record of an operation execution guarded by an idempotency key.

    Tracks execution state, request fingerprint, and cached result payload
    to prevent duplicate side-effects (e.g., duplicate payments, refunds, or emails).
    """

    __tablename__ = "idempotency_records"

    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    request_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[IdempotencyStatus] = mapped_column(
        SQLEnum(IdempotencyStatus, native_enum=False, length=50),
        default=IdempotencyStatus.PROCESSING,
        index=True,
        nullable=False,
    )
    response_payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),
        Index("ix_idempotency_records_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        status_val = self.status.value if hasattr(self.status, "value") else str(self.status)
        return f"<IdempotencyRecord(id='{self.id}', scope='{self.scope}', key='{self.idempotency_key}', status='{status_val}')>"
