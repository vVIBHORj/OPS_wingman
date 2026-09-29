"""Schemas for Human Approval Queue (Phase 3 - Deliverable D-12)."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from database.models.enums import ApprovalStatus


class ApprovalResponse(BaseModel):
    """Standardized response schema representing a human approval record."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    approval_id: str
    run_id: str
    workflow_id: str
    action: str
    action_name: Optional[str] = None
    risk_level: str
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[str] = None
    target_entity: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    policy_decision: Optional[Dict[str, Any]] = Field(default_factory=dict)
    status: ApprovalStatus
    requested_at: datetime
    decided_at: Optional[datetime] = None
    approver_id: Optional[str] = None
    approver_identity: Optional[str] = None
    rejection_reason: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __init__(self, **data: Any) -> None:
        if "action" in data and not data.get("action_name"):
            data["action_name"] = data["action"]
        elif "action_name" in data and not data.get("action"):
            data["action"] = data["action_name"]
        if "target_entity_id" in data and not data.get("target_entity"):
            data["target_entity"] = data["target_entity_id"]
        elif "target_entity" in data and not data.get("target_entity_id"):
            data["target_entity_id"] = data["target_entity"]
        if "approver_id" in data and not data.get("approver_identity"):
            data["approver_identity"] = data["approver_id"]
        elif "approver_identity" in data and not data.get("approver_id"):
            data["approver_id"] = data["approver_identity"]
        if data.get("policy_decision") is None:
            data["policy_decision"] = {}
        super().__init__(**data)


class ApprovalActionRequest(BaseModel):
    """Payload to grant approval for a pending operational action."""
    approver_id: Optional[str] = Field(default="ops_supervisor_1", description="Identifier of approving manager")
    approver_identity: Optional[str] = Field(default=None, description="Alias for approver_id")
    comment: Optional[str] = Field(default=None, description="Optional approval remark or reference")

    def __init__(self, **data: Any) -> None:
        if "approver_identity" in data and ("approver_id" not in data or data["approver_id"] == "ops_supervisor_1"):
            data["approver_id"] = data["approver_identity"]
        elif "approver_id" in data and "approver_identity" not in data:
            data["approver_identity"] = data["approver_id"]
        super().__init__(**data)


class RejectionActionRequest(BaseModel):
    """Payload to deny approval for a pending operational action."""
    reason: Optional[str] = Field(default=None, description="Mandatory justification for denying approval")
    rejection_reason: Optional[str] = Field(default=None, description="Alias for reason")
    approver_id: Optional[str] = Field(default="ops_supervisor_1", description="Identifier of rejecting manager")
    approver_identity: Optional[str] = Field(default=None, description="Alias for approver_id")

    def __init__(self, **data: Any) -> None:
        if "rejection_reason" in data and not data.get("reason"):
            data["reason"] = data["rejection_reason"]
        elif "reason" in data and not data.get("rejection_reason"):
            data["rejection_reason"] = data["reason"]
        if "approver_identity" in data and ("approver_id" not in data or data["approver_id"] == "ops_supervisor_1"):
            data["approver_id"] = data["approver_identity"]
        elif "approver_id" in data and "approver_identity" not in data:
            data["approver_identity"] = data["approver_id"]
        super().__init__(**data)
