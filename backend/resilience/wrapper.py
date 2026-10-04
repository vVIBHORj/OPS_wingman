"""Resilient Tool Execution Wrapper for OpsWingman (Phase 4 - Deliverable D-15).

Composes IdempotencyService and RetryExecutor into a unified execution boundary that:
1. Provides durable idempotency protection and deduplication for state-changing tools.
2. Applies transient error detection, exponential backoff, and timeout-budget enforcement.
3. Guarantees that duplicate executions or retries do not cause duplicate business mutations.
4. Correctly classifies transient errors vs non-transient domain/business validation errors.
5. Captures comprehensive resilience telemetry for workflow checkpoints.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Type
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models.enums import IdempotencyStatus
from backend.resilience.idempotency import (
    IdempotencyService,
    IdempotencyRequestHashMismatchError,
    idempotency_service as default_idempotency_service,
)
from backend.resilience.retry import (
    RetryExecutor,
    MaxRetriesExceededError,
    TimeoutBudgetExceededError,
    is_transient_error,
    retry_executor as default_retry_executor,
)
from backend.resilience.schemas import RetryPolicyConfig
from backend.tools.base import RiskLevel, ToolDefinition, ToolExecutionResult, ToolType
from sqlalchemy.exc import DBAPIError, OperationalError

# Default transient exceptions for tools (infrastructure network + database transient errors)
DEFAULT_TOOL_TRANSIENT_EXCEPTIONS: tuple[Type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    OSError,
    OperationalError,
    DBAPIError,
)


# ==============================================================================
# Idempotency Key & Scope Helpers
# ==============================================================================

def resolve_idempotency_key(
    tool: ToolDefinition,
    params: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Deterministically resolves the idempotency key for a logical tool execution.

    Precedence:
    1. Explicit key in `context["idempotency_key"]` or `params.get("idempotency_key")`.
    2. Composed key: `wf:{logical_id}:{tool.name}:{target_entity}` where:
       - `logical_id`: `context.get("workflow_id")` or `context.get("run_id")` or `context.get("action_id")`.
       - `target_entity`:
         - for order tools: `params.get("order_id")` or `params.get("order_number")`
         - for refund tools: `params.get("order_id")` or `params.get("payment_id")`
         - for ticket tools: `params.get("order_id")` or `params.get("customer_id")` or `params.get("ticket_number")`
         - fallback: canonical param fingerprint.
       - If no workflow/run context is provided:
         `tool:{tool.name}:{target_entity}`
    """
    ctx = context or {}
    if ctx.get("idempotency_key"):
        return str(ctx["idempotency_key"])
    if params.get("idempotency_key"):
        return str(params["idempotency_key"])

    # Resolve target entity
    target_entity = (
        params.get("order_id")
        or params.get("order_number")
        or params.get("payment_id")
        or params.get("payment_reference")
        or params.get("customer_id")
        or params.get("ticket_number")
        or params.get("tracking_number")
    )
    if target_entity is None:
        # Fallback to parameter hash fragment
        clean_params = {k: v for k, v in params.items() if not k.startswith("_")}
        param_str = json.dumps(clean_params, sort_keys=True, default=str)
        target_entity = hashlib.sha256(param_str.encode("utf-8")).hexdigest()[:12]
    else:
        target_entity = str(target_entity)

    logical_id = (
        ctx.get("run_id")
        or ctx.get("workflow_id")
        or ctx.get("action_id")
    )

    if logical_id:
        return f"wf:{logical_id}:{tool.name}:{target_entity}"
    return f"tool:{tool.name}:{target_entity}"


def resolve_scope(
    tool: ToolDefinition,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Resolves the idempotency scope namespace."""
    if context and context.get("idempotency_scope"):
        return str(context["idempotency_scope"])
    return f"tool:{tool.name}"


def compute_request_hash(params: Dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 fingerprint hash of request parameters."""
    clean = {k: v for k, v in params.items() if not k.startswith("_")}
    serialized = json.dumps(clean, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def is_state_changing(tool: ToolDefinition) -> bool:
    """Returns True if the tool performs persistent state mutations requiring idempotency."""
    if tool.tool_type == ToolType.WRITE:
        return True
    return tool.name in {"cancel_order", "request_refund", "create_ticket"}


def _invoke_tool_handler(
    handler: Callable[..., Any],
    validated_inputs: BaseModel,
    context: Optional[Dict[str, Any]] = None,
) -> Any:
    """Invokes handler with validated inputs and optional context, supporting both model and keyword signatures."""
    sig = None
    try:
        sig = inspect.signature(handler)
    except (ValueError, TypeError):
        pass

    if sig is not None:
        param_names = list(sig.parameters.keys())
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        has_context = "context" in param_names or has_var_kw

        # If handler arguments match model attributes rather than accepting the model directly
        if (
            len(param_names) > 0
            and param_names[0] not in ("inputs", "validated_inputs", "params")
            and hasattr(validated_inputs, param_names[0])
        ):
            kwargs = validated_inputs.model_dump()
            if has_context:
                kwargs["context"] = context
            return handler(**kwargs)

        if has_context:
            return handler(validated_inputs, context=context)
        return handler(validated_inputs)

    # Fallback
    try:
        if context:
            return handler(validated_inputs, context=context)
        return handler(validated_inputs)
    except TypeError:
        try:
            return handler(validated_inputs)
        except TypeError:
            return handler(**validated_inputs.model_dump())


# ==============================================================================
# Resilient Tool Executor
# ==============================================================================

class ResilientToolExecutor:
    """Composes IdempotencyService and RetryExecutor for resilient tool execution."""

    def __init__(
        self,
        idempotency_service: Optional[IdempotencyService] = None,
        retry_executor: Optional[RetryExecutor] = None,
        default_policy: Optional[RetryPolicyConfig] = None,
    ) -> None:
        self.idempotency_service = idempotency_service or default_idempotency_service
        self.retry_executor = retry_executor or default_retry_executor
        self.default_policy = default_policy or RetryPolicyConfig()

    def execute(
        self,
        tool: ToolDefinition,
        validated_inputs: BaseModel,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        """Executes a tool with idempotency protection and retry-on-transient-failure."""
        ctx = context or {}
        db: Optional[Session] = ctx.get("db")
        policy: RetryPolicyConfig = ctx.get("retry_policy") or self.default_policy
        idempotency_svc = ctx.get("idempotency_service") or self.idempotency_service
        retry_exec = ctx.get("retry_executor") or self.retry_executor
        retryable_exceptions = ctx.get("retryable_exceptions") or DEFAULT_TOOL_TRANSIENT_EXCEPTIONS
        classifier = ctx.get("classifier")
        sleeper = ctx.get("sleeper")
        time_fn = ctx.get("time_fn")

        # 1. READ tools do not require idempotency records
        if not is_state_changing(tool) or ctx.get("skip_idempotency"):
            return self._execute_read_tool(
                tool=tool,
                validated_inputs=validated_inputs,
                context=context,
                policy=policy,
                retry_exec=retry_exec,
                retryable_exceptions=retryable_exceptions,
                classifier=classifier,
                sleeper=sleeper,
                time_fn=time_fn,
            )

        # 2. State-changing tools without database session
        if db is None:
            return self._execute_without_idempotency(
                tool=tool,
                validated_inputs=validated_inputs,
                context=context,
                policy=policy,
                retry_exec=retry_exec,
                retryable_exceptions=retryable_exceptions,
                classifier=classifier,
                sleeper=sleeper,
                time_fn=time_fn,
            )

        # 3. State-changing tools with active database session: Full Idempotency + Retry
        params_dict = validated_inputs.model_dump()
        key = resolve_idempotency_key(tool, params_dict, context=context)
        scope = resolve_scope(tool, context=context)
        req_hash = compute_request_hash(params_dict)

        # Step 3a: Acquire idempotency lease
        try:
            acq = idempotency_svc.acquire(
                session=db,
                idempotency_key=key,
                scope=scope,
                request_hash=req_hash,
            )
        except IdempotencyRequestHashMismatchError as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Idempotency conflict: {exc}",
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                attempts=1,
                resilience_metadata={
                    "idempotency_key": key,
                    "scope": scope,
                    "conflict": True,
                    "error_type": "IdempotencyRequestHashMismatchError",
                    "error_message": str(exc),
                    "retryable": False,
                },
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                error=f"Idempotency acquisition failure: {exc}",
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                attempts=1,
                resilience_metadata={
                    "idempotency_key": key,
                    "scope": scope,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "retryable": False,
                },
            )

        # Step 3b: If already cached (COMPLETED), replay without calling mutation handler
        if acq.is_cached:
            data = acq.cached_response if isinstance(acq.cached_response, dict) else {"result": acq.cached_response}
            return ToolExecutionResult(
                success=True,
                data=data,
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                is_cached=True,
                attempts=0,
                execution_time_seconds=0.0,
                retry_delays=[],
                resilience_metadata={
                    "tool_name": tool.name,
                    "idempotency_key": key,
                    "scope": scope,
                    "is_cached": True,
                    "attempt_count": 0,
                    "attempts": 0,
                    "final_status": "CACHED",
                },
            )

        # Step 3c: If in-flight by concurrent process and not acquired
        if acq.is_processing and not acq.is_acquired:
            return ToolExecutionResult(
                success=False,
                error=f"Operation '{tool.name}' with idempotency key '{key}' is already in-flight.",
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                is_cached=False,
                attempts=1,
                resilience_metadata={
                    "tool_name": tool.name,
                    "idempotency_key": key,
                    "scope": scope,
                    "in_flight": True,
                    "conflict": True,
                    "attempt_count": 1,
                    "attempts": 1,
                    "final_status": "PROCESSING",
                },
            )

        # Step 3d: Caller won execution ownership (`acq.is_acquired=True`)
        attempt_count = 0
        retry_delays: List[float] = []
        clock = time.monotonic if time_fn is None else time_fn
        start_time = clock()

        def recording_sleeper(secs: float) -> None:
            retry_delays.append(secs)
            if sleeper:
                sleeper(secs)
            else:
                time.sleep(secs)

        def operation_closure() -> Any:
            nonlocal attempt_count
            attempt_count += 1
            try:
                return _invoke_tool_handler(tool.handler, validated_inputs, context=context)
            except Exception:
                # Rollback uncommitted DB work on attempt failure to keep session healthy
                if db:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                raise

        try:
            raw_result = retry_exec.execute(
                operation_closure,
                policy=policy,
                retryable_exceptions=retryable_exceptions,
                classifier=classifier,
                sleeper=recording_sleeper,
                time_fn=clock,
            )
            elapsed = clock() - start_time

            if isinstance(raw_result, BaseModel):
                data = raw_result.model_dump()
            elif isinstance(raw_result, dict):
                data = raw_result
            else:
                data = {"result": raw_result}

            # Persist completed idempotency record
            try:
                idempotency_svc.complete(
                    session=db,
                    idempotency_key=key,
                    scope=scope,
                    response_payload=data,
                )
            except Exception:
                pass

            return ToolExecutionResult(
                success=True,
                data=data,
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                is_cached=False,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
                resilience_metadata={
                    "tool_name": tool.name,
                    "idempotency_key": key,
                    "scope": scope,
                    "is_cached": False,
                    "attempt_count": attempt_count,
                    "attempts": attempt_count,
                    "retry_delays": retry_delays,
                    "elapsed_seconds": elapsed,
                    "final_status": "COMPLETED",
                    "timed_out": False,
                    "retryable": False,
                },
            )

        except MaxRetriesExceededError as exc:
            elapsed = clock() - start_time
            try:
                idempotency_svc.fail(
                    session=db,
                    idempotency_key=key,
                    scope=scope,
                    response_payload={"error": str(exc)},
                )
            except Exception:
                pass

            return ToolExecutionResult(
                success=False,
                error=f"Retry exhaustion: {exc}",
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
                resilience_metadata={
                    "tool_name": tool.name,
                    "idempotency_key": key,
                    "scope": scope,
                    "attempt_count": attempt_count,
                    "attempts": attempt_count,
                    "retry_delays": retry_delays,
                    "elapsed_seconds": elapsed,
                    "final_status": "FAILED",
                    "timed_out": False,
                    "retryable": True,
                    "error_type": "MaxRetriesExceededError",
                    "error_message": str(exc),
                },
            )

        except TimeoutBudgetExceededError as exc:
            elapsed = clock() - start_time
            try:
                idempotency_svc.fail(
                    session=db,
                    idempotency_key=key,
                    scope=scope,
                    response_payload={"error": str(exc)},
                )
            except Exception:
                pass

            return ToolExecutionResult(
                success=False,
                error=f"Timeout budget exceeded: {exc}",
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
                resilience_metadata={
                    "tool_name": tool.name,
                    "idempotency_key": key,
                    "scope": scope,
                    "attempt_count": attempt_count,
                    "attempts": attempt_count,
                    "retry_delays": retry_delays,
                    "elapsed_seconds": elapsed,
                    "final_status": "FAILED",
                    "timed_out": True,
                    "timeout_occurred": True,
                    "retryable": True,
                    "error_type": "TimeoutBudgetExceededError",
                    "error_message": str(exc),
                },
            )

        except Exception as exc:
            # Non-transient or business domain exception
            elapsed = clock() - start_time
            try:
                idempotency_svc.fail(
                    session=db,
                    idempotency_key=key,
                    scope=scope,
                    response_payload={"error": str(exc)},
                )
            except Exception:
                pass

            return ToolExecutionResult(
                success=False,
                error=str(exc),
                tool_name=tool.name,
                risk_level=tool.risk_level,
                idempotency_key=key,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
                resilience_metadata={
                    "tool_name": tool.name,
                    "idempotency_key": key,
                    "scope": scope,
                    "attempt_count": attempt_count,
                    "attempts": attempt_count,
                    "retry_delays": retry_delays,
                    "elapsed_seconds": elapsed,
                    "final_status": "FAILED",
                    "timed_out": False,
                    "retryable": False,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )

    def _execute_read_tool(
        self,
        tool: ToolDefinition,
        validated_inputs: BaseModel,
        context: Optional[Dict[str, Any]],
        policy: RetryPolicyConfig,
        retry_exec: RetryExecutor,
        retryable_exceptions: Any,
        classifier: Any,
        sleeper: Any,
        time_fn: Any,
    ) -> ToolExecutionResult:
        """Executes a read-only tool directly without idempotency records."""
        attempt_count = 0
        retry_delays: List[float] = []
        clock = time.monotonic if time_fn is None else time_fn
        start_time = clock()

        def recording_sleeper(secs: float) -> None:
            retry_delays.append(secs)
            if sleeper:
                sleeper(secs)
            else:
                time.sleep(secs)

        def op() -> Any:
            nonlocal attempt_count
            attempt_count += 1
            return _invoke_tool_handler(tool.handler, validated_inputs, context=context)

        try:
            raw_result = retry_exec.execute(
                op,
                policy=policy,
                retryable_exceptions=retryable_exceptions,
                classifier=classifier,
                sleeper=recording_sleeper,
                time_fn=clock,
            )
            elapsed = clock() - start_time
            if isinstance(raw_result, BaseModel):
                data = raw_result.model_dump()
            elif isinstance(raw_result, dict):
                data = raw_result
            else:
                data = {"result": raw_result}

            return ToolExecutionResult(
                success=True,
                data=data,
                tool_name=tool.name,
                risk_level=tool.risk_level,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
                resilience_metadata=None,
            )
        except Exception as exc:
            elapsed = clock() - start_time
            return ToolExecutionResult(
                success=False,
                error=str(exc),
                tool_name=tool.name,
                risk_level=tool.risk_level,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
                resilience_metadata=None,
            )

    def _execute_without_idempotency(
        self,
        tool: ToolDefinition,
        validated_inputs: BaseModel,
        context: Optional[Dict[str, Any]],
        policy: RetryPolicyConfig,
        retry_exec: RetryExecutor,
        retryable_exceptions: Any,
        classifier: Any,
        sleeper: Any,
        time_fn: Any,
    ) -> ToolExecutionResult:
        """Executes a tool with retry but without durable idempotency persistence when db session is absent."""
        attempt_count = 0
        retry_delays: List[float] = []
        clock = time.monotonic if time_fn is None else time_fn
        start_time = clock()

        def recording_sleeper(secs: float) -> None:
            retry_delays.append(secs)
            if sleeper:
                sleeper(secs)
            else:
                time.sleep(secs)

        def op() -> Any:
            nonlocal attempt_count
            attempt_count += 1
            return _invoke_tool_handler(tool.handler, validated_inputs, context=context)

        try:
            raw_result = retry_exec.execute(
                op,
                policy=policy,
                retryable_exceptions=retryable_exceptions,
                classifier=classifier,
                sleeper=recording_sleeper,
                time_fn=clock,
            )
            elapsed = clock() - start_time
            if isinstance(raw_result, BaseModel):
                data = raw_result.model_dump()
            elif isinstance(raw_result, dict):
                data = raw_result
            else:
                data = {"result": raw_result}

            return ToolExecutionResult(
                success=True,
                data=data,
                tool_name=tool.name,
                risk_level=tool.risk_level,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
            )
        except Exception as exc:
            elapsed = clock() - start_time
            return ToolExecutionResult(
                success=False,
                error=str(exc),
                tool_name=tool.name,
                risk_level=tool.risk_level,
                attempts=attempt_count,
                execution_time_seconds=elapsed,
                retry_delays=retry_delays,
            )


# Default singleton executor wrapper
resilient_tool_executor = ResilientToolExecutor()
