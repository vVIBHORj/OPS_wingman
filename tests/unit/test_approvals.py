"""Unit tests for Phase 3 D-12 Human Approval System."""

import uuid
import pytest
from sqlalchemy.orm import Session

from backend.approvals.service import ApprovalService
from backend.policies.schemas import PolicyEvaluationResult
from backend.tools.schemas import StructuredAction
from database.models.enums import ApprovalStatus


def test_create_and_get_approval(db_session: Session):
    service = ApprovalService(db_session)
    action = StructuredAction(
        action_name="cancel_order",
        parameters={"order_number": "ORD-20260929-200001"},
        reason="Customer cancellation request",
        risk="HIGH",
    )
    pol_dec = PolicyEvaluationResult(
        allowed=True,
        requires_approval=True,
        decision="Approval required under policy",
        policy_id="POL-CAN-001",
        policy_version="1.0.0",
        matched_rules=["CAN-R01"],
    )

    record = service.create_approval(
        workflow_id="wf-test-001",
        action=action,
        risk_level="HIGH",
        reason="Supervisor review required",
        policy_decision=pol_dec,
        target_entity="ORD-20260929-200001",
    )

    assert record.id is not None
    assert record.workflow_id == "wf-test-001"
    assert record.action_name == "cancel_order"
    assert record.status == ApprovalStatus.PENDING
    assert record.policy_version == "1.0.0"

    fetched = service.get_approval(record.id)
    assert fetched is not None
    assert fetched.id == record.id
    assert fetched.action_name == "cancel_order"


def test_list_pending_approvals(db_session: Session):
    service = ApprovalService(db_session)
    action = StructuredAction(action_name="cancel_order", parameters={"order_id": "123"}, reason="Test")
    service.create_approval(workflow_id="wf-list-1", action=action, risk_level="HIGH", reason="Test 1")
    service.create_approval(workflow_id="wf-list-2", action=action, risk_level="HIGH", reason="Test 2")

    pending = service.list_approvals(status=ApprovalStatus.PENDING)
    assert len(pending) >= 2


def test_approve_approval_flow(db_session: Session):
    service = ApprovalService(db_session)
    action = StructuredAction(action_name="request_refund", parameters={"amount": 5000}, reason="Test")
    record = service.create_approval(workflow_id="wf-approve-1", action=action, risk_level="HIGH", reason="Test")

    # Approve
    updated, ok, msg = service.approve(record.id, approver_identity="ops_manager@opswingman.local")
    assert ok is True
    assert updated.status == ApprovalStatus.APPROVED
    assert updated.approver_identity == "ops_manager@opswingman.local"
    assert updated.decided_at is not None

    # Cannot approve already-approved request twice
    _, ok_dup, msg_dup = service.approve(record.id, approver_identity="ops_manager@opswingman.local")
    assert ok_dup is False
    assert "Cannot approve request in 'APPROVED' state" in msg_dup


def test_reject_approval_flow(db_session: Session):
    service = ApprovalService(db_session)
    action = StructuredAction(action_name="cancel_order", parameters={"order_id": "999"}, reason="Test")
    record = service.create_approval(workflow_id="wf-reject-1", action=action, risk_level="HIGH", reason="Test")

    # Reject without reason fails
    _, ok_empty, _ = service.reject(record.id, approver_identity="ops_manager@opswingman.local", rejection_reason="")
    assert ok_empty is False

    # Reject with reason succeeds
    updated, ok, msg = service.reject(
        record.id,
        approver_identity="ops_manager@opswingman.local",
        rejection_reason="Fraudulent request detected",
    )
    assert ok is True
    assert updated.status == ApprovalStatus.REJECTED
    assert updated.rejection_reason == "Fraudulent request detected"
    assert updated.decided_at is not None

    # Cannot approve rejected request
    _, ok_reapprove, msg_reapp = service.approve(record.id, approver_identity="ops_manager@opswingman.local")
    assert ok_reapprove is False
    assert "Cannot approve request in 'REJECTED' state" in msg_reapp
