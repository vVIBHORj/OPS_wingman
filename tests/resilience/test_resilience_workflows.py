"""Resilience workflow tests for OpsWingman (Phase 4 - Deliverables D-14, D-15).

Verifies real-world resilience patterns:
- Idempotency under duplicate and replayed requests
- In-flight execution locking and hash mismatch detection
- Retry backoff, transient error recovery, and failure recovery
- Immediate failure on non-transient errors without retry loops
- State verification detecting divergence between reported tool success and persisted DB state
"""

import uuid
from decimal import Decimal
from typing import Any, Dict

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.resilience import (
    IdempotencyRequestHashMismatchError,
    IdempotencyService,
    MaxRetriesExceededError,
    ResilientToolExecutor,
    RetryExecutor,
    RetryPolicyConfig,
    TimeoutBudgetExceededError,
)
from backend.tools.base import RiskLevel, ToolDefinition, ToolType
from backend.verification.schemas import VerificationStatus
from backend.verification.service import StateVerificationService
from database.models import Customer, IdempotencyRecord, IdempotencyStatus, Order, OrderStatus

# ==============================================================================
# 1. Idempotency Under Duplicate / Replayed Requests
# ==============================================================================


def test_duplicate_request_replays_cached_output_without_second_mutation(db_session: Session):
    """Verifies that executing a mutating operation with an identical idempotency key
    returns the cached response without invoking the mutation function a second time.
    """
    mutation_invocations = 0

    def mutating_operation(inputs, context=None) -> Dict[str, Any]:
        nonlocal mutation_invocations
        mutation_invocations += 1
        return {"mutation_id": mutation_invocations, "order_id": inputs.order_id}

    from pydantic import BaseModel

    class InputSchema(BaseModel):
        order_id: str

    tool = ToolDefinition(
        name="cancel_order",
        description="Cancels an order",
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.HIGH,
        input_schema=InputSchema,
        handler=mutating_operation,
    )

    executor = ResilientToolExecutor(
        idempotency_service=IdempotencyService(),
        retry_executor=RetryExecutor(),
    )

    shared_key = f"idemp-test-{uuid.uuid4().hex[:8]}"
    ctx = {
        "db": db_session,
        "idempotency_key": shared_key,
        "idempotency_scope": "order:cancellation",
        "approved": True,
    }

    # Call 1: Must execute mutation
    res1 = executor.execute(tool, InputSchema(order_id="ord-100"), context=ctx)
    assert res1.success is True
    assert res1.data["mutation_id"] == 1
    assert mutation_invocations == 1

    # Verify IdempotencyRecord is marked COMPLETED in database
    rec = db_session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == shared_key,
            IdempotencyRecord.scope == "order:cancellation",
        )
    )
    assert rec is not None
    assert rec.status == IdempotencyStatus.COMPLETED

    # Call 2: Replay must return cached response with ZERO additional mutation
    res2 = executor.execute(tool, InputSchema(order_id="ord-100"), context=ctx)
    assert res2.success is True
    assert res2.data["mutation_id"] == 1
    assert mutation_invocations == 1


def test_in_flight_concurrent_acquisition_returns_processing_status(db_session: Session):
    """Verifies that attempting to acquire a key currently in PROCESSING state
    fails acquisition, returning owns_execution=False.
    """
    idemp_service = IdempotencyService()
    key = f"key-inflight-{uuid.uuid4().hex[:8]}"
    scope = "payment:refund"

    # Step 1: Initial acquire succeeds
    acquire1 = idemp_service.acquire(db_session, idempotency_key=key, scope=scope)
    assert acquire1.is_acquired is True
    assert acquire1.owns_execution is True
    assert acquire1.status == IdempotencyStatus.PROCESSING

    # Step 2: Concurrent acquire while still PROCESSING returns is_acquired=False
    acquire2 = idemp_service.acquire(db_session, idempotency_key=key, scope=scope)
    assert acquire2.is_acquired is False
    assert acquire2.owns_execution is False
    assert acquire2.is_processing is True
    assert acquire2.cached_response is None


def test_conflicting_request_hash_raises_mismatch_error(db_session: Session):
    """Verifies that submitting a different request payload with an already-used
    idempotency key raises an IdempotencyRequestHashMismatchError.
    """
    idemp_service = IdempotencyService()
    key = f"key-hash-{uuid.uuid4().hex[:8]}"
    scope = "order:cancel"

    # Acquire with initial hash
    idemp_service.acquire(
        db_session,
        idempotency_key=key,
        scope=scope,
        request_hash="sha256:initial_payload_hash",
    )

    # Acquire with conflicting hash
    with pytest.raises(IdempotencyRequestHashMismatchError):
        idemp_service.acquire(
            db_session,
            idempotency_key=key,
            scope=scope,
            request_hash="sha256:conflicting_payload_hash",
        )


# ==============================================================================
# 2. Retry Behavior and Failure Recovery
# ==============================================================================


def test_transient_error_recovers_after_retry():
    """Verifies that transient errors (e.g. ConnectionError) trigger retry attempts
    and succeed when the operation recovers on attempt 2.
    """
    attempts = 0

    def unreliable_service():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("Temporary carrier network drop")
        return {"status": "DELIVERED", "attempts": attempts}

    policy = RetryPolicyConfig(
        max_attempts=3,
        initial_delay_seconds=0.001,
        max_delay_seconds=0.01,
        backoff_multiplier=2.0,
    )
    executor = RetryExecutor(default_policy=policy)

    result = executor.execute(unreliable_service, policy=policy)
    assert result == {"status": "DELIVERED", "attempts": 2}
    assert attempts == 2


def test_permanent_transient_failure_exhausts_retries():
    """Verifies that a permanent transient failure exhausts all configured retry attempts
    and raises MaxRetriesExceededError with full telemetry.
    """
    invocations = 0

    def permanently_down_service():
        nonlocal invocations
        invocations += 1
        raise ConnectionError("Gateway completely unreachable")

    policy = RetryPolicyConfig(
        max_attempts=3,
        initial_delay_seconds=0.001,
        max_delay_seconds=0.01,
    )
    executor = RetryExecutor(default_policy=policy)

    with pytest.raises(MaxRetriesExceededError) as exc_info:
        executor.execute(permanently_down_service, policy=policy)

    assert len(exc_info.value.attempts) == 3
    assert invocations == 3


def test_non_transient_error_fails_immediately_without_retries():
    """Verifies that non-transient validation errors (e.g. ValueError) fail on attempt 1
    without executing retries.
    """
    invocations = 0

    def validating_service():
        nonlocal invocations
        invocations += 1
        raise ValueError("Invalid order status: cannot cancel delivered order")

    policy = RetryPolicyConfig(max_attempts=5, initial_delay_seconds=0.001)
    executor = RetryExecutor(default_policy=policy)

    with pytest.raises(ValueError, match="Invalid order status"):
        executor.execute(validating_service, policy=policy)

    assert invocations == 1


def test_timeout_budget_exceeded_aborts_retry_loop():
    """Verifies that when an operation exceeds its configured timeout budget,
    further retries are aborted and TimeoutBudgetExceededError is raised.
    """
    invocations = 0

    def slow_failing_service():
        nonlocal invocations
        invocations += 1
        raise ConnectionError("Network timeout")

    # Policy with 0.05s timeout budget
    policy = RetryPolicyConfig(
        max_attempts=10,
        initial_delay_seconds=0.05,
        timeout_seconds=0.04,
    )
    executor = RetryExecutor(default_policy=policy)

    with pytest.raises(TimeoutBudgetExceededError):
        executor.execute(slow_failing_service, policy=policy)


# ==============================================================================
# 3. Post-Action State Verification & Divergence Detection
# ==============================================================================


def test_verification_detects_ghost_success_divergence(db_session: Session):
    """Verifies that when a tool reports success but the database entity state
    was never modified (or rolled back), StateVerificationService detects DIVERGENT state.
    """
    cust = Customer(
        id=uuid.uuid4(),
        first_name="Ghost",
        last_name="Test",
        email=f"ghost.{uuid.uuid4().hex[:6]}@example.com",
    )
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-GHOST-{uuid.uuid4().hex[:6].upper()}",
        customer_id=cust.id,
        status=OrderStatus.PENDING,
        total_amount=Decimal("1500.00"),
    )
    db_session.add_all([cust, order])
    db_session.commit()

    verifier = StateVerificationService()

    # Tool execution claims order was cancelled, but DB status is still PENDING
    result = verifier.verify_order_cancellation(
        session=db_session,
        order_id=order.id,
    )

    assert result.verified is False
    assert result.status == VerificationStatus.DIVERGENT
    assert result.target_state == OrderStatus.CANCELLED.value
    assert result.actual_state == OrderStatus.PENDING.value
    assert any(
        "Order status mismatch: expected 'CANCELLED'" in d
        for d in result.discrepancies
    )


def test_verification_detects_missing_entity(db_session: Session):
    """Verifies that verifying a non-existent entity reports VerificationStatus.NOT_FOUND."""
    verifier = StateVerificationService()
    missing_id = uuid.uuid4()

    result = verifier.verify_order_cancellation(
        session=db_session,
        order_id=missing_id,
    )

    assert result.verified is False
    assert result.status == VerificationStatus.NOT_FOUND


def test_verification_confirms_valid_state_persistence(db_session: Session):
    """Verifies that when the persisted database state matches expected outcome,
    StateVerificationService reports VerificationStatus.VERIFIED.
    """
    cust = Customer(
        id=uuid.uuid4(),
        first_name="Verified",
        last_name="User",
        email=f"ver.{uuid.uuid4().hex[:6]}@example.com",
    )
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-VER-{uuid.uuid4().hex[:6].upper()}",
        customer_id=cust.id,
        status=OrderStatus.CANCELLED,
        total_amount=Decimal("1500.00"),
        cancellation_reason="Customer request",
    )
    db_session.add_all([cust, order])
    db_session.commit()

    verifier = StateVerificationService()
    result = verifier.verify_order_cancellation(
        session=db_session,
        order_id=order.id,
        expected_reason="Customer request",
    )

    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED
    assert len(result.discrepancies) == 0
