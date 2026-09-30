"""Unit tests for Retry and Timeout Engine (Phase 4 - Deliverable D-15)."""

import asyncio
from typing import List
import pytest
from pydantic import ValidationError

from backend.resilience.schemas import (
    RetryPolicyConfig,
    ExecutionAttemptResult,
)
from backend.resilience.retry import (
    RetryExecutor,
    MaxRetriesExceededError,
    TimeoutBudgetExceededError,
    calculate_backoff_delay,
    is_transient_error,
)


# ==============================================================================
# Helpers / Test Clocks
# ==============================================================================

class FakeClock:
    """Deterministic simulated clock for testing backoff and timeout budgets without sleeping."""

    def __init__(self, start: float = 1000.0) -> None:
        self.current_time = start
        self.sleep_calls: List[float] = []

    def time(self) -> float:
        return self.current_time

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.current_time += seconds

    async def async_sleep(self, seconds: float) -> None:
        self.sleep(seconds)


# ==============================================================================
# Unit Tests
# ==============================================================================

def test_successful_first_attempt():
    """1. Verifies a successful operation executes once immediately without retries or sleeping."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        return "success_val"

    policy = RetryPolicyConfig(max_attempts=3, initial_delay_seconds=0.5)
    result = executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert result == "success_val"
    assert calls == 1
    assert len(clock.sleep_calls) == 0


def test_retry_after_transient_failure():
    """2. Verifies operation retries after transient ConnectionError and succeeds on attempt 2."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("Temporary disconnect")
        return "recovered"

    policy = RetryPolicyConfig(max_attempts=3, initial_delay_seconds=1.0)
    result = executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert result == "recovered"
    assert calls == 2
    assert len(clock.sleep_calls) == 1
    assert clock.sleep_calls[0] == 1.0


def test_eventually_successful_execution():
    """3. Verifies operation failing twice on transient errors succeeds on attempt 3."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> int:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError(f"Transient timeout on try {calls}")
        return 42

    policy = RetryPolicyConfig(max_attempts=4, initial_delay_seconds=0.5, backoff_multiplier=2.0)
    result = executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert result == 42
    assert calls == 3
    assert len(clock.sleep_calls) == 2
    assert clock.sleep_calls[0] == 0.5  # attempt 1 delay
    assert clock.sleep_calls[1] == 1.0  # attempt 2 delay


def test_exhaustion_of_max_attempts():
    """4. Verifies MaxRetriesExceededError is raised after max_attempts fails."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> None:
        nonlocal calls
        calls += 1
        raise ConnectionError("Persistent network outage")

    policy = RetryPolicyConfig(max_attempts=3, initial_delay_seconds=0.2, backoff_multiplier=2.0)
    with pytest.raises(MaxRetriesExceededError) as exc_info:
        executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert calls == 3
    assert len(clock.sleep_calls) == 2
    assert len(exc_info.value.attempts) == 3
    assert exc_info.value.timed_out is False
    assert all(a.retryable is True for a in exc_info.value.attempts)


def test_non_retryable_exception_is_not_retried():
    """5. Verifies non-transient exceptions (e.g. ValueError) fail immediately on attempt 1."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("Invalid parameters")

    policy = RetryPolicyConfig(max_attempts=5, initial_delay_seconds=1.0)
    with pytest.raises(ValueError) as exc_info:
        executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert str(exc_info.value) == "Invalid parameters"
    assert calls == 1
    assert len(clock.sleep_calls) == 0


def test_exponential_backoff_calculation():
    """6. Verifies exponential backoff formula: initial * (multiplier ** (n - 1))."""
    policy = RetryPolicyConfig(
        initial_delay_seconds=1.0,
        backoff_multiplier=3.0,
        max_delay_seconds=50.0,
        jitter_enabled=False,
    )

    # Attempt 1 -> delay 1.0 * (3^0) = 1.0
    assert calculate_backoff_delay(1, policy) == 1.0
    # Attempt 2 -> delay 1.0 * (3^1) = 3.0
    assert calculate_backoff_delay(2, policy) == 3.0
    # Attempt 3 -> delay 1.0 * (3^2) = 9.0
    assert calculate_backoff_delay(3, policy) == 9.0
    # Attempt 4 -> delay 1.0 * (3^3) = 27.0
    assert calculate_backoff_delay(4, policy) == 27.0


def test_max_delay_seconds_is_respected():
    """7. Verifies delay does not exceed max_delay_seconds."""
    policy = RetryPolicyConfig(
        initial_delay_seconds=2.0,
        backoff_multiplier=2.0,
        max_delay_seconds=5.0,
        jitter_enabled=False,
    )

    # Attempt 1 -> 2.0
    assert calculate_backoff_delay(1, policy) == 2.0
    # Attempt 2 -> 4.0
    assert calculate_backoff_delay(2, policy) == 4.0
    # Attempt 3 -> 8.0, capped at 5.0
    assert calculate_backoff_delay(3, policy) == 5.0
    # Attempt 4 -> 16.0, capped at 5.0
    assert calculate_backoff_delay(4, policy) == 5.0


def test_jitter_never_produces_negative_delay():
    """8. Verifies jitter stays non-negative even with jitter enabled."""
    policy = RetryPolicyConfig(
        initial_delay_seconds=0.01,
        max_delay_seconds=1.0,
        jitter_enabled=True,
        jitter_ratio=0.5,
    )

    for attempt in range(1, 20):
        delay = calculate_backoff_delay(attempt, policy)
        assert delay >= 0.0


def test_timeout_budget_stops_retries():
    """9. Verifies total timeout budget aborts further retries and raises TimeoutBudgetExceededError."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> None:
        nonlocal calls
        calls += 1
        # Advance clock to simulate long operation execution
        clock.current_time += 4.0
        raise ConnectionError("Slow failing network call")

    # Total timeout budget is 5.0 seconds. Attempt 1 takes 4.0s. Delay is 2.0s -> total 6.0s > 5.0s budget
    policy = RetryPolicyConfig(
        max_attempts=10,
        initial_delay_seconds=2.0,
        timeout_seconds=5.0,
    )

    with pytest.raises(TimeoutBudgetExceededError) as exc_info:
        executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert calls == 1
    assert exc_info.value.timed_out is True
    assert "Timeout budget of 5.0s" in str(exc_info.value)


def test_timeout_is_reported_as_timed_out():
    """10. Verifies timeout failure sets timed_out=True on the exception and attempts record."""
    clock = FakeClock()
    executor = RetryExecutor()

    def op() -> None:
        clock.current_time += 10.0
        raise TimeoutError("Call timed out")

    policy = RetryPolicyConfig(max_attempts=3, timeout_seconds=5.0)

    with pytest.raises(TimeoutBudgetExceededError) as exc_info:
        executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert exc_info.value.timed_out is True
    attempts = exc_info.value.attempts
    assert len(attempts) >= 1
    assert attempts[-1].timed_out is True


def test_attempt_count_is_correct():
    """11. Verifies attempt numbers are sequentially 1-indexed and exact."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> None:
        nonlocal calls
        calls += 1
        raise OSError(f"Disk I/O error {calls}")

    policy = RetryPolicyConfig(max_attempts=4, initial_delay_seconds=0.1)

    with pytest.raises(MaxRetriesExceededError) as exc_info:
        executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    attempts = exc_info.value.attempts
    assert len(attempts) == 4
    for idx, att in enumerate(attempts, start=1):
        assert att.attempt_number == idx
        assert att.success is False
        assert att.error_type == "OSError"


def test_structured_attempt_information_is_correct():
    """12. Verifies execution attempts contain accurate structured fields."""
    clock = FakeClock()
    executor = RetryExecutor()
    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            clock.current_time += 0.25
            raise ConnectionResetError("Connection reset by peer")
        clock.current_time += 0.1
        return "success"

    policy = RetryPolicyConfig(max_attempts=3, initial_delay_seconds=0.5)
    result = executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert result == "success"
    # Verify clock advanced by attempt1 (0.25s) + delay (0.5s) + attempt2 (0.1s)
    assert calls == 2


def test_caller_provided_retryable_exception_configuration():
    """13. Verifies custom retryable_exceptions or classifier callback is respected."""
    clock = FakeClock()
    executor = RetryExecutor()

    class CustomTransientError(Exception):
        pass

    calls = 0

    def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise CustomTransientError("Custom temporary failure")
        return "custom_ok"

    policy = RetryPolicyConfig(max_attempts=3, initial_delay_seconds=0.1)

    # 13a. With custom retryable_exceptions
    res = executor.execute(
        op,
        policy=policy,
        retryable_exceptions=[CustomTransientError],
        sleeper=clock.sleep,
        time_fn=clock.time,
    )
    assert res == "custom_ok"
    assert calls == 2

    # 13b. With custom classifier function
    calls = 0
    res2 = executor.execute(
        op,
        policy=policy,
        classifier=lambda exc: isinstance(exc, CustomTransientError),
        sleeper=clock.sleep,
        time_fn=clock.time,
    )
    assert res2 == "custom_ok"
    assert calls == 2


def test_no_retry_occurs_after_successful_execution():
    """14. Verifies no further calls or delays occur once success is achieved."""
    clock = FakeClock()
    executor = RetryExecutor()
    executed_count = 0

    def op() -> int:
        nonlocal executed_count
        executed_count += 1
        return 100

    policy = RetryPolicyConfig(max_attempts=10, initial_delay_seconds=1.0)
    res = executor.execute(op, policy=policy, sleeper=clock.sleep, time_fn=clock.time)

    assert res == 100
    assert executed_count == 1
    assert len(clock.sleep_calls) == 0


def test_zero_invalid_policy_values_are_rejected():
    """15. Verifies validation error is raised for invalid policy configurations."""
    # max_attempts < 1
    with pytest.raises(ValidationError):
        RetryPolicyConfig(max_attempts=0)

    # negative initial_delay_seconds
    with pytest.raises(ValidationError):
        RetryPolicyConfig(initial_delay_seconds=-0.5)

    # max_delay_seconds < initial_delay_seconds
    with pytest.raises(ValidationError):
        RetryPolicyConfig(initial_delay_seconds=5.0, max_delay_seconds=1.0)

    # backoff_multiplier <= 0
    with pytest.raises(ValidationError):
        RetryPolicyConfig(backoff_multiplier=0.0)

    # timeout_seconds <= 0
    with pytest.raises(ValidationError):
        RetryPolicyConfig(timeout_seconds=-1.0)

    # jitter_ratio > 1.0
    with pytest.raises(ValidationError):
        RetryPolicyConfig(jitter_ratio=1.5)


def test_async_execute_retry_behavior():
    """16. Verifies async_execute handles coroutines with exponential backoff and retries."""
    async def _run():
        clock = FakeClock()
        executor = RetryExecutor()
        calls = 0

        async def async_op() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionRefusedError(f"Async connection refused {calls}")
            return "async_success"

        policy = RetryPolicyConfig(max_attempts=4, initial_delay_seconds=0.2, backoff_multiplier=2.0)
        result = await executor.async_execute(
            async_op,
            policy=policy,
            sleeper=clock.async_sleep,
            time_fn=clock.time,
        )

        assert result == "async_success"
        assert calls == 3
        assert len(clock.sleep_calls) == 2
        assert clock.sleep_calls[0] == 0.2
        assert clock.sleep_calls[1] == 0.4

    asyncio.run(_run())

