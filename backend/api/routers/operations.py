"""
Operational Dashboard and Telemetry API Router (Phase 4 - Deliverable D-16).
Provides read-only operational telemetry, workflow provenance, step traces, and system health aggregates.
"""

import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.api.operations_schemas import (
    OperationalSummary,
    PolicyTelemetry,
    ResilienceTelemetry,
    RiskTelemetry,
    VerificationTelemetry,
    WorkflowRunDetailResponse,
    WorkflowRunTelemetry,
    WorkflowStepTelemetry,
)
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import WorkflowRunRecord, WorkflowState

router = APIRouter(prefix="/operations", tags=["Operations & Telemetry"])

# Validation pattern: allows alphanumeric, hyphens, and underscores, length 1-128.
# Strictly rejects path-traversal (..), slashes, whitespace, and injection characters.
RUN_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")

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
)


def _validate_run_id(run_id: str) -> None:
    """Validates that a run_id adheres to safe alphanumeric format."""
    if not run_id or not RUN_ID_REGEX.match(run_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed run_id: '{run_id}'. Run identifiers must be 1-128 characters containing only letters, numbers, hyphens, or underscores.",
        )


def _sanitize_value(value: Any) -> Any:
    """Recursively redacts values for sensitive keys in payloads and dictionaries."""
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in value.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_value(v)
        return sanitized
    elif isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _normalize_resilience(records: List[Dict[str, Any]]) -> List[ResilienceTelemetry]:
    """Normalizes raw resilience records into strongly typed ResilienceTelemetry models."""
    normalized: List[ResilienceTelemetry] = []
    for r in records:
        attempts = int(r.get("attempts", r.get("attempt_count", 1)) or 1)
        raw_delays = r.get("retry_delays") or []
        delays = [float(d) for d in raw_delays if isinstance(d, (int, float))]
        elapsed = r.get("elapsed_seconds")
        if elapsed is not None:
            try:
                elapsed = float(elapsed)
            except (ValueError, TypeError):
                elapsed = None

        timed_out = bool(
            r.get("timed_out") is True
            or r.get("timeout_occurred") is True
            or "Timeout" in str(r.get("error_type", ""))
            or "Timeout" in str(r.get("error_message", ""))
        )

        retryable = bool(r.get("retryable", False))
        conflict = bool(r.get("conflict", False))
        in_flight = bool(r.get("in_flight", False))
        is_cached = bool(r.get("is_cached", False) or r.get("final_status") == "CACHED")

        normalized.append(
            ResilienceTelemetry(
                tool_name=r.get("tool_name"),
                idempotency_key=r.get("idempotency_key"),
                scope=r.get("scope"),
                is_cached=is_cached,
                attempts=attempts,
                attempt_count=attempts,
                retry_delays=delays,
                elapsed_seconds=elapsed,
                final_status=r.get("final_status"),
                timed_out=timed_out,
                retryable=retryable,
                conflict=conflict,
                in_flight=in_flight,
                error_type=r.get("error_type"),
                error_message=r.get("error_message"),
            )
        )
    return normalized


def _normalize_risk(risk_data: Optional[Dict[str, Any]]) -> Optional[RiskTelemetry]:
    """Normalizes raw risk assessment dictionaries into RiskTelemetry."""
    if not risk_data:
        return None

    score = risk_data.get("risk_score")
    if score is not None:
        try:
            score = float(score)
        except (ValueError, TypeError):
            score = None

    risk_band = risk_data.get("risk_band")
    if risk_band is not None:
        risk_band = str(risk_band).upper()

    is_high_risk = bool(
        risk_data.get("is_high_risk", False)
        or (score is not None and score >= 0.70)
        or risk_band == "HIGH"
    )

    anomaly_dict = risk_data.get("anomaly") or {}
    anomaly_flags = list(anomaly_dict.get("anomaly_flags") or [])
    anomaly_score = anomaly_dict.get("anomaly_score")
    if anomaly_score is not None:
        try:
            anomaly_score = float(anomaly_score)
        except (ValueError, TypeError):
            anomaly_score = None

    anomaly_detected = bool(
        anomaly_dict.get("is_anomaly", False) or len(anomaly_flags) > 0
    )

    return RiskTelemetry(
        model_name=str(risk_data.get("model_name", "OperationalRiskModel")),
        model_version=str(risk_data.get("model_version", "v1.0.0")),
        risk_score=score,
        risk_band=risk_band,
        is_high_risk=is_high_risk,
        anomaly_detected=anomaly_detected,
        anomaly_score=anomaly_score,
        anomaly_reasons=anomaly_flags,
        top_risk_factors=list(risk_data.get("top_risk_factors") or []),
        feature_contributions=list(risk_data.get("contributions") or []),
        features=_sanitize_value(risk_data.get("features")),
        evaluated_at=risk_data.get("evaluated_at"),
    )


def _normalize_verification(records: List[Dict[str, Any]]) -> List[VerificationTelemetry]:
    """Normalizes post-action verification evidence into VerificationTelemetry models."""
    normalized: List[VerificationTelemetry] = []
    for vr in records:
        entity_id_val = vr.get("entity_id")
        normalized.append(
            VerificationTelemetry(
                entity_type=vr.get("entity_type"),
                entity_id=str(entity_id_val) if entity_id_val is not None else None,
                target_state=vr.get("target_state"),
                actual_state=vr.get("actual_state"),
                status=vr.get("status"),
                verified=bool(vr.get("verified", False)),
                discrepancies=list(vr.get("discrepancies") or []),
                operation=vr.get("operation"),
                error=vr.get("error"),
                timestamp=vr.get("timestamp"),
                details=_sanitize_value(vr.get("details") or {}),
            )
        )
    return normalized


def _normalize_policy(records: List[Dict[str, Any]]) -> List[PolicyTelemetry]:
    """Normalizes policy evaluation results into PolicyTelemetry models."""
    normalized: List[PolicyTelemetry] = []
    for pd in records:
        normalized.append(
            PolicyTelemetry(
                policy_id=pd.get("policy_id"),
                policy_version=str(pd.get("policy_version", "1.0.0")),
                decision=pd.get("decision"),
                allowed=bool(pd.get("allowed", True)),
                requires_approval=bool(pd.get("requires_approval", False)),
                risk_level=pd.get("risk_level"),
                matched_rules=list(pd.get("matched_rules") or []),
                relevant_facts=_sanitize_value(pd.get("relevant_facts") or {}),
            )
        )
    return normalized


def _build_step_telemetry(run: WorkflowRunRecord) -> List[WorkflowStepTelemetry]:
    """Builds ordered workflow step telemetry records with sanitized metadata."""
    return [
        WorkflowStepTelemetry(
            step_id=step.step_id,
            step_name=step.step_name,
            state=step.state.value if hasattr(step.state, "value") else str(step.state),
            tool_name=step.tool_name,
            input_payload=_sanitize_value(step.input_payload),
            output_payload=_sanitize_value(step.output_payload),
            error=step.error,
            timestamp=step.timestamp,
        )
        for step in run.steps
    ]


# ==============================================================================
# Read-Only Operational Endpoints
# ==============================================================================

@router.get("/summary", response_model=OperationalSummary, status_code=status.HTTP_200_OK)
def get_operational_summary(
    limit: int = Query(default=500, ge=1, le=5000, description="Checkpoint analysis window limit"),
) -> OperationalSummary:
    """
    Returns aggregate operational metrics across recorded workflow runs in the checkpoint store.
    Read-only inspection endpoint.
    """
    runs = checkpoint_store.list_runs(limit=limit)

    total_runs = len(runs)
    completed = 0
    failed = 0
    waiting_for_approval = 0
    cancelled = 0
    running = 0
    verification_failures = 0
    retry_failures = 0
    timeout_failures = 0
    high_risk_assessments = 0
    anomalous_assessments = 0

    for run in runs:
        state_str = run.state.value if hasattr(run.state, "value") else str(run.state)

        if state_str == WorkflowState.COMPLETED.value:
            completed += 1
        elif state_str == WorkflowState.FAILED.value:
            failed += 1
        elif state_str == WorkflowState.WAITING_FOR_APPROVAL.value:
            waiting_for_approval += 1
        elif state_str == WorkflowState.CANCELLED.value:
            cancelled += 1
        else:
            running += 1

        # Check verification failures
        if any(
            not vr.get("verified", False)
            or str(vr.get("status")).upper() in ("DIVERGENT", "NOT_FOUND", "ERROR")
            or vr.get("error") is not None
            for vr in run.verification_results
        ):
            verification_failures += 1

        # Check resilience retry exhaustion failures
        if any(
            r.get("error_type") == "MaxRetriesExceededError"
            or "MaxRetriesExceededError" in str(r.get("error_message", ""))
            or "Retry exhaustion" in str(r.get("error_message", ""))
            for r in run.resilience_records
        ):
            retry_failures += 1

        # Check timeout failures
        if any(
            r.get("timed_out") is True
            or r.get("timeout_occurred") is True
            or "Timeout" in str(r.get("error_type", ""))
            or "Timeout" in str(r.get("error_message", ""))
            for r in run.resilience_records
        ):
            timeout_failures += 1

        # Check ML risk & anomalies
        if run.risk_assessment:
            score = run.risk_assessment.get("risk_score")
            band = str(run.risk_assessment.get("risk_band", "")).upper()
            if (score is not None and float(score) >= 0.70) or band == "HIGH":
                high_risk_assessments += 1

            anomaly = run.risk_assessment.get("anomaly") or {}
            flags = anomaly.get("anomaly_flags") or []
            if bool(anomaly.get("is_anomaly", False)) or len(flags) > 0:
                anomalous_assessments += 1

    return OperationalSummary(
        total_runs=total_runs,
        completed=completed,
        failed=failed,
        waiting_for_approval=waiting_for_approval,
        cancelled=cancelled,
        running=running,
        verification_failures=verification_failures,
        retry_failures=retry_failures,
        timeout_failures=timeout_failures,
        high_risk_assessments=high_risk_assessments,
        anomalous_assessments=anomalous_assessments,
        data_source="in_memory_and_disk_checkpoints",
        notes="Aggregate metrics derived from checkpoint store runs without requiring database migrations.",
    )


@router.get("/runs/{run_id}", response_model=WorkflowRunDetailResponse, status_code=status.HTTP_200_OK)
def get_workflow_run_detail(run_id: str) -> WorkflowRunDetailResponse:
    """
    Returns full workflow run details including verification results, risk assessment,
    resilience records, policy decisions, and current execution step.
    Strictly read-only.
    """
    _validate_run_id(run_id)

    run = checkpoint_store.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{run_id}' not found.",
        )

    current_step = run.steps[-1].step_name if run.steps else None
    state_str = run.state.value if hasattr(run.state, "value") else str(run.state)

    return WorkflowRunDetailResponse(
        workflow_id=run.workflow_id,
        run_id=run.run_id,
        workflow_type=run.workflow_type,
        state=state_str,
        current_step=current_step,
        customer_id=run.customer_id,
        order_id=run.order_id,
        input_text=run.input_text,
        intent=run.intent,
        final_response=run.final_response,
        error=run.error,
        steps=_build_step_telemetry(run),
        verification_results=_normalize_verification(run.verification_results),
        risk_assessment=_normalize_risk(run.risk_assessment),
        resilience_records=_normalize_resilience(run.resilience_records),
        policy_decisions=_normalize_policy(run.policy_decisions),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("/runs/{run_id}/steps", response_model=List[WorkflowStepTelemetry], status_code=status.HTTP_200_OK)
def get_workflow_run_steps(run_id: str) -> List[WorkflowStepTelemetry]:
    """
    Returns ordered workflow/checkpoint steps with execution states, timestamps,
    sanitized payloads, and errors.
    Strictly read-only.
    """
    _validate_run_id(run_id)

    run = checkpoint_store.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{run_id}' not found.",
        )

    return _build_step_telemetry(run)


@router.get("/runs/{run_id}/telemetry", response_model=WorkflowRunTelemetry, status_code=status.HTTP_200_OK)
def get_workflow_run_telemetry(run_id: str) -> WorkflowRunTelemetry:
    """
    Returns normalized operational telemetry summarizing executed tools, policy governance,
    ML risk scoring, verification results, retry counts, timeout state, idempotency outcomes,
    and failure information.
    Strictly read-only.
    """
    _validate_run_id(run_id)

    run = checkpoint_store.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{run_id}' not found.",
        )

    current_step = run.steps[-1].step_name if run.steps else None
    state_str = run.state.value if hasattr(run.state, "value") else str(run.state)

    # Executed tools collection
    executed_tools: List[str] = []
    for step in run.steps:
        if step.tool_name and step.tool_name not in executed_tools:
            executed_tools.append(step.tool_name)
    for r in run.resilience_records:
        tool = r.get("tool_name")
        if tool and tool not in executed_tools:
            executed_tools.append(tool)

    # Retry counts and total retries
    retry_counts: Dict[str, int] = {}
    for r in run.resilience_records:
        tool = r.get("tool_name", "unknown")
        attempts = int(r.get("attempts", r.get("attempt_count", 1)) or 1)
        retries = max(0, attempts - 1)
        retry_counts[tool] = retry_counts.get(tool, 0) + retries
    total_retries = sum(retry_counts.values())

    # Timeout & retry exhaustion
    timeout_occurred = any(
        r.get("timed_out") is True
        or r.get("timeout_occurred") is True
        or "Timeout" in str(r.get("error_type", ""))
        or "Timeout" in str(r.get("error_message", ""))
        for r in run.resilience_records
    )
    retry_exhausted = any(
        r.get("error_type") == "MaxRetriesExceededError"
        or "MaxRetriesExceededError" in str(r.get("error_message", ""))
        or "Retry exhaustion" in str(r.get("error_message", ""))
        for r in run.resilience_records
    )

    # Idempotency outcomes
    idempotency_outcomes: Dict[str, Any] = {
        "total_records": len(run.resilience_records),
        "cached_count": sum(
            1 for r in run.resilience_records if r.get("is_cached") is True or r.get("final_status") == "CACHED"
        ),
        "conflict_count": sum(1 for r in run.resilience_records if r.get("conflict") is True),
        "completed_count": sum(1 for r in run.resilience_records if r.get("final_status") == "COMPLETED"),
        "failed_count": sum(1 for r in run.resilience_records if r.get("final_status") == "FAILED"),
        "keys": [r.get("idempotency_key") for r in run.resilience_records if r.get("idempotency_key")],
    }

    # Normalized subsystems
    resilience_telemetry = _normalize_resilience(run.resilience_records)
    risk_telemetry = _normalize_risk(run.risk_assessment)
    verification_results = _normalize_verification(run.verification_results)
    policy_decisions = _normalize_policy(run.policy_decisions)

    # ML flags
    is_high_risk = risk_telemetry.is_high_risk if risk_telemetry else False
    anomaly_detected = risk_telemetry.anomaly_detected if risk_telemetry else False
    anomaly_reasons = risk_telemetry.anomaly_reasons if risk_telemetry else []
    model_version = risk_telemetry.model_version if risk_telemetry else None

    # Failure information
    failure_information: Optional[Dict[str, Any]] = None
    if state_str == WorkflowState.FAILED.value or run.error is not None or retry_exhausted or timeout_occurred:
        failed_steps = [
            s.step_name
            for s in run.steps
            if (s.state.value if hasattr(s.state, "value") else str(s.state)) == WorkflowState.FAILED.value
            or s.error is not None
        ]
        resilience_failures = [
            {
                "tool_name": r.get("tool_name"),
                "error_type": r.get("error_type"),
                "error_message": r.get("error_message"),
                "timed_out": r.get("timed_out", False),
                "retryable": r.get("retryable", False),
            }
            for r in run.resilience_records
            if r.get("final_status") == "FAILED" or r.get("error_message")
        ]
        failure_information = {
            "workflow_error": run.error,
            "failed_steps": failed_steps,
            "resilience_failures": resilience_failures,
            "timeout_occurred": timeout_occurred,
            "retry_exhausted": retry_exhausted,
        }

    return WorkflowRunTelemetry(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        workflow_type=run.workflow_type,
        state=state_str,
        status=state_str,
        current_step=current_step,
        executed_tools=executed_tools,
        policy_decisions=policy_decisions,
        risk_telemetry=risk_telemetry,
        verification_results=verification_results,
        resilience_telemetry=resilience_telemetry,
        retry_counts=retry_counts,
        total_retries=total_retries,
        timeout_occurred=timeout_occurred,
        retry_exhausted=retry_exhausted,
        idempotency_outcomes=idempotency_outcomes,
        failure_information=failure_information,
        is_high_risk=is_high_risk,
        anomaly_detected=anomaly_detected,
        anomaly_reasons=anomaly_reasons,
        model_version=model_version,
        final_response=run.final_response,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
