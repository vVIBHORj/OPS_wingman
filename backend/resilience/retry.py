"""Deterministic Retry and Timeout Engine (Phase 4 - Deliverable D-15).

Provides configurable exponential backoff, transient error classification,
jitter, timeout budget enforcement, and structured execution telemetry for
synchronous and asynchronous operations.
"""

import asyncio
import random
import time
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from backend.resilience.schemas import (
    ExecutionAttemptResult,
    RetryPolicyConfig,
)

T = TypeVar("T")

# Standard infrastructure and network exceptions classified as transient by default
DEFAULT_TRANSIENT_EXCEPTIONS: tuple[Type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    OSError,
)


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class RetryError(Exception):
    """Base exception for operations failing inside the retry engine."""

    def __init__(
        self,
        message: str,
        *,
        attempts: List[ExecutionAttemptResult],
        last_exception: Optional[BaseException] = None,
        timed_out: bool = False,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception
        self.timed_out = timed_out


class MaxRetriesExceededError(RetryError):
    """Raised when maximum retry attempts are exhausted without success."""
    pass


class TimeoutBudgetExceededError(RetryError):
    """Raised when the cumulative execution time budget is exhausted."""
    pass


# ==============================================================================
# Helper Functions
# ==============================================================================

def is_transient_error(
    exc: BaseException,
    retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
    classifier: Optional[Callable[[BaseException], bool]] = None,
) -> bool:
    """Determines whether an exception is classified as transient / retryable.

    Evaluation precedence:
    1. Custom boolean `classifier(exc)` if provided.
    2. Explicit `retryable_exceptions` tuple/list if provided.
    3. `DEFAULT_TRANSIENT_EXCEPTIONS` (TimeoutError, ConnectionError, OSError).
    """
    if classifier is not None:
        return classifier(exc)

    candidate_types = (
        tuple(retryable_exceptions)
        if retryable_exceptions is not None
        else DEFAULT_TRANSIENT_EXCEPTIONS
    )
    return isinstance(exc, candidate_types)


def calculate_backoff_delay(
    attempt_index: int,
    policy: RetryPolicyConfig,
) -> float:
    """Calculates exponential backoff delay for the given attempt sequence.

    Formula:
        delay_n = min(max_delay_seconds, initial_delay_seconds * (backoff_multiplier ** (n - 1)))

    If jitter_enabled:
        Applies random uniform bounded jitter around the base delay.
    """
    if attempt_index < 1:
        attempt_index = 1

    exponent = attempt_index - 1
    base_delay = policy.initial_delay_seconds * (policy.backoff_multiplier ** exponent)
    capped_delay = min(policy.max_delay_seconds, base_delay)

    if policy.jitter_enabled and policy.jitter_ratio > 0.0:
        spread = capped_delay * policy.jitter_ratio
        min_bound = max(0.0, capped_delay - spread)
        max_bound = capped_delay + spread
        return max(0.0, random.uniform(min_bound, max_bound))

    return max(0.0, capped_delay)


# ==============================================================================
# Retry Executor
# ==============================================================================

class RetryExecutor:
    """Executes callables under configured exponential backoff, timeout budget, and transient error policies."""

    def __init__(self, default_policy: Optional[RetryPolicyConfig] = None) -> None:
        self.default_policy = default_policy or RetryPolicyConfig()

    def execute(
        self,
        operation: Callable[[], T],
        *,
        policy: Optional[RetryPolicyConfig] = None,
        retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
        classifier: Optional[Callable[[BaseException], bool]] = None,
        sleeper: Callable[[float], None] = time.sleep,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> T:
        """Executes a synchronous operation with retry and timeout protection.

        Args:
            operation: Zero-argument callable to execute.
            policy: Custom RetryPolicyConfig (defaults to executor's policy).
            retryable_exceptions: Explicit tuple of retryable exception classes.
            classifier: Custom callback (exc) -> bool.
            sleeper: Sleep function for delays (injected for deterministic testing).
            time_fn: Monotonic clock function (injected for deterministic testing).

        Returns:
            The return value of `operation()`.

        Raises:
            MaxRetriesExceededError: When all retry attempts fail on transient errors.
            TimeoutBudgetExceededError: When cumulative execution time exceeds timeout_seconds.
            Exception: Re-raises immediately if a non-transient error occurs.
        """
        active_policy = policy or self.default_policy
        start_time = time_fn()
        attempts: List[ExecutionAttemptResult] = []
        prev_delay = 0.0

        for attempt_num in range(1, active_policy.max_attempts + 1):
            # Check if timeout budget was exceeded prior to starting attempt
            total_elapsed = time_fn() - start_time
            if total_elapsed >= active_policy.timeout_seconds:
                timeout_res = ExecutionAttemptResult(
                    attempt_number=attempt_num,
                    success=False,
                    elapsed_seconds=0.0,
                    delay_before_attempt=prev_delay,
                    error_type="TimeoutBudgetExceededError",
                    error_message=f"Timeout budget of {active_policy.timeout_seconds}s exceeded before attempt {attempt_num}.",
                    retryable=True,
                    timed_out=True,
                )
                attempts.append(timeout_res)
                raise TimeoutBudgetExceededError(
                    f"Timeout budget of {active_policy.timeout_seconds}s exhausted before attempt {attempt_num}.",
                    attempts=attempts,
                    last_exception=attempts[-2].error_message if len(attempts) > 1 else None,  # type: ignore
                    timed_out=True,
                )

            attempt_start = time_fn()
            try:
                result = operation()
                attempt_duration = time_fn() - attempt_start
                attempts.append(
                    ExecutionAttemptResult(
                        attempt_number=attempt_num,
                        success=True,
                        elapsed_seconds=attempt_duration,
                        delay_before_attempt=prev_delay,
                        retryable=False,
                        timed_out=False,
                    )
                )
                return result

            except BaseException as exc:
                attempt_duration = time_fn() - attempt_start
                transient = is_transient_error(exc, retryable_exceptions, classifier)

                # Non-transient errors terminate immediately
                if not transient:
                    attempts.append(
                        ExecutionAttemptResult(
                            attempt_number=attempt_num,
                            success=False,
                            elapsed_seconds=attempt_duration,
                            delay_before_attempt=prev_delay,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            retryable=False,
                            timed_out=False,
                        )
                    )
                    raise

                # Record transient attempt failure
                attempt_rec = ExecutionAttemptResult(
                    attempt_number=attempt_num,
                    success=False,
                    elapsed_seconds=attempt_duration,
                    delay_before_attempt=prev_delay,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    retryable=True,
                    timed_out=False,
                )
                attempts.append(attempt_rec)

                # Check if this was the last allowed attempt
                if attempt_num >= active_policy.max_attempts:
                    raise MaxRetriesExceededError(
                        f"Operation failed after {attempt_num} attempts. Last error: {type(exc).__name__}: {exc}",
                        attempts=attempts,
                        last_exception=exc,
                        timed_out=False,
                    ) from exc

                # Calculate next backoff delay
                delay = calculate_backoff_delay(attempt_num, active_policy)
                time_after_delay = (time_fn() - start_time) + delay

                # Check if sleeping this delay would exceed total timeout budget
                if time_after_delay >= active_policy.timeout_seconds:
                    attempt_rec.timed_out = True
                    raise TimeoutBudgetExceededError(
                        f"Timeout budget of {active_policy.timeout_seconds}s would be exceeded by backoff delay ({delay:.3f}s) before attempt {attempt_num + 1}.",
                        attempts=attempts,
                        last_exception=exc,
                        timed_out=True,
                    ) from exc

                # Sleep and prepare for next iteration
                sleeper(delay)
                prev_delay = delay

        # Fallback safeguard (unreachable under normal loop conditions)
        raise MaxRetriesExceededError(
            f"Operation exhausted all {active_policy.max_attempts} attempts.",
            attempts=attempts,
            timed_out=False,
        )

    async def async_execute(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        policy: Optional[RetryPolicyConfig] = None,
        retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
        classifier: Optional[Callable[[BaseException], bool]] = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> T:
        """Executes an asynchronous coroutine with retry and timeout protection.

        Args:
            operation: Zero-argument callable returning an Awaitable[T].
            policy: Custom RetryPolicyConfig (defaults to executor's policy).
            retryable_exceptions: Explicit tuple of retryable exception classes.
            classifier: Custom callback (exc) -> bool.
            sleeper: Async sleep function for delays.
            time_fn: Monotonic clock function.

        Returns:
            The resolved result of `await operation()`.
        """
        active_policy = policy or self.default_policy
        start_time = time_fn()
        attempts: List[ExecutionAttemptResult] = []
        prev_delay = 0.0

        for attempt_num in range(1, active_policy.max_attempts + 1):
            total_elapsed = time_fn() - start_time
            if total_elapsed >= active_policy.timeout_seconds:
                timeout_res = ExecutionAttemptResult(
                    attempt_number=attempt_num,
                    success=False,
                    elapsed_seconds=0.0,
                    delay_before_attempt=prev_delay,
                    error_type="TimeoutBudgetExceededError",
                    error_message=f"Timeout budget of {active_policy.timeout_seconds}s exceeded before attempt {attempt_num}.",
                    retryable=True,
                    timed_out=True,
                )
                attempts.append(timeout_res)
                raise TimeoutBudgetExceededError(
                    f"Timeout budget of {active_policy.timeout_seconds}s exhausted before attempt {attempt_num}.",
                    attempts=attempts,
                    last_exception=attempts[-2].error_message if len(attempts) > 1 else None,  # type: ignore
                    timed_out=True,
                )

            attempt_start = time_fn()
            try:
                result = await operation()
                attempt_duration = time_fn() - attempt_start
                attempts.append(
                    ExecutionAttemptResult(
                        attempt_number=attempt_num,
                        success=True,
                        elapsed_seconds=attempt_duration,
                        delay_before_attempt=prev_delay,
                        retryable=False,
                        timed_out=False,
                    )
                )
                return result

            except BaseException as exc:
                attempt_duration = time_fn() - attempt_start
                transient = is_transient_error(exc, retryable_exceptions, classifier)

                if not transient:
                    attempts.append(
                        ExecutionAttemptResult(
                            attempt_number=attempt_num,
                            success=False,
                            elapsed_seconds=attempt_duration,
                            delay_before_attempt=prev_delay,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            retryable=False,
                            timed_out=False,
                        )
                    )
                    raise

                attempt_rec = ExecutionAttemptResult(
                    attempt_number=attempt_num,
                    success=False,
                    elapsed_seconds=attempt_duration,
                    delay_before_attempt=prev_delay,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    retryable=True,
                    timed_out=False,
                )
                attempts.append(attempt_rec)

                if attempt_num >= active_policy.max_attempts:
                    raise MaxRetriesExceededError(
                        f"Async operation failed after {attempt_num} attempts. Last error: {type(exc).__name__}: {exc}",
                        attempts=attempts,
                        last_exception=exc,
                        timed_out=False,
                    ) from exc

                delay = calculate_backoff_delay(attempt_num, active_policy)
                time_after_delay = (time_fn() - start_time) + delay

                if time_after_delay >= active_policy.timeout_seconds:
                    attempt_rec.timed_out = True
                    raise TimeoutBudgetExceededError(
                        f"Timeout budget of {active_policy.timeout_seconds}s would be exceeded by backoff delay ({delay:.3f}s) before attempt {attempt_num + 1}.",
                        attempts=attempts,
                        last_exception=exc,
                        timed_out=True,
                    ) from exc

                await sleeper(delay)
                prev_delay = delay

        raise MaxRetriesExceededError(
            f"Async operation exhausted all {active_policy.max_attempts} attempts.",
            attempts=attempts,
            timed_out=False,
        )


# Global default executor
retry_executor = RetryExecutor()
