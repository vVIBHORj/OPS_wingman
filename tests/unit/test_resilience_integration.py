"""Unit and Integration tests for Deliverable D-15: Resilience Layer Integration.

Validates the composition of IdempotencyService and RetryExecutor into ToolRegistry
and OpsAgent workflow:
1. Successful state-changing operation (idempotency record COMPLETED, attempt=1).
2. Transient failure followed by success (retried with backoff, attempt=2).
3. Retry exhaustion (MaxRetriesExceeded -> record FAILED, tool failure).
4. Timeout budget exceeded (TimeoutBudgetExceeded -> record FAILED, tool failure).
5. Non-transient exception is not retried (ValueError -> attempt=1, record FAILED).
6. Same idempotency key executes mutation only once.
7. Duplicate request returns stored response (is_cached=True, attempts=0).
8. Same idempotency key with different request hash produces conflict.
9. Transient failure after mutation does not cause duplicate mutation.
10. Idempotency + retry composition works together.
11. Approved action resumption uses resilience.
12. D-14 verification still executes after resilient successful mutation.
13. Verification divergence is not retried as a tool execution failure.
14. Workflow records retry/idempotency metadata in checkpoints.
15. Existing Phase 1-3 behavior remains unchanged.
16. D-13 risk assessment remains unchanged.
17. Read-only tools are not unnecessarily idempotency-wrapped.
"""

import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional
import pytest
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import simulator
from backend.agents.ops_agent import OpsAgent
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.resilience import (
    IdempotencyService,
    RetryExecutor,
    RetryPolicyConfig,
    ResilientToolExecutor,
    MaxRetriesExceededError,
    TimeoutBudgetExceededError,
    idempotency_service,
    resolve_idempotency_key,
    resolve_scope,
    compute_request_hash,
)
from backend.tools.base import RiskLevel, ToolDefinition, ToolExecutionResult, ToolRegistry, ToolType
from backend.tools.registry import create_default_tool_registry
from backend.verification import (
    StateVerificationService,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    state_verification_service,
)
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import WorkflowRunRecord, WorkflowState
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
        timeout_seconds=2.0,
    )


def _setup_test_order(
    db: Session,
    amount: Decimal = Decimal("1500.00"),
    status: OrderStatus = OrderStatus.CONFIRMED,
) -> tuple[Customer, Order, Payment]:
    cust_id = uuid.uuid4()
    cust = Customer(
        id=cust_id,
        first_name="Anita",
        last_name="Roy",
        email=f"anita.{uuid.uuid4().hex[:6]}@example.com",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
    )
    prod_id = uuid.uuid4()
    prod = Product(
        id=prod_id,
        sku=f"SKU-RES-{uuid.uuid4().hex[:6]}",
        name="Resilience Test Gadget",
        unit_price=amount,
        currency="INR",
        inventory_count=50,
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
    simulator.capture_payment(session=db, payment_id=pay.id, gateway_transaction_id=f"pay_res_{uuid.uuid4().hex[:6]}")
    db.refresh(order)
    return cust, order, pay


class MockMutationInput(BaseModel):
    order_id: str
    action_notes: str = "Resilience test note"


# ==============================================================================
# 1. Successful state-changing operation
# ==============================================================================

def test_successful_state_changing_operation(db_session: Session):
    """Verifies that a state-changing operation executes successfully through the resilience wrapper,
    creates an IdempotencyRecord marked COMPLETED, and records telemetry.
    """
    mutation_count = 0

    def dummy_mutation(order_id: str, action_notes: str = "note") -> Dict[str, Any]:
        nonlocal mutation_count
        mutation_count += 1
        return {"status": "success", "order_id": order_id, "notes": action_notes}

    tool = ToolDefinition(
        name="dummy_cancel",
        description="Cancels order with resilience",
        input_schema=MockMutationInput,
        handler=dummy_mutation,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )

    registry = ToolRegistry()
    registry.register(tool)

    order_id = str(uuid.uuid4())
    key = f"idemp-succ-{uuid.uuid4().hex[:8]}"

    res = registry.execute(
        name="dummy_cancel",
        params={"order_id": order_id, "action_notes": "Cancel first time"},
        context={"db": db_session, "idempotency_key": key},
    )

    assert res.success is True
    assert mutation_count == 1
    assert res.idempotency_key == key
    assert res.is_cached is False
    assert res.attempts == 1
    assert res.data is not None
    assert res.data["status"] == "success"

    # Check that database IdempotencyRecord was created and is COMPLETED
    record = db_session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == key,
            IdempotencyRecord.scope == "tool:dummy_cancel",
        )
    )
    assert record is not None
    assert record.status == IdempotencyStatus.COMPLETED
    assert isinstance(record.response_payload, dict)
    assert record.response_payload["status"] == "success"


# ==============================================================================
# 2. Transient failure followed by success
# ==============================================================================

def test_transient_failure_followed_by_success(db_session: Session, fast_retry_policy: RetryPolicyConfig):
    """Verifies that a transient failure (e.g. OperationalError) is retried,
    eventually succeeds, and records multiple attempts and retry delays.
    """
    call_count = 0

    def flaky_mutation(order_id: str, action_notes: str = "flaky") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OperationalError("Connection dropped by database", params=None, orig=Exception("dropped"))
        return {"status": "recovered", "attempts_taken": call_count}

    tool = ToolDefinition(
        name="flaky_tool",
        description="Flaky mutation tool",
        input_schema=MockMutationInput,
        handler=flaky_mutation,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )

    registry = ToolRegistry()
    registry.register(tool)

    key = f"idemp-flaky-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="flaky_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "Try flaky"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )

    assert res.success is True
    assert call_count == 2
    assert res.attempts == 2
    assert len(res.retry_delays) == 1
    assert res.data is not None
    assert res.data["status"] == "recovered"

    record = db_session.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    )
    assert record is not None
    assert record.status == IdempotencyStatus.COMPLETED


# ==============================================================================
# 3. Retry exhaustion
# ==============================================================================

def test_retry_exhaustion(db_session: Session, fast_retry_policy: RetryPolicyConfig):
    """Verifies that transient errors exceeding max_attempts exhaust retries,
    fail execution, and mark the idempotency record FAILED.
    """
    call_count = 0

    def always_transient_fail(order_id: str, action_notes: str = "fail") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        raise OperationalError("Persistent DB deadlock", params=None, orig=Exception("deadlock"))

    tool = ToolDefinition(
        name="deadlock_tool",
        description="Always fails with transient error",
        input_schema=MockMutationInput,
        handler=always_transient_fail,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )

    registry = ToolRegistry()
    registry.register(tool)

    key = f"idemp-exhaust-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="deadlock_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "Exhaust retries"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )

    assert res.success is False
    # max_attempts=3 -> 3 attempts total
    assert call_count == 3
    assert res.attempts == 3
    assert res.error is not None
    assert "retries exceeded" in res.error.lower() or "deadlock" in res.error.lower()

    record = db_session.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    )
    assert record is not None
    assert record.status == IdempotencyStatus.FAILED


# ==============================================================================
# 4. Timeout budget exceeded
# ==============================================================================

def test_timeout_budget_exceeded(db_session: Session):
    """Verifies that exceeding the timeout budget halts retries and fails the tool."""
    call_count = 0

    def slow_failing_mutation(order_id: str, action_notes: str = "slow") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        time.sleep(0.04)
        raise ConnectionResetError("Connection reset by peer")

    tool = ToolDefinition(
        name="slow_fail_tool",
        description="Slowly fails with transient error",
        input_schema=MockMutationInput,
        handler=slow_failing_mutation,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )

    registry = ToolRegistry()
    registry.register(tool)

    tight_policy = RetryPolicyConfig(
        max_attempts=5,
        initial_delay_seconds=0.03,
        timeout_seconds=0.06,  # Timeout budget will be hit after 1 attempt + delay
    )

    key = f"idemp-timeout-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="slow_fail_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "Hit timeout"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": tight_policy},
    )

    assert res.success is False
    assert res.error is not None
    assert "timeout" in res.error.lower()
    assert res.resilience_metadata is not None
    assert res.resilience_metadata.get("timeout_occurred") is True

    record = db_session.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    )
    assert record is not None
    assert record.status == IdempotencyStatus.FAILED


# ==============================================================================
# 5. Non-transient exception is not retried
# ==============================================================================

def test_non_transient_exception_not_retried(db_session: Session, fast_retry_policy: RetryPolicyConfig):
    """Verifies that non-transient exceptions (ValueError, domain errors) are NOT retried."""
    call_count = 0

    def domain_validation_fail(order_id: str, action_notes: str = "fail") -> Dict[str, Any]:
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid order state: Order has already shipped")

    tool = ToolDefinition(
        name="domain_fail_tool",
        description="Fails immediately with business rule validation",
        input_schema=MockMutationInput,
        handler=domain_validation_fail,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )

    registry = ToolRegistry()
    registry.register(tool)

    key = f"idemp-nontrans-{uuid.uuid4().hex[:8]}"
    res = registry.execute(
        name="domain_fail_tool",
        params={"order_id": str(uuid.uuid4()), "action_notes": "Validation test"},
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )

    assert res.success is False
    assert call_count == 1  # Exactly 1 call, zero retries
    assert res.attempts == 1
    assert res.error is not None
    assert "already shipped" in res.error

    record = db_session.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    )
    assert record is not None
    assert record.status == IdempotencyStatus.FAILED


# ==============================================================================
# 6. Same idempotency key executes mutation only once
# ==============================================================================

def test_same_idempotency_key_executes_mutation_only_once(db_session: Session):
    """Verifies that multiple sequential executions with the same idempotency key
    only invoke the actual mutation handler once.
    """
    mutation_invocations = 0

    def counted_mutation(order_id: str, action_notes: str = "once") -> Dict[str, Any]:
        nonlocal mutation_invocations
        mutation_invocations += 1
        return {"mutation_id": mutation_invocations, "order_id": order_id}

    tool = ToolDefinition(
        name="counted_tool",
        description="Counts mutations",
        input_schema=MockMutationInput,
        handler=counted_mutation,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )

    registry = ToolRegistry()
    registry.register(tool)

    key = f"idemp-once-{uuid.uuid4().hex[:8]}"
    payload = {"order_id": str(uuid.uuid4()), "action_notes": "Once only"}

    res1 = registry.execute(
        name="counted_tool",
        params=payload,
        context={"db": db_session, "idempotency_key": key},
    )
    assert res1.success is True
    assert res1.is_cached is False
    assert mutation_invocations == 1
    assert res1.data is not None
    assert res1.data["mutation_id"] == 1

    # Second execution with exact same key and payload
    res2 = registry.execute(
        name="counted_tool",
        params=payload,
        context={"db": db_session, "idempotency_key": key},
    )
    assert res2.success is True
    assert res2.is_cached is True
    assert res2.attempts == 0
    # The mutation handler was NOT invoked a second time!
    assert mutation_invocations == 1
    assert res2.data is not None
    assert res2.data["mutation_id"] == 1


# ==============================================================================
# 7. Duplicate request returns stored response
# ==============================================================================

def test_duplicate_request_returns_stored_response(db_session: Session):
    """Verifies that an identical request replaying the same idempotency key
    returns the exact cached payload stored from the first run.
    """
    _, order, _ = _setup_test_order(db_session)
    registry = create_default_tool_registry()

    order_id_str = str(order.id)
    key = f"idemp-cancel-{order_id_str}"

    res1 = registry.execute(
        name="cancel_order",
        params={"order_id": order_id_str, "reason": "Customer changed mind"},
        context={"db": db_session, "idempotency_key": key, "approved": True},
    )
    assert res1.success is True
    assert res1.is_cached is False
    assert res1.data is not None
    orig_cancelled_at = res1.data.get("cancelled_at")

    # Replay identical request
    res2 = registry.execute(
        name="cancel_order",
        params={"order_id": order_id_str, "reason": "Customer changed mind"},
        context={"db": db_session, "idempotency_key": key, "approved": True},
    )
    assert res2.success is True
    assert res2.is_cached is True
    assert res2.data is not None
    assert res2.data.get("cancelled_at") == orig_cancelled_at
    assert res2.resilience_metadata is not None
    assert res2.resilience_metadata["is_cached"] is True


# ==============================================================================
# 8. Same idempotency key with different request hash produces conflict
# ==============================================================================

def test_same_key_with_different_hash_produces_conflict(db_session: Session):
    """Verifies that presenting a different request payload with an existing idempotency key
    returns an idempotency conflict.
    """
    tool = ToolDefinition(
        name="keyed_tool",
        description="Tool for conflict testing",
        input_schema=MockMutationInput,
        handler=lambda order_id, action_notes="": {"ok": True},
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    key = f"idemp-conflict-{uuid.uuid4().hex[:8]}"

    res1 = registry.execute(
        name="keyed_tool",
        params={"order_id": "order-123", "action_notes": "Note A"},
        context={"db": db_session, "idempotency_key": key},
    )
    assert res1.success is True

    # Same key, different parameters
    res2 = registry.execute(
        name="keyed_tool",
        params={"order_id": "order-123", "action_notes": "Note B (DIFFERENT)"},
        context={"db": db_session, "idempotency_key": key},
    )
    assert res2.success is False
    assert res2.error is not None
    assert "conflict" in res2.error.lower() or "mismatch" in res2.error.lower()
    assert res2.resilience_metadata is not None
    assert res2.resilience_metadata.get("conflict") is True


# ==============================================================================
# 9. Transient failure after mutation does not cause duplicate mutation
# ==============================================================================

def test_transient_failure_after_mutation_does_not_cause_duplicate_mutation(db_session: Session):
    """Verifies that if a mutation has completed and the idempotency record is COMPLETED,
    any subsequent replay/retry returns the cached response without running the mutation again.
    """
    mutation_runs = 0

    def mutating_operation(order_id: str, action_notes: str = "transfer") -> Dict[str, Any]:
        nonlocal mutation_runs
        mutation_runs += 1
        return {"action": "transferred", "run": mutation_runs}

    tool = ToolDefinition(
        name="transfer_tool",
        description="Simulates financial transfer",
        input_schema=MockMutationInput,
        handler=mutating_operation,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    key = f"idemp-postmut-{uuid.uuid4().hex[:8]}"
    payload = {"order_id": str(uuid.uuid4()), "action_notes": "Transfer $100"}

    # Run 1: Mutation executes successfully
    res1 = registry.execute(tool.name, payload, context={"db": db_session, "idempotency_key": key})
    assert res1.success is True
    assert mutation_runs == 1

    # Simulate client timeout / retry reconnecting with the same idempotency key
    res2 = registry.execute(tool.name, payload, context={"db": db_session, "idempotency_key": key})
    assert res2.success is True
    assert res2.is_cached is True
    assert mutation_runs == 1  # Crucial: zero duplicate execution!


# ==============================================================================
# 10. Idempotency + retry composition works together
# ==============================================================================

def test_idempotency_and_retry_composition_work_together(
    db_session: Session, fast_retry_policy: RetryPolicyConfig
):
    """Verifies that transient retry recovers, completes idempotency record,
    and subsequent replay of the same key returns the cached result without retry.
    """
    attempts_seen = 0

    def transient_then_done(order_id: str, action_notes: str = "comp") -> Dict[str, Any]:
        nonlocal attempts_seen
        attempts_seen += 1
        if attempts_seen == 1:
            raise OperationalError("Transient glitch", None, Exception("glitch"))
        return {"result": "final_success", "attempts": attempts_seen}

    tool = ToolDefinition(
        name="composed_tool",
        description="Composed resilience test tool",
        input_schema=MockMutationInput,
        handler=transient_then_done,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
    )
    registry = ToolRegistry()
    registry.register(tool)

    key = f"idemp-comp-{uuid.uuid4().hex[:8]}"
    payload = {"order_id": str(uuid.uuid4()), "action_notes": "Compose test"}

    # First execution: fails on attempt 1, retries and succeeds on attempt 2
    res1 = registry.execute(
        name="composed_tool",
        params=payload,
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )
    assert res1.success is True
    assert res1.attempts == 2
    assert res1.is_cached is False
    assert attempts_seen == 2

    # Second execution: immediately returns cached response without invoking handler or retry
    res2 = registry.execute(
        name="composed_tool",
        params=payload,
        context={"db": db_session, "idempotency_key": key, "retry_policy": fast_retry_policy},
    )
    assert res2.success is True
    assert res2.is_cached is True
    assert res2.attempts == 0
    assert attempts_seen == 2  # Handler never ran again


# ==============================================================================
# 11. Approved action resumption uses resilience
# ==============================================================================

def test_approved_action_resumption_uses_resilience(db_session: Session):
    """Verifies that resuming an approved action in OpsAgent executes through
    the resilience wrapper, creating an idempotency record and persisting resilience telemetry.
    """
    _, order, _ = _setup_test_order(db_session, amount=Decimal("3500.00"))
    agent = OpsAgent()

    # Step 1: Request cancellation (triggers High Risk approval)
    run_record = agent.run(
        input_text=f"Please cancel order {order.order_number}",
        db=db_session,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run_record.approval_id is not None

    # Step 2: Resume with approval
    resumed = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
        reason="Approved by supervisor",
    )
    assert resumed.state == WorkflowState.COMPLETED
    assert len(resumed.resilience_records) >= 1

    # Check resilience telemetry
    res_rec = resumed.resilience_records[0]
    assert "idempotency_key" in res_rec
    assert res_rec["tool_name"] == "cancel_order"
    assert res_rec["attempts"] >= 1
    assert res_rec["is_cached"] is False

    # Check that the idempotency record exists in the database
    idemp_rec = db_session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == res_rec["idempotency_key"]
        )
    )
    assert idemp_rec is not None
    assert idemp_rec.status == IdempotencyStatus.COMPLETED


# ==============================================================================
# 12. D-14 verification still executes after resilient successful mutation
# ==============================================================================

def test_d14_verification_still_executes_after_resilient_mutation(db_session: Session):
    """Verifies that D-14 post-action verification executes and succeeds
    following a resilient tool mutation.
    """
    _, order, _ = _setup_test_order(db_session, amount=Decimal("2000.00"))
    agent = OpsAgent()

    run_record = agent.run(
        input_text=f"Cancel my order {order.order_number}",
        db=db_session,
    )
    resumed = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
        reason="Verified valid customer cancellation",
    )

    assert resumed.state == WorkflowState.COMPLETED
    assert len(resumed.verification_results) == 1
    ver = resumed.verification_results[0]
    assert ver["status"] == VerificationStatus.VERIFIED.value
    assert ver["verified"] is True
    assert ver["entity_type"] == "order"
    assert ver["entity_id"] == str(order.id)
    assert ver["target_state"] == "CANCELLED"


# ==============================================================================
# 13. Verification divergence is not retried as a tool execution failure
# ==============================================================================

def test_verification_divergence_not_retried_as_tool_failure(db_session: Session):
    """Verifies that when D-14 reports DIVERGENT state (tool reported success but DB state unchanged),
    the workflow fails without automatically retrying the tool.
    """
    mutation_invocations = 0

    _, order, _ = _setup_test_order(db_session)

    from backend.tools.schemas import CancelOrderInput
    def fake_canceller(inputs: CancelOrderInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        nonlocal mutation_invocations
        mutation_invocations += 1
        # Pretend tool succeeded, but do NOT actually update order status in DB!
        return {
            "id": str(inputs.order_id),
            "order_number": order.order_number,
            "status": "CONFIRMED",
            "cancellation_reason": inputs.reason,
        }

    registry = create_default_tool_registry()
    registry._tools.pop("cancel_order", None)
    registry.register(ToolDefinition(
        name="cancel_order",
        description="Cancels an order",
        input_schema=CancelOrderInput,
        handler=fake_canceller,
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.HIGH,
    ))

    agent = OpsAgent(tool_registry=registry)

    # 1. Run agent, triggers WAITING_FOR_APPROVAL
    run_record = agent.run(
        input_text=f"Please cancel my order {order.order_number}",
        db=db_session,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL

    # 2. Resuming action
    resumed = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
        reason="Approved fake cancel",
    )

    # State must be FAILED due to verification divergence
    assert resumed.state == WorkflowState.FAILED
    assert resumed.error is not None
    assert "divergence" in resumed.error.lower() or "verification" in resumed.error.lower()
    assert len(resumed.verification_results) == 1
    assert resumed.verification_results[0]["status"] == VerificationStatus.DIVERGENT.value
    # The tool was executed once, NOT retried upon verification failure!
    assert mutation_invocations == 1


# ==============================================================================
# 14. Workflow records retry/idempotency metadata
# ==============================================================================

def test_workflow_records_resilience_metadata_in_checkpoints(db_session: Session):
    """Verifies that WorkflowRunRecord and checkpoints persist rich resilience metadata."""
    _, order, _ = _setup_test_order(db_session)
    agent = OpsAgent()

    run = agent.run(input_text=f"Please cancel my order {order.order_number}", db=db_session)
    resumed = agent.resume(run_id=run.run_id, approved=True, db=db_session)

    # Check WorkflowRunRecord
    assert hasattr(resumed, "resilience_records")
    assert len(resumed.resilience_records) >= 1
    meta = resumed.resilience_records[0]
    assert "idempotency_key" in meta
    assert "attempts" in meta
    assert "tool_name" in meta
    assert meta["tool_name"] == "cancel_order"

    # Check persistent checkpoint
    cp = checkpoint_store.get(run.run_id)
    assert cp is not None
    assert len(cp.resilience_records) >= 1
    assert cp.resilience_records[0]["idempotency_key"] == meta["idempotency_key"]


# ==============================================================================
# 15. Existing Phase 1-3 behavior remains unchanged
# ==============================================================================

def test_existing_phase1_3_read_operations_remain_unchanged(db_session: Session):
    """Verifies that Phase 1-3 read workflows (e.g. order inquiry) continue
    to execute cleanly through OpsAgent.
    """
    _, order, _ = _setup_test_order(db_session)
    agent = OpsAgent()

    run = agent.run(
        input_text=f"What is the status of my order {order.order_number}?",
        db=db_session,
    )
    assert run.state == WorkflowState.COMPLETED
    assert run.approval_id is None
    assert run.final_response is not None
    assert order.order_number in run.final_response or "confirmed" in run.final_response.lower()


# ==============================================================================
# 16. D-13 risk assessment remains unchanged
# ==============================================================================

def test_d13_risk_assessment_remains_unchanged(db_session: Session):
    """Verifies that high-risk requests still trigger ML risk scoring and require approval."""
    _, order, _ = _setup_test_order(db_session, amount=Decimal("9500.00"))
    agent = OpsAgent()

    run = agent.run(
        input_text=f"Cancel order {order.order_number} immediately",
        db=db_session,
    )
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.approval_id is not None
    assert run.risk_assessment is not None
    assert run.risk_assessment.get("risk_score") is not None
    assert float(run.risk_assessment["risk_score"]) > 0.0


# ==============================================================================
# 17. Read-only tools are not unnecessarily idempotency-wrapped
# ==============================================================================

def test_read_only_tools_bypass_idempotency_records(db_session: Session):
    """Verifies that ToolType.READ queries (e.g. get_order) do not generate
    IdempotencyRecord entries in the database.
    """
    _, order, _ = _setup_test_order(db_session)
    registry = create_default_tool_registry()

    initial_count = db_session.scalar(
        select(func.count()).select_from(IdempotencyRecord)
    ) or 0

    res = registry.execute(
        name="get_order",
        params={"order_id": str(order.id)},
        context={"db": db_session},
    )

    assert res.success is True
    assert res.data is not None
    assert res.data["order_number"] == order.order_number
    assert res.is_cached is False
    assert res.idempotency_key is None  # Read tools do not assign idempotency keys

    after_count = db_session.scalar(
        select(func.count()).select_from(IdempotencyRecord)
    ) or 0

    # No idempotency records created for read tools!
    assert after_count == initial_count
