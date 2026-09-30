"""Unit tests for IdempotencyService (Phase 4 - Deliverable D-15)."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import IdempotencyRecord, IdempotencyStatus
from backend.resilience.idempotency import (
    IdempotencyService,
    IdempotencyRecordNotFoundError,
    IdempotencyRequestHashMismatchError,
    IdempotencyInvalidStateTransitionError,
)


@pytest.fixture
def service() -> IdempotencyService:
    return IdempotencyService()


def test_acquire_creates_processing_record(db_session: Session, service: IdempotencyService):
    """1. Verifies that first-time acquire creates a PROCESSING record and returns is_acquired=True."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:orders"

    result = service.acquire(db_session, idempotency_key=key, scope=scope)

    assert result.is_acquired is True
    assert result.owns_execution is True
    assert result.status == IdempotencyStatus.PROCESSING
    assert result.idempotency_key == key
    assert result.scope == scope
    assert result.cached_response is None
    assert result.is_cached is False

    # Check database state
    record = db_session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    assert record is not None
    assert record.status == IdempotencyStatus.PROCESSING


def test_second_acquire_returns_existing_processing_record(db_session: Session, service: IdempotencyService):
    """2. Verifies that acquiring an in-flight key returns is_acquired=False with status PROCESSING."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:payments"

    res1 = service.acquire(db_session, idempotency_key=key, scope=scope)
    assert res1.is_acquired is True

    res2 = service.acquire(db_session, idempotency_key=key, scope=scope)
    assert res2.is_acquired is False
    assert res2.owns_execution is False
    assert res2.status == IdempotencyStatus.PROCESSING
    assert res2.is_processing is True
    assert res2.cached_response is None


def test_completed_record_returns_cached_response(db_session: Session, service: IdempotencyService):
    """3. Verifies that acquiring a COMPLETED record returns cached_response without re-executing."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "agent:refund"
    payload = {"refund_id": "rfnd_123", "amount": 2500.0, "success": True}

    service.acquire(db_session, idempotency_key=key, scope=scope)
    service.complete(db_session, idempotency_key=key, scope=scope, response_payload=payload)

    # Subsequent acquisition
    res = service.acquire(db_session, idempotency_key=key, scope=scope)
    assert res.is_acquired is False
    assert res.status == IdempotencyStatus.COMPLETED
    assert res.is_cached is True
    assert res.cached_response == payload


def test_complete_transitions_processing_to_completed(db_session: Session, service: IdempotencyService):
    """4. Verifies complete() transitions PROCESSING to COMPLETED and stores payload."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:shipments"
    payload = {"shipment_id": "shp_abc", "tracking_number": "TRK-999"}

    service.acquire(db_session, idempotency_key=key, scope=scope)
    record = service.complete(db_session, idempotency_key=key, scope=scope, response_payload=payload)

    assert record.status == IdempotencyStatus.COMPLETED
    assert record.response_payload == payload

    # Re-fetch via get()
    resp = service.get(db_session, idempotency_key=key, scope=scope)
    assert resp is not None
    assert resp.status == IdempotencyStatus.COMPLETED
    assert resp.response_payload == payload


def test_fail_transitions_processing_to_failed(db_session: Session, service: IdempotencyService):
    """5. Verifies fail() transitions PROCESSING to FAILED and stores error details."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:tickets"
    error_payload = {"error": "Gateway Timeout", "code": 504}

    service.acquire(db_session, idempotency_key=key, scope=scope)
    record = service.fail(db_session, idempotency_key=key, scope=scope, response_payload=error_payload)

    assert record.status == IdempotencyStatus.FAILED
    assert record.response_payload == error_payload

    # Re-fetch via get()
    resp = service.get(db_session, idempotency_key=key, scope=scope)
    assert resp is not None
    assert resp.status == IdempotencyStatus.FAILED
    assert resp.response_payload == error_payload


def test_missing_record_on_complete_is_explicit_failure(db_session: Session, service: IdempotencyService):
    """6. Verifies complete() on non-existent record raises IdempotencyRecordNotFoundError."""
    with pytest.raises(IdempotencyRecordNotFoundError):
        service.complete(db_session, idempotency_key="missing-key", scope="api:test", response_payload={})


def test_missing_record_on_fail_is_explicit_failure(db_session: Session, service: IdempotencyService):
    """7. Verifies fail() on non-existent record raises IdempotencyRecordNotFoundError."""
    with pytest.raises(IdempotencyRecordNotFoundError):
        service.fail(db_session, idempotency_key="missing-key", scope="api:test", response_payload={})


def test_same_key_different_scopes_are_independent(db_session: Session, service: IdempotencyService):
    """8. Verifies that identical keys in different scopes can be acquired and completed independently."""
    shared_key = f"shared-{uuid.uuid4().hex[:8]}"
    scope_a = "webhook:razorpay"
    scope_b = "api:cancellation"

    res_a = service.acquire(db_session, idempotency_key=shared_key, scope=scope_a)
    res_b = service.acquire(db_session, idempotency_key=shared_key, scope=scope_b)

    assert res_a.is_acquired is True
    assert res_b.is_acquired is True

    service.complete(db_session, idempotency_key=shared_key, scope=scope_a, response_payload={"source": "a"})
    service.complete(db_session, idempotency_key=shared_key, scope=scope_b, response_payload={"source": "b"})

    get_a = service.get(db_session, idempotency_key=shared_key, scope=scope_a)
    get_b = service.get(db_session, idempotency_key=shared_key, scope=scope_b)

    assert get_a is not None and get_a.response_payload == {"source": "a"}
    assert get_b is not None and get_b.response_payload == {"source": "b"}


def test_request_hash_is_persisted(db_session: Session, service: IdempotencyService):
    """9. Verifies request_hash is stored and returned on subsequent lookups."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:orders"
    req_hash = "sha256:d8249823f9823f8"

    result = service.acquire(db_session, idempotency_key=key, scope=scope, request_hash=req_hash)
    assert result.request_hash == req_hash

    fetched = service.get(db_session, idempotency_key=key, scope=scope)
    assert fetched is not None
    assert fetched.request_hash == req_hash


def test_request_hash_conflict_is_rejected(db_session: Session, service: IdempotencyService):
    """10. Verifies attempting to reuse key with a conflicting request_hash raises IdempotencyRequestHashMismatchError."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:payments"

    service.acquire(db_session, idempotency_key=key, scope=scope, request_hash="hash_AAA")

    with pytest.raises(IdempotencyRequestHashMismatchError) as exc_info:
        service.acquire(db_session, idempotency_key=key, scope=scope, request_hash="hash_BBB")

    assert "previously registered with a different request hash" in str(exc_info.value)


def test_duplicate_acquisition_does_not_create_two_records(db_session: Session, service: IdempotencyService):
    """11. Verifies database contains exactly one record after multiple acquisition attempts."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:actions"

    service.acquire(db_session, idempotency_key=key, scope=scope)
    service.acquire(db_session, idempotency_key=key, scope=scope)
    service.acquire(db_session, idempotency_key=key, scope=scope)

    records = db_session.scalars(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
    ).all()
    assert len(records) == 1


def test_failed_record_is_returned_as_failed(db_session: Session, service: IdempotencyService):
    """12. Verifies that acquiring a FAILED record returns is_acquired=False with status FAILED."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:sync"
    err = {"msg": "Permanent failure"}

    service.acquire(db_session, idempotency_key=key, scope=scope)
    service.fail(db_session, idempotency_key=key, scope=scope, response_payload=err)

    res = service.acquire(db_session, idempotency_key=key, scope=scope)
    assert res.is_acquired is False
    assert res.status == IdempotencyStatus.FAILED
    assert res.is_failed is True
    assert res.cached_response == err


def test_expiration_handling(db_session: Session, service: IdempotencyService):
    """13. Verifies that expired records are re-acquired with status PROCESSING."""
    key = f"key-{uuid.uuid4().hex[:8]}"
    scope = "api:ephemeral"

    # Create record that has already expired
    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
    record = IdempotencyRecord(
        idempotency_key=key,
        scope=scope,
        status=IdempotencyStatus.COMPLETED,
        response_payload={"old": "data"},
        expires_at=past_expiry,
    )
    db_session.add(record)
    db_session.commit()

    # Re-acquire with new expiry
    new_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    res = service.acquire(db_session, idempotency_key=key, scope=scope, expires_at=new_expiry)

    assert res.is_acquired is True
    assert res.is_expired is True
    assert res.status == IdempotencyStatus.PROCESSING
    assert res.cached_response is None

    # Database record updated
    updated = service.get_record(db_session, idempotency_key=key, scope=scope)
    assert updated is not None
    assert updated.status == IdempotencyStatus.PROCESSING
    assert updated.response_payload is None


def test_concurrent_acquisition_handling(db_session: Session, service: IdempotencyService):
    """14. Verifies graceful recovery and session rollback when an IntegrityError simulates a race condition."""
    key = f"race-key-{uuid.uuid4().hex[:8]}"
    scope = "api:race"

    # 1. Pre-insert the winning record to exist in DB
    winner = IdempotencyRecord(
        idempotency_key=key,
        scope=scope,
        status=IdempotencyStatus.PROCESSING,
    )
    db_session.add(winner)
    db_session.commit()

    # 2. Simulate a racer thread that tried to insert new_record and hit IntegrityError
    # We patch session.commit to simulate IntegrityError on commit of second attempt
    original_commit = db_session.commit
    call_count = 0

    def mock_commit():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise IntegrityError("mock unique violation", orig=Exception(), params={})
        return original_commit()

    # Simulate acquisition on the same key with the simulated race condition
    with patch.object(db_session, "commit", side_effect=mock_commit):
        res = service.acquire(db_session, idempotency_key=key, scope=scope)

    assert res.is_acquired is False
    assert res.status == IdempotencyStatus.PROCESSING
    assert res.idempotency_key == key
