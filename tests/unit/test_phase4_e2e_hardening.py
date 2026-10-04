"""End-to-End Failure Matrix and Production Hardening Tests for Phase 4.

Validates the complete composition of:
Request -> Planning -> Resilience/Idempotency -> ML Risk Assessment ->
Policy Evaluation -> Approval Gate -> Resumed Execution -> Post-Action Verification -> Final Response.

Failure Matrix:
1. transient failure -> retry -> success
2. transient failure -> retry exhaustion
3. timeout budget exceeded
4. non-transient failure -> no retry
5. duplicate idempotency key -> no second mutation
6. approved action resumed twice -> only one mutation
7. tool reports success but DB state unchanged -> DIVERGENT
8. target entity missing -> NOT_FOUND
9. verification query error -> ERROR
10. high ML risk -> policy approval gate
11. ML anomaly -> policy approval gate
12. low risk + normal operation -> existing policy behavior preserved
13. risk assessment failure -> safe/defined policy behavior
14. retry failure followed by workflow failure -> no verification falsely reported as successful
15. successful mutation -> verification -> COMPLETED
"""

import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import simulator
from backend.agents.ops_agent import OpsAgent
from backend.ml import (
    AnomalyInfo,
    MLRiskService,
    RiskAssessmentResult,
    RiskBand,
    RiskFeatureVector,
)
from backend.policies.schemas import PolicyEvaluationResult
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.resilience import (
    IdempotencyService,
    MaxRetriesExceededError,
    ResilientToolExecutor,
    RetryExecutor,
    RetryPolicyConfig,
    TimeoutBudgetExceededError,
)
from backend.tools.base import RiskLevel, ToolDefinition, ToolRegistry, ToolType
from backend.tools.registry import create_default_tool_registry
from backend.tools.schemas import CancelOrderInput, RequestRefundInput
from backend.verification import (
    StateVerificationService,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import StructuredAction, WorkflowRunRecord, WorkflowState
from database.models import (
    Customer,
    IdempotencyRecord,
    IdempotencyStatus,
    Order,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Product,
)


@pytest.fixture(autouse=True)
def seed_kb(db_session: Session):
    seed_default_knowledge(db_session)


@pytest.fixture
def fast_retry_policy() -> RetryPolicyConfig:
    return RetryPolicyConfig(
        max_attempts=3,
        initial_delay_seconds=0.005,
        backoff_multiplier=1.5,
        timeout_seconds=1.5,
    )


def _setup_order(
    db: Session,
    amount: Decimal = Decimal("2500.00"),
    status: OrderStatus = OrderStatus.CONFIRMED,
) -> tuple[Customer, Order, Payment]:
    cust_id = uuid.uuid4()
    cust = Customer(
        id=cust_id,
        first_name="Ramesh",
        last_name="Gupta",
        email=f"ramesh.{uuid.uuid4().hex[:6]}@example.com",
        city="Delhi",
        state="Delhi",
        pincode="110001",
    )
    prod_id = uuid.uuid4()
    prod = Product(
        id=prod_id,
        sku=f"SKU-HARDEN-{uuid.uuid4().hex[:6]}",
        name="Hardening Test Appliance",
        unit_price=amount,
        currency="INR",
        inventory_count=25,
        is_active=True,
    )
    db.add_all([cust, prod])
    db.commit()

    order = simulator.create_order(
        session=db,
        customer_id=cust.id,
        items=[{"product_id": prod.id, "quantity": 1}],
    )

    pay = simulator.create_payment(
        session=db,
        order_id=order.id,
        amount=amount,
        payment_method=PaymentMethod.UPI,
    )
    simulator.capture_payment(session=db, payment_id=pay.id, gateway_transaction_id=f"pay_hard_{uuid.uuid4().hex[:6]}")
    db.refresh(order)
    return cust, order, pay


class MockOrderMutationInput(BaseModel):
    order_id: str
    action_notes: str = "Hardening note"


# ==============================================================================
# 1. Transient failure -> retry -> success
# ==============================================================================

def test_transient_failure_retry_success(db_session: Session, fast_retry_policy: RetryPolicyConfig):
    """Verifies that transient errors (ConnectionError) trigger retry and succeed on attempt 2."""
    call_count = 0

    def transient_recovering(order_id: str, action_notes: str = "note") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionResetError("Connection reset by peer during network write")
        return {"result": "success", "recovered_on": call_count}

    tool = ToolDefinition(
        name="transient_retry_tool",
        description="Recovers on retry",
        input_schema=MockOrderMutationInput,
        handler=transient_recovering,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    key = f"key-retry-succ-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="transient_retry_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "Retry test"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )

    assert res.success is True
    assert call_count == 2
    assert res.attempts == 2
    assert len(res.retry_delays) == 1
    assert res.data is not None
    assert res.data["result"] == "success"

    # Idempotency record is COMPLETED
    rec = db_session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key))
    assert rec is not None
    assert rec.status == IdempotencyStatus.COMPLETED


# ==============================================================================
# 2. Transient failure -> retry exhaustion
# ==============================================================================

def test_transient_failure_retry_exhaustion(db_session: Session, fast_retry_policy: RetryPolicyConfig):
    """Verifies that permanent transient failure exhausts all retries and results in structured failure."""
    call_count = 0

    def always_transient(order_id: str, action_notes: str = "note") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Persistent network outage")

    tool = ToolDefinition(
        name="exhaustion_tool",
        description="Always fails transiently",
        input_schema=MockOrderMutationInput,
        handler=always_transient,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    key = f"key-exhaust-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="exhaustion_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "Exhaust"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )

    assert res.success is False
    assert call_count == 3  # max_attempts=3
    assert res.attempts == 3
    assert res.error is not None
    assert "retry exhaustion" in res.error.lower() or "network outage" in res.error.lower()
    assert res.resilience_metadata is not None
    assert res.resilience_metadata.get("final_status") == "FAILED"

    rec = db_session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key))
    assert rec is not None
    assert rec.status == IdempotencyStatus.FAILED


# ==============================================================================
# 3. Timeout budget exceeded
# ==============================================================================

def test_timeout_budget_exceeded(db_session: Session):
    """Verifies that exceeding the timeout budget stops retrying and fails gracefully."""
    call_count = 0

    def slow_failing(order_id: str, action_notes: str = "note") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        time.sleep(0.04)
        raise TimeoutError("Remote socket timed out")

    tool = ToolDefinition(
        name="timeout_tool",
        description="Times out",
        input_schema=MockOrderMutationInput,
        handler=slow_failing,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    tight_policy = RetryPolicyConfig(
        max_attempts=5,
        initial_delay_seconds=0.03,
        timeout_seconds=0.06,
    )

    key = f"key-timeout-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="timeout_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "Timeout"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": tight_policy},
    )

    assert res.success is False
    assert res.error is not None
    assert "timeout" in res.error.lower()
    assert res.resilience_metadata is not None
    assert res.resilience_metadata.get("timed_out") is True or res.resilience_metadata.get("timeout_occurred") is True


# ==============================================================================
# 4. Non-transient failure -> no retry
# ==============================================================================

def test_non_transient_failure_no_retry(db_session: Session, fast_retry_policy: RetryPolicyConfig):
    """Verifies that non-transient validation errors fail immediately on attempt 1 without retries."""
    call_count = 0

    def validation_error(order_id: str, action_notes: str = "note") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid order status: cannot cancel delivered order")

    tool = ToolDefinition(
        name="val_error_tool",
        description="Fails with ValueError",
        input_schema=MockOrderMutationInput,
        handler=validation_error,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    key = f"key-non-trans-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="val_error_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "No retry"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )

    assert res.success is False
    assert call_count == 1  # Crucial: exactly 1 attempt
    assert res.attempts == 1
    assert res.error is not None
    assert "delivered order" in res.error


# ==============================================================================
# 5. Duplicate idempotency key -> no second mutation
# ==============================================================================

def test_duplicate_idempotency_key_no_second_mutation(db_session: Session):
    """Verifies that replaying the same idempotency key returns cached output without second mutation."""
    mutation_count = 0

    def counting_mutation(order_id: str, action_notes: str = "note") -> Dict[str, Any]:
        nonlocal mutation_count
        mutation_count += 1
        return {"mutation_index": mutation_count, "order_id": order_id}

    tool = ToolDefinition(
        name="counting_tool",
        description="Counts mutations",
        input_schema=MockOrderMutationInput,
        handler=counting_mutation,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    key = f"key-dup-{uuid.uuid4().hex[:8]}"
    params = {"order_id": str(uuid.uuid4()), "action_notes": "Once"}

    res1 = registry.execute(tool.name, params, context={"db": db_session, "idempotency_key": key})
    assert res1.success is True
    assert mutation_count == 1
    assert res1.is_cached is False

    res2 = registry.execute(tool.name, params, context={"db": db_session, "idempotency_key": key})
    assert res2.success is True
    assert mutation_count == 1  # Handler NOT called again
    assert res2.is_cached is True
    assert res2.attempts == 0
    assert res2.data == res1.data


# ==============================================================================
# 6. Approved action resumed twice -> only one mutation
# ==============================================================================

def test_approved_action_resumed_twice_only_one_mutation(db_session: Session):
    """Verifies that resuming an approved action twice fails gracefully on the second call
    and only executes the mutation once.
    """
    _, order, _ = _setup_order(db_session, amount=Decimal("3000.00"))
    agent = OpsAgent()

    # Step 1: Request cancellation (triggers approval)
    run_record = agent.run(input_text=f"Please cancel my order {order.order_number}", db=db_session)
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL
    run_id = run_record.run_id

    # Step 2: First resume succeeds
    resumed1 = agent.resume(run_id=run_id, approved=True, db=db_session, reason="Operator approved")
    assert resumed1.state == WorkflowState.COMPLETED
    assert len(resumed1.resilience_records) >= 1

    # Step 3: Second resume on already completed workflow raises ValueError and executes zero mutations
    with pytest.raises(ValueError, match="is in state 'COMPLETED', not WAITING_FOR_APPROVAL"):
        agent.resume(run_id=run_id, approved=True, db=db_session, reason="Operator approved again")

    # Verify database state
    db_session.refresh(order)
    assert order.status == OrderStatus.CANCELLED


# ==============================================================================
# 7. Tool reports success but DB state unchanged -> DIVERGENT
# ==============================================================================

def test_tool_reports_success_but_db_unchanged_divergent(db_session: Session):
    """Verifies that when a tool reports success but leaves DB state unchanged,
    D-14 flags DIVERGENT and workflow fails without retrying the tool.
    """
    _, order, _ = _setup_order(db_session)

    registry = create_default_tool_registry()
    registry._tools.pop("cancel_order", None)

    call_count = 0
    def fake_canceller(inputs: CancelOrderInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        # Pretend success without modifying DB
        return {
            "id": str(inputs.order_id),
            "order_number": order.order_number,
            "status": "CONFIRMED",
            "cancellation_reason": inputs.reason,
        }

    registry.register(ToolDefinition(
        name="cancel_order",
        description="Fakes cancellation",
        input_schema=CancelOrderInput,
        handler=fake_canceller,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.HIGH,
    ))

    agent = OpsAgent(tool_registry=registry)
    run = agent.run(input_text=f"Please cancel my order {order.order_number}", db=db_session)
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL

    resumed = agent.resume(run_id=run.run_id, approved=True, db=db_session)
    assert resumed.state == WorkflowState.FAILED
    assert "divergent" in (resumed.error or "").lower() or "verification" in (resumed.error or "").lower()
    assert len(resumed.verification_results) == 1
    assert resumed.verification_results[0]["status"] == VerificationStatus.DIVERGENT.value
    # Crucial: Tool was NOT retried on verification failure
    assert call_count == 1


# ==============================================================================
# 8. Target entity missing -> NOT_FOUND
# ==============================================================================

def test_target_entity_missing_not_found(db_session: Session):
    """Verifies that verifying a non-existent entity returns NOT_FOUND status."""
    ver_svc = StateVerificationService()
    non_existent_id = str(uuid.uuid4())

    req = VerificationRequest(
        entity_type="order",
        entity_id=non_existent_id,
        target_state="CANCELLED",
        operation="cancel_order",
    )
    result = ver_svc.verify(session=db_session, request=req)

    assert result.verified is False
    assert result.status == VerificationStatus.NOT_FOUND
    assert result.actual_state == "NOT_FOUND"


# ==============================================================================
# 9. Verification query error -> ERROR
# ==============================================================================

def test_verification_query_error(db_session: Session):
    """Verifies that database errors during verification return status ERROR without crashing."""
    ver_svc = StateVerificationService()
    mock_session = MagicMock(spec=Session)
    mock_session.get.side_effect = RuntimeError("Database connection lost during inspection")
    mock_session.scalar.side_effect = RuntimeError("Database connection lost during inspection")

    req = VerificationRequest(
        entity_type="order",
        entity_id=str(uuid.uuid4()),
        target_state="CANCELLED",
        operation="cancel_order",
    )
    result = ver_svc.verify(session=mock_session, request=req)

    assert result.verified is False
    assert result.status == VerificationStatus.ERROR
    assert result.error is not None
    assert "Database connection lost" in result.error


# ==============================================================================
# 10. High ML risk -> policy approval gate
# ==============================================================================

def test_high_ml_risk_triggers_policy_approval_gate(db_session: Session):
    """Verifies that an order evaluated as HIGH ML risk triggers human approval gate."""
    _, order, _ = _setup_order(db_session, amount=Decimal("8000.00"))

    mock_risk_service = MagicMock(spec=MLRiskService)
    features = RiskFeatureVector(order_amount=8000.0)
    mock_risk_service.assess_order.return_value = RiskAssessmentResult(
        model_version="v1.0.0",
        risk_score=0.82,
        risk_band=RiskBand.HIGH,
        is_high_risk=True,
        features=features,
        contributions=[],
        top_risk_factors=["High value order", "Elevated risk profile"],
        anomaly=AnomalyInfo(is_anomaly=False, anomaly_score=0.2, anomaly_flags=[]),
    )

    agent = OpsAgent(risk_service=mock_risk_service)

    run = agent.run(input_text=f"Please cancel my order {order.order_number}", db=db_session)
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.approval_id is not None
    assert run.risk_assessment is not None
    assert run.risk_assessment["risk_band"] == RiskBand.HIGH.value
    assert run.risk_assessment["risk_score"] == 0.82


# ==============================================================================
# 11. ML anomaly -> policy approval gate
# ==============================================================================

def test_ml_anomaly_triggers_policy_approval_gate(db_session: Session):
    """Verifies that an operational anomaly (e.g. multiple failed payments or severe delay)
    causes policy approval gate to trigger even on lower value orders.
    """
    _, order, pay = _setup_order(db_session, amount=Decimal("1500.00"))

    # Create custom risk service that flags an anomaly
    mock_risk_service = MagicMock(spec=MLRiskService)
    features = RiskFeatureVector(order_amount=1500.0, failed_payment_count=3)
    mock_risk_service.assess_order.return_value = RiskAssessmentResult(
        model_version="v1.0.0",
        risk_score=0.75,
        risk_band=RiskBand.HIGH,
        is_high_risk=True,
        features=features,
        contributions=[],
        top_risk_factors=["Severe payment anomaly"],
        anomaly=AnomalyInfo(
            is_anomaly=True,
            anomaly_score=0.88,
            anomaly_flags=["REPEATED_FAILED_PAYMENT_SPIKE"],
            description="Repeated failed payments before refund request",
        ),
    )

    agent = OpsAgent(risk_service=mock_risk_service)
    run = agent.run(input_text=f"Cancel order {order.order_number}", db=db_session)

    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.approval_id is not None
    assert run.risk_assessment is not None
    assert run.risk_assessment["anomaly"]["is_anomaly"] is True
    assert "REPEATED_FAILED_PAYMENT_SPIKE" in run.risk_assessment["anomaly"]["anomaly_flags"]


# ==============================================================================
# 12. Low risk + normal operation -> existing policy behavior preserved
# ==============================================================================

def test_low_risk_normal_operation_preserves_policy(db_session: Session):
    """Verifies that low-risk read inquiries complete without approval gates."""
    _, order, _ = _setup_order(db_session, amount=Decimal("500.00"))
    agent = OpsAgent()

    run = agent.run(input_text=f"What is the status of my order {order.order_number}?", db=db_session)
    assert run.state == WorkflowState.COMPLETED
    assert run.approval_id is None
    assert run.final_response is not None
    assert order.order_number in run.final_response


# ==============================================================================
# 13. Risk assessment failure -> safe/defined policy behavior
# ==============================================================================

def test_risk_assessment_failure_safe_defined_behavior(db_session: Session):
    """Verifies that if the ML risk model crashes unexpectedly, the agent falls back
    to a safe defined risk assessment and policy evaluation continues safely.
    """
    _, order, _ = _setup_order(db_session, amount=Decimal("1200.00"))

    broken_risk_service = MagicMock(spec=MLRiskService)
    broken_risk_service.assess_order.side_effect = RuntimeError("ML engine GPU memory allocation error")
    broken_risk_service.assess_risk.side_effect = RuntimeError("ML engine GPU memory allocation error")

    agent = OpsAgent(risk_service=broken_risk_service)
    # Cancellation still requires approval under POL-CAN-001 for state-changing action,
    # but does not crash from the broken risk service
    run = agent.run(input_text=f"Please cancel my order {order.order_number}", db=db_session)

    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.risk_assessment is not None
    assert "fallback" in run.risk_assessment["model_version"].lower()


# ==============================================================================
# 14. Retry failure followed by workflow failure -> no false verification success
# ==============================================================================

def test_retry_failure_prevents_false_verification_success(db_session: Session, fast_retry_policy: RetryPolicyConfig):
    """Verifies that when tool execution fails (e.g. retry exhaustion),
    post-action verification is NOT reported as verified.
    """
    _, order, _ = _setup_order(db_session)

    registry = create_default_tool_registry()
    registry._tools.pop("cancel_order", None)

    def failing_canceller(inputs: CancelOrderInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise ConnectionError("Payment gateway network dropped connection")

    registry.register(ToolDefinition(
        name="cancel_order",
        description="Failing canceller",
        input_schema=CancelOrderInput,
        handler=failing_canceller,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.HIGH,
    ))

    agent = OpsAgent(tool_registry=registry)
    run = agent.run(input_text=f"Please cancel my order {order.order_number}", db=db_session)
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL

    resumed = agent.resume(run_id=run.run_id, approved=True, db=db_session)
    assert resumed.state == WorkflowState.FAILED
    # Zero verification results reported because mutation never completed
    assert len(resumed.verification_results) == 0


# ==============================================================================
# 15. Successful mutation -> verification -> COMPLETED
# ==============================================================================

def test_successful_mutation_verification_completed(db_session: Session):
    """Verifies the complete happy path:
    Request -> Approval -> Resilient execution -> State verification -> COMPLETED.
    """
    _, order, _ = _setup_order(db_session, amount=Decimal("2500.00"))
    agent = OpsAgent()

    # Step 1: Request
    run = agent.run(input_text=f"Cancel my order {order.order_number}", db=db_session)
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.approval_id is not None

    # Step 2: Resume
    resumed = agent.resume(run_id=run.run_id, approved=True, db=db_session, reason="Valid customer request")
    assert resumed.state == WorkflowState.COMPLETED
    assert len(resumed.resilience_records) >= 1
    assert len(resumed.verification_results) == 1

    # Verify resilience metadata
    res_rec = next(r for r in resumed.resilience_records if r.get("tool_name") == "cancel_order")
    assert res_rec["tool_name"] == "cancel_order"
    assert res_rec["attempts"] >= 1
    assert res_rec["is_cached"] is False
    assert res_rec["final_status"] == "COMPLETED"

    # Verify verification metadata
    ver = resumed.verification_results[0]
    assert ver["status"] == VerificationStatus.VERIFIED.value
    assert ver["verified"] is True
    assert ver["target_state"] == "CANCELLED"
    assert ver["actual_state"] == "CANCELLED"

    # Verify persistent database state
    db_session.refresh(order)
    assert order.status == OrderStatus.CANCELLED

    # Check checkpoint persistence
    cp = checkpoint_store.get(run.run_id)
    assert cp is not None
    assert cp.state == WorkflowState.COMPLETED
    assert len(cp.resilience_records) >= 1
    assert len(cp.verification_results) == 1
