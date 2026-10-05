"""
Pydantic Schemas and Sanitization for Audit & Observability Subsystem (Phase 4/5 - Deliverable D-16).
Defines strongly typed event models, event types, timeline responses, and security redaction.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from database.models.enums import AuditEventType


SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "conn_str",
    "database_url",
    "auth_header",
    "bearer",
)


def sanitize_audit_data(value: Any) -> Any:
    """Recursively redacts sensitive keys and values from dictionaries, lists, and primitives."""
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in value.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_audit_data(v)
        return sanitized
    elif isinstance(value, list):
        return [sanitize_audit_data(item) for item in value]
    return value


class AuditEventBase(BaseModel):
    """Base fields common to audit event input and responses."""
    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(description="Workflow execution run ID for end-to-end correlation")
    event_type: AuditEventType = Field(description="Categorical lifecycle event classification")
    actor: str = Field(default="OpsAgent", description="Source or actor initiating the event")
    workflow_state: Optional[str] = Field(default=None, description="Workflow lifecycle state at event time")
    entity_type: Optional[str] = Field(default=None, description="Associated business entity type, e.g. order, payment")
    entity_id: Optional[str] = Field(default=None, description="Identifier of associated business entity")
    operation: Optional[str] = Field(default=None, description="Operation or action name executed")
    tool_name: Optional[str] = Field(default=None, description="Name of tool invoked, if any")
    tool_arguments: Optional[Dict[str, Any]] = Field(default=None, description="Sanitized arguments passed to tool")
    tool_result_summary: Optional[Dict[str, Any]] = Field(default=None, description="Sanitized result payload summary")
    policy_decision: Optional[Dict[str, Any]] = Field(default=None, description="Evaluated policy rule decisions and rationale")
    risk_assessment_summary: Optional[Dict[str, Any]] = Field(default=None, description="ML risk score, band, and anomalies")
    verification_status: Optional[str] = Field(default=None, description="Post-action state verification outcome")
    approval_status: Optional[str] = Field(default=None, description="Human approval decision or status, if applicable")
    retry_attempt: Optional[int] = Field(default=None, description="Execution attempt counter if retries intervened")
    idempotency_info: Optional[Dict[str, Any]] = Field(default=None, description="Safe idempotency scope, key, and cache hit state")
    success: bool = Field(default=True, description="True if operation/step succeeded without fatal errors")
    error_message: Optional[str] = Field(default=None, description="Sanitized failure explanation, if failed")
    metadata_provenance: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata_provenance", "metadata"),
        serialization_alias="metadata_provenance",
        description="Audit provenance and correlation metadata",
    )


class AuditEventCreate(AuditEventBase):
    """Input payload to record a new audit event."""
    pass


class AuditEventResponse(AuditEventBase):
    """Response representation of a persisted audit event."""
    id: Optional[UUID] = Field(default=None, description="Internal primary key UUID")
    event_id: str = Field(description="Unique audit event identifier")
    timestamp: datetime = Field(description="UTC timestamp when audit event was recorded")


class AuditTimelineResponse(BaseModel):
    """Structured chronological timeline summarizing all audit events for a workflow run."""
    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(description="Workflow run ID")
    total_events: int = Field(default=0, description="Total audit events recorded for this run")
    start_time: Optional[datetime] = Field(default=None, description="Timestamp of first audit event")
    end_time: Optional[datetime] = Field(default=None, description="Timestamp of most recent audit event")
    workflow_state: Optional[str] = Field(default=None, description="Final or current workflow lifecycle state")
    intent: Optional[str] = Field(default=None, description="Inferred operational intent")
    executed_tools: List[str] = Field(default_factory=list, description="List of unique tools executed")
    policy_decisions: List[Dict[str, Any]] = Field(default_factory=list, description="Policy decisions made during run")
    risk_summary: Optional[Dict[str, Any]] = Field(default=None, description="ML risk assessment summary")
    verification_summary: Optional[Dict[str, Any]] = Field(default=None, description="Summary of state verification outcomes")
    resilience_interventions: List[Dict[str, Any]] = Field(default_factory=list, description="Retries and idempotency interventions")
    events: List[AuditEventResponse] = Field(default_factory=list, description="Chronologically ordered audit events")
