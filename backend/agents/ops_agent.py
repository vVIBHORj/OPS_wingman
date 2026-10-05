"""Stateful Ops Agent powered by LangGraph (Phase 3 - Deliverables D-10, D-11, D-12).

Coordinates intent interpretation, RAG knowledge retrieval, tool planning,
deterministic policy evaluation, human approval gating, and response synthesis.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, TypedDict, cast
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

import simulator
from backend.approvals.service import ApprovalService
from backend.audit import (
    AuditService,
    audit_service as default_audit_service,
    AuditEventType,
    AuditEventCreate,
)
from backend.ml import (
    AnomalyInfo,
    MLRiskService,
    RiskAssessmentResult,
    RiskBand,
    RiskFeatureVector,
    ml_risk_service,
)
from backend.policies.engine import policy_engine
from backend.policies.schemas import PolicyEvaluationResult
from backend.rag.schemas import KnowledgeCitation, RetrievalRequest
from backend.rag.service import RAGService
from backend.resilience import (
    IdempotencyService,
    ResilientToolExecutor,
    RetryExecutor,
    idempotency_service as default_idempotency_service,
    retry_executor as default_retry_executor,
)
from backend.tools.base import RiskLevel, ToolRegistry
from backend.tools.registry import create_default_tool_registry
from backend.verification import (
    StateVerificationService,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    state_verification_service,
)
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import StructuredAction, WorkflowRunRecord, WorkflowState
from database.models.enums import ApprovalStatus


class AgentGraphState(TypedDict, total=False):
    """Execution state schema flowing through the LangGraph agent."""
    workflow_id: str
    run_id: str
    input_text: str
    customer_id: Optional[str]
    order_id: Optional[str]
    order_number: Optional[str]
    intent: Optional[str]
    extracted_entities: Dict[str, Any]
    retrieved_citations: List[Dict[str, Any]]
    planned_tools: List[str]
    executed_tools: List[str]
    tool_results: Dict[str, Any]
    proposed_actions: List[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    policy_decisions: List[Dict[str, Any]]
    verification_results: List[Dict[str, Any]]
    resilience_records: List[Dict[str, Any]]
    requires_approval: bool
    approval_id: Optional[str]
    final_response: Optional[str]
    workflow_state: str
    error: Optional[str]
    db: Optional[Session]


class OpsAgent:
    """Stateful workflow agent orchestrating operational inquiries and policy-gated actions."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        verification_service: Optional[StateVerificationService] = None,
        risk_service: Optional[MLRiskService] = None,
        idempotency_service: Optional[IdempotencyService] = None,
        retry_executor: Optional[RetryExecutor] = None,
        resilience_wrapper: Optional[ResilientToolExecutor] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.idempotency_service = idempotency_service or default_idempotency_service
        self.retry_executor = retry_executor or default_retry_executor
        self.resilience_wrapper = resilience_wrapper or ResilientToolExecutor(
            idempotency_service=self.idempotency_service,
            retry_executor=self.retry_executor,
        )
        self.tools = tool_registry or create_default_tool_registry(
            resilience_wrapper=self.resilience_wrapper,
        )
        self.verification_service = verification_service or state_verification_service
        self.risk_service = risk_service or ml_risk_service
        self.audit_service = audit_service or default_audit_service
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(cast(Any, AgentGraphState))

        builder.add_node("interpret_request", self._node_interpret_request)
        builder.add_node("retrieve_knowledge", self._node_retrieve_knowledge)
        builder.add_node("plan_tools", self._node_plan_tools)
        builder.add_node("execute_tools", self._node_execute_tools)
        builder.add_node("assess_risk", self._node_assess_risk)
        builder.add_node("evaluate_policy", self._node_evaluate_policy)
        builder.add_node("verify_execution", self._node_verify_execution)
        builder.add_node("synthesize_response", self._node_synthesize_response)

        builder.set_entry_point("interpret_request")
        builder.add_edge("interpret_request", "retrieve_knowledge")
        builder.add_edge("retrieve_knowledge", "plan_tools")
        builder.add_edge("plan_tools", "execute_tools")
        builder.add_edge("execute_tools", "assess_risk")
        builder.add_edge("assess_risk", "evaluate_policy")
        builder.add_edge("evaluate_policy", "verify_execution")
        builder.add_edge("verify_execution", "synthesize_response")
        builder.add_edge("synthesize_response", END)

        return builder.compile()

    # ==========================================================================
    # Graph Nodes
    # ==========================================================================

    def _node_interpret_request(self, state: AgentGraphState) -> Dict[str, Any]:
        """Extracts intent and key entities (order number, email, UUIDs)."""
        text = state.get("input_text", "")
        entities: Dict[str, Any] = {}

        # 1. Regex Entity Extraction
        order_match = re.search(r"ORD-\d{8}-[A-Z0-9]{6}", text, re.IGNORECASE)
        if order_match:
            entities["order_number"] = order_match.group(0).upper()
        elif state.get("order_number"):
            entities["order_number"] = str(state.get("order_number"))

        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        if email_match:
            entities["email"] = email_match.group(0).lower()

        uuid_match = re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            text,
            re.IGNORECASE,
        )
        if uuid_match:
            entities["entity_uuid"] = uuid_match.group(0)

        # 2. Intent Classification
        text_lower = text.lower()
        if any(k in text_lower for k in ["cancel", "cancellation", "abort order"]):
            intent = "cancel_order_request"
        elif any(k in text_lower for k in ["refund", "money back", "return payment", "refund everything"]):
            intent = "request_refund"
        elif any(k in text_lower for k in ["track", "shipment", "courier", "delivery status", "where is my"]):
            intent = "track_shipment"
        elif any(k in text_lower for k in ["payment", "charged", "invoice"]):
            intent = "check_payment_status"
        elif any(k in text_lower for k in ["status", "order status", "order update"]):
            intent = "check_order_status"
        else:
            intent = "general_order_inquiry"

        run_id = state.get("run_id", "")
        checkpoint_store.add_step(
            run_id=run_id,
            step_name="interpret_request",
            state=WorkflowState.RUNNING,
            input_payload={"input_text": text},
            output_payload={"intent": intent, "extracted_entities": entities},
        )

        self.audit_service.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=AuditEventType.INTENT_INTERPRETED,
                actor="OpsAgent",
                workflow_state=WorkflowState.RUNNING.value,
                entity_type="order" if entities.get("order_number") else None,
                entity_id=entities.get("order_number") or entities.get("entity_uuid"),
                tool_result_summary={"intent": intent, "extracted_entities": entities},
                success=True,
            ),
            session=state.get("db"),
        )

        return {
            "intent": intent,
            "extracted_entities": entities,
            "order_number": entities.get("order_number") or state.get("order_number"),
            "workflow_state": WorkflowState.RUNNING.value,
        }

    def _node_retrieve_knowledge(self, state: AgentGraphState) -> Dict[str, Any]:
        """Retrieves relevant policy, SOP, and guideline documents via RAG (D-10)."""
        input_text = state.get("input_text", "")
        db = state.get("db")
        citations: List[Dict[str, Any]] = []

        if db and input_text:
            try:
                rag_service = RAGService(db)
                retrieval_res = rag_service.retrieve(
                    RetrievalRequest(query=input_text, top_k=3, min_similarity=0.0)
                )
                citations = [c.model_dump() for c in retrieval_res.results]
            except Exception as e:
                citations = []

        run_id = state.get("run_id", "")
        checkpoint_store.add_step(
            run_id=run_id,
            step_name="retrieve_knowledge",
            state=WorkflowState.RUNNING,
            input_payload={"query": input_text},
            output_payload={"citations_count": len(citations), "citations": citations},
        )

        return {
            "retrieved_citations": citations,
        }

    def _node_plan_tools(self, state: AgentGraphState) -> Dict[str, Any]:
        """Plans read tools and structured action proposals based on intent."""
        intent = state.get("intent", "general_order_inquiry")
        planned: List[str] = []
        proposed_actions: List[Dict[str, Any]] = []

        if intent in ["check_order_status", "general_order_inquiry"]:
            planned.extend(["get_order", "get_shipment"])
        elif intent == "track_shipment":
            planned.extend(["get_order", "get_shipment"])
        elif intent == "check_payment_status":
            planned.extend(["get_order", "get_payment"])
        elif intent == "cancel_order_request":
            planned.extend(["get_order", "get_shipment"])
            proposed_actions.append({
                "action": "cancel_order",
                "parameters": {
                    "order_number": state.get("order_number"),
                    "reason": "Customer cancellation request",
                },
                "reason": "Customer explicitly requested order cancellation",
                "risk": RiskLevel.HIGH.value,
                "requires_approval": True,
            })
        elif intent == "request_refund":
            planned.extend(["get_order", "get_payment"])
            proposed_actions.append({
                "action": "request_refund",
                "parameters": {
                    "order_number": state.get("order_number"),
                    "reason": "Customer refund request",
                },
                "reason": "Customer requested refund for transaction",
                "risk": RiskLevel.HIGH.value,
                "requires_approval": True,
            })

        run_id = state.get("run_id", "")
        checkpoint_store.add_step(
            run_id=run_id,
            step_name="plan_tools",
            state=WorkflowState.RUNNING,
            output_payload={"planned_tools": planned, "proposed_actions": proposed_actions},
        )

        self.audit_service.record_event(
            AuditEventCreate(
                run_id=run_id,
                event_type=AuditEventType.TOOL_PLANNED,
                actor="OpsAgent",
                workflow_state=WorkflowState.RUNNING.value,
                metadata_provenance={"planned_tools": planned, "proposed_actions": proposed_actions},
                success=True,
            ),
            session=state.get("db"),
        )

        return {
            "planned_tools": planned,
            "proposed_actions": proposed_actions,
        }

    def _node_execute_tools(self, state: AgentGraphState) -> Dict[str, Any]:
        """Executes read tools safely through ToolRegistry."""
        planned = state.get("planned_tools", [])
        results: Dict[str, Any] = {}
        executed: List[str] = []
        resilience_records: List[Dict[str, Any]] = list(state.get("resilience_records") or [])
        db = state.get("db")
        run_id = state.get("run_id", "")

        order_number = state.get("order_number")
        order_id = state.get("order_id")

        for tool_name in planned:
            params: Dict[str, Any] = {}
            if tool_name == "get_order":
                if order_number:
                    params["order_number"] = order_number
                elif order_id:
                    params["order_id"] = order_id
            elif tool_name == "get_shipment":
                order_res = results.get("get_order")
                ord_data = (order_res.get("data") or {}) if order_res else {}
                if ord_data.get("id"):
                    params["order_id"] = ord_data["id"]
                elif order_id:
                    params["order_id"] = order_id
            elif tool_name == "get_payment":
                order_res = results.get("get_order")
                ord_data = (order_res.get("data") or {}) if order_res else {}
                if ord_data.get("id"):
                    params["order_id"] = ord_data["id"]
                elif order_id:
                    params["order_id"] = order_id

            tool_context = {
                "db": db,
                "workflow_id": state.get("workflow_id", run_id),
                "run_id": run_id,
            } if db else None
            res = self.tools.execute(tool_name, params=params, context=tool_context)
            results[tool_name] = res.model_dump()
            executed.append(tool_name)
            if res.resilience_metadata:
                resilience_records.append(res.resilience_metadata)

            checkpoint_store.add_step(
                run_id=run_id,
                step_name=f"execute_tool_{tool_name}",
                state=WorkflowState.RUNNING if res.success else WorkflowState.FAILED,
                tool_name=tool_name,
                input_payload=params,
                output_payload=res.model_dump(),
                error=res.error,
            )

            self.audit_service.record_tool_execution(
                run_id=run_id,
                tool_name=tool_name,
                arguments=params,
                result=res.data if res.success else None,
                success=res.success,
                error=res.error,
                workflow_state=WorkflowState.RUNNING.value if res.success else WorkflowState.FAILED.value,
                resilience_metadata=res.resilience_metadata,
                session=db,
            )

        return {
            "executed_tools": executed,
            "tool_results": results,
            "resilience_records": resilience_records,
        }

    def _node_assess_risk(self, state: AgentGraphState) -> Dict[str, Any]:
        """Assesses dynamic operational risk using the ML risk subsystem (D-13).

        Evaluates features from database entities or execution state, records model metadata
        and anomalies, and updates proposed action risk ratings accordingly.
        """
        tool_results = state.get("tool_results", {})
        order_data = tool_results.get("get_order", {}).get("data") or {}
        shipment_data = tool_results.get("get_shipment", {}).get("data") or {}
        payment_data = tool_results.get("get_payment", {}).get("data") or {}

        target_order_id = (
            order_data.get("id")
            or state.get("order_id")
            or order_data.get("order_number")
            or state.get("order_number")
        )
        db = state.get("db")
        run_id = state.get("run_id", "")

        risk_res = None
        if db is not None and target_order_id is not None:
            try:
                risk_res = self.risk_service.assess_order(session=db, order_id=str(target_order_id))
            except Exception:
                risk_res = None

        if risk_res is None:
            try:
                # Fallback to feature-vector scoring from in-memory tool results
                order_amount = float(order_data.get("total_amount", 0.0) or 0.0)
                delivery_delay_hours = (
                    24.0
                    if (shipment_data.get("delay_reason") or shipment_data.get("status") == "DELAYED")
                    else 0.0
                )
                failed_payments = 1 if payment_data.get("status") == "FAILED" else 0
                features = RiskFeatureVector(
                    order_amount=max(0.0, order_amount),
                    delivery_delay_hours=delivery_delay_hours,
                    failed_payment_count=failed_payments,
                )
                risk_res = self.risk_service.assess_risk(features)
            except Exception as exc:
                # Safe defined fallback if ML risk assessment completely fails
                features = RiskFeatureVector()
                risk_res = RiskAssessmentResult(
                    model_version="v1.0.0-fallback",
                    risk_score=0.5,
                    risk_band=RiskBand.MEDIUM,
                    is_high_risk=False,
                    features=features,
                    contributions=[],
                    top_risk_factors=[f"ML scoring fallback: {exc}"],
                    anomaly=AnomalyInfo(is_anomaly=False, anomaly_score=0.0, anomaly_flags=[]),
                )

        risk_dict = risk_res.model_dump(mode="json")
        anomaly_flags = list(risk_res.anomaly.anomaly_flags) if risk_res.anomaly else []
        risk_flags = anomaly_flags or risk_res.top_risk_factors

        # Update proposed actions with ML risk insights
        proposed_actions = list(state.get("proposed_actions", []))
        if risk_res.risk_band == RiskBand.HIGH:
            for act in proposed_actions:
                act["risk"] = RiskLevel.HIGH.value
                if risk_flags:
                    reasons = "; ".join(risk_flags)
                    existing_reason = act.get("reason", "")
                    act["reason"] = f"{existing_reason} [Elevated Risk: {reasons}]".strip()
        elif risk_res.risk_band == RiskBand.MEDIUM:
            for act in proposed_actions:
                if act.get("risk") == RiskLevel.LOW.value:
                    act["risk"] = RiskLevel.MEDIUM.value

        checkpoint_store.add_step(
            run_id=run_id,
            step_name="assess_risk",
            state=WorkflowState.RUNNING,
            output_payload={
                "risk_assessment": risk_dict,
            },
        )

        self.audit_service.record_risk_assessment(
            run_id=run_id,
            risk_assessment=risk_dict,
            operation="assess_risk",
            workflow_state=WorkflowState.RUNNING.value,
            session=state.get("db"),
        )

        return {
            "risk_assessment": risk_dict,
            "proposed_actions": proposed_actions,
        }

    def _node_evaluate_policy(self, state: AgentGraphState) -> Dict[str, Any]:
        """Evaluates domain policies deterministically against ground-truth database facts (D-11).

        Creates durable ApprovalRecord if human approval is required (D-12).
        """
        proposed_actions = state.get("proposed_actions", [])
        tool_results = state.get("tool_results", {})
        retrieved_citations_raw = state.get("retrieved_citations", [])
        citations = [KnowledgeCitation(**c) for c in retrieved_citations_raw]

        order_data = tool_results.get("get_order", {}).get("data") or {}
        shipment_data = tool_results.get("get_shipment", {}).get("data") or {}
        payment_data = tool_results.get("get_payment", {}).get("data") or {}

        risk_assessment = state.get("risk_assessment") or {}
        ml_risk_score = float(risk_assessment.get("risk_score", 0.0) or 0.0)
        ml_risk_band = str(risk_assessment.get("risk_band", "LOW")).upper()
        anomaly_dict = risk_assessment.get("anomaly") or {}
        ml_anomalies = list(anomaly_dict.get("anomaly_flags") or [])
        ml_anomaly_detected = bool(anomaly_dict.get("is_anomaly", False)) or len(ml_anomalies) > 0
        ml_version = str(risk_assessment.get("model_version", "v1.0.0"))

        # Construct ground truth facts
        facts: Dict[str, Any] = {
            "order_status": order_data.get("status"),
            "order_total": order_data.get("total_amount", 0.0),
            "payment_status": payment_data.get("status"),
            "refund_amount": payment_data.get("amount") or order_data.get("total_amount", 0.0),
            "shipment_status": shipment_data.get("status"),
            "is_delayed": bool(shipment_data.get("delay_reason")),
            "cancellation_window_valid": order_data.get("status") in ["PENDING", "CONFIRMED"],
            "ml_risk_score": ml_risk_score,
            "ml_risk_band": ml_risk_band,
            "ml_anomaly_detected": ml_anomaly_detected,
            "ml_anomaly_reasons": ml_anomalies,
            "ml_model_version": ml_version,
        }

        policy_decisions: List[Dict[str, Any]] = []
        requires_approval = False
        approval_id: Optional[str] = None
        db = state.get("db")
        run_id = state.get("run_id", "")
        wf_id = state.get("workflow_id", run_id)

        for act in proposed_actions:
            struct_action = StructuredAction(**act)
            eval_result: PolicyEvaluationResult = policy_engine.evaluate(
                action=struct_action,
                facts=facts,
                citations=citations,
            )
            policy_decisions.append(eval_result.model_dump())
            self.audit_service.record_policy_decision(
                run_id=run_id,
                policy_decision=eval_result.model_dump(),
                operation=struct_action.action,
                workflow_state=WorkflowState.RUNNING.value,
                session=db,
            )

            if eval_result.requires_approval:
                requires_approval = True
                # Create durable approval record if db is available
                if db:
                    approval_service = ApprovalService(db)
                    record = approval_service.create_approval(
                        workflow_id=wf_id,
                        action=struct_action,
                        risk_level=act.get("risk", RiskLevel.HIGH.value),
                        reason=eval_result.decision,
                        policy_decision=eval_result,
                        target_entity=order_data.get("order_number") or state.get("order_number"),
                    )
                    approval_id = str(record.id)
                self.audit_service.record_approval(
                    run_id=run_id,
                    approval_id=approval_id or "pending_approval",
                    action=struct_action.action,
                    status="PENDING",
                    reason=eval_result.decision,
                    workflow_state=WorkflowState.WAITING_FOR_APPROVAL.value,
                    session=db,
                )

        if not proposed_actions:
            self.audit_service.record_policy_decision(
                run_id=run_id,
                policy_decision={
                    "policy_id": "POL-INQ-001",
                    "allowed": True,
                    "decision": "ALLOWED",
                    "reason": "Read-only inquiry permitted under standard data policy.",
                },
                operation="evaluate_policy",
                workflow_state=WorkflowState.RUNNING.value,
                session=db,
            )

        wf_state = (
            WorkflowState.WAITING_FOR_APPROVAL
            if requires_approval
            else WorkflowState.RUNNING
        )

        checkpoint_store.add_step(
            run_id=run_id,
            step_name="evaluate_policy",
            state=wf_state,
            output_payload={
                "policy_decisions": policy_decisions,
                "requires_approval": requires_approval,
                "approval_id": approval_id,
                "workflow_state": wf_state.value,
            },
        )

        return {
            "policy_decisions": policy_decisions,
            "requires_approval": requires_approval,
            "approval_id": approval_id,
            "workflow_state": wf_state.value,
        }

    def _node_verify_execution(self, state: AgentGraphState) -> Dict[str, Any]:
        """Runs post-action state verification on executed state-changing operations (D-14)."""
        executed_tools = state.get("executed_tools", [])
        tool_results = state.get("tool_results", {})
        db = state.get("db")
        run_id = state.get("run_id", "")
        verification_results: List[Dict[str, Any]] = list(state.get("verification_results") or [])
        errors: List[str] = []

        if not db:
            return {"verification_results": verification_results}

        for tool_name in executed_tools:
            res_dict = tool_results.get(tool_name, {})
            # Only verify if tool execution reported success
            if not res_dict or not res_dict.get("success", False):
                continue

            data = res_dict.get("data") or {}

            if tool_name == "cancel_order":
                order_id = data.get("id") or data.get("order_number") or state.get("order_id") or state.get("order_number")
                if order_id:
                    ver_req = VerificationRequest(
                        entity_type="order",
                        entity_id=str(order_id),
                        target_state="CANCELLED",
                        operation="cancel_order",
                        expected_attributes={"cancellation_reason": data.get("cancellation_reason")} if data.get("cancellation_reason") else {},
                    )
                    ver_res = self.verification_service.verify(session=db, request=ver_req)
                    ver_dump = ver_res.model_dump(mode="json")
                    verification_results.append(ver_dump)
                    self.audit_service.record_verification(
                        run_id=run_id,
                        verification_result=ver_dump,
                        operation=tool_name,
                        workflow_state=WorkflowState.RUNNING.value if ver_res.verified else WorkflowState.FAILED.value,
                        session=db,
                    )
                    if not ver_res.verified:
                        errors.append(f"Verification {ver_res.status.value}: {', '.join(ver_res.discrepancies) or ver_res.error or 'State mismatch'}")

            elif tool_name == "request_refund":
                order_id = data.get("order_id") or state.get("order_id")
                if order_id:
                    ver_req = VerificationRequest(
                        entity_type="payment",
                        entity_id=str(order_id),
                        target_state="REFUNDED",
                        operation="request_refund",
                    )
                    ver_res = self.verification_service.verify(session=db, request=ver_req)
                    ver_dump = ver_res.model_dump(mode="json")
                    verification_results.append(ver_dump)
                    self.audit_service.record_verification(
                        run_id=run_id,
                        verification_result=ver_dump,
                        operation=tool_name,
                        workflow_state=WorkflowState.RUNNING.value if ver_res.verified else WorkflowState.FAILED.value,
                        session=db,
                    )
                    if not ver_res.verified:
                        errors.append(f"Verification {ver_res.status.value}: {', '.join(ver_res.discrepancies) or ver_res.error or 'State mismatch'}")

            elif tool_name == "create_ticket":
                ticket_id = data.get("id") or data.get("ticket_number")
                if ticket_id:
                    ver_req = VerificationRequest(
                        entity_type="ticket",
                        entity_id=str(ticket_id),
                        target_state="OPEN",
                        operation="create_ticket",
                        expected_attributes={"priority": data.get("priority")} if data.get("priority") else {},
                    )
                    ver_res = self.verification_service.verify(session=db, request=ver_req)
                    ver_dump = ver_res.model_dump(mode="json")
                    verification_results.append(ver_dump)
                    self.audit_service.record_verification(
                        run_id=run_id,
                        verification_result=ver_dump,
                        operation=tool_name,
                        workflow_state=WorkflowState.RUNNING.value if ver_res.verified else WorkflowState.FAILED.value,
                        session=db,
                    )
                    if not ver_res.verified:
                        errors.append(f"Verification {ver_res.status.value}: {', '.join(ver_res.discrepancies) or ver_res.error or 'State mismatch'}")

        if verification_results:
            has_divergence = any(
                r.get("status") in [
                    VerificationStatus.DIVERGENT.value,
                    VerificationStatus.NOT_FOUND.value,
                    VerificationStatus.ERROR.value,
                ]
                for r in verification_results
            )
            step_state = WorkflowState.FAILED if has_divergence else WorkflowState.RUNNING
            checkpoint_store.add_step(
                run_id=run_id,
                step_name="verify_execution",
                state=step_state,
                output_payload={"verification_results": verification_results},
                error="; ".join(errors) if errors else None,
            )

        updated_state: Dict[str, Any] = {
            "verification_results": verification_results,
        }
        if errors:
            updated_state["error"] = "; ".join(errors)
            updated_state["workflow_state"] = WorkflowState.FAILED.value

        return updated_state

    def _node_synthesize_response(self, state: AgentGraphState) -> Dict[str, Any]:
        """Synthesizes human-readable operational response based on retrieved data and policy decisions."""
        intent = state.get("intent", "general_order_inquiry")
        tool_results = state.get("tool_results", {})
        order_info = tool_results.get("get_order", {}).get("data")
        shipment_info = tool_results.get("get_shipment", {}).get("data")
        payment_info = tool_results.get("get_payment", {}).get("data")
        policy_decisions = state.get("policy_decisions", [])
        requires_approval = state.get("requires_approval", False)
        approval_id = state.get("approval_id")
        run_id = state.get("run_id", "")
        db: Optional[Session] = state.get("db")

        # Format citation references for transparency
        citations = state.get("retrieved_citations", [])
        citation_tags = [f"[{c.get('document_id')} v{c.get('version')}]" for c in citations[:2]]
        citation_suffix = f" (Policy Refs: {', '.join(citation_tags)})" if citation_tags else ""

        # Check if post-action verification produced any divergence or error
        ver_results = state.get("verification_results", [])
        ver_failure = next(
            (
                r for r in ver_results
                if r.get("status") in [
                    VerificationStatus.DIVERGENT.value,
                    VerificationStatus.NOT_FOUND.value,
                    VerificationStatus.ERROR.value,
                ]
            ),
            None,
        )

        err_details: Optional[str] = None
        if ver_failure:
            err_details = ", ".join(ver_failure.get("discrepancies", [])) or ver_failure.get("error") or ver_failure.get("status")
            response = f"Action execution failed post-action state verification ({ver_failure.get('status')}): {err_details}"
            final_state = WorkflowState.FAILED
        elif state.get("workflow_state") == WorkflowState.FAILED.value and state.get("error"):
            response = f"Workflow execution failed: {state.get('error')}"
            final_state = WorkflowState.FAILED
        elif not order_info and not state.get("order_number"):
            response = "Thank you for reaching out to OpsWingman. Could you please provide your Order Number (e.g., ORD-YYYYMMDD-XXXXXX) so I can retrieve your details?"
            final_state = WorkflowState.COMPLETED
        elif not order_info:
            err = tool_results.get("get_order", {}).get("error", "Order not found")
            response = f"I could not locate an order with reference {state.get('order_number')}. Error: {err}. Please verify your order number."
            final_state = WorkflowState.COMPLETED
        elif intent == "cancel_order_request":
            # Check policy evaluation decision
            pol_dec = policy_decisions[0] if policy_decisions else None
            if pol_dec and not pol_dec.get("allowed"):
                response = (
                    f"Cancellation Denied for order {order_info.get('order_number')}: {pol_dec.get('decision')}. "
                    f"Under policy {pol_dec.get('policy_id')} v{pol_dec.get('policy_version')}, shipped orders cannot be cancelled directly."
                    + citation_suffix
                )
                final_state = WorkflowState.COMPLETED
            elif requires_approval:
                response = (
                    f"Your cancellation request for order {order_info.get('order_number')} (Status: {order_info.get('status')}) "
                    f"has been submitted for supervisor approval (Approval ID: {approval_id or 'Pending'}). "
                    f"Policy Decision: {pol_dec.get('decision') if pol_dec else 'Approval Required'}."
                    + citation_suffix
                )
                final_state = WorkflowState.WAITING_FOR_APPROVAL
            else:
                response = f"Cancellation request for order {order_info.get('order_number')} processed successfully." + citation_suffix
                final_state = WorkflowState.COMPLETED

        elif intent == "request_refund":
            pol_dec = policy_decisions[0] if policy_decisions else None
            if pol_dec and not pol_dec.get("allowed"):
                response = (
                    f"Refund Denied for order {order_info.get('order_number')}: {pol_dec.get('decision')}. "
                    f"Policy reference: {pol_dec.get('policy_id')} v{pol_dec.get('policy_version')}."
                    + citation_suffix
                )
                final_state = WorkflowState.COMPLETED
            elif requires_approval:
                response = (
                    f"Your refund request for order {order_info.get('order_number')} (Amount: INR {order_info.get('total_amount')}) "
                    f"exceeds the automatic refund threshold and has been submitted to a supervisor for approval (Approval ID: {approval_id or 'Pending'}). "
                    f"Policy Decision: {pol_dec.get('decision') if pol_dec else 'Approval Required'}."
                    + citation_suffix
                )
                final_state = WorkflowState.WAITING_FOR_APPROVAL
            else:
                response = f"Refund request for order {order_info.get('order_number')} approved under policy." + citation_suffix
                final_state = WorkflowState.COMPLETED

        elif intent in ["track_shipment", "check_order_status", "general_order_inquiry"]:
            order_num = order_info.get("order_number")
            status = order_info.get("status")
            total = order_info.get("total_amount")
            currency = order_info.get("currency", "INR")

            parts = [f"Order {order_num} is currently in {status} state (Total: {currency} {total})."]

            if shipment_info:
                carrier = shipment_info.get("carrier")
                trk = shipment_info.get("tracking_number")
                shp_status = shipment_info.get("status")
                loc = shipment_info.get("current_location")
                parts.append(f"Shipment ({carrier}, Tracking #{trk}) is {shp_status}.")
                if loc:
                    parts.append(f"Current location: {loc}.")
                if shipment_info.get("delay_reason"):
                    parts.append(f"Delay Notice: {shipment_info.get('delay_reason')}.")

            response = " ".join(parts) + citation_suffix
            final_state = WorkflowState.COMPLETED

        elif intent == "check_payment_status":
            order_num = order_info.get("order_number")
            pay_status = payment_info.get("status") if payment_info else "UNKNOWN"
            amount = payment_info.get("amount") if payment_info else order_info.get("total_amount")
            response = f"Order {order_num} payment status is {pay_status} for amount INR {amount}." + citation_suffix
            final_state = WorkflowState.COMPLETED
        else:
            response = f"Order {order_info.get('order_number')} details retrieved successfully." + citation_suffix
            final_state = WorkflowState.COMPLETED

        checkpoint_store.add_step(
            run_id=run_id,
            step_name="synthesize_response",
            state=final_state,
            output_payload={"final_response": response},
        )

        # Update run record final values
        run_record = checkpoint_store.get(run_id)
        if run_record:
            run_record.final_response = response
            run_record.state = final_state
            if final_state == WorkflowState.FAILED:
                run_record.error = state.get("error") or (err_details if ver_failure else None)
            run_record.intent = intent
            run_record.extracted_entities = state.get("extracted_entities", {})
            run_record.proposed_actions = [StructuredAction(**a) for a in state.get("proposed_actions", [])]
            run_record.citations = state.get("retrieved_citations", [])
            run_record.policy_decisions = state.get("policy_decisions", [])
            run_record.verification_results = state.get("verification_results", [])
            run_record.risk_assessment = state.get("risk_assessment")
            run_record.resilience_records = state.get("resilience_records", [])
            run_record.approval_id = state.get("approval_id")
            if order_info:
                run_record.order_id = order_info.get("id")
                run_record.customer_id = order_info.get("customer_id")
            checkpoint_store.save(run_record)

        # Audit workflow completion or failure
        if final_state == WorkflowState.FAILED:
            self.audit_service.record_workflow_failure(
                run_id=run_id,
                workflow_state=final_state.value,
                error=state.get("error") or (err_details if ver_failure else response),
                final_response=response,
                session=db,
            )
        elif final_state == WorkflowState.COMPLETED:
            self.audit_service.record_workflow_completion(
                run_id=run_id,
                workflow_state=final_state.value,
                final_response=response,
                metadata={"intent": intent, "order_number": state.get("order_number")},
                session=db,
            )

        return {
            "final_response": response,
            "workflow_state": final_state.value,
        }

    # ==========================================================================
    # Run Entrypoint
    # ==========================================================================

    def run(
        self,
        input_text: str,
        order_number: Optional[str] = None,
        customer_id: Optional[str] = None,
        db: Optional[Session] = None,
        workflow_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> WorkflowRunRecord:
        """Executes a complete workflow run from a customer request or operational event."""
        wf_id = workflow_id or str(uuid.uuid4())
        r_id = run_id or str(uuid.uuid4())

        # Initialize checkpoint record
        run_record = WorkflowRunRecord(
            workflow_id=wf_id,
            run_id=r_id,
            input_text=input_text,
            customer_id=customer_id,
            state=WorkflowState.CREATED,
        )
        checkpoint_store.save(run_record)

        # Audit incoming request
        self.audit_service.record_event(
            AuditEventCreate(
                run_id=r_id,
                event_type=AuditEventType.REQUEST_RECEIVED,
                actor="user",
                workflow_state=WorkflowState.CREATED.value,
                tool_arguments={"input_text": input_text, "order_number": order_number, "customer_id": customer_id},
                metadata_provenance={"workflow_id": wf_id},
            ),
            session=db,
        )

        # Initial graph state
        initial_state: AgentGraphState = {
            "workflow_id": wf_id,
            "run_id": r_id,
            "input_text": input_text,
            "order_number": order_number,
            "customer_id": customer_id,
            "planned_tools": [],
            "executed_tools": [],
            "tool_results": {},
            "proposed_actions": [],
            "retrieved_citations": [],
            "policy_decisions": [],
            "verification_results": [],
            "risk_assessment": None,
            "resilience_records": [],
            "requires_approval": False,
            "approval_id": None,
            "workflow_state": WorkflowState.CREATED.value,
            "db": db,
        }

        # Invoke the LangGraph execution pipeline
        self.graph.invoke(initial_state)

        return checkpoint_store.get(r_id) or run_record

    def resume(
        self,
        run_id: str,
        approved: bool,
        db: Optional[Session] = None,
        reason: Optional[str] = None,
    ) -> WorkflowRunRecord:
        """Resumes a paused workflow run awaiting human approval.

        If approved: executes the gated structured action using approved authorization token,
        performs post-action state verification against persistent database truth, and synthesizes response.
        If rejected: marks workflow CANCELLED without executing action.
        """
        run_record = checkpoint_store.get(run_id)
        if not run_record:
            raise ValueError(f"Workflow run '{run_id}' not found.")

        if run_record.state != WorkflowState.WAITING_FOR_APPROVAL:
            raise ValueError(
                f"Workflow run '{run_id}' is in state '{run_record.state.value}', not WAITING_FOR_APPROVAL."
            )

        if not approved:
            rej_response = f"Action rejected: {reason or 'Approval denied by operator.'}"
            self.audit_service.record_approval(
                run_id=run_id,
                approval_status="REJECTED",
                actor="supervisor",
                decision_reason=reason,
                session=db,
            )
            self.audit_service.record_workflow_failure(
                run_id=run_id,
                workflow_state=WorkflowState.CANCELLED.value,
                error=rej_response,
                final_response=rej_response,
                session=db,
            )
            checkpoint_store.add_step(
                run_id=run_id,
                step_name="resume_approval_decision",
                state=WorkflowState.CANCELLED,
                input_payload={"approved": False, "reason": reason},
                output_payload={"decision": "REJECTED", "final_response": rej_response},
            )
            run_record.state = WorkflowState.CANCELLED
            run_record.final_response = rej_response
            return checkpoint_store.save(run_record)

        self.audit_service.record_approval(
            run_id=run_id,
            approval_status="APPROVED",
            actor="supervisor",
            decision_reason=reason,
            session=db,
        )

        # Process approved actions
        for action in run_record.proposed_actions:
            if action.action == "cancel_order":
                order_id = run_record.order_id
                if not order_id and action.parameters.get("order_number") and db:
                    ord_obj = simulator.get_order(
                        session=db,
                        order_number=str(action.parameters.get("order_number")),
                    )
                    order_id = str(ord_obj.id)

                if not order_id:
                    raise ValueError("Cannot execute cancel_order: order_id could not be resolved.")

                # Execute HIGH-risk tool with approval authorization token
                res = self.tools.execute(
                    "cancel_order",
                    params={"order_id": order_id, "reason": action.reason},
                    context={
                        "db": db,
                        "approved": True,
                        "workflow_id": run_record.workflow_id,
                        "run_id": run_id,
                        "action_id": "cancel_order",
                    },
                )
                if res.resilience_metadata:
                    run_record.resilience_records.append(res.resilience_metadata)

                self.audit_service.record_tool_execution(
                    run_id=run_id,
                    tool_name="cancel_order",
                    arguments={"order_id": order_id, "reason": action.reason},
                    result=res.model_dump(),
                    resilience_metadata=res.resilience_metadata,
                    workflow_state=WorkflowState.RUNNING.value if res.success else WorkflowState.FAILED.value,
                    session=db,
                )

                checkpoint_store.add_step(
                    run_id=run_id,
                    step_name="execute_approved_action_cancel_order",
                    state=WorkflowState.RUNNING if res.success else WorkflowState.FAILED,
                    tool_name="cancel_order",
                    input_payload={"order_id": order_id, "reason": action.reason},
                    output_payload=res.model_dump(),
                    error=res.error,
                )

                if not res.success:
                    run_record.state = WorkflowState.FAILED
                    run_record.error = res.error
                    run_record.final_response = f"Failed to execute approved cancellation: {res.error}"
                    self.audit_service.record_workflow_failure(
                        run_id=run_id,
                        workflow_state=WorkflowState.FAILED.value,
                        error=res.error or "Failed to execute approved cancellation",
                        final_response=run_record.final_response,
                        session=db,
                    )
                    return checkpoint_store.save(run_record)

                # Post-action state verification
                if db:
                    ver_req = VerificationRequest(
                        entity_type="order",
                        entity_id=str(order_id),
                        target_state="CANCELLED",
                        operation="cancel_order",
                        expected_attributes={"cancellation_reason": action.reason} if action.reason else {},
                    )
                    ver_res = self.verification_service.verify(session=db, request=ver_req)
                    ver_dump = ver_res.model_dump(mode="json")
                    run_record.verification_results.append(ver_dump)

                    self.audit_service.record_verification(
                        run_id=run_id,
                        verification_result=ver_dump,
                        operation="cancel_order",
                        workflow_state=WorkflowState.RUNNING.value if ver_res.verified else WorkflowState.FAILED.value,
                        session=db,
                    )

                    checkpoint_store.add_step(
                        run_id=run_id,
                        step_name="verify_execution_cancel_order",
                        state=WorkflowState.RUNNING if ver_res.verified else WorkflowState.FAILED,
                        tool_name="cancel_order",
                        input_payload=ver_req.model_dump(mode="json"),
                        output_payload=ver_dump,
                        error=ver_res.error or (", ".join(ver_res.discrepancies) if not ver_res.verified else None),
                    )

                    if not ver_res.verified:
                        run_record.state = WorkflowState.FAILED
                        err_details = ", ".join(ver_res.discrepancies) or ver_res.error or f"State verification failed with status {ver_res.status.value}"
                        err_msg = f"Post-action verification failed [{ver_res.status.value}]: {err_details}"
                        run_record.error = err_msg
                        run_record.final_response = f"Approved cancellation executed but state verification failed ({ver_res.status.value}): {err_details}"
                        self.audit_service.record_workflow_failure(
                            run_id=run_id,
                            workflow_state=WorkflowState.FAILED.value,
                            error=err_msg,
                            final_response=run_record.final_response,
                            session=db,
                        )
                        return checkpoint_store.save(run_record)

            elif action.action == "request_refund":
                order_id = run_record.order_id
                if not order_id and action.parameters.get("order_number") and db:
                    ord_obj = simulator.get_order(
                        session=db,
                        order_number=str(action.parameters.get("order_number")),
                    )
                    order_id = str(ord_obj.id)

                if not order_id:
                    raise ValueError("Cannot execute request_refund: order_id missing.")

                res = self.tools.execute(
                    "request_refund",
                    params={"order_id": order_id, "reason": action.reason},
                    context={
                        "db": db,
                        "approved": True,
                        "workflow_id": run_record.workflow_id,
                        "run_id": run_id,
                        "action_id": "request_refund",
                    },
                )
                if res.resilience_metadata:
                    run_record.resilience_records.append(res.resilience_metadata)

                self.audit_service.record_tool_execution(
                    run_id=run_id,
                    tool_name="request_refund",
                    arguments={"order_id": order_id, "reason": action.reason},
                    result=res.model_dump(),
                    resilience_metadata=res.resilience_metadata,
                    workflow_state=WorkflowState.RUNNING.value if res.success else WorkflowState.FAILED.value,
                    session=db,
                )

                checkpoint_store.add_step(
                    run_id=run_id,
                    step_name="execute_approved_action_request_refund",
                    state=WorkflowState.RUNNING if res.success else WorkflowState.FAILED,
                    tool_name="request_refund",
                    input_payload={"order_id": order_id, "reason": action.reason},
                    output_payload=res.model_dump(),
                    error=res.error,
                )
                if not res.success:
                    run_record.state = WorkflowState.FAILED
                    run_record.error = res.error
                    run_record.final_response = f"Failed to execute approved refund: {res.error}"
                    self.audit_service.record_workflow_failure(
                        run_id=run_id,
                        workflow_state=WorkflowState.FAILED.value,
                        error=res.error or "Failed to execute approved refund",
                        final_response=run_record.final_response,
                        session=db,
                    )
                    return checkpoint_store.save(run_record)

                # Post-action state verification
                if db:
                    ver_req = VerificationRequest(
                        entity_type="payment",
                        entity_id=str(order_id),
                        target_state="REFUNDED",
                        operation="request_refund",
                    )
                    ver_res = self.verification_service.verify(session=db, request=ver_req)
                    ver_dump = ver_res.model_dump(mode="json")
                    run_record.verification_results.append(ver_dump)

                    self.audit_service.record_verification(
                        run_id=run_id,
                        verification_result=ver_dump,
                        operation="request_refund",
                        workflow_state=WorkflowState.RUNNING.value if ver_res.verified else WorkflowState.FAILED.value,
                        session=db,
                    )

                    checkpoint_store.add_step(
                        run_id=run_id,
                        step_name="verify_execution_request_refund",
                        state=WorkflowState.RUNNING if ver_res.verified else WorkflowState.FAILED,
                        tool_name="request_refund",
                        input_payload=ver_req.model_dump(mode="json"),
                        output_payload=ver_dump,
                        error=ver_res.error or (", ".join(ver_res.discrepancies) if not ver_res.verified else None),
                    )

                    if not ver_res.verified:
                        run_record.state = WorkflowState.FAILED
                        err_details = ", ".join(ver_res.discrepancies) or ver_res.error or f"State verification failed with status {ver_res.status.value}"
                        err_msg = f"Post-action verification failed [{ver_res.status.value}]: {err_details}"
                        run_record.error = err_msg
                        run_record.final_response = f"Approved refund executed but state verification failed ({ver_res.status.value}): {err_details}"
                        self.audit_service.record_workflow_failure(
                            run_id=run_id,
                            workflow_state=WorkflowState.FAILED.value,
                            error=err_msg,
                            final_response=run_record.final_response,
                            session=db,
                        )
                        return checkpoint_store.save(run_record)

            elif action.action == "create_ticket":
                res = self.tools.execute(
                    "create_ticket",
                    params=action.parameters,
                    context={
                        "db": db,
                        "approved": True,
                        "workflow_id": run_record.workflow_id,
                        "run_id": run_id,
                        "action_id": "create_ticket",
                    },
                )
                if res.resilience_metadata:
                    run_record.resilience_records.append(res.resilience_metadata)

                self.audit_service.record_tool_execution(
                    run_id=run_id,
                    tool_name="create_ticket",
                    arguments=action.parameters,
                    result=res.model_dump(),
                    resilience_metadata=res.resilience_metadata,
                    workflow_state=WorkflowState.RUNNING.value if res.success else WorkflowState.FAILED.value,
                    session=db,
                )

                checkpoint_store.add_step(
                    run_id=run_id,
                    step_name="execute_approved_action_create_ticket",
                    state=WorkflowState.RUNNING if res.success else WorkflowState.FAILED,
                    tool_name="create_ticket",
                    input_payload=action.parameters,
                    output_payload=res.model_dump(),
                    error=res.error,
                )
                if not res.success:
                    run_record.state = WorkflowState.FAILED
                    run_record.error = res.error
                    run_record.final_response = f"Failed to execute approved ticket creation: {res.error}"
                    self.audit_service.record_workflow_failure(
                        run_id=run_id,
                        workflow_state=WorkflowState.FAILED.value,
                        error=res.error or "Failed to execute approved ticket creation",
                        final_response=run_record.final_response,
                        session=db,
                    )
                    return checkpoint_store.save(run_record)

                if db and res.data:
                    ticket_id = res.data.get("id") or res.data.get("ticket_number")
                    if ticket_id:
                        ver_req = VerificationRequest(
                            entity_type="ticket",
                            entity_id=str(ticket_id),
                            target_state="OPEN",
                            operation="create_ticket",
                            expected_attributes={"priority": res.data.get("priority")} if res.data.get("priority") else {},
                        )
                        ver_res = self.verification_service.verify(session=db, request=ver_req)
                        ver_dump = ver_res.model_dump(mode="json")
                        run_record.verification_results.append(ver_dump)

                        self.audit_service.record_verification(
                            run_id=run_id,
                            verification_result=ver_dump,
                            operation="create_ticket",
                            workflow_state=WorkflowState.RUNNING.value if ver_res.verified else WorkflowState.FAILED.value,
                            session=db,
                        )

                        checkpoint_store.add_step(
                            run_id=run_id,
                            step_name="verify_execution_create_ticket",
                            state=WorkflowState.RUNNING if ver_res.verified else WorkflowState.FAILED,
                            tool_name="create_ticket",
                            input_payload=ver_req.model_dump(mode="json"),
                            output_payload=ver_dump,
                            error=ver_res.error or (", ".join(ver_res.discrepancies) if not ver_res.verified else None),
                        )

                        if not ver_res.verified:
                            run_record.state = WorkflowState.FAILED
                            err_details = ", ".join(ver_res.discrepancies) or ver_res.error or f"State verification failed with status {ver_res.status.value}"
                            err_msg = f"Post-action verification failed [{ver_res.status.value}]: {err_details}"
                            run_record.error = err_msg
                            run_record.final_response = f"Approved ticket creation executed but state verification failed ({ver_res.status.value}): {err_details}"
                            self.audit_service.record_workflow_failure(
                                run_id=run_id,
                                workflow_state=WorkflowState.FAILED.value,
                                error=err_msg,
                                final_response=run_record.final_response,
                                session=db,
                            )
                            return checkpoint_store.save(run_record)

        succ_response = "Approved actions executed successfully. Order operations completed."
        checkpoint_store.add_step(
            run_id=run_id,
            step_name="complete_resumed_workflow",
            state=WorkflowState.COMPLETED,
            input_payload={"approved": True, "reason": reason},
            output_payload={"decision": "APPROVED", "final_response": succ_response},
        )
        run_record.state = WorkflowState.COMPLETED
        run_record.final_response = succ_response
        self.audit_service.record_workflow_completion(
            run_id=run_id,
            workflow_state=WorkflowState.COMPLETED.value,
            final_response=succ_response,
            metadata={"resumed": True, "approved": True},
            session=db,
        )
        return checkpoint_store.save(run_record)

    def resume_approved_action(
        self,
        run_id: str,
        approved: bool = True,
        db: Optional[Session] = None,
        reason: Optional[str] = None,
    ) -> WorkflowRunRecord:
        """Resumes an approved action and executes post-action state verification."""
        return self.resume(run_id=run_id, approved=approved, db=db, reason=reason)
