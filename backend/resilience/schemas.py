"""Schemas for Resilience and Idempotency Subsystem (Phase 4 - Deliverable D-15)."""

import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from database.models.enums import IdempotencyStatus


class IdempotencyAcquisitionResult(BaseModel):
    """Result of an atomic idempotency key acquisition attempt."""
    model_config = ConfigDict(from_attributes=True)

    status: IdempotencyStatus = Field(description="Current status of the idempotency record")
    is_acquired: bool = Field(description="True if caller won execution rights, False if record already existed")
    idempotency_key: str = Field(description="Unique idempotency key")
    scope: str = Field(description="Logical operational scope")
    request_hash: Optional[str] = Field(default=None, description="Request fingerprint hash")
    cached_response: Optional[Any] = Field(default=None, description="Cached response payload if previously COMPLETED or FAILED")
    is_cached: bool = Field(default=False, description="True if a COMPLETED response payload is available")
    is_processing: bool = Field(default=False, description="True if operation is currently in-flight")
    is_failed: bool = Field(default=False, description="True if operation previously failed")
    is_expired: bool = Field(default=False, description="True if a previously expired record was re-acquired")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")

    @property
    def owns_execution(self) -> bool:
        """Helper to indicate whether caller has execution ownership."""
        return self.is_acquired


class IdempotencyRecordResponse(BaseModel):
    """Standardized view of a persisted IdempotencyRecord."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idempotency_key: str
    scope: str
    request_hash: Optional[str] = None
    status: IdempotencyStatus
    response_payload: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None


class RetryPolicyConfig(BaseModel):
    """Configuration governing retry attempts, exponential backoff, and total execution budget."""
    model_config = ConfigDict(from_attributes=True)

    max_attempts: int = Field(default=3, ge=1, description="Maximum total attempts (initial attempt + retries). Must be >= 1.")
    initial_delay_seconds: float = Field(default=0.1, ge=0.0, description="Initial backoff delay in seconds. Must be >= 0.")
    max_delay_seconds: float = Field(default=2.0, ge=0.0, description="Upper bound for backoff delay in seconds. Must be >= initial_delay_seconds.")
    backoff_multiplier: float = Field(default=2.0, gt=0.0, description="Exponential backoff multiplier factor. Must be > 0.")
    timeout_seconds: float = Field(default=10.0, gt=0.0, description="Total maximum execution time budget in seconds. Must be > 0.")
    jitter_enabled: bool = Field(default=False, description="Whether to apply random jitter to backoff delays.")
    jitter_ratio: float = Field(default=0.1, ge=0.0, le=1.0, description="Jitter fraction [0.0, 1.0] applied symmetrically around calculated delay.")

    @model_validator(mode="after")
    def validate_delays(self) -> "RetryPolicyConfig":
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError(
                f"max_delay_seconds ({self.max_delay_seconds}) cannot be less than initial_delay_seconds ({self.initial_delay_seconds})"
            )
        return self


class ExecutionAttemptResult(BaseModel):
    """Structured record of a single execution attempt."""
    model_config = ConfigDict(from_attributes=True)

    attempt_number: int = Field(description="1-indexed sequence number of this attempt")
    success: bool = Field(description="True if this attempt succeeded")
    elapsed_seconds: float = Field(default=0.0, description="Duration of this specific attempt in seconds")
    delay_before_attempt: float = Field(default=0.0, description="Backoff delay slept prior to starting this attempt")
    error_type: Optional[str] = Field(default=None, description="Class name of exception if attempt failed")
    error_message: Optional[str] = Field(default=None, description="Message string of exception if attempt failed")
    retryable: bool = Field(default=False, description="Whether the encountered error was classified as retryable/transient")
    timed_out: bool = Field(default=False, description="True if total timeout budget was exhausted")

