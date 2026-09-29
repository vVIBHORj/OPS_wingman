"""Human Approval API Router for OpsWingman Phase 3 (D-12).

Exposes endpoints for querying, approving, and rejecting human-in-the-loop action proposals.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.agents.service import agent_service
from backend.approvals.schemas import (
    ApprovalActionRequest,
    ApprovalResponse,
    RejectionActionRequest,
)
from backend.approvals.service import ApprovalService
from backend.workflows.state import WorkflowState
from database.models.enums import ApprovalStatus
from database.session import get_db

router = APIRouter(prefix="/approvals", tags=["Human Approvals"])


@router.get("", response_model=List[ApprovalResponse])
def list_approvals(
    status_filter: Optional[ApprovalStatus] = Query(default=None, alias="status", description="Filter by approval status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[ApprovalResponse]:
    """List approval requests with optional status filtering (e.g. ?status=PENDING)."""
    service = ApprovalService(db)
    records = service.list_approvals(status=status_filter, limit=limit, offset=offset)
    return [ApprovalResponse.model_validate(r) for r in records]


@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval(
    approval_id: UUID,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Get approval request details by UUID."""
    service = ApprovalService(db)
    record = service.get_approval(approval_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found.",
        )
    return ApprovalResponse.model_validate(record)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
def approve_request(
    approval_id: UUID,
    request: ApprovalActionRequest,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Approve a pending high-risk action request and resume the paused workflow."""
    service = ApprovalService(db)
    identity = request.approver_identity or request.approver_id or "ops_supervisor_1"
    record, ok, msg = service.approve(
        approval_id=approval_id,
        approver_identity=identity,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # Resume workflow if it exists and is waiting for approval
    run_record = agent_service.get_run(record.workflow_id)
    if run_record and run_record.state == WorkflowState.WAITING_FOR_APPROVAL:
        agent_service.resume_workflow(
            run_id=record.workflow_id,
            db=db,
            approved=True,
        )

    # Refresh record
    db.refresh(record)
    return ApprovalResponse.model_validate(record)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
def reject_request(
    approval_id: UUID,
    request: RejectionActionRequest,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    """Reject a pending high-risk action request and terminate/resume workflow without execution."""
    service = ApprovalService(db)
    identity = request.approver_identity or request.approver_id or "ops_supervisor_1"
    reason = request.rejection_reason or request.reason or "Rejected by supervisor"
    record, ok, msg = service.reject(
        approval_id=approval_id,
        approver_identity=identity,
        rejection_reason=reason,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # Resume workflow if it exists and is waiting for approval
    run_record = agent_service.get_run(record.workflow_id)
    if run_record and run_record.state == WorkflowState.WAITING_FOR_APPROVAL:
        agent_service.resume_workflow(
            run_id=record.workflow_id,
            db=db,
            approved=False,
            reason=reason,
        )



    # Refresh record
    db.refresh(record)
    return ApprovalResponse.model_validate(record)
