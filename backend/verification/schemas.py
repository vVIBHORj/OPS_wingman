"""Schemas for Post-Action State Verification Subsystem (Phase 4 - Deliverable D-14)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class VerificationStatus(str, Enum):
    """Categorical status of a post-action state verification check."""
    VERIFIED = "VERIFIED"
    DIVERGENT = "DIVERGENT"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


class VerificationRequest(BaseModel):
    """Specification of an intended state change to verify against persistent business truth."""
    model_config = ConfigDict(from_attributes=True)

    entity_type: str = Field(description="Target entity type, e.g. 'order', 'payment', 'ticket', 'shipment', 'event'")
    entity_id: str = Field(description="UUID or human-readable identifier of the target entity")
    target_state: str = Field(description="Expected target status or state descriptor")
    operation: Optional[str] = Field(default=None, description="Action or tool name that caused the state change")
    expected_attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional field values expected on the entity")


class VerificationResult(BaseModel):
    """Structured evidence of post-action state verification."""
    model_config = ConfigDict(from_attributes=True)

    verified: bool = Field(description="True if actual persisted state matches expected target state exactly")
    status: VerificationStatus = Field(description="Detailed verification outcome status")
    entity_type: str = Field(description="Target entity type")
    entity_id: str = Field(description="Target entity identifier")
    target_state: str = Field(description="Expected target state or status value")
    actual_state: Optional[str] = Field(default=None, description="Actual state observed in the database")
    discrepancies: List[str] = Field(default_factory=list, description="List of specific attribute mismatches or divergence details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp when verification occurred")
    operation: Optional[str] = Field(default=None, description="Operation being verified")
    details: Dict[str, Any] = Field(default_factory=dict, description="Observed entity attributes or audit context")
    error: Optional[str] = Field(default=None, description="Error message if an unexpected failure prevented state inspection")
