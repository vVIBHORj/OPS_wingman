"""
Stateful Ops Agent powered by LangGraph (Phase 2 - Deliverable D-08).
Coordinates intent interpretation, tool planning, policy-aware execution, and structured action proposals.
"""

import re
import uuid
from typing import Dict, Any, List, Optional, TypedDict, cast
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

import simulator
from backend.tools.base import ToolRegistry, RiskLevel
from backend.tools.registry import create_default_tool_registry
from backend.workflows.state import WorkflowState, StructuredAction, WorkflowRunRecord
from backend.workflows.checkpoint import checkpoint_store


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
    planned_tools: List[str]
    executed_tools: List[str]
    tool_results: Dict[str, Any]
    proposed_actions: List[Dict[str, Any]]
    requires_approval: bool
    final_response: Optional[str]
    workflow_state: str
    error: Optional[str]
    db: Optional[Session]


class OpsAgent:
    """
    Stateful workflow agent orchestrating operational inquiries and actions.
    Uses deterministic parsing and guarded ToolRegistry execution.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None) -> None:
        self.tools = tool_registry or create_default_tool_registry()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(cast(Any, AgentGraphState))


        builder.add_node("interpret_request", self._node_interpret_request)
        builder.add_node("plan_tools", self._node_plan_tools)
        builder.add_node("execute_tools", self._node_execute_tools)
        builder.add_node("evaluate_policy", self._node_evaluate_policy)
        builder.add_node("synthesize_response", self._node_synthesize_response)

        builder.set_entry_point("interpret_request")
        builder.add_edge("interpret_request", "plan_tools")
        builder.add_edge("plan_tools", "execute_tools")
        builder.add_edge("execute_tools", "evaluate_policy")
        builder.add_edge("evaluate_policy", "synthesize_response")
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

        uuid_match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text, re.IGNORECASE)
        if uuid_match:
            entities["entity_uuid"] = uuid_match.group(0)

        # 2. Intent Classification
        text_lower = text.lower()
        if any(k in text_lower for k in ["cancel", "cancellation", "abort order"]):
            intent = "cancel_order_request"
        elif any(k in text_lower for k in ["track", "shipment", "courier", "delivery status", "where is my"]):
            intent = "track_shipment"
        elif any(k in text_lower for k in ["status", "order status", "order update"]):
            intent = "check_order_status"
        elif any(k in text_lower for k in ["payment", "refund", "charged", "invoice"]):
            intent = "check_payment_status"
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

        return {
            "intent": intent,
            "extracted_entities": entities,
            "order_number": entities.get("order_number") or state.get("order_number"),
            "workflow_state": WorkflowState.RUNNING.value,
        }

    def _node_plan_tools(self, state: AgentGraphState) -> Dict[str, Any]:
        """Plans tools and structured actions based on the classified intent."""
        intent = state.get("intent", "general_order_inquiry")
        planned: List[str] = []
        proposed_actions: List[Dict[str, Any]] = []
        requires_approval = False

        if intent in ["check_order_status", "general_order_inquiry"]:
            planned.append("get_order")
            planned.append("get_shipment")
        elif intent == "track_shipment":
            planned.append("get_order")
            planned.append("get_shipment")
        elif intent == "check_payment_status":
            planned.append("get_order")
            planned.append("get_payment")
        elif intent == "cancel_order_request":
            planned.append("get_order")
            planned.append("get_policy")
            # Action proposed: high risk cancellation proposal
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
            requires_approval = True

        run_id = state.get("run_id", "")
        checkpoint_store.add_step(
            run_id=run_id,
            step_name="plan_tools",
            state=WorkflowState.RUNNING,
            output_payload={"planned_tools": planned, "proposed_actions": proposed_actions},
        )

        return {
            "planned_tools": planned,
            "proposed_actions": proposed_actions,
            "requires_approval": requires_approval,
        }

    def _node_execute_tools(self, state: AgentGraphState) -> Dict[str, Any]:
        """Executes read tools safely through ToolRegistry."""
        planned = state.get("planned_tools", [])
        results: Dict[str, Any] = {}
        executed: List[str] = []
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
                if order_res and order_res.get("data", {}).get("id"):
                    params["order_id"] = order_res["data"]["id"]
                elif order_id:
                    params["order_id"] = order_id
            elif tool_name == "get_payment":
                order_res = results.get("get_order")
                if order_res and order_res.get("data", {}).get("id"):
                    params["order_id"] = order_res["data"]["id"]
                elif order_id:
                    params["order_id"] = order_id
            elif tool_name == "get_policy":
                params["policy_name"] = "cancellation_window"

            res = self.tools.execute(tool_name, params=params, context={"db": db} if db else None)
            results[tool_name] = res.model_dump()
            executed.append(tool_name)

            checkpoint_store.add_step(
                run_id=run_id,
                step_name=f"execute_tool_{tool_name}",
                state=WorkflowState.RUNNING,
                tool_name=tool_name,
                input_payload=params,
                output_payload=res.model_dump(),
                error=res.error,
            )

        return {
            "executed_tools": executed,
            "tool_results": results,
        }

    def _node_evaluate_policy(self, state: AgentGraphState) -> Dict[str, Any]:
        """Evaluates whether high risk actions halt the workflow for approval."""
        requires_approval = state.get("requires_approval", False)
        wf_state = WorkflowState.WAITING_FOR_APPROVAL if requires_approval else WorkflowState.RUNNING
        run_id = state.get("run_id", "")

        checkpoint_store.add_step(
            run_id=run_id,
            step_name="evaluate_policy",
            state=wf_state,
            output_payload={"requires_approval": requires_approval, "workflow_state": wf_state.value},
        )

        return {
            "workflow_state": wf_state.value,
        }

    def _node_synthesize_response(self, state: AgentGraphState) -> Dict[str, Any]:
        """Synthesizes human-readable operational response based on retrieved data."""
        intent = state.get("intent", "general_order_inquiry")
        tool_results = state.get("tool_results", {})
        order_info = tool_results.get("get_order", {}).get("data")
        shipment_info = tool_results.get("get_shipment", {}).get("data")
        payment_info = tool_results.get("get_payment", {}).get("data")
        requires_approval = state.get("requires_approval", False)
        run_id = state.get("run_id", "")

        if not order_info and not state.get("order_number"):
            response = "Thank you for reaching out to OpsWingman. Could you please provide your Order Number (e.g., ORD-YYYYMMDD-XXXXXX) so I can retrieve your details?"
            final_state = WorkflowState.COMPLETED
        elif not order_info:
            err = tool_results.get("get_order", {}).get("error", "Order not found")
            response = f"I could not locate an order with reference {state.get('order_number')}. Error: {err}. Please verify your order number."
            final_state = WorkflowState.COMPLETED
        elif intent == "cancel_order_request":
            order_status = order_info.get("status")
            if order_status in ["PENDING", "CONFIRMED"]:
                response = (
                    f"Your cancellation request for order {order_info.get('order_number')} (Status: {order_status}) "
                    f"has been initiated and submitted to our operations team for approval (Risk: HIGH)."
                )
            else:
                response = (
                    f"Order {order_info.get('order_number')} is currently {order_status}. "
                    "Under our policy, orders that have already shipped cannot be directly cancelled. "
                    "Please initiate a return once the package is delivered."
                )
            final_state = WorkflowState.WAITING_FOR_APPROVAL if requires_approval else WorkflowState.COMPLETED
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

            response = " ".join(parts)
            final_state = WorkflowState.COMPLETED
        elif intent == "check_payment_status":
            order_num = order_info.get("order_number")
            pay_status = payment_info.get("status") if payment_info else "UNKNOWN"
            amount = payment_info.get("amount") if payment_info else order_info.get("total_amount")
            response = f"Order {order_num} payment status is {pay_status} for amount INR {amount}."
            final_state = WorkflowState.COMPLETED
        else:
            response = f"Order {order_info.get('order_number')} details retrieved successfully."
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
            run_record.intent = intent
            run_record.extracted_entities = state.get("extracted_entities", {})
            run_record.proposed_actions = [StructuredAction(**a) for a in state.get("proposed_actions", [])]
            if order_info:
                run_record.order_id = order_info.get("id")
                run_record.customer_id = order_info.get("customer_id")
            checkpoint_store.save(run_record)

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
            "requires_approval": False,
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
        """
        Resumes a paused workflow run awaiting human approval.
        If approved: executes the gated structured action using approved authorization token.
        If rejected: cancels or rejects the pending action and marks workflow CANCELLED.
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

        # Process approved actions
        for action in run_record.proposed_actions:
            if action.action == "cancel_order":
                order_id = run_record.order_id
                if not order_id and action.parameters.get("order_number") and db:
                    ord_obj = simulator.get_order(session=db, order_number=str(action.parameters.get("order_number")))
                    order_id = str(ord_obj.id)

                if not order_id:
                    raise ValueError("Cannot execute cancel_order: order_id could not be resolved.")

                # Execute HIGH-risk tool with approval authorization token
                res = self.tools.execute(
                    "cancel_order",
                    params={"order_id": order_id, "reason": action.reason},
                    context={"db": db, "approved": True},
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
                    return checkpoint_store.save(run_record)

            elif action.action == "request_refund":
                order_id = run_record.order_id
                if not order_id and action.parameters.get("order_number") and db:
                    ord_obj = simulator.get_order(session=db, order_number=str(action.parameters.get("order_number")))
                    order_id = str(ord_obj.id)

                if not order_id:
                    raise ValueError("Cannot execute request_refund: order_id missing.")

                res = self.tools.execute(
                    "request_refund",
                    params={"order_id": order_id, "reason": action.reason},
                    context={"db": db, "approved": True},
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
                    return checkpoint_store.save(run_record)

        succ_response = (
            f"Approved actions executed successfully. "
            f"Order operations completed."
        )
        checkpoint_store.add_step(
            run_id=run_id,
            step_name="complete_resumed_workflow",
            state=WorkflowState.COMPLETED,
            input_payload={"approved": True, "reason": reason},
            output_payload={"decision": "APPROVED", "final_response": succ_response},
        )
        run_record.state = WorkflowState.COMPLETED
        run_record.final_response = succ_response
        return checkpoint_store.save(run_record)

