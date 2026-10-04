"""
Pydantic Schemas for Operational Telemetry and Workflow Provenance API (Phase 4 - Deliverable D-16).
Provides strongly typed read-only models for inspecting workflow execution, risk provenance,
resilience metrics, post-action verification, and operational health summaries.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ResilienceTelemetry(BaseModel):
    """Normalized operational telemetry for tool execution resilience (retries, timeouts, idempotency)."""
    model_config = ConfigDict(from_attributes=True)

    tool_name: Optional[str] = Field(default=None, description="Name of executed tool or operation")
    idempotency_key: Optional[str] = Field(default=None, description="Safe idempotency key reference")
    scope: Optional[str] = Field(default=None, description="Idempotency scope partition")
    is_cached: bool = Field(default=False, description="True if result was served from idempotency cache")
    attempts: int = Field(default=1, description="Number of execution attempts performed")
    attempt_count: int = Field(default=1, description="Alias for attempt count")
    retry_delays: List[float] = Field(default_factory=list, description="Observed backoff delays between retries in seconds")
    elapsed_seconds: Optional[float] = Field(default=None, description="Total wall-clock duration of the tool execution")
    final_status: Optional[str] = Field(default=None, description="Terminal state, e.g. COMPLETED, FAILED, CACHED, PROCESSING")
    timed_out: bool = Field(default=False, description="True if execution exceeded configured timeout budget")
    retryable: bool = Field(default=False, description="True if operation was classified as retryable")
    conflict: bool = Field(default=False, description="True if an idempotency hash mismatch or in-flight conflict was encountered")
    in_flight: bool = Field(default=False, description="True if operation was concurrently processing")
    error_type: Optional[str] = Field(default=None, description="Classification of exception class if failed")
    error_message: Optional[str] = Field(default=None, description="Sanitized failure explanation if failed")


class RiskTelemetry(BaseModel):
    """Normalized operational ML risk and anomaly detection telemetry."""
    model_config = ConfigDict(from_attributes=True)

    model_name: str = Field(default="OperationalRiskModel", description="Name of operational scoring model")
    model_version: str = Field(default="v1.0.0", description="Semantic model version")
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Calibrated operational risk score [0.0, 1.0]")
    risk_band: Optional[str] = Field(default=None, description="Categorical risk band (LOW, MEDIUM, HIGH)")
    is_high_risk: bool = Field(default=False, description="True if risk_score >= 0.70 or risk_band is HIGH")
    anomaly_detected: bool = Field(default=False, description="True if anomalous pattern flags were triggered")
    anomaly_score: Optional[float] = Field(default=None, description="Anomaly severity score")
    anomaly_reasons: List[str] = Field(default_factory=list, description="Triggered anomaly reason tags")
    top_risk_factors: List[str] = Field(default_factory=list, description="Top human-readable risk drivers")
    feature_contributions: List[Dict[str, Any]] = Field(default_factory=list, description="Explainable feature contribution breakdown")
    features: Optional[Dict[str, Any]] = Field(default=None, description="Observed feature inputs")
    evaluated_at: Optional[datetime] = Field(default=None, description="Timestamp of risk assessment")


class VerificationTelemetry(BaseModel):
    """Normalized post-action state verification outcome."""
    model_config = ConfigDict(from_attributes=True)

    entity_type: Optional[str] = Field(default=None, description="Verified entity type, e.g. order, payment, shipment")
    entity_id: Optional[str] = Field(default=None, description="Identifier of verified entity")
    target_state: Optional[str] = Field(default=None, description="Expected state or status")
    actual_state: Optional[str] = Field(default=None, description="Observed actual state in database")
    status: Optional[str] = Field(default=None, description="Verification outcome: VERIFIED, DIVERGENT, NOT_FOUND, ERROR")
    verified: bool = Field(default=False, description="True if actual state matches expected target state")
    discrepancies: List[str] = Field(default_factory=list, description="Specific attribute mismatches if divergent")
    operation: Optional[str] = Field(default=None, description="Tool action that triggered the state transition")
    error: Optional[str] = Field(default=None, description="Inspection error if check failed")
    timestamp: Optional[datetime] = Field(default=None, description="Timestamp when verification occurred")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional observed attributes or audit metadata")


class PolicyTelemetry(BaseModel):
    """Normalized deterministic policy governance decision."""
    model_config = ConfigDict(from_attributes=True)

    policy_id: Optional[str] = Field(default=None, description="Policy identifier, e.g. POL-CAN-001")
    policy_version: Optional[str] = Field(default="1.0.0", description="Policy version")
    decision: Optional[str] = Field(default=None, description="Policy engine decision rationale")
    allowed: bool = Field(default=True, description="Whether action complies with deterministic policy")
    requires_approval: bool = Field(default=False, description="Whether human supervisor approval is required")
    risk_level: Optional[str] = Field(default=None, description="Assigned policy risk level")
    matched_rules: List[str] = Field(default_factory=list, description="Rule IDs triggered")
    relevant_facts: Dict[str, Any] = Field(default_factory=dict, description="Ground-truth facts evaluated")


class WorkflowStepTelemetry(BaseModel):
    """Ordered execution step telemetry with input/output payloads and error classification."""
    model_config = ConfigDict(from_attributes=True)

    step_id: str = Field(description="Step identifier")
    step_name: str = Field(description="Execution phase or node name")
    state: str = Field(description="Workflow state at this step")
    tool_name: Optional[str] = Field(default=None, description="Tool invoked during this step")
    input_payload: Optional[Dict[str, Any]] = Field(default=None, description="Sanitized input arguments")
    output_payload: Optional[Dict[str, Any]] = Field(default=None, description="Sanitized output data")
    error: Optional[str] = Field(default=None, description="Error message if step failed")
    timestamp: datetime = Field(description="Step execution timestamp")


class WorkflowRunDetailResponse(BaseModel):
    """Comprehensive read-only workflow execution inspection response."""
    model_config = ConfigDict(from_attributes=True)

    workflow_id: str = Field(description="Parent workflow ID")
    run_id: str = Field(description="Execution run ID")
    workflow_type: str = Field(description="Workflow category")
    state: str = Field(description="Current lifecycle state")
    current_step: Optional[str] = Field(default=None, description="Most recent executed step name")
    customer_id: Optional[str] = Field(default=None, description="Associated customer ID")
    order_id: Optional[str] = Field(default=None, description="Associated order ID")
    input_text: str = Field(description="Original user/system input text")
    intent: Optional[str] = Field(default=None, description="Inferred operational intent")
    final_response: Optional[str] = Field(default=None, description="Synthesized final response")
    error: Optional[str] = Field(default=None, description="Top-level error message if failed")
    steps: List[WorkflowStepTelemetry] = Field(default_factory=list, description="Ordered step records")
    verification_results: List[VerificationTelemetry] = Field(default_factory=list, description="Post-action state verification checks")
    risk_assessment: Optional[RiskTelemetry] = Field(default=None, description="ML risk and anomaly evaluation")
    resilience_records: List[ResilienceTelemetry] = Field(default_factory=list, description="Tool resilience and idempotency records")
    policy_decisions: List[PolicyTelemetry] = Field(default_factory=list, description="Policy decisions evaluated")
    created_at: datetime = Field(description="Run creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class WorkflowRunTelemetry(BaseModel):
    """Normalized operational telemetry view summarizing workflow execution, resilience, risk, and verification."""
    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(description="Execution run ID")
    workflow_id: str = Field(description="Parent workflow ID")
    workflow_type: str = Field(description="Workflow classification")
    state: str = Field(description="Current workflow execution state")
    status: str = Field(description="Operational status descriptor (alias for state)")
    current_step: Optional[str] = Field(default=None, description="Most recent executed step name")
    executed_tools: List[str] = Field(default_factory=list, description="Distinct tools executed during this run")
    policy_decisions: List[PolicyTelemetry] = Field(default_factory=list, description="Evaluated policy decisions")
    risk_telemetry: Optional[RiskTelemetry] = Field(default=None, description="ML risk score and anomaly flags")
    verification_results: List[VerificationTelemetry] = Field(default_factory=list, description="State verification outcomes")
    resilience_telemetry: List[ResilienceTelemetry] = Field(default_factory=list, description="Resilience records")
    retry_counts: Dict[str, int] = Field(default_factory=dict, description="Retry counts keyed by tool name")
    total_retries: int = Field(default=0, description="Total number of retries executed across all tools")
    timeout_occurred: bool = Field(default=False, description="True if any tool encountered a timeout")
    retry_exhausted: bool = Field(default=False, description="True if retry budget was exceeded")
    idempotency_outcomes: Dict[str, Any] = Field(default_factory=dict, description="Summary of idempotency cache hits and conflicts")
    failure_information: Optional[Dict[str, Any]] = Field(default=None, description="Detailed failure taxonomy if workflow or tools failed")
    is_high_risk: bool = Field(default=False, description="True if ML risk was assessed as HIGH")
    anomaly_detected: bool = Field(default=False, description="True if operational anomalies were detected")
    anomaly_reasons: List[str] = Field(default_factory=list, description="Triggered anomaly flags")
    model_version: Optional[str] = Field(default=None, description="ML model version used")
    final_response: Optional[str] = Field(default=None, description="Synthesized response")
    error: Optional[str] = Field(default=None, description="Workflow error message")
    created_at: datetime = Field(description="Run creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class OperationalSummary(BaseModel):
    """Aggregate operational metrics derived from checkpoint store."""
    model_config = ConfigDict(from_attributes=True)

    total_runs: int = Field(default=0, description="Total workflow runs recorded")
    completed: int = Field(default=0, description="Runs in COMPLETED state")
    failed: int = Field(default=0, description="Runs in FAILED state")
    waiting_for_approval: int = Field(default=0, description="Runs currently awaiting human approval")
    cancelled: int = Field(default=0, description="Runs in CANCELLED state")
    running: int = Field(default=0, description="Runs currently in progress")
    verification_failures: int = Field(default=0, description="Runs that experienced post-action verification failure or divergence")
    retry_failures: int = Field(default=0, description="Runs that encountered retry exhaustion")
    timeout_failures: int = Field(default=0, description="Runs that encountered tool execution timeouts")
    high_risk_assessments: int = Field(default=0, description="Runs assessed with high operational risk")
    anomalous_assessments: int = Field(default=0, description="Runs with detected operational anomalies")
    data_source: str = Field(default="in_memory_and_disk_checkpoints", description="Source of truth for operational aggregate")
    notes: str = Field(
        default="Aggregate metrics derived from checkpoint store runs without requiring database migrations.",
        description="Architectural boundary notes",
    )
