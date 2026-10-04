"""
Unit Tests for Operational Telemetry & Provenance API (Phase 4 - Deliverable D-16).
Tests read-only operational endpoints, normalization, ML risk telemetry, resilience telemetry,
post-action verification, operational summary, error handling, and read-only invariants.
"""

import uuid
from datetime import datetime, timezone
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import (
    WorkflowRunRecord,
    WorkflowState,
    WorkflowStepRecord,
)


@pytest.fixture(autouse=True)
def clean_checkpoints() -> Generator[None, None, None]:
    """Ensures a clean checkpoint store before and after every test."""
    checkpoint_store.clear(clear_disk=True)
    yield
    checkpoint_store.clear(clear_disk=True)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient for API endpoints."""
    with TestClient(app) as test_client:
        yield test_client


def test_successful_run_telemetry(client: TestClient):
    """Verifies complete telemetry for a cleanly completed workflow run."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-001",
        workflow_type="order_operations",
        state=WorkflowState.COMPLETED,
        customer_id="cust-123",
        order_id="ord-456",
        input_text="Check order status",
        intent="track_order",
        final_response="Order ord-456 is currently SHIPPED.",
        steps=[
            WorkflowStepRecord(
                step_name="interpret_request",
                state=WorkflowState.RUNNING,
            ),
            WorkflowStepRecord(
                step_name="execute_tools",
                state=WorkflowState.RUNNING,
                tool_name="get_order",
                input_payload={"order_number": "ord-456"},
                output_payload={"status": "SHIPPED"},
            ),
            WorkflowStepRecord(
                step_name="synthesize_response",
                state=WorkflowState.COMPLETED,
            ),
        ],
    )
    checkpoint_store.save(run)

    # 1. GET /operations/runs/{run_id}
    res_detail = client.get(f"/operations/runs/{run_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["run_id"] == run_id
    assert detail["state"] == "COMPLETED"
    assert detail["current_step"] == "synthesize_response"
    assert detail["final_response"] == "Order ord-456 is currently SHIPPED."
    assert len(detail["steps"]) == 3
    assert detail["customer_id"] == "cust-123"

    # 2. GET /operations/runs/{run_id}/steps
    res_steps = client.get(f"/operations/runs/{run_id}/steps")
    assert res_steps.status_code == 200
    steps = res_steps.json()
    assert len(steps) == 3
    assert steps[0]["step_name"] == "interpret_request"
    assert steps[1]["tool_name"] == "get_order"
    assert steps[1]["output_payload"] == {"status": "SHIPPED"}

    # 3. GET /operations/runs/{run_id}/telemetry
    res_telem = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res_telem.status_code == 200
    telem = res_telem.json()
    assert telem["run_id"] == run_id
    assert telem["state"] == "COMPLETED"
    assert telem["status"] == "COMPLETED"
    assert telem["executed_tools"] == ["get_order"]
    assert telem["total_retries"] == 0
    assert telem["timeout_occurred"] is False
    assert telem["retry_exhausted"] is False
    assert telem["failure_information"] is None


def test_successful_run_with_risk_assessment_telemetry(client: TestClient):
    """Verifies that ML risk evaluation provenance is exposed in telemetry."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-risk-01",
        state=WorkflowState.COMPLETED,
        input_text="Cancel order ord-1",
        risk_assessment={
            "model_name": "OperationalRiskModel",
            "model_version": "v1.0.0",
            "risk_score": 0.25,
            "risk_band": "LOW",
            "is_high_risk": False,
            "anomaly": {
                "is_anomaly": False,
                "anomaly_score": 0.05,
                "anomaly_flags": [],
            },
            "top_risk_factors": ["Normal account history"],
            "contributions": [
                {
                    "feature_name": "order_amount",
                    "feature_value": 450.0,
                    "normalized_value": 0.09,
                    "weight": 0.25,
                    "contribution_score": 0.0225,
                    "explanation": "Standard order value",
                }
            ],
        },
    )
    checkpoint_store.save(run)

    res = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res.status_code == 200
    telem = res.json()

    assert telem["model_version"] == "v1.0.0"
    assert telem["is_high_risk"] is False
    assert telem["anomaly_detected"] is False
    assert telem["anomaly_reasons"] == []

    risk = telem["risk_telemetry"]
    assert risk is not None
    assert risk["risk_score"] == 0.25
    assert risk["risk_band"] == "LOW"
    assert len(risk["feature_contributions"]) == 1
    assert risk["feature_contributions"][0]["feature_name"] == "order_amount"


def test_high_risk_and_anomalous_ml_telemetry(client: TestClient):
    """Verifies telemetry exposure for high-risk and anomalous workflow runs."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-anomaly-01",
        state=WorkflowState.COMPLETED,
        input_text="Refund expensive order",
        risk_assessment={
            "model_name": "OperationalRiskModel",
            "model_version": "v1.0.0",
            "risk_score": 0.88,
            "risk_band": "HIGH",
            "is_high_risk": True,
            "anomaly": {
                "is_anomaly": True,
                "anomaly_score": 0.90,
                "anomaly_flags": ["REFUND_BURST", "UNUSUAL_ORDER_AMOUNT"],
            },
            "top_risk_factors": ["High refund frequency", "Outlier order total"],
        },
    )
    checkpoint_store.save(run)

    res = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res.status_code == 200
    telem = res.json()

    assert telem["is_high_risk"] is True
    assert telem["anomaly_detected"] is True
    assert "REFUND_BURST" in telem["anomaly_reasons"]
    assert "UNUSUAL_ORDER_AMOUNT" in telem["anomaly_reasons"]
    assert telem["risk_telemetry"]["risk_score"] == 0.88


def test_successful_run_with_resilience_telemetry(client: TestClient):
    """Verifies that tool retry delays, elapsed time, and idempotency status are captured."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-resilience-01",
        state=WorkflowState.COMPLETED,
        resilience_records=[
            {
                "tool_name": "cancel_order",
                "idempotency_key": "idemp-cancel-123",
                "scope": "order:ord-100",
                "is_cached": False,
                "attempts": 3,
                "retry_delays": [0.05, 0.10],
                "elapsed_seconds": 0.16,
                "final_status": "COMPLETED",
                "timed_out": False,
                "retryable": True,
            }
        ],
    )
    checkpoint_store.save(run)

    res = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res.status_code == 200
    telem = res.json()

    assert telem["total_retries"] == 2
    assert telem["retry_counts"]["cancel_order"] == 2
    assert telem["timeout_occurred"] is False
    assert telem["retry_exhausted"] is False
    assert telem["idempotency_outcomes"]["total_records"] == 1
    assert telem["idempotency_outcomes"]["completed_count"] == 1
    assert "idemp-cancel-123" in telem["idempotency_outcomes"]["keys"]

    res_rec = telem["resilience_telemetry"][0]
    assert res_rec["tool_name"] == "cancel_order"
    assert res_rec["attempts"] == 3
    assert res_rec["retry_delays"] == [0.05, 0.10]
    assert res_rec["elapsed_seconds"] == 0.16


def test_successful_run_with_verification_result(client: TestClient):
    """Verifies that post-action verification outcomes are visible."""
    run_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-verify-01",
        state=WorkflowState.COMPLETED,
        verification_results=[
            {
                "entity_type": "order",
                "entity_id": "ord-200",
                "target_state": "CANCELLED",
                "actual_state": "CANCELLED",
                "status": "VERIFIED",
                "verified": True,
                "discrepancies": [],
                "operation": "cancel_order",
                "timestamp": now_iso,
                "details": {"current_status": "CANCELLED"},
            }
        ],
    )
    checkpoint_store.save(run)

    # In detail endpoint
    res_detail = client.get(f"/operations/runs/{run_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["verification_results"]) == 1
    vr = detail["verification_results"][0]
    assert vr["entity_type"] == "order"
    assert vr["entity_id"] == "ord-200"
    assert vr["status"] == "VERIFIED"
    assert vr["verified"] is True

    # In telemetry endpoint
    res_telem = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res_telem.status_code == 200
    telem = res_telem.json()
    assert len(telem["verification_results"]) == 1
    assert telem["verification_results"][0]["verified"] is True


def test_failed_workflow_telemetry(client: TestClient):
    """Verifies that top-level workflow failure and failed steps are structured in telemetry."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-fail-01",
        state=WorkflowState.FAILED,
        error="Simulated network failure while communicating with payment gateway",
        steps=[
            WorkflowStepRecord(
                step_name="interpret_request",
                state=WorkflowState.RUNNING,
            ),
            WorkflowStepRecord(
                step_name="execute_tools",
                state=WorkflowState.FAILED,
                tool_name="request_refund",
                error="Gateway unreachable",
            ),
        ],
    )
    checkpoint_store.save(run)

    res = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res.status_code == 200
    telem = res.json()

    assert telem["state"] == "FAILED"
    assert telem["status"] == "FAILED"
    assert telem["error"] is not None
    assert telem["failure_information"] is not None
    assert "Simulated network failure" in telem["failure_information"]["workflow_error"]
    assert "execute_tools" in telem["failure_information"]["failed_steps"]


def test_retry_exhaustion_telemetry(client: TestClient):
    """Verifies telemetry when retry budget is exhausted."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-exhaust-01",
        state=WorkflowState.FAILED,
        error="Tool execution failed after 3 retries",
        resilience_records=[
            {
                "tool_name": "track_shipment",
                "idempotency_key": "idemp-track-1",
                "attempts": 3,
                "retry_delays": [0.05, 0.10],
                "final_status": "FAILED",
                "error_type": "MaxRetriesExceededError",
                "error_message": "Exceeded maximum retries (3) for track_shipment",
                "retryable": True,
            }
        ],
    )
    checkpoint_store.save(run)

    res = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res.status_code == 200
    telem = res.json()

    assert telem["retry_exhausted"] is True
    assert telem["failure_information"] is not None
    assert telem["failure_information"]["retry_exhausted"] is True
    assert len(telem["failure_information"]["resilience_failures"]) == 1
    assert telem["failure_information"]["resilience_failures"][0]["error_type"] == "MaxRetriesExceededError"


def test_timeout_telemetry(client: TestClient):
    """Verifies telemetry when tool execution exceeds timeout budget."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-timeout-01",
        state=WorkflowState.FAILED,
        error="Execution exceeded timeout budget of 5.0s",
        resilience_records=[
            {
                "tool_name": "create_payment",
                "idempotency_key": "idemp-pay-1",
                "attempts": 2,
                "final_status": "FAILED",
                "timed_out": True,
                "error_type": "TimeoutBudgetExceededError",
                "error_message": "Timeout budget of 5.0s exceeded",
                "retryable": True,
            }
        ],
    )
    checkpoint_store.save(run)

    res = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res.status_code == 200
    telem = res.json()

    assert telem["timeout_occurred"] is True
    assert telem["failure_information"] is not None
    assert telem["failure_information"]["timeout_occurred"] is True
    assert telem["failure_information"]["resilience_failures"][0]["timed_out"] is True


def test_waiting_for_approval_telemetry(client: TestClient):
    """Verifies telemetry for a workflow paused awaiting human approval."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-approval-01",
        state=WorkflowState.WAITING_FOR_APPROVAL,
        approval_id="appr-test-123",
        policy_decisions=[
            {
                "policy_id": "POL-CAN-001",
                "policy_version": "1.0.0",
                "decision": "Order cancellation requires supervisor approval for orders > 5000",
                "allowed": True,
                "requires_approval": True,
                "risk_level": "HIGH",
                "matched_rules": ["RULE-HIGH-VAL-CANCEL"],
            }
        ],
    )
    checkpoint_store.save(run)

    res = client.get(f"/operations/runs/{run_id}/telemetry")
    assert res.status_code == 200
    telem = res.json()

    assert telem["state"] == "WAITING_FOR_APPROVAL"
    assert telem["status"] == "WAITING_FOR_APPROVAL"
    assert len(telem["policy_decisions"]) == 1
    assert telem["policy_decisions"][0]["requires_approval"] is True
    assert telem["policy_decisions"][0]["policy_id"] == "POL-CAN-001"


def test_missing_run_returns_404(client: TestClient):
    """Verifies that non-existent valid run identifiers return clean 404 responses."""
    missing_id = "00000000-0000-0000-0000-000000000000"

    res_detail = client.get(f"/operations/runs/{missing_id}")
    assert res_detail.status_code == 404
    assert f"Workflow run '{missing_id}' not found" in res_detail.json()["detail"]

    res_steps = client.get(f"/operations/runs/{missing_id}/steps")
    assert res_steps.status_code == 404

    res_telem = client.get(f"/operations/runs/{missing_id}/telemetry")
    assert res_telem.status_code == 404


def test_malformed_run_identifier_returns_400(client: TestClient):
    """Verifies that malformed or unsafe run identifiers return clean 400 Bad Request."""
    malformed_ids = [
        "run..with..dots",
        "run/with/slashes",
        "run\\with\\backslashes",
        "run with spaces",
        "run*with*asterisks",
        "run!with!exclamation",
        "a" * 150,  # exceeds 128 chars
    ]

    for bad_id in malformed_ids:
        # Note: requests/TestClient URL-encodes if necessary
        res_detail = client.get(f"/operations/runs/{bad_id}")
        assert res_detail.status_code in (400, 404)
        if res_detail.status_code == 400:
            assert "Malformed run_id" in res_detail.json()["detail"]

        res_telem = client.get(f"/operations/runs/{bad_id}/telemetry")
        assert res_telem.status_code in (400, 404)

        res_steps = client.get(f"/operations/runs/{bad_id}/steps")
        assert res_steps.status_code in (400, 404)


def test_read_only_invariant(client: TestClient):
    """Verifies that calling telemetry endpoints does NOT alter checkpoint or workflow state."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        workflow_id="wf-readonly-01",
        state=WorkflowState.COMPLETED,
        input_text="Immutable query",
        steps=[
            WorkflowStepRecord(
                step_name="step_one",
                state=WorkflowState.COMPLETED,
            )
        ],
    )
    checkpoint_store.save(run)

    # Snapshot before read calls
    record_before = checkpoint_store.get(run_id)
    assert record_before is not None
    json_before = record_before.model_dump_json()

    # Call all read-only endpoints
    client.get(f"/operations/runs/{run_id}")
    client.get(f"/operations/runs/{run_id}/steps")
    client.get(f"/operations/runs/{run_id}/telemetry")
    client.get("/operations/summary")

    # Snapshot after read calls
    record_after = checkpoint_store.get(run_id)
    assert record_after is not None
    json_after = record_after.model_dump_json()

    # Must be 100% byte-for-byte identical
    assert json_before == json_after


def test_operational_summary_aggregation(client: TestClient):
    """Verifies aggregate operational metrics computation across multiple workflow runs."""
    # 1. Completed normal run
    r1 = WorkflowRunRecord(
        run_id=str(uuid.uuid4()),
        state=WorkflowState.COMPLETED,
    )
    checkpoint_store.save(r1)

    # 2. Failed run with retry exhaustion
    r2 = WorkflowRunRecord(
        run_id=str(uuid.uuid4()),
        state=WorkflowState.FAILED,
        resilience_records=[
            {
                "tool_name": "refund",
                "error_type": "MaxRetriesExceededError",
                "final_status": "FAILED",
                "attempts": 3,
            }
        ],
    )
    checkpoint_store.save(r2)

    # 3. Failed run with timeout
    r3 = WorkflowRunRecord(
        run_id=str(uuid.uuid4()),
        state=WorkflowState.FAILED,
        resilience_records=[
            {
                "tool_name": "shipment",
                "timed_out": True,
                "final_status": "FAILED",
                "attempts": 1,
            }
        ],
    )
    checkpoint_store.save(r3)

    # 4. Waiting for approval run
    r4 = WorkflowRunRecord(
        run_id=str(uuid.uuid4()),
        state=WorkflowState.WAITING_FOR_APPROVAL,
    )
    checkpoint_store.save(r4)

    # 5. Cancelled run
    r5 = WorkflowRunRecord(
        run_id=str(uuid.uuid4()),
        state=WorkflowState.CANCELLED,
    )
    checkpoint_store.save(r5)

    # 6. High-risk and anomalous completed run
    r6 = WorkflowRunRecord(
        run_id=str(uuid.uuid4()),
        state=WorkflowState.COMPLETED,
        risk_assessment={
            "risk_score": 0.85,
            "risk_band": "HIGH",
            "anomaly": {
                "is_anomaly": True,
                "anomaly_flags": ["HIGH_VALUE_ANOMALY"],
            },
        },
    )
    checkpoint_store.save(r6)

    # 7. Run with verification failure / divergence
    r7 = WorkflowRunRecord(
        run_id=str(uuid.uuid4()),
        state=WorkflowState.COMPLETED,
        verification_results=[
            {
                "entity_type": "order",
                "entity_id": "ord-div",
                "target_state": "CANCELLED",
                "actual_state": "CONFIRMED",
                "status": "DIVERGENT",
                "verified": False,
            }
        ],
    )
    checkpoint_store.save(r7)

    res = client.get("/operations/summary")
    assert res.status_code == 200
    summary = res.json()

    assert summary["total_runs"] == 7
    assert summary["completed"] == 3  # r1, r6, r7
    assert summary["failed"] == 2     # r2, r3
    assert summary["waiting_for_approval"] == 1  # r4
    assert summary["cancelled"] == 1  # r5
    assert summary["retry_failures"] == 1    # r2
    assert summary["timeout_failures"] == 1  # r3
    assert summary["high_risk_assessments"] == 1  # r6
    assert summary["anomalous_assessments"] == 1  # r6
    assert summary["verification_failures"] == 1  # r7
    assert summary["data_source"] == "in_memory_and_disk_checkpoints"


def test_operational_summary_empty_store(client: TestClient):
    """Verifies that operational summary returns clean zero counts when no runs exist."""
    res = client.get("/operations/summary")
    assert res.status_code == 200
    summary = res.json()

    assert summary["total_runs"] == 0
    assert summary["completed"] == 0
    assert summary["failed"] == 0
    assert summary["waiting_for_approval"] == 0
    assert summary["cancelled"] == 0
    assert summary["running"] == 0
    assert summary["verification_failures"] == 0
    assert summary["retry_failures"] == 0
    assert summary["timeout_failures"] == 0
    assert summary["high_risk_assessments"] == 0
    assert summary["anomalous_assessments"] == 0


def test_sensitive_credentials_sanitized(client: TestClient):
    """Verifies that credentials and tokens inside payloads are redacted in telemetry output."""
    run_id = str(uuid.uuid4())
    run = WorkflowRunRecord(
        run_id=run_id,
        state=WorkflowState.COMPLETED,
        steps=[
            WorkflowStepRecord(
                step_name="auth_check",
                state=WorkflowState.COMPLETED,
                input_payload={
                    "customer_id": "cust-1",
                    "api_key": "super_secret_api_key_123",
                    "auth_token": "bearer eyJhbGciOi...",
                },
                output_payload={
                    "status": "authenticated",
                    "database_url": "postgresql://user:pass@localhost:5432/db",
                },
            )
        ],
    )
    checkpoint_store.save(run)

    res_steps = client.get(f"/operations/runs/{run_id}/steps")
    assert res_steps.status_code == 200
    step_data = res_steps.json()[0]

    assert step_data["input_payload"]["customer_id"] == "cust-1"
    assert step_data["input_payload"]["api_key"] == "[REDACTED]"
    assert step_data["input_payload"]["auth_token"] == "[REDACTED]"
    assert step_data["output_payload"]["database_url"] == "[REDACTED]"
    assert step_data["output_payload"]["status"] == "authenticated"
