"""
Policy Engine Schemas for Deterministic Business Rule Governance (Phase 3 - Deliverable D-11).
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from backend.rag.schemas import KnowledgeCitation


class PolicyEvaluationRequest(BaseModel):
    """Input payload containing structured action and verified domain facts."""
    action: str = Field(..., description="Proposed action name, e.g. 'cancel_order', 'request_refund'")
    facts: Dict[str, Any] = Field(default_factory=dict, description="Verified domain state facts")
    citations: Optional[List[KnowledgeCitation]] = Field(default=None, description="Attached RAG knowledge citations")


class PolicyEvaluationResult(BaseModel):
    """Standardized policy evaluation outcome governing tool execution and approval gating."""
    allowed: bool = Field(..., description="Whether action complies with business policies")
    requires_approval: bool = Field(..., description="Whether action requires human supervisor approval")
    decision: str = Field(..., description="Human-readable explanation of policy decision")
    policy_id: str = Field(..., description="Identifier of governing policy, e.g. 'POL-CAN-001'")
    policy_version: str = Field(default="1.0.0", description="Version of governing policy")
    matched_rules: List[str] = Field(default_factory=list, description="List of specific rule IDs triggered")
    relevant_facts: Dict[str, Any] = Field(default_factory=dict, description="Snapshot of domain facts evaluated")
    citations: List[KnowledgeCitation] = Field(default_factory=list, description="Grounding knowledge citations")
