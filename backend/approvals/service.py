"""Approval service for OpsWingman Phase 3 (D-12).

Manages the lifecycle of human approval requests for HIGH-risk or policy-gated actions.
Prevents duplicate decisions, invalid state transitions, and unapproved execution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.approvals.schemas import ApprovalResponse
from backend.policies.schemas import PolicyEvaluationResult
from backend.tools.schemas import StructuredAction
from database.models.approval import ApprovalRecord
from database.models.enums import ApprovalStatus

logger = logging.getLogger(__name__)


class ApprovalService:
    """Service to create, query, approve, and reject human approval requests."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_approval(
        self,
        workflow_id: str,
        action: StructuredAction,
        risk_level: str,
        reason: str,
        policy_decision: PolicyEvaluationResult | None = None,
        target_entity: str | None = None,
    ) -> ApprovalRecord:
        """Create a durable pending approval record bound to a specific workflow and action."""
        citations_data: list[dict[str, Any]] = []
        policy_decision_dict: dict[str, Any] | None = None
        policy_version: str | None = None

        if policy_decision:
            policy_decision_dict = policy_decision.model_dump()
            policy_version = policy_decision.policy_version
            citations_data = [c.model_dump() for c in policy_decision.citations]

        # Extract target entity if not passed explicitly
        if not target_entity and action.parameters:
            target_entity = (
                str(action.parameters.get("order_id"))
                or str(action.parameters.get("payment_id"))
                or str(action.parameters.get("shipment_id"))
                or str(action.parameters.get("customer_id"))
            )

        record = ApprovalRecord(
            workflow_id=workflow_id,
            action_name=action.action_name,
            target_entity=target_entity,
            parameters=action.parameters,
            risk_level=risk_level,
            reason=reason,
            policy_decision=policy_decision_dict,
            policy_version=policy_version,
            citations=citations_data,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(timezone.utc),
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Created ApprovalRecord %s for workflow %s (action: %s, risk: %s)",
            record.id,
            workflow_id,
            action.action_name,
            risk_level,
        )
        return record

    def get_approval(self, approval_id: UUID) -> ApprovalRecord | None:
        """Retrieve an approval record by UUID."""
        stmt = select(ApprovalRecord).where(ApprovalRecord.id == approval_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_approval_by_workflow(self, workflow_id: str) -> ApprovalRecord | None:
        """Retrieve the latest approval record associated with a workflow_id."""
        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.workflow_id == workflow_id)
            .order_by(ApprovalRecord.requested_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def list_approvals(
        self,
        status: ApprovalStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ApprovalRecord]:
        """List approval records with optional status filtering."""
        stmt = select(ApprovalRecord).order_by(ApprovalRecord.requested_at.desc())
        if status is not None:
            stmt = stmt.where(ApprovalRecord.status == status)
        stmt = stmt.limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def approve(
        self,
        approval_id: UUID,
        approver_identity: str,
    ) -> tuple[ApprovalRecord, bool, str]:
        """Approve a pending approval request.

        Returns:
            tuple: (record, success, message)
        """
        record = self.get_approval(approval_id)
        if not record:
            return ApprovalRecord(), False, f"Approval request {approval_id} not found."

        if record.status != ApprovalStatus.PENDING:
            return (
                record,
                False,
                f"Cannot approve request in '{record.status.value}' state. Only PENDING requests can be approved.",
            )

        now = datetime.now(timezone.utc)
        record.status = ApprovalStatus.APPROVED
        record.decided_at = now
        record.approver_identity = approver_identity

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Approved request %s by %s for workflow %s",
            approval_id,
            approver_identity,
            record.workflow_id,
        )
        return record, True, "Approval granted successfully."

    def reject(
        self,
        approval_id: UUID,
        approver_identity: str,
        rejection_reason: str,
    ) -> tuple[ApprovalRecord, bool, str]:
        """Reject a pending approval request.

        Returns:
            tuple: (record, success, message)
        """
        record = self.get_approval(approval_id)
        if not record:
            return ApprovalRecord(), False, f"Approval request {approval_id} not found."

        if record.status != ApprovalStatus.PENDING:
            return (
                record,
                False,
                f"Cannot reject request in '{record.status.value}' state. Only PENDING requests can be rejected.",
            )

        if not rejection_reason or not rejection_reason.strip():
            return record, False, "Rejection reason must be provided."

        now = datetime.now(timezone.utc)
        record.status = ApprovalStatus.REJECTED
        record.decided_at = now
        record.approver_identity = approver_identity
        record.rejection_reason = rejection_reason.strip()

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Rejected request %s by %s for workflow %s (Reason: %s)",
            approval_id,
            approver_identity,
            record.workflow_id,
            rejection_reason,
        )
        return record, True, "Approval rejected successfully."
