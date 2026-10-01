"""Unit and Integration tests for OpsAgent Phase 4 Post-Action State Verification (Deliverable D-14).

Verifies:
a. Successful order cancellation -> verification VERIFIED
b. Successful refund -> verification VERIFIED
c. Tool reports success but DB state remains unchanged -> DIVERGENT
d. Expected entity cannot be found -> NOT_FOUND
e. Verification query/database failure -> ERROR
f. Verification results are persisted in workflow state and checkpoint store
g. Approved-action resume performs verification after execution
h. Existing Phase 1-3 agent behavior remains unchanged
i. Verification does not mutate the business entity itself
j. Dedicated verify_execution LangGraph node behavior
k. resume_approved_action alias execution
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, Optional
import pytest
from sqlalchemy.orm import Session

import simulator
from backend.agents.ops_agent import AgentGraphState, OpsAgent
from backend.approvals.service import ApprovalService
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.tools.base import RiskLevel, ToolDefinition, ToolRegistry, ToolType
from backend.tools.registry import create_default_tool_registry
from backend.tools.schemas import CancelOrderInput
from backend.verification import (
    StateVerificationService,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    state_verification_service,
)
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import WorkflowRunRecord, WorkflowState
from database.models import Customer, Order, OrderStatus, Payment, PaymentMethod, PaymentStatus, Product


@pytest.fixture(autouse=True)
def seed_kb(db_session: Session):
    seed_default_knowledge(db_session)


@pytest.fixture
def agent() -> OpsAgent:
    return OpsAgent()


def _setup_test_order(
    db: Session,
    amount: Decimal = Decimal("2500.00"),
    status: OrderStatus = OrderStatus.CONFIRMED,
) -> tuple[Customer, Order, Payment]:
    cust_id = uuid.uuid4()
    cust = Customer(
        id=cust_id,
        first_name="Rohan",
        last_name="Verma",
        email=f"rohan.{uuid.uuid4().hex[:6]}@example.com",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
    )
    prod_id = uuid.uuid4()
    prod = Product(
        id=prod_id,
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        name="Smart Fitness Tracker",
        unit_price=amount,
        currency="INR",
        inventory_count=40,
        is_active=True,
    )
    db.add_all([cust, prod])
    db.commit()

    order = simulator.create_order(
        session=db,
        customer_id=cust.id,
        items=[{"product_id": prod.id, "quantity": 1}],
    )

    pay = simulator.create_payment(
        session=db,
        order_id=order.id,
        amount=amount,
        payment_method=PaymentMethod.UPI,
    )
    simulator.capture_payment(session=db, payment_id=pay.id, gateway_transaction_id="pay_ver_001")
    db.refresh(order)
    return cust, order, pay


# ==============================================================================
# a. Successful order cancellation -> verification VERIFIED
# ==============================================================================

def test_successful_cancellation_verification_verified(agent: OpsAgent, db_session: Session):
    _, order, _ = _setup_test_order(db_session)

    run_record = agent.run(
        input_text=f"Please cancel my order {order.order_number}",
        db=db_session,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run_record.approval_id is not None

    # Operator approves and resumes
    resumed = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
        reason="Customer cancellation within valid window",
    )

    assert resumed.state == WorkflowState.COMPLETED
    assert len(resumed.verification_results) == 1

    ver = resumed.verification_results[0]
    assert ver["verified"] is True
    assert ver["status"] == VerificationStatus.VERIFIED.value
    assert ver["entity_type"] == "order"
    assert ver["entity_id"] == str(order.id)
    assert ver["target_state"] == "CANCELLED"
    assert ver["actual_state"] == "CANCELLED"
    assert ver["operation"] == "cancel_order"
    assert ver["discrepancies"] == []
    assert ver["error"] is None

    # Verify DB state directly
    db_session.refresh(order)
    assert order.status == OrderStatus.CANCELLED


# ==============================================================================
# b. Successful refund -> verification VERIFIED
# ==============================================================================

def test_successful_refund_verification_verified(agent: OpsAgent, db_session: Session):
    # High value refund requiring approval (> 2000 INR)
    _, order, pay = _setup_test_order(db_session, amount=Decimal("7500.00"))

    run_record = agent.run(
        input_text=f"Please refund my order {order.order_number}",
        db=db_session,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run_record.approval_id is not None

    resumed = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
        reason="Supervisor approved refund",
    )

    assert resumed.state == WorkflowState.COMPLETED
    assert len(resumed.verification_results) == 1

    ver = resumed.verification_results[0]
    assert ver["verified"] is True
    assert ver["status"] == VerificationStatus.VERIFIED.value
    assert ver["entity_type"] == "payment"
    assert ver["entity_id"] == str(order.id)
    assert ver["target_state"] == "REFUNDED"
    assert ver["actual_state"] == "REFUNDED"
    assert ver["operation"] == "refund_payment"
    assert ver["discrepancies"] == []

    # Verify DB state directly
    db_session.refresh(pay)
    assert pay.status == PaymentStatus.REFUNDED


# ==============================================================================
# c. Tool reports success but DB state remains unchanged -> DIVERGENT
# ==============================================================================

def test_tool_success_but_db_unchanged_divergent(db_session: Session):
    _, order, _ = _setup_test_order(db_session)

    # Custom registry with buggy cancel_order tool that claims success without modifying DB
    registry = create_default_tool_registry()
    registry._tools.pop("cancel_order", None)

    def buggy_cancel_order(inputs: CancelOrderInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "id": str(inputs.order_id),
            "order_number": order.order_number,
            "status": "CONFIRMED",  # Kept unchanged in DB
            "cancellation_reason": inputs.reason,
        }

    registry.register(ToolDefinition(
        name="cancel_order",
        description="Buggy cancel order that does not persist changes.",
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.HIGH,
        input_schema=CancelOrderInput,
        handler=buggy_cancel_order,
    ))

    buggy_agent = OpsAgent(tool_registry=registry)
    run_record = buggy_agent.run(
        input_text=f"Please cancel my order {order.order_number}",
        db=db_session,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL

    # Resuming should fail due to state divergence
    resumed = buggy_agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
    )

    assert resumed.state == WorkflowState.FAILED
    assert "DIVERGENT" in (resumed.error or "")
    assert len(resumed.verification_results) == 1

    ver = resumed.verification_results[0]
    assert ver["verified"] is False
    assert ver["status"] == VerificationStatus.DIVERGENT.value
    assert ver["entity_type"] == "order"
    assert ver["target_state"] == "CANCELLED"
    assert ver["actual_state"] == "CONFIRMED"
    assert len(ver["discrepancies"]) > 0

    # Ensure DB was indeed NOT modified
    db_session.refresh(order)
    assert order.status == OrderStatus.CONFIRMED


# ==============================================================================
# d. Expected entity cannot be found -> NOT_FOUND
# ==============================================================================

def test_expected_entity_not_found(agent: OpsAgent, db_session: Session):
    non_existent_id = str(uuid.uuid4())

    # Directly run verification against non-existent order
    req = VerificationRequest(
        entity_type="order",
        entity_id=non_existent_id,
        target_state="CANCELLED",
        operation="cancel_order",
    )
    ver_res = state_verification_service.verify(session=db_session, request=req)

    assert ver_res.verified is False
    assert ver_res.status == VerificationStatus.NOT_FOUND
    assert ver_res.actual_state == "NOT_FOUND"
    assert len(ver_res.discrepancies) > 0


# ==============================================================================
# e. Verification query/database failure -> ERROR
# ==============================================================================

def test_verification_query_failure_error(agent: OpsAgent, db_session: Session):
    _, order, _ = _setup_test_order(db_session)

    # Use a custom verification service that encounters a database exception
    class BrokenVerificationService(StateVerificationService):
        def verify(self, session: Session, request: VerificationRequest) -> VerificationResult:
            return VerificationResult(
                verified=False,
                status=VerificationStatus.ERROR,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                target_state=request.target_state,
                actual_state="ERROR",
                discrepancies=["Simulated connection timeout during inspection."],
                operation=request.operation,
                error="OperationalError: DB connection lost",
            )

    agent_with_broken_ver = OpsAgent(verification_service=BrokenVerificationService())
    run_record = agent_with_broken_ver.run(
        input_text=f"Please cancel my order {order.order_number}",
        db=db_session,
    )

    resumed = agent_with_broken_ver.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
    )

    assert resumed.state == WorkflowState.FAILED
    assert "ERROR" in (resumed.error or "")
    assert len(resumed.verification_results) == 1
    assert resumed.verification_results[0]["status"] == VerificationStatus.ERROR.value
    assert resumed.verification_results[0]["verified"] is False


# ==============================================================================
# f. Verification results are persisted in workflow state and checkpoint store
# ==============================================================================

def test_verification_results_persisted_in_workflow_state_and_checkpoints(
    agent: OpsAgent,
    db_session: Session,
):
    _, order, _ = _setup_test_order(db_session)

    run_record = agent.run(
        input_text=f"Please cancel my order {order.order_number}",
        db=db_session,
    )
    resumed = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
    )

    # Check WorkflowRunRecord fields
    assert hasattr(resumed, "verification_results")
    assert isinstance(resumed.verification_results, list)
    assert len(resumed.verification_results) == 1

    item = resumed.verification_results[0]
    expected_fields = [
        "verified",
        "status",
        "entity_type",
        "entity_id",
        "target_state",
        "actual_state",
        "discrepancies",
        "timestamp",
        "operation",
        "details",
        "error",
    ]
    for field in expected_fields:
        assert field in item, f"Missing expected field '{field}' in verification result"

    # Check checkpoint store persistence
    stored = checkpoint_store.get(run_record.run_id)
    assert stored is not None
    assert stored.verification_results == resumed.verification_results


# ==============================================================================
# g. Approved-action resume performs verification after execution
# ==============================================================================

def test_approved_action_resume_performs_verification_after_execution(
    agent: OpsAgent,
    db_session: Session,
):
    _, order, _ = _setup_test_order(db_session)

    run_record = agent.run(
        input_text=f"Please cancel my order {order.order_number}",
        db=db_session,
    )
    resumed = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=db_session,
    )

    steps = resumed.steps
    step_names = [s.step_name for s in steps]

    assert "execute_approved_action_cancel_order" in step_names
    assert "verify_execution_cancel_order" in step_names
    assert "complete_resumed_workflow" in step_names

    exec_idx = step_names.index("execute_approved_action_cancel_order")
    ver_idx = step_names.index("verify_execution_cancel_order")
    comp_idx = step_names.index("complete_resumed_workflow")

    # Verification MUST happen after execution and before completion
    assert exec_idx < ver_idx < comp_idx


# ==============================================================================
# h. Existing Phase 1-3 agent behavior remains unchanged
# ==============================================================================

def test_existing_phase1_to_3_agent_behavior_unchanged(agent: OpsAgent, db_session: Session):
    _, order, _ = _setup_test_order(db_session)

    # 1. Read inquiry
    res = agent.run(
        input_text=f"What is the status of my order {order.order_number}?",
        db=db_session,
    )
    assert res.state == WorkflowState.COMPLETED
    assert order.order_number in (res.final_response or "")
    assert len(res.citations) > 0
    # Read tool execution should not add redundant verification results
    assert len(res.verification_results) == 0

    # 2. Rejection of approval flow
    cancel_run = agent.run(
        input_text=f"Cancel order {order.order_number}",
        db=db_session,
    )
    assert cancel_run.state == WorkflowState.WAITING_FOR_APPROVAL

    rejected = agent.resume(
        run_id=cancel_run.run_id,
        approved=False,
        db=db_session,
        reason="Customer called to keep order",
    )
    assert rejected.state == WorkflowState.CANCELLED
    assert "Action rejected" in (rejected.final_response or "")
    # No action executed, so no verification results
    assert len(rejected.verification_results) == 0


# ==============================================================================
# i. Verification does not mutate the business entity itself
# ==============================================================================

def test_verification_does_not_mutate_business_entity(db_session: Session):
    _, order, _ = _setup_test_order(db_session)
    orig_status = order.status
    orig_reason = order.cancellation_reason

    # Verification against CANCELLED state on a CONFIRMED order
    ver_res = state_verification_service.verify_order_cancellation(
        session=db_session,
        order_id=order.id,
    )

    assert ver_res.verified is False
    assert ver_res.status == VerificationStatus.DIVERGENT

    # Verify that the DB record was NOT mutated
    db_session.refresh(order)
    assert order.status == orig_status
    assert order.cancellation_reason == orig_reason


# ==============================================================================
# j. resume_approved_action alias execution
# ==============================================================================

def test_resume_approved_action_alias(agent: OpsAgent, db_session: Session):
    _, order, _ = _setup_test_order(db_session)

    run_record = agent.run(
        input_text=f"Please cancel my order {order.order_number}",
        db=db_session,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL

    # Using the alias resume_approved_action()
    resumed = agent.resume_approved_action(
        run_id=run_record.run_id,
        db=db_session,
        reason="Supervisor verified",
    )

    assert resumed.state == WorkflowState.COMPLETED
    assert len(resumed.verification_results) == 1
    assert resumed.verification_results[0]["status"] == VerificationStatus.VERIFIED.value


# ==============================================================================
# k. Dedicated verify_execution LangGraph node behavior
# ==============================================================================

def test_graph_node_verify_execution_in_workflow_steps(agent: OpsAgent, db_session: Session):
    _, order, _ = _setup_test_order(db_session)

    res = agent.run(
        input_text=f"What is the status of my order {order.order_number}?",
        db=db_session,
    )
    assert res.state == WorkflowState.COMPLETED

    # Verify that verify_execution node is an active node in the graph pipeline
    node_names = list(agent.graph.nodes.keys())
    assert "verify_execution" in node_names


def test_graph_node_verify_execution_on_state_changing_tool(db_session: Session):
    cust, order, _ = _setup_test_order(db_session)

    # Agent with planned create_ticket
    agent = OpsAgent()

    # Execute create_ticket tool to create ticket in DB
    tool_res = agent.tools.execute(
        "create_ticket",
        params={
            "customer_id": str(cust.id),
            "order_id": str(order.id),
            "subject": "Late delivery complaint",
            "description": "Customer reported late delivery",
            "priority": "MEDIUM",
        },
        context={"db": db_session},
    )
    assert tool_res.success is True
    assert tool_res.data is not None

    state: AgentGraphState = {
        "run_id": str(uuid.uuid4()),
        "workflow_id": str(uuid.uuid4()),
        "executed_tools": ["create_ticket"],
        "tool_results": {
            "create_ticket": tool_res.model_dump(),
        },
        "db": db_session,
    }

    node_out = agent._node_verify_execution(state)
    assert len(node_out["verification_results"]) == 1
    ver = node_out["verification_results"][0]
    assert ver["verified"] is True
    assert ver["status"] == VerificationStatus.VERIFIED.value
    assert ver["entity_type"] == "ticket"
    assert ver["actual_state"] == "OPEN"

