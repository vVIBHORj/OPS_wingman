"""Approval Record database model for OpsWingman Human Approval Queue (Phase 3 - Deliverable D-12)."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.enums import ApprovalStatus


class ApprovalRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable record of a pending or decided human approval request.

    Connects policy decisions, workflow executions, proposed actions, and operator decisions.
    """

    __tablename__ = "approval_records"

    approval_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)
    target_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    policy_decision: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        SQLEnum(ApprovalStatus, native_enum=False, length=50),
        default=ApprovalStatus.PENDING,
        index=True,
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approver_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citations: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    __table_args__ = (
        Index("ix_approvals_status_requested", "status", "requested_at"),
    )

    def __init__(self, **kwargs: Any) -> None:
        if "action_name" in kwargs and "action" not in kwargs:
            kwargs["action"] = kwargs.pop("action_name")
        if "target_entity" in kwargs and "target_entity_id" not in kwargs:
            kwargs["target_entity_id"] = kwargs.pop("target_entity")
        if "approver_identity" in kwargs and "approver_id" not in kwargs:
            kwargs["approver_id"] = kwargs.pop("approver_identity")
        if "approval_id" not in kwargs and "id" in kwargs:
            kwargs["approval_id"] = str(kwargs["id"])
        elif "approval_id" not in kwargs:
            kwargs["approval_id"] = str(uuid.uuid4())
        if "run_id" not in kwargs and "workflow_id" in kwargs:
            kwargs["run_id"] = kwargs["workflow_id"]
        super().__init__(**kwargs)

    @property
    def action_name(self) -> str:
        return self.action

    @property
    def approver_identity(self) -> Optional[str]:
        return self.approver_id

    @approver_identity.setter
    def approver_identity(self, value: Optional[str]) -> None:
        self.approver_id = value

    @property
    def target_entity(self) -> Optional[str]:
        return self.target_entity_id

    @target_entity.setter
    def target_entity(self, value: Optional[str]) -> None:
        self.target_entity_id = value

    def __repr__(self) -> str:
        status_val = self.status.value if hasattr(self.status, "value") else str(self.status)
        return f"<ApprovalRecord(id='{self.approval_id}', action='{self.action}', risk='{self.risk_level}', status='{status_val}')>"
