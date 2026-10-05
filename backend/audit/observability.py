"""
Observability Abstraction for OpsWingman (Phase 4/5 - Deliverable D-16).
Provides local-first structured logging by default and optional pluggable sinks
for OpenTelemetry and Langfuse without requiring external services to be online.
"""

import abc
import json
import logging
from typing import Any, Dict, List, Optional
from database.models.enums import AuditEventType

logger = logging.getLogger("opswingman.audit")


class BaseObservabilitySink(abc.ABC):
    """Abstract base class for observability sinks."""

    @abc.abstractmethod
    def emit_event(
        self,
        event_id: str,
        run_id: str,
        event_type: AuditEventType,
        actor: str,
        data: Dict[str, Any],
    ) -> None:
        """Emits a structured audit/observability event to the sink."""
        pass


class StructuredLoggingSink(BaseObservabilitySink):
    """Local-first structured logging sink outputting JSON-compatible audit logs."""

    def __init__(self, log_level: int = logging.INFO) -> None:
        self.logger = logger
        self.log_level = log_level

    def emit_event(
        self,
        event_id: str,
        run_id: str,
        event_type: AuditEventType,
        actor: str,
        data: Dict[str, Any],
    ) -> None:
        record = {
            "audit_event_id": event_id,
            "run_id": run_id,
            "event_type": event_type.value if hasattr(event_type, "value") else str(event_type),
            "actor": actor,
            "payload": data,
        }
        self.logger.log(
            self.log_level,
            "AUDIT_RECORD: %s",
            json.dumps(record, default=str),
        )


class PluggableObservabilitySink(BaseObservabilitySink):
    """Optional forwarder to OpenTelemetry / Langfuse if configured in the environment."""

    def __init__(self, otel_enabled: bool = False, langfuse_enabled: bool = False) -> None:
        self.otel_enabled = otel_enabled
        self.langfuse_enabled = langfuse_enabled

    def emit_event(
        self,
        event_id: str,
        run_id: str,
        event_type: AuditEventType,
        actor: str,
        data: Dict[str, Any],
    ) -> None:
        # Gracefully handle optional OTel / Langfuse integration without breaking local-first runtime
        if self.otel_enabled:
            # Placeholder hook for OpenTelemetry span attribute forwarding
            pass
        if self.langfuse_enabled:
            # Placeholder hook for Langfuse trace/event ingestion
            pass


class ObservabilityManager:
    """Dispatches audit events to all registered observability sinks."""

    def __init__(self, sinks: Optional[List[BaseObservabilitySink]] = None) -> None:
        self.sinks: List[BaseObservabilitySink] = sinks or [StructuredLoggingSink()]

    def add_sink(self, sink: BaseObservabilitySink) -> None:
        self.sinks.append(sink)

    def register_sink(self, sink: BaseObservabilitySink) -> None:
        self.add_sink(sink)

    def dispatch(
        self,
        event_id: str,
        run_id: str,
        event_type: AuditEventType,
        actor: str,
        data: Dict[str, Any],
    ) -> None:
        for sink in self.sinks:
            try:
                sink.emit_event(event_id, run_id, event_type, actor, data)
            except Exception as exc:
                logger.warning("Failed to emit audit event to sink %s: %s", type(sink).__name__, exc)


# Default singleton instance
default_observability_manager = ObservabilityManager()
