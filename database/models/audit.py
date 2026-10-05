"""Audit Record database model for OpsWingman Audit and Observability Layer (Phase 4/5 - Deliverable D-16)."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEventRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable record of an operational event, tool interaction, policy decision, or state verification.

    Connects workflow runs, actor sources, tools, policies, ML risk evaluations,
    resilience interventions, and post-action verification outcomes into an immutable audit trail.
    """

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(100), default="OpsAgent", nullable=False)
    workflow_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    operation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_arguments: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tool_result_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    policy_decision: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    risk_assessment_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    verification_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    approval_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    retry_attempt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    idempotency_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    __table_args__ = (
        Index("ix_audit_events_run_id_timestamp", "run_id", "timestamp"),
        Index("ix_audit_events_type_timestamp", "event_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditEventRecord(id='{self.id}', event_id='{self.event_id}', run_id='{self.run_id}', type='{self.event_type}')>"
