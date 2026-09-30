"""Unit tests for IdempotencyRecord database model and constraints (Phase 4 - Deliverable D-15)."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import IdempotencyRecord, IdempotencyStatus


def test_create_idempotency_record(db_session: Session):
    """Verifies creation of an IdempotencyRecord with default values and timestamps."""
    key = f"idemp-test-{uuid.uuid4().hex[:8]}"
    record = IdempotencyRecord(
        idempotency_key=key,
        scope="api:order_cancellation",
        request_hash="sha256:abc123mockhash",
        status=IdempotencyStatus.PROCESSING,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)

    assert record.id is not None
    assert isinstance(record.id, uuid.UUID)
    assert record.idempotency_key == key
    assert record.scope == "api:order_cancellation"
    assert record.request_hash == "sha256:abc123mockhash"
    assert record.status == IdempotencyStatus.PROCESSING
    assert record.response_payload is None
    assert record.created_at is not None
    assert record.updated_at is not None
    assert record.expires_at is not None


def test_idempotency_scope_key_uniqueness(db_session: Session):
    """Verifies that inserting duplicate (scope, idempotency_key) tuples is rejected by unique constraint."""
    key = "unique-key-12345"
    scope = "webhook:razorpay"

    rec1 = IdempotencyRecord(
        idempotency_key=key,
        scope=scope,
        status=IdempotencyStatus.COMPLETED,
        response_payload={"status": "success", "tx_id": "tx_001"},
    )
    db_session.add(rec1)
    db_session.commit()

    rec2 = IdempotencyRecord(
        idempotency_key=key,
        scope=scope,
        status=IdempotencyStatus.PROCESSING,
    )
    db_session.add(rec2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_idempotency_same_key_different_scopes_allowed(db_session: Session):
    """Verifies that the same idempotency key can be safely used across distinct scopes."""
    shared_key = "evt-shared-999"

    rec1 = IdempotencyRecord(
        idempotency_key=shared_key,
        scope="webhook:shipment",
        status=IdempotencyStatus.COMPLETED,
        response_payload={"tracking_status": "DELIVERED"},
    )
    rec2 = IdempotencyRecord(
        idempotency_key=shared_key,
        scope="api:manual_sync",
        status=IdempotencyStatus.PROCESSING,
    )
    db_session.add_all([rec1, rec2])
    db_session.commit()

    records = db_session.scalars(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == shared_key)
    ).all()
    assert len(records) == 2
    scopes = {r.scope for r in records}
    assert scopes == {"webhook:shipment", "api:manual_sync"}


def test_idempotency_status_transitions_and_payload(db_session: Session):
    """Verifies updating idempotency status and attaching cached JSON response payload."""
    key = f"idemp-trans-{uuid.uuid4().hex[:8]}"
    record = IdempotencyRecord(
        idempotency_key=key,
        scope="agent:refund_action",
        status=IdempotencyStatus.PROCESSING,
    )
    db_session.add(record)
    db_session.commit()

    # Transition to COMPLETED with response payload
    record.status = IdempotencyStatus.COMPLETED
    record.response_payload = {
        "action": "refund_order",
        "refund_id": "rfnd_998877",
        "amount": 1500.0,
        "verified": True,
    }
    db_session.commit()
    db_session.refresh(record)

    assert record.status == IdempotencyStatus.COMPLETED
    payload = record.response_payload
    assert payload is not None
    assert payload["refund_id"] == "rfnd_998877"
    assert payload["verified"] is True
