"""
Comprehensive Test Suite for Audit & Observability Subsystem (Phase 4/5 - Deliverable D-16).

Covers:
- Audit event model creation and validation
- Sensitive field sanitization and redaction
- Persistence in database and in-memory buffer
- Observability sinks and manager
- Resilience (retries, timeouts, idempotency) provenance
- Policy decision provenance
- ML risk assessment (D-13) provenance
- Post-action verification (D-14) provenance
- Human approval gating and resolution audit
- Workflow completion and failure audit
- Timeline chronological ordering and correlation
- Non-mutation of business entities
- Read-only REST API endpoints (/audit/runs, /audit/events, /audit/timeline)
- End-to-end OpsAgent workflow audit timeline correlation
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

import simulator
from backend.agents.ops_agent import OpsAgent
from backend.audit import (
    AuditEventCreate,
    AuditEventRecord,
    AuditEventType,
    AuditService,
    ObservabilityManager,
    PluggableObservabilitySink,
    StructuredLoggingSink,
    audit_service,
    observability_manager,
    sanitize_audit_data,
)
from backend.main import app
from backend.workflows.state import WorkflowState
from database.models import Customer, Order, OrderItem, Payment, Product
from database.models.enums import OrderStatus, PaymentStatus


# ==============================================================================
# 1. Model Validation & Sanitization Tests
# ==============================================================================

def test_audit_event_creation_and_defaults():
    """Verifies AuditEventCreate instantiation, defaults, and type correctness."""
    run_id = str(uuid.uuid4())
    event = AuditEventCreate(
        run_id=run_id,
        event_type=AuditEventType.REQUEST_RECEIVED,
        actor="TestUser",
        tool_arguments={"input_text": "Cancel my order"},
    )
    assert event.run_id == run_id
    assert event.event_type == AuditEventType.REQUEST_RECEIVED
    assert event.actor == "TestUser"
    assert event.success is True
    assert event.error_message is None
    assert event.metadata_provenance == {}


def test_sensitive_field_sanitization():
    """Verifies recursive sanitization of credentials, keys, and authorization headers."""
    raw_payload = {
        "user_email": "user@example.com",
        "password": "SuperSecretPassword123!",
        "api_key": "sk-proj-999988887777",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "nested": {
            "access_token": "token_xyz",
            "safe_counter": 42,
            "secret_client_id": "client_abc",
        },
        "list_items": [
            {"credential": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC", "id": 1},
            {"name": "harmless_product", "price": 99.99},
        ],
    }

    sanitized = sanitize_audit_data(raw_payload)

    assert sanitized["user_email"] == "user@example.com"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["nested"]["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["secret_client_id"] == "[REDACTED]"
    assert sanitized["nested"]["safe_counter"] == 42
    assert sanitized["list_items"][0]["credential"] == "[REDACTED]"
    assert sanitized["list_items"][0]["id"] == 1
    assert sanitized["list_items"][1]["name"] == "harmless_product"


# ==============================================================================
# 2. Persistence & Buffer Tests
# ==============================================================================

def test_event_persistence_in_db(db_session):
    """Verifies that audit events are durably persisted to the database."""
    run_id = str(uuid.uuid4())
    record = audit_service.record_event(
        AuditEventCreate(
            run_id=run_id,
            event_type=AuditEventType.INTENT_INTERPRETED,
            actor="TestAgent",
            operation="interpret_request",
            workflow_state="RUNNING",
            tool_arguments={"intent": "cancel_order_request"},
            metadata_provenance={"confidence": 0.98},
        ),
        session=db_session,
    )

    assert record.id is not None
    assert record.event_id is not None
    assert record.run_id == run_id
    assert record.event_type == AuditEventType.INTENT_INTERPRETED.value

    # Verify query directly from DB session
    db_record = db_session.query(AuditEventRecord).filter_by(event_id=record.event_id).first()
    assert db_record is not None
    assert db_record.run_id == run_id
    assert db_record.operation == "interpret_request"
    assert db_record.tool_arguments == {"intent": "cancel_order_request"}


def test_audit_service_in_memory_buffer():
    """Verifies thread-safe in-memory buffering when no database session is passed."""
    service = AuditService()
    run_id = f"mem-run-{uuid.uuid4()}"

    ev = service.record_event(
        AuditEventCreate(
            run_id=run_id,
            event_type=AuditEventType.REQUEST_RECEIVED,
            tool_arguments={"query": "test buffer"},
        )
    )

    found = service.get_event(ev.event_id)
    assert found is not None
    assert found.event_id == ev.event_id

    run_events = service.get_run_events(run_id)
    assert len(run_events) == 1
    assert run_events[0].run_id == run_id


# ==============================================================================
# 3. Observability Sinks & Manager Tests
# ==============================================================================

class MockObservabilitySink(PluggableObservabilitySink):
    """Test spy sink tracking emitted audit events."""
    def __init__(self):
        super().__init__()
        self.emitted_events: List[Dict[str, Any]] = []

    def emit_event(
        self,
        event_id: str,
        run_id: str,
        event_type: AuditEventType,
        actor: str,
        data: Dict[str, Any],
    ) -> None:
        self.emitted_events.append({
            "event_id": event_id,
            "run_id": run_id,
            "event_type": event_type.value if hasattr(event_type, "value") else str(event_type),
            "actor": actor,
            "data": data,
        })


def test_observability_manager_fanout():
    """Verifies observability manager fans out events to all registered sinks."""
    manager = ObservabilityManager()
    mock_sink = MockObservabilitySink()
    manager.register_sink(mock_sink)

    service = AuditService(observability=manager)
    run_id = str(uuid.uuid4())

    service.record_event(
        AuditEventCreate(
            run_id=run_id,
            event_type=AuditEventType.TOOL_EXECUTED,
            tool_name="get_order",
            success=True,
        )
    )

    assert len(mock_sink.emitted_events) == 1
    assert mock_sink.emitted_events[0]["run_id"] == run_id
    assert mock_sink.emitted_events[0]["event_type"] == AuditEventType.TOOL_EXECUTED.value


# ==============================================================================
# 4. Resilience & Idempotency Provenance Tests
# ==============================================================================

def test_record_tool_execution_with_resilience_and_idempotency(db_session):
    """Verifies that retry attempts and idempotency cache hits generate distinct audit entries."""
    service = AuditService()
    run_id = str(uuid.uuid4())

    # Case 1: Execution with retries and timeout metadata
    res_record = service.record_tool_execution(
        run_id=run_id,
        tool_name="cancel_order",
        arguments={"order_id": "ord-123", "password": "redact_me"},
        result={"cancelled": True},
        resilience_metadata={
            "attempts": 3,
            "idempotency_key": "idemp-cancel-123",
            "scope": "order:cancel",
            "is_cached": False,
            "retry_delays": [0.1, 0.2],
            "timed_out": False,
        },
        session=db_session,
    )

    events = service.get_run_events(run_id, session=db_session)
    # Expect RETRY_ATTEMPTED + ACTION_EXECUTED (or TOOL_EXECUTED)
    event_types = [e.event_type for e in events]
    assert AuditEventType.RETRY_ATTEMPTED.value in event_types
    assert AuditEventType.ACTION_EXECUTED.value in event_types

    # Ensure sensitive arguments were sanitized
    action_ev = next(e for e in events if e.event_type == AuditEventType.ACTION_EXECUTED.value)
    assert action_ev.tool_arguments is not None
    assert action_ev.tool_arguments["password"] == "[REDACTED]"
    assert action_ev.retry_attempt == 3
    assert action_ev.idempotency_info is not None
    assert action_ev.idempotency_info["idempotency_key"] == "idemp-cancel-123"

    # Case 2: Idempotency Cache Hit
    run_id_cached = str(uuid.uuid4())
    service.record_tool_execution(
        run_id=run_id_cached,
        tool_name="cancel_order",
        arguments={"order_id": "ord-123"},
        result={"cancelled": True},
        resilience_metadata={
            "idempotency_key": "idemp-cancel-123",
            "scope": "order:cancel",
            "is_cached": True,
            "attempts": 1,
        },
        session=db_session,
    )

    cached_events = service.get_run_events(run_id_cached, session=db_session)
    cached_types = [e.event_type for e in cached_events]
    assert AuditEventType.IDEMPOTENCY_HIT.value in cached_types


# ==============================================================================
# 5. Policy, ML Risk & Verification Provenance Tests
# ==============================================================================

def test_record_policy_decision(db_session):
    """Verifies deterministic policy decision audit captures rule ID and allowed status."""
    service = AuditService()
    run_id = str(uuid.uuid4())

    service.record_policy_decision(
        run_id=run_id,
        policy_decision={
            "policy_id": "POL-CANC-001",
            "policy_version": "1.2.0",
            "allowed": False,
            "decision": "DENIED",
            "reason": "Order already dispatched",
            "requires_approval": False,
        },
        operation="cancel_order",
        workflow_state="COMPLETED",
        session=db_session,
    )

    events = service.get_run_events(run_id, session=db_session)
    assert len(events) == 1
    assert events[0].event_type == AuditEventType.POLICY_EVALUATED.value
    assert events[0].policy_decision is not None
    assert events[0].policy_decision["policy_id"] == "POL-CANC-001"
    assert events[0].success is False


def test_record_risk_assessment_provenance(db_session):
    """Verifies D-13 ML risk scoring provenance (model name, version, score, anomalies)."""
    service = AuditService()
    run_id = str(uuid.uuid4())

    risk_data = {
        "model_name": "risk_gradient_boost_v1",
        "model_version": "1.0.0",
        "risk_score": 0.88,
        "risk_band": "CRITICAL",
        "anomaly_flags": ["VELOCITY_EXCEEDED", "UNUSUAL_HOURS"],
        "feature_contributions": {"order_amount": 0.45, "payment_attempts": 0.35},
    }

    service.record_risk_assessment(
        run_id=run_id,
        risk_assessment=risk_data,
        session=db_session,
    )

    events = service.get_run_events(run_id, session=db_session)
    assert len(events) == 1
    assert events[0].event_type == AuditEventType.RISK_ASSESSED.value
    assert events[0].risk_assessment_summary is not None
    assert events[0].risk_assessment_summary["model_version"] == "1.0.0"
    assert events[0].risk_assessment_summary["risk_band"] == "CRITICAL"
    assert "VELOCITY_EXCEEDED" in events[0].risk_assessment_summary["anomaly_flags"]


def test_record_verification_provenance(db_session):
    """Verifies D-14 post-action verification provenance including divergences and ground truth."""
    service = AuditService()
    run_id = str(uuid.uuid4())

    ver_data = {
        "verified": False,
        "status": "DIVERGENT",
        "entity_type": "order",
        "entity_id": "ORD-2026-999",
        "target_state": "CANCELLED",
        "actual_state": "SHIPPED",
        "discrepancies": ["Status mismatch: expected CANCELLED, actual SHIPPED"],
        "error": "State divergence detected",
    }

    service.record_verification(
        run_id=run_id,
        verification_result=ver_data,
        operation="cancel_order",
        session=db_session,
    )

    events = service.get_run_events(run_id, session=db_session)
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == AuditEventType.VERIFICATION_COMPLETED.value
    assert ev.verification_status == "DIVERGENT"
    assert ev.success is False
    assert ev.metadata_provenance["target_state"] == "CANCELLED"
    assert ev.metadata_provenance["actual_state"] == "SHIPPED"
    assert "Status mismatch: expected CANCELLED, actual SHIPPED" in ev.metadata_provenance["discrepancies"]


# ==============================================================================
# 6. Approvals & Workflow Lifecycle Tests
# ==============================================================================

def test_record_approval_events(db_session):
    """Verifies human approval requested and resolution audit records."""
    service = AuditService()
    run_id = str(uuid.uuid4())

    # Requested
    service.record_approval(
        run_id=run_id,
        approval_id="APP-001",
        action="request_refund",
        status="PENDING",
        session=db_session,
    )

    # Resolved - Approved
    service.record_approval(
        run_id=run_id,
        approval_id="APP-001",
        action="request_refund",
        status="APPROVED",
        actor="OpsSupervisor",
        decision_reason="Legitimate customer dissatisfaction",
        session=db_session,
    )

    events = service.get_run_events(run_id, session=db_session)
    assert len(events) == 2
    assert events[0].event_type == AuditEventType.APPROVAL_REQUESTED.value
    assert events[1].event_type == AuditEventType.APPROVAL_RESOLVED.value
    assert events[1].actor == "OpsSupervisor"
    assert events[1].metadata_provenance["reason"] == "Legitimate customer dissatisfaction"


def test_record_workflow_completion_and_failure(db_session):
    """Verifies workflow completion and failure events."""
    service = AuditService()
    run_id_success = str(uuid.uuid4())
    run_id_fail = str(uuid.uuid4())

    service.record_workflow_completion(
        run_id=run_id_success,
        final_response="Order status is DELIVERED.",
        session=db_session,
    )

    service.record_workflow_failure(
        run_id=run_id_fail,
        error="Downstream fulfillment service connection timeout",
        session=db_session,
    )

    succ_ev = service.get_run_events(run_id_success, session=db_session)[0]
    assert succ_ev.event_type == AuditEventType.WORKFLOW_COMPLETED.value
    assert succ_ev.success is True

    fail_ev = service.get_run_events(run_id_fail, session=db_session)[0]
    assert fail_ev.event_type == AuditEventType.WORKFLOW_FAILED.value
    assert fail_ev.success is False
    assert fail_ev.error_message == "Downstream fulfillment service connection timeout"


# ==============================================================================
# 7. Timeline Ordering & Immutability Tests
# ==============================================================================

def test_timeline_ordering(db_session):
    """Verifies timeline events are ordered chronologically and correlated by run_id."""
    service = AuditService()
    run_id = str(uuid.uuid4())

    service.record_event(AuditEventCreate(run_id=run_id, event_type=AuditEventType.REQUEST_RECEIVED), session=db_session)
    service.record_event(AuditEventCreate(run_id=run_id, event_type=AuditEventType.INTENT_INTERPRETED), session=db_session)
    service.record_event(AuditEventCreate(run_id=run_id, event_type=AuditEventType.TOOL_PLANNED), session=db_session)
    service.record_event(AuditEventCreate(run_id=run_id, event_type=AuditEventType.WORKFLOW_COMPLETED), session=db_session)

    timeline = service.get_timeline(run_id, session=db_session)
    assert timeline.run_id == run_id
    assert timeline.total_events == 4
    event_types = [e.event_type for e in timeline.events]
    assert event_types == [
        AuditEventType.REQUEST_RECEIVED,
        AuditEventType.INTENT_INTERPRETED,
        AuditEventType.TOOL_PLANNED,
        AuditEventType.WORKFLOW_COMPLETED,
    ]


def test_business_entity_immutability(db_session):
    """Ensures that audit recording never mutates business database models."""
    cust = db_session.query(Customer).first()
    assert cust is not None

    prod = db_session.query(Product).first()
    assert prod is not None

    order = Order(
        customer_id=cust.id,
        order_number="ORD-IMMUTABLE-001",
        status=OrderStatus.PENDING,
        total_amount=Decimal("1999.00"),
        currency="INR",
        shipping_city="Mumbai",
        shipping_pincode="400001",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    original_updated_at = order.updated_at
    original_status = order.status

    # Record audit events referencing the order
    service = AuditService()
    service.record_event(
        AuditEventCreate(
            run_id=str(uuid.uuid4()),
            event_type=AuditEventType.ACTION_EXECUTED,
            entity_type="order",
            entity_id=str(order.id),
            operation="inspect_order",
        ),
        session=db_session,
    )

    db_session.refresh(order)
    assert order.status == original_status
    assert order.updated_at == original_updated_at


# ==============================================================================
# 8. REST API Endpoint Tests
# ==============================================================================

def test_audit_api_endpoints(db_session):
    """Tests GET /audit/runs/{run_id}, GET /audit/events/{event_id}, and GET /audit/runs/{run_id}/timeline."""
    client = TestClient(app)
    run_id = str(uuid.uuid4())

    # Create test event
    ev = audit_service.record_event(
        AuditEventCreate(
            run_id=run_id,
            event_type=AuditEventType.REQUEST_RECEIVED,
            actor="APITester",
            tool_arguments={"query": "Check status"},
        ),
        session=db_session,
    )

    # 1. GET /audit/runs/{run_id}
    res_run = client.get(f"/audit/runs/{run_id}")
    assert res_run.status_code == 200
    events_data = res_run.json()
    assert len(events_data) >= 1
    assert events_data[0]["run_id"] == run_id

    # 2. GET /audit/events/{event_id}
    res_ev = client.get(f"/audit/events/{ev.event_id}")
    assert res_ev.status_code == 200
    ev_data = res_ev.json()
    assert ev_data["event_id"] == ev.event_id
    assert ev_data["actor"] == "APITester"

    # 3. GET /audit/runs/{run_id}/timeline
    res_tl = client.get(f"/audit/runs/{run_id}/timeline")
    assert res_tl.status_code == 200
    tl_data = res_tl.json()
    assert tl_data["run_id"] == run_id
    assert tl_data["total_events"] >= 1
    assert tl_data["events"][0]["event_id"] == ev.event_id

    # 4. 404 on non-existent run and event
    non_existent_id = str(uuid.uuid4())
    res_not_found = client.get(f"/audit/runs/{non_existent_id}")
    assert res_not_found.status_code == 404

    res_ev_not_found = client.get(f"/audit/events/{non_existent_id}")
    assert res_ev_not_found.status_code == 404


# ==============================================================================
# 9. End-to-End Workflow Audit Integration Test
# ==============================================================================

def test_ops_agent_workflow_produces_correlated_audit_timeline(db_session):
    """Proves that a complete OpsAgent run produces a fully correlated audit timeline.

    Verifies presence and correlation of:
    - REQUEST_RECEIVED
    - INTENT_INTERPRETED
    - TOOL_PLANNED
    - TOOL_EXECUTED
    - RISK_ASSESSED
    - POLICY_EVALUATED
    - WORKFLOW_COMPLETED
    All bound by the exact same run_id.
    """
    cust = db_session.query(Customer).first()
    assert cust is not None

    prod = db_session.query(Product).first()
    assert prod is not None

    # Seed an order in the database
    order = Order(
        customer_id=cust.id,
        order_number="ORD-AUDIT-E2E-001",
        status=OrderStatus.CONFIRMED,
        total_amount=Decimal("1999.00"),
        currency="INR",
        shipping_city="Mumbai",
        shipping_pincode="400001",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    # Run agent inquiry workflow
    agent = OpsAgent()
    run_id = f"audit-e2e-{uuid.uuid4()}"
    run_record = agent.run(
        input_text="What is the status of my order ORD-AUDIT-E2E-001?",
        order_number="ORD-AUDIT-E2E-001",
        customer_id=str(cust.id),
        db=db_session,
        run_id=run_id,
    )

    assert run_record.state == WorkflowState.COMPLETED

    # Retrieve timeline from AuditService
    timeline = audit_service.get_timeline(run_id, session=db_session)
    assert timeline.run_id == run_id
    assert timeline.total_events >= 5

    event_types = [e.event_type for e in timeline.events]
    assert AuditEventType.REQUEST_RECEIVED in event_types
    assert AuditEventType.INTENT_INTERPRETED in event_types
    assert AuditEventType.TOOL_PLANNED in event_types
    assert AuditEventType.TOOL_EXECUTED in event_types
    assert AuditEventType.RISK_ASSESSED in event_types
    assert AuditEventType.POLICY_EVALUATED in event_types
    assert AuditEventType.WORKFLOW_COMPLETED in event_types

    # Ensure every single event in the timeline shares the run_id
    for ev in timeline.events:
        assert ev.run_id == run_id

    # Verify risk audit event contains ML provenance
    risk_ev = next(e for e in timeline.events if e.event_type == AuditEventType.RISK_ASSESSED)
    assert risk_ev.risk_assessment_summary is not None
    assert "risk_score" in risk_ev.risk_assessment_summary
    assert "risk_band" in risk_ev.risk_assessment_summary


def test_ops_agent_approval_gated_workflow_audit_integration(db_session):
    """Proves that an approval-gated workflow produces an audit timeline capturing:

    - APPROVAL_REQUESTED
    - APPROVAL_RESOLVED
    - Action execution with resilience provenance
    - Post-action state verification (VERIFICATION_COMPLETED)
    - Resumed completion (WORKFLOW_COMPLETED)
    All correlated by run_id.
    """
    cust = db_session.query(Customer).first()
    assert cust is not None

    # Create an order with high amount that requires supervisor approval to cancel
    order = Order(
        customer_id=cust.id,
        order_number="ORD-AUDIT-APPROVAL-001",
        status=OrderStatus.PENDING,
        total_amount=Decimal("15000.00"),
        currency="INR",
        shipping_city="Delhi",
        shipping_pincode="110001",
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    agent = OpsAgent()
    run_id = f"audit-approval-{uuid.uuid4()}"
    run_record = agent.run(
        input_text="Cancel my order ORD-AUDIT-APPROVAL-001 immediately.",
        order_number="ORD-AUDIT-APPROVAL-001",
        customer_id=str(cust.id),
        db=db_session,
        run_id=run_id,
    )

    # Initial run should pause waiting for approval
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL

    timeline_paused = audit_service.get_timeline(run_id, session=db_session)
    paused_types = [e.event_type for e in timeline_paused.events]
    assert AuditEventType.APPROVAL_REQUESTED in paused_types

    # Resume with supervisor approval
    resumed_record = agent.resume(
        run_id=run_id,
        approved=True,
        db=db_session,
        reason="Verified customer requested cancellation directly.",
    )
    assert resumed_record.state == WorkflowState.COMPLETED

    # Verify final timeline
    final_timeline = audit_service.get_timeline(run_id, session=db_session)
    final_types = [e.event_type for e in final_timeline.events]

    assert AuditEventType.REQUEST_RECEIVED in final_types
    assert AuditEventType.APPROVAL_REQUESTED in final_types
    assert AuditEventType.APPROVAL_RESOLVED in final_types
    assert AuditEventType.VERIFICATION_COMPLETED in final_types
    assert AuditEventType.WORKFLOW_COMPLETED in final_types

    # Verify post-action verification audit provenance
    ver_event = next(e for e in final_timeline.events if e.event_type == AuditEventType.VERIFICATION_COMPLETED)
    assert ver_event.verification_status == "VERIFIED"
    assert ver_event.success is True

    # Verify approval resolution details
    approval_res_ev = next(e for e in final_timeline.events if e.event_type == AuditEventType.APPROVAL_RESOLVED)
    assert approval_res_ev.approval_status == "APPROVED"
    assert approval_res_ev.metadata_provenance.get("reason") == "Verified customer requested cancellation directly."

