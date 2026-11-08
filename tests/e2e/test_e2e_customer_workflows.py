"""End-to-End Customer Journey and Operational Workflow Tests.

Validates complete multi-step agent lifecycles:
1. Order Tracking Inquiry: Customer prompt -> Intent -> Tool execution -> RAG -> Response.
2. Gated Refund with Manager Approval: Request -> ML Risk -> Policy Gate -> Manager Approval ->
   Resumed Execution -> Verification -> DB Mutation -> Final Response.
3. Gated Cancellation with Manager Rejection: Request -> Gate -> Manager Rejection ->
   Resumed Execution -> Clean Rejection Response -> Zero DB Mutation.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

import simulator
from backend.agents.ops_agent import OpsAgent
from backend.approvals.service import ApprovalService
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.workflows.state import WorkflowState
from database.models import (
    Customer,
    Order,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Product,
    ShipmentStatus,
)
from database.models.enums import ApprovalStatus


def _create_seed_environment(
    db: Session,
    amount: Decimal = Decimal("4999.00"),
    status: OrderStatus = OrderStatus.CONFIRMED,
) -> tuple[Customer, Order, Payment]:
    """Sets up a complete deterministic customer, product, order, payment, and shipment."""
    seed_default_knowledge(db)

    cust_id = uuid.uuid4()
    cust = Customer(
        id=cust_id,
        first_name="Rohan",
        last_name="Verma",
        email=f"rohan.{uuid.uuid4().hex[:6]}@example.com",
        city="Delhi",
        state="Delhi",
        pincode="110001",
        phone="+919123456789",
    )
    prod_id = uuid.uuid4()
    prod = Product(
        id=prod_id,
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Noise-Cancelling Headphones",
        unit_price=amount,
        currency="INR",
        inventory_count=30,
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
        payment_method=PaymentMethod.CARD,
    )
    simulator.capture_payment(session=db, payment_id=pay.id, gateway_transaction_id="pay_e2e_001")

    if status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
        simulator.update_order_status(
            session=db, order_id=order.id, new_status=OrderStatus.PROCESSING
        )
        shp = simulator.create_shipment(session=db, order_id=order.id, carrier="BlueDart")
        simulator.update_shipment_status(
            session=db, shipment_id=shp.id, new_status=ShipmentStatus.IN_TRANSIT
        )
        if status == OrderStatus.DELIVERED:
            simulator.deliver_shipment(session=db, shipment_id=shp.id)

    db.refresh(order)
    db.refresh(pay)
    return cust, order, pay


def test_e2e_order_tracking_inquiry_workflow(db_session: Session):
    """End-to-end test of a customer tracking their package."""
    _, order, _ = _create_seed_environment(
        db_session, amount=Decimal("1500.00"), status=OrderStatus.SHIPPED
    )
    agent = OpsAgent()

    run = agent.run(
        input_text=f"Where is my package for order {order.order_number}?",
        order_number=order.order_number,
        db=db_session,
    )

    # Workflow finishes cleanly without gating
    assert run.state == WorkflowState.COMPLETED
    assert run.approval_id is None
    assert "BlueDart" in (run.final_response or "")
    assert len(run.citations) > 0

    # Read-only operation: order status is untouched
    db_session.refresh(order)
    assert order.status == OrderStatus.SHIPPED


def test_e2e_gated_refund_approval_and_resumption_workflow(db_session: Session):
    """End-to-end test of a high-value customer refund request requiring manager approval."""
    _, order, pay = _create_seed_environment(
        db_session, amount=Decimal("5999.00"), status=OrderStatus.DELIVERED
    )
    agent = OpsAgent()

    # Step 1: Customer submits refund request
    run1 = agent.run(
        input_text=f"I want a refund for my order {order.order_number} because it was defective",
        order_number=order.order_number,
        db=db_session,
    )

    # Step 2: Policy Engine halts workflow for human review
    assert run1.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run1.approval_id is not None
    assert run1.risk_assessment is not None

    approval_svc = ApprovalService(db_session)
    appr_id = uuid.UUID(run1.approval_id)
    appr = approval_svc.get_approval(appr_id)
    assert appr.status == ApprovalStatus.PENDING

    # Payment in DB is still captured, not refunded
    db_session.refresh(pay)
    assert pay.status == PaymentStatus.SUCCESSFUL

    # Step 3: Operations Manager approves
    approval_svc.approve(appr_id, approver_identity="operations_lead@opswingman.local")

    # Step 4: Resume agent workflow
    resumed = agent.resume(
        run_id=run1.run_id,
        approved=True,
        reason="Approved after receipt verification",
        db=db_session,
    )

    # Step 5: Verify execution, verification, and database state
    assert resumed.state == WorkflowState.COMPLETED
    assert "Approved actions executed successfully" in (resumed.final_response or "")

    db_session.refresh(pay)
    assert pay.status == PaymentStatus.REFUNDED


def test_e2e_cancellation_manager_rejection_workflow(db_session: Session):
    """End-to-end test of an order cancellation request rejected by operations manager."""
    _, order, _ = _create_seed_environment(
        db_session, amount=Decimal("4500.00"), status=OrderStatus.CONFIRMED
    )
    agent = OpsAgent()

    # Step 1: Customer requests cancellation
    run1 = agent.run(
        input_text=f"Cancel my order {order.order_number} please",
        order_number=order.order_number,
        db=db_session,
    )

    assert run1.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run1.approval_id is not None

    # Step 2: Manager rejects request
    approval_svc = ApprovalService(db_session)
    appr_id = uuid.UUID(run1.approval_id)
    approval_svc.reject(
        appr_id,
        approver_identity="supervisor@opswingman.local",
        rejection_reason="Package already custom-built and staged for loading",
    )

    # Step 3: Resume workflow with rejection
    resumed = agent.resume(
        run_id=run1.run_id,
        approved=False,
        reason="Package already custom-built and staged for loading",
        db=db_session,
    )

    # Step 4: Verify workflow is cancelled/rejected and DB order status is intact
    assert resumed.state == WorkflowState.CANCELLED
    assert "Action rejected" in (resumed.final_response or "")

    db_session.refresh(order)
    assert order.status == OrderStatus.CONFIRMED

