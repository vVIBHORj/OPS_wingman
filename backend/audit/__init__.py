"""
Audit and Observability Subsystem for OpsWingman (Phase 4/5 - Deliverable D-16).
Provides structured auditing, observability dispatch, timeline compilation, and provenance tracking.
"""

from database.models.enums import AuditEventType
from database.models.audit import AuditEventRecord
from backend.audit.schemas import (
    AuditEventCreate,
    AuditEventResponse,
    AuditTimelineResponse,
    sanitize_audit_data,
)
from backend.audit.observability import (
    BaseObservabilitySink,
    StructuredLoggingSink,
    PluggableObservabilitySink,
    ObservabilityManager,
    default_observability_manager,
)
from backend.audit.service import AuditService, audit_service

observability_manager = default_observability_manager

__all__ = [
    "AuditEventType",
    "AuditEventRecord",
    "AuditEventCreate",
    "AuditEventResponse",
    "AuditTimelineResponse",
    "sanitize_audit_data",
    "BaseObservabilitySink",
    "StructuredLoggingSink",
    "PluggableObservabilitySink",
    "ObservabilityManager",
    "default_observability_manager",
    "observability_manager",
    "AuditService",
    "audit_service",
]
