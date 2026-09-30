"""Durable Idempotency Service backed by PostgreSQL/SQLAlchemy (Phase 4 - Deliverable D-15).

Guarantees exactly-once execution semantics across distributed workers, webhooks,
API requests, and agent tool actions using durable database unique constraints.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.enums import IdempotencyStatus
from database.models.idempotency import IdempotencyRecord
from backend.resilience.schemas import (
    IdempotencyAcquisitionResult,
    IdempotencyRecordResponse,
)


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class IdempotencyError(Exception):
    """Base exception for all idempotency service errors."""
    pass


class IdempotencyRecordNotFoundError(IdempotencyError):
    """Raised when an idempotency record expected to exist is missing."""
    pass


class IdempotencyRequestHashMismatchError(IdempotencyError):
    """Raised when an existing idempotency key is reused with a different request payload/hash."""
    pass


class IdempotencyInvalidStateTransitionError(IdempotencyError):
    """Raised when attempting an invalid status transition on an idempotency record."""
    pass


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Helper ensuring datetimes are timezone-aware UTC for safe comparisons across SQLite and Postgres."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ==============================================================================
# Service Implementation
# ==============================================================================

class IdempotencyService:
    """Provides atomic acquisition, caching, and state transitions for idempotent operations."""

    def acquire(
        self,
        session: Session,
        *,
        idempotency_key: str,
        scope: str,
        request_hash: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> IdempotencyAcquisitionResult:
        """Atomically attempts to acquire execution rights for an operation.

        If no record exists for (scope, idempotency_key), a new record in status
        PROCESSING is created and the caller receives execution ownership (`is_acquired=True`).

        If an active record exists:
        - Checks expiration: if expired, resets state to PROCESSING and grants ownership.
        - Validates request_hash: raises IdempotencyRequestHashMismatchError on mismatch.
        - Returns existing state, including cached response payload if COMPLETED.

        Concurrency & Integrity:
        Handles race conditions via database unique constraint `uq_idempotency_scope_key`.
        If an IntegrityError occurs due to concurrent insertion, rolls back cleanly and
        fetches the winning record.
        """
        now = datetime.now(timezone.utc)

        # 1. Check for existing record
        existing = session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )

        if existing is not None:
            # Check expiration with timezone normalization
            existing_expiry = _ensure_utc(existing.expires_at)
            if existing_expiry is not None and existing_expiry <= now:
                # Re-acquire expired record
                existing.status = IdempotencyStatus.PROCESSING
                existing.request_hash = request_hash
                existing.response_payload = None
                existing.expires_at = expires_at
                existing.updated_at = now
                session.commit()
                session.refresh(existing)
                return IdempotencyAcquisitionResult(
                    status=IdempotencyStatus.PROCESSING,
                    is_acquired=True,
                    idempotency_key=idempotency_key,
                    scope=scope,
                    request_hash=request_hash,
                    cached_response=None,
                    is_cached=False,
                    is_processing=True,
                    is_failed=False,
                    is_expired=True,
                    created_at=existing.created_at,
                    expires_at=existing.expires_at,
                )

            # Validate request_hash consistency
            if request_hash is not None and existing.request_hash is not None and existing.request_hash != request_hash:
                raise IdempotencyRequestHashMismatchError(
                    f"Idempotency key '{idempotency_key}' in scope '{scope}' was previously registered with a different request hash."
                )

            is_completed = existing.status == IdempotencyStatus.COMPLETED
            is_processing = existing.status == IdempotencyStatus.PROCESSING
            is_failed = existing.status == IdempotencyStatus.FAILED

            return IdempotencyAcquisitionResult(
                status=existing.status,
                is_acquired=False,
                idempotency_key=idempotency_key,
                scope=scope,
                request_hash=existing.request_hash,
                cached_response=existing.response_payload,
                is_cached=is_completed,
                is_processing=is_processing,
                is_failed=is_failed,
                is_expired=False,
                created_at=existing.created_at,
                expires_at=existing.expires_at,
            )

        # 2. Attempt atomic creation of new record
        new_record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            scope=scope,
            request_hash=request_hash,
            status=IdempotencyStatus.PROCESSING,
            response_payload=None,
            expires_at=expires_at,
        )
        session.add(new_record)

        try:
            session.commit()
            session.refresh(new_record)
            return IdempotencyAcquisitionResult(
                status=IdempotencyStatus.PROCESSING,
                is_acquired=True,
                idempotency_key=idempotency_key,
                scope=scope,
                request_hash=request_hash,
                cached_response=None,
                is_cached=False,
                is_processing=True,
                is_failed=False,
                is_expired=False,
                created_at=new_record.created_at,
                expires_at=new_record.expires_at,
            )
        except IntegrityError:
            session.rollback()
            # Concurrent racer won; retrieve the winning record
            winner = session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.scope == scope,
                    IdempotencyRecord.idempotency_key == idempotency_key,
                )
            )
            if winner is None:
                raise IdempotencyError(
                    f"IntegrityError encountered but record not found for scope '{scope}', key '{idempotency_key}'."
                )

            if request_hash is not None and winner.request_hash is not None and winner.request_hash != request_hash:
                raise IdempotencyRequestHashMismatchError(
                    f"Idempotency key '{idempotency_key}' in scope '{scope}' was registered concurrently with a different request hash."
                )

            is_completed = winner.status == IdempotencyStatus.COMPLETED
            is_processing = winner.status == IdempotencyStatus.PROCESSING
            is_failed = winner.status == IdempotencyStatus.FAILED

            return IdempotencyAcquisitionResult(
                status=winner.status,
                is_acquired=False,
                idempotency_key=idempotency_key,
                scope=scope,
                request_hash=winner.request_hash,
                cached_response=winner.response_payload,
                is_cached=is_completed,
                is_processing=is_processing,
                is_failed=is_failed,
                is_expired=False,
                created_at=winner.created_at,
                expires_at=winner.expires_at,
            )

    def get_record(
        self,
        session: Session,
        *,
        idempotency_key: str,
        scope: str,
    ) -> Optional[IdempotencyRecord]:
        """Fetches the raw ORM IdempotencyRecord if present."""
        return session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )

    def get(
        self,
        session: Session,
        *,
        idempotency_key: str,
        scope: str,
    ) -> Optional[IdempotencyRecordResponse]:
        """Fetches a typed IdempotencyRecordResponse if present."""
        record = self.get_record(session, idempotency_key=idempotency_key, scope=scope)
        if record is None:
            return None
        return IdempotencyRecordResponse(
            id=record.id,
            idempotency_key=record.idempotency_key,
            scope=record.scope,
            request_hash=record.request_hash,
            status=record.status,
            response_payload=record.response_payload,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
        )

    def complete(
        self,
        session: Session,
        *,
        idempotency_key: str,
        scope: str,
        response_payload: Any = None,
    ) -> IdempotencyRecord:
        """Transitions an in-flight PROCESSING record to COMPLETED and stores the result payload."""
        record = self.get_record(session, idempotency_key=idempotency_key, scope=scope)
        if record is None:
            raise IdempotencyRecordNotFoundError(
                f"Idempotency record not found for scope '{scope}', key '{idempotency_key}'."
            )

        if record.status != IdempotencyStatus.PROCESSING:
            raise IdempotencyInvalidStateTransitionError(
                f"Cannot complete idempotency record in status '{record.status}'. Must be '{IdempotencyStatus.PROCESSING}'."
            )

        record.status = IdempotencyStatus.COMPLETED
        record.response_payload = response_payload
        record.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(record)
        return record

    def fail(
        self,
        session: Session,
        *,
        idempotency_key: str,
        scope: str,
        response_payload: Any = None,
    ) -> IdempotencyRecord:
        """Transitions an in-flight PROCESSING record to FAILED and optionally records error details."""
        record = self.get_record(session, idempotency_key=idempotency_key, scope=scope)
        if record is None:
            raise IdempotencyRecordNotFoundError(
                f"Idempotency record not found for scope '{scope}', key '{idempotency_key}'."
            )

        record.status = IdempotencyStatus.FAILED
        record.response_payload = response_payload
        record.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(record)
        return record


# Global default instance
idempotency_service = IdempotencyService()
