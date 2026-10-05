"""
Audit Service for OpsWingman (Phase 4/5 - Deliverable D-16).
Provides centralized, thread-safe, durable recording of agent workflow provenance,
tool executions, policy governance, ML risk evaluations, resilience interventions,
and post-action state verifications.
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.audit import AuditEventRecord
from database.models.enums import AuditEventType
from backend.audit.schemas import (
    AuditEventCreate,
    AuditEventResponse,
    AuditTimelineResponse,
    sanitize_audit_data,
)
from backend.audit.observability import ObservabilityManager, default_observability_manager


class AuditService:
    """Service for creating, querying, and managing durable audit and provenance records."""

    def __init__(
        self,
        db: Optional[Session] = None,
        observability: Optional[ObservabilityManager] = None,
    ) -> None:
        self.db = db
        self.observability = observability or default_observability_manager
        self._lock = threading.Lock()
        # Fast queryable cache by run_id and event_id for offline/test reliability
        self._events_by_run: Dict[str, List[AuditEventRecord]] = {}
        self._events_by_id: Dict[str, AuditEventRecord] = {}

    def _get_active_session(self, explicit_session: Optional[Session] = None) -> Optional[Session]:
        """Resolves the preferred database session."""
        return explicit_session or self.db

    def record_event(
        self,
        event: AuditEventCreate,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records a generic structured audit event."""
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Sanitize sensitive arguments and payload data
        clean_args = sanitize_audit_data(event.tool_arguments)
        clean_result = sanitize_audit_data(event.tool_result_summary)
        clean_policy = sanitize_audit_data(event.policy_decision)
        clean_risk = sanitize_audit_data(event.risk_assessment_summary)
        clean_idemp = sanitize_audit_data(event.idempotency_info)
        clean_meta = sanitize_audit_data(event.metadata_provenance)

        record = AuditEventRecord(
            event_id=event_id,
            run_id=event.run_id,
            timestamp=now,
            event_type=event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            actor=event.actor,
            workflow_state=event.workflow_state,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            operation=event.operation,
            tool_name=event.tool_name,
            tool_arguments=clean_args,
            tool_result_summary=clean_result,
            policy_decision=clean_policy,
            risk_assessment_summary=clean_risk,
            verification_status=event.verification_status,
            approval_status=event.approval_status,
            retry_attempt=event.retry_attempt,
            idempotency_info=clean_idemp,
            success=event.success,
            error_message=event.error_message,
            metadata_provenance=clean_meta,
        )

        # 1. Persist to database if a session is accessible
        active_db = self._get_active_session(session)
        if active_db:
            try:
                active_db.add(record)
                active_db.flush()
            except Exception:
                # Fall back safely without crashing active workflow
                pass

        # 2. Store in thread-safe memory store
        with self._lock:
            if event.run_id not in self._events_by_run:
                self._events_by_run[event.run_id] = []
            self._events_by_run[event.run_id].append(record)
            self._events_by_id[event_id] = record

        # 3. Dispatch to observability sinks
        self.observability.dispatch(
            event_id=event_id,
            run_id=event.run_id,
            event_type=event.event_type,
            actor=event.actor,
            data={
                "operation": event.operation,
                "tool_name": event.tool_name,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "success": event.success,
                "error_message": event.error_message,
            },
        )

        return record

    def record_tool_execution(
        self,
        run_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[Dict[str, Any]],
        success: bool = True,
        error: Optional[str] = None,
        workflow_state: Optional[str] = None,
        resilience_metadata: Optional[Dict[str, Any]] = None,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records an operational tool execution with its arguments, result, and resilience telemetry."""
        res_meta = resilience_metadata or {}
        event_type = AuditEventType.TOOL_EXECUTED if success else AuditEventType.TOOL_FAILED

        # Check if an idempotency hit occurred
        is_cached = bool(res_meta.get("is_cached") is True or res_meta.get("final_status") == "CACHED")
        if is_cached:
            # Emit dedicated idempotency audit event first
            self.record_event(
                AuditEventCreate(
                    run_id=run_id,
                    event_type=AuditEventType.IDEMPOTENCY_HIT,
                    tool_name=tool_name,
                    operation=tool_name,
                    workflow_state=workflow_state,
                    idempotency_info={
                        "idempotency_key": res_meta.get("idempotency_key"),
                        "scope": res_meta.get("scope"),
                        "is_cached": True,
                    },
                    success=True,
                ),
                session=session,
            )

        # Check if retries were attempted
        attempt_count = int(res_meta.get("attempts", res_meta.get("attempt_count", 1)) or 1)
        if attempt_count > 1:
            self.record_event(
                AuditEventCreate(
                    run_id=run_id,
                    event_type=AuditEventType.RETRY_ATTEMPTED,
                    tool_name=tool_name,
                    operation=tool_name,
                    workflow_state=workflow_state,
                    retry_attempt=attempt_count,
                    idempotency_info={
                        "idempotency_key": res_meta.get("idempotency_key"),
                        "retry_delays": res_meta.get("retry_delays"),
                        "timed_out": res_meta.get("timed_out", False),
                    },
                    success=success,
                    error_message=res_meta.get("error_message") or error,
                ),
                session=session,
            )

        # For state-changing mutations, record ACTION_EXECUTED
        if success and tool_name in ["cancel_order", "request_refund", "create_ticket"]:
            self.record_event(
                AuditEventCreate(
                    run_id=run_id,
                    event_type=AuditEventType.ACTION_EXECUTED,
                    operation=tool_name,
                    tool_name=tool_name,
                    tool_arguments=arguments,
                    tool_result_summary=result,
                    workflow_state=workflow_state,
                    retry_attempt=attempt_count,
                    idempotency_info={
                        "idempotency_key": res_meta.get("idempotency_key"),
                        "scope": res_meta.get("scope"),
                        "is_cached": is_cached,
                        "timed_out": res_meta.get("timed_out", False),
                    },
                    success=True,
                ),
                session=session,
            )

        return self.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=event_type,
                operation=tool_name,
                tool_name=tool_name,
                tool_arguments=arguments,
                tool_result_summary=result,
                workflow_state=workflow_state,
                retry_attempt=attempt_count,
                idempotency_info={
                    "idempotency_key": res_meta.get("idempotency_key"),
                    "scope": res_meta.get("scope"),
                    "is_cached": is_cached,
                    "timed_out": res_meta.get("timed_out", False),
                },
                success=success,
                error_message=error,
            ),
            session=session,
        )

    def record_policy_decision(
        self,
        run_id: str,
        policy_decision: Dict[str, Any],
        operation: Optional[str] = None,
        workflow_state: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records deterministic policy governance decision and triggered rules."""
        return self.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=AuditEventType.POLICY_EVALUATED,
                operation=operation or str(policy_decision.get("policy_id", "policy_evaluation")),
                policy_decision=policy_decision,
                workflow_state=workflow_state,
                success=bool(policy_decision.get("allowed", True)),
            ),
            session=session,
        )

    def record_risk_assessment(
        self,
        run_id: str,
        risk_assessment: Dict[str, Any],
        operation: Optional[str] = None,
        workflow_state: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records ML risk scoring evaluation, anomaly flags, and explainability provenance."""
        return self.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=AuditEventType.RISK_ASSESSED,
                operation=operation or "assess_risk",
                risk_assessment_summary=risk_assessment,
                workflow_state=workflow_state,
                success=True,
            ),
            session=session,
        )

    def record_verification(
        self,
        run_id: str,
        verification_result: Dict[str, Any],
        operation: Optional[str] = None,
        workflow_state: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records post-action state verification against persistent database ground truth."""
        status_val = str(verification_result.get("status", "VERIFIED"))
        verified_bool = bool(verification_result.get("verified", False))

        return self.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=AuditEventType.VERIFICATION_COMPLETED,
                operation=operation or verification_result.get("operation") or "verify_state",
                entity_type=verification_result.get("entity_type"),
                entity_id=str(verification_result.get("entity_id", "")),
                verification_status=status_val,
                metadata_provenance={
                    "target_state": verification_result.get("target_state"),
                    "actual_state": verification_result.get("actual_state"),
                    "discrepancies": verification_result.get("discrepancies") or [],
                },
                workflow_state=workflow_state,
                success=verified_bool,
                error_message=verification_result.get("error"),
            ),
            session=session,
        )

    def record_approval(
        self,
        run_id: str,
        approval_id: Optional[str] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        approval_status: Optional[str] = None,
        approver_id: Optional[str] = None,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        decision_reason: Optional[str] = None,
        workflow_state: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records human approval requests or operator decisions."""
        resolved_status = approval_status or status or "PENDING"
        resolved_reason = decision_reason or reason
        resolved_actor = actor or approver_id or "Supervisor"
        event_type = (
            AuditEventType.APPROVAL_REQUESTED
            if resolved_status == "PENDING"
            else AuditEventType.APPROVAL_RESOLVED
        )

        return self.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=event_type,
                operation=action or "approval_decision",
                approval_status=resolved_status,
                actor=resolved_actor,
                workflow_state=workflow_state,
                metadata_provenance={
                    "approval_id": approval_id or "Pending",
                    "reason": resolved_reason,
                },
                success=(resolved_status != "REJECTED"),
            ),
            session=session,
        )

    def record_workflow_completion(
        self,
        run_id: str,
        final_response: str,
        workflow_state: Optional[str] = "COMPLETED",
        metadata: Optional[Dict[str, Any]] = None,
        metadata_provenance: Optional[Dict[str, Any]] = None,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records successful workflow execution completion."""
        meta = metadata_provenance or metadata or {}
        return self.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=AuditEventType.WORKFLOW_COMPLETED,
                workflow_state=workflow_state or "COMPLETED",
                tool_result_summary={"final_response": final_response},
                metadata_provenance=meta,
                success=True,
            ),
            session=session,
        )

    def record_workflow_failure(
        self,
        run_id: str,
        error: Optional[str] = None,
        workflow_state: Optional[str] = "FAILED",
        final_response: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        metadata_provenance: Optional[Dict[str, Any]] = None,
        session: Optional[Session] = None,
    ) -> AuditEventRecord:
        """Records workflow failure or unhandled exception."""
        meta = metadata_provenance or metadata or {}
        tool_res = {"final_response": final_response} if final_response else None
        err_msg = error or "Workflow execution failed"
        return self.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=AuditEventType.WORKFLOW_FAILED,
                workflow_state=workflow_state or "FAILED",
                tool_result_summary=tool_res,
                error_message=err_msg,
                metadata_provenance=meta,
                success=False,
            ),
            session=session,
        )

    def get_event(
        self,
        event_id: str,
        session: Optional[Session] = None,
    ) -> Optional[AuditEventResponse]:
        """Retrieves a specific audit event by unique event_id."""
        active_db = self._get_active_session(session)
        if active_db:
            try:
                stmt = select(AuditEventRecord).where(AuditEventRecord.event_id == event_id)
                db_record = active_db.scalar(stmt)
                if db_record:
                    return AuditEventResponse.model_validate(db_record)
            except Exception:
                pass

        with self._lock:
            cached = self._events_by_id.get(event_id)
            if cached:
                return AuditEventResponse.model_validate(cached)

        return None

    def get_run_events(
        self,
        run_id: str,
        session: Optional[Session] = None,
    ) -> List[AuditEventResponse]:
        """Retrieves all audit events associated with a run_id in chronological order."""
        active_db = self._get_active_session(session)
        if active_db:
            try:
                stmt = (
                    select(AuditEventRecord)
                    .where(AuditEventRecord.run_id == run_id)
                    .order_by(AuditEventRecord.timestamp.asc())
                )
                db_records = list(active_db.scalars(stmt).all())
                if db_records:
                    return [AuditEventResponse.model_validate(r) for r in db_records]
            except Exception:
                pass

        with self._lock:
            cached_list = list(self._events_by_run.get(run_id, []))
            cached_list.sort(key=lambda r: r.timestamp)
            return [AuditEventResponse.model_validate(r) for r in cached_list]

    def get_timeline(
        self,
        run_id: str,
        session: Optional[Session] = None,
    ) -> AuditTimelineResponse:
        """Constructs an integrated chronological timeline summary for a workflow execution."""
        events = self.get_run_events(run_id, session=session)
        if not events:
            return AuditTimelineResponse(
                run_id=run_id,
                total_events=0,
                events=[],
            )

        start_time = events[0].timestamp
        end_time = events[-1].timestamp
        latest_state = events[-1].workflow_state

        executed_tools: List[str] = []
        policy_decisions: List[Dict[str, Any]] = []
        risk_summary: Optional[Dict[str, Any]] = None
        verification_summary: Optional[Dict[str, Any]] = None
        resilience_interventions: List[Dict[str, Any]] = []
        intent: Optional[str] = None

        for ev in events:
            if ev.event_type == AuditEventType.INTENT_INTERPRETED and ev.tool_result_summary:
                intent = ev.tool_result_summary.get("intent")
            if ev.tool_name and ev.tool_name not in executed_tools:
                executed_tools.append(ev.tool_name)
            if ev.policy_decision:
                policy_decisions.append(ev.policy_decision)
            if ev.risk_assessment_summary:
                risk_summary = ev.risk_assessment_summary
            if ev.verification_status:
                verification_summary = {
                    "entity_type": ev.entity_type,
                    "entity_id": ev.entity_id,
                    "status": ev.verification_status,
                    "success": ev.success,
                }
            if ev.event_type in (AuditEventType.RETRY_ATTEMPTED, AuditEventType.IDEMPOTENCY_HIT):
                resilience_interventions.append({
                    "event_type": ev.event_type.value,
                    "tool_name": ev.tool_name,
                    "idempotency_info": ev.idempotency_info,
                    "retry_attempt": ev.retry_attempt,
                })

        return AuditTimelineResponse(
            run_id=run_id,
            total_events=len(events),
            start_time=start_time,
            end_time=end_time,
            workflow_state=latest_state,
            intent=intent,
            executed_tools=executed_tools,
            policy_decisions=policy_decisions,
            risk_summary=risk_summary,
            verification_summary=verification_summary,
            resilience_interventions=resilience_interventions,
            events=events,
        )

    def clear(self) -> None:
        """Clears in-memory event cache (useful for test isolation)."""
        with self._lock:
            self._events_by_run.clear()
            self._events_by_id.clear()


# Default singleton instance
audit_service = AuditService()
