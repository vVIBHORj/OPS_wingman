"""Integration tests for real-world business workflows in OpsWingman.

Validates end-to-end interactions across:
- API request to database persistence and response contracts
- Order cancellation and refund with policy enforcement
- Human approval lifecycle (creation, rejection without mutation, approval and resumption)
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import simulator
from backend.agents.ops_agent import OpsAgent
from backend.approvals.service import ApprovalService
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.workflows.state import WorkflowState
from database.models import (
    ApprovalRecord,
    Customer,
    DomainEvent,
    EventType,
    Order,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Product,
    ShipmentStatus,
)
from database.models.enums import ApprovalStatus


def _setup_order(
    db: Session,
    amount: Decimal = Decimal("2500.00"),
    status: OrderStatus = OrderStatus.CONFIRMED,
) -> tuple[Customer, Order, Payment]:
    """Helper creating a customer, order, and captured payment via the simulator."""
    cust_id = uuid.uuid4()
    cust = Customer(
        id=cust_id,
        first_name="Aarav",
        last_name="Sharma",
        email=f"aarav.{uuid.uuid4().hex[:6]}@example.com",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
    )
    prod_id = uuid.uuid4()
    prod = Product(
        id=prod_id,
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Wireless Audio Adapter",
        unit_price=amount,
        currency="INR",
        inventory_count=50,
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
    simulator.capture_payment(session=db, payment_id=pay.id, gateway_transaction_id="pay_test_001")

    if status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
        simulator.update_order_status(
            session=db, order_id=order.id, new_status=OrderStatus.PROCESSING
        )
        shp = simulator.create_shipment(session=db, order_id=order.id, carrier="Delhivery")
        simulator.update_shipment_status(
            session=db, shipment_id=shp.id, new_status=ShipmentStatus.IN_TRANSIT
        )
        if status == OrderStatus.DELIVERED:
            simulator.deliver_shipment(session=db, shipment_id=shp.id)

    db.refresh(order)
    db.refresh(pay)
    return cust, order, pay


def test_api_order_creation_persists_to_database(api_client: TestClient, db_session: Session):
    """Verifies that POST /orders creates and commits an order with items in SQLite,
    and returns matching response contract.
    """
    cust = db_session.execute(select(Customer)).scalars().first()
    prod = db_session.execute(select(Product)).scalars().first()
    assert cust is not None and prod is not None

    payload = {
        "customer_id": str(cust.id),
        "items": [
            {
                "sku": prod.sku,
                "quantity": 2,
            }
        ],
        "shipping_amount": "0.00",
        "discount_amount": "0.00",
    }

    response = api_client.post("/orders", json=payload)
    assert response.status_code == 201
    data = response.json()
    order_id = uuid.UUID(data["id"])
    assert data["customer_id"] == str(cust.id)
    assert data["status"] == "PENDING"
    assert data["subtotal_amount"] == str(prod.unit_price * 2)

    # Verify physical database persistence
    db_order = db_session.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    assert db_order is not None
    assert db_order.customer_id == cust.id
    assert db_order.status == OrderStatus.PENDING
    assert db_order.total_amount == Decimal(str(data["total_amount"]))
    assert len(db_order.items) == 1
    assert db_order.items[0].product_id == prod.id
    assert db_order.items[0].quantity == 2

    # Verify GET by ID returns the persisted record
    get_res = api_client.get(f"/orders/{order_id}")
    assert get_res.status_code == 200
    assert get_res.json()["order_number"] == db_order.order_number


def test_order_cancellation_allowed_when_pending(api_client: TestClient, db_session: Session):
    """Verifies that an order in PENDING status can be cancelled via API and commits
    both the status update and an ORDER_CANCELLED domain event.
    """
    cust = db_session.execute(select(Customer)).scalars().first()
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-CAN-{uuid.uuid4().hex[:6].upper()}",
        customer_id=cust.id,
        status=OrderStatus.PENDING,
        total_amount=Decimal("1500.00"),
    )
    db_session.add(order)
    db_session.commit()

    res = api_client.post(
        f"/orders/{order.id}/cancel",
        json={"reason": "Customer changed mind"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"

    # Database verification
    db_session.refresh(order)
    assert order.status == OrderStatus.CANCELLED

    # Domain event verification
    event = db_session.execute(
        select(DomainEvent).where(
            DomainEvent.entity_id == order.id,
            DomainEvent.event_type == EventType.ORDER_CANCELLED,
        )
    ).scalar_one_or_none()
    assert event is not None
    assert event.payload.get("reason") == "Customer changed mind"


def test_order_cancellation_blocked_by_policy_when_delivered(
    api_client: TestClient, db_session: Session
):
    """Verifies that cancelling an already DELIVERED order is rejected by policy
    and preserves the existing DELIVERED state in DB.
    """
    cust = db_session.execute(select(Customer)).scalars().first()
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-DELIV-{uuid.uuid4().hex[:6].upper()}",
        customer_id=cust.id,
        status=OrderStatus.DELIVERED,
        total_amount=Decimal("2500.00"),
    )
    db_session.add(order)
    db_session.commit()

    res = api_client.post(
        f"/orders/{order.id}/cancel",
        json={"reason": "Item not wanted anymore"},
    )
    assert res.status_code in [400, 409, 422]

    # Database remains intact
    db_session.refresh(order)
    assert order.status == OrderStatus.DELIVERED


def test_low_value_refund_auto_approved(db_session: Session):
    """Verifies that an agent-driven refund for a low-value order (<= 2000 INR)
    under normal conditions is auto-approved and does not trigger an approval block.
    """
    seed_default_knowledge(db_session)
    _, order, _ = _setup_order(
        db_session, amount=Decimal("1200.00"), status=OrderStatus.DELIVERED
    )
    agent = OpsAgent()

    run = agent.run(
        input_text=f"Please refund my order {order.order_number} as item was defective",
        order_number=order.order_number,
        db=db_session,
    )

    assert run.state == WorkflowState.COMPLETED
    assert run.approval_id is None
    assert any("POL-REF-001.R2" in str(d.get("matched_rules")) for d in run.policy_decisions)


def test_high_value_refund_gated_by_policy(db_session: Session):
    """Verifies that a refund for a high-value order (> 2000 INR) is gated by policy
    (POL-REF-001.R1) and halts in WAITING_FOR_APPROVAL with an approval record.
    """
    seed_default_knowledge(db_session)
    _, order, pay = _setup_order(
        db_session, amount=Decimal("6500.00"), status=OrderStatus.DELIVERED
    )
    agent = OpsAgent()

    run = agent.run(
        input_text=f"I want a refund for my order {order.order_number} because it was defective",
        order_number=order.order_number,
        db=db_session,
    )

    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.approval_id is not None

    approval = db_session.execute(
        select(ApprovalRecord).where(ApprovalRecord.id == uuid.UUID(run.approval_id))
    ).scalar_one_or_none()
    assert approval is not None
    assert approval.status == ApprovalStatus.PENDING
    assert approval.action in ["request_refund", "process_refund"]

    # Payment in DB must still be SUCCESSFUL (not yet refunded)
    db_session.refresh(pay)
    assert pay.status == PaymentStatus.SUCCESSFUL


def test_human_approval_rejection_leaves_database_untouched(db_session: Session):
    """Verifies that when a human operator rejects a gated action, the workflow
    transitions to CANCELLED, approval becomes REJECTED, and zero DB mutations occur.
    """
    seed_default_knowledge(db_session)
    _, order, pay = _setup_order(
        db_session, amount=Decimal("7000.00"), status=OrderStatus.DELIVERED
    )
    agent = OpsAgent()

    run = agent.run(
        input_text=f"I want a refund for my order {order.order_number} because it was defective",
        order_number=order.order_number,
        db=db_session,
    )
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL

    # Operator rejects the approval in ApprovalService
    approval_svc = ApprovalService(db_session)
    approval_svc.reject(
        uuid.UUID(run.approval_id),
        approver_identity="finance_lead@opswingman.local",
        rejection_reason="Suspicious high amount transaction without purchase proof",
    )

    # Resume workflow with rejection
    resumed = agent.resume(
        run_id=run.run_id,
        approved=False,
        reason="Suspicious high amount transaction without purchase proof",
        db=db_session,
    )

    assert resumed.state == WorkflowState.CANCELLED

    # Verify approval status in DB
    appr_record = approval_svc.get_approval(uuid.UUID(run.approval_id))
    assert appr_record.status == ApprovalStatus.REJECTED

    # Verify payment remains untouched
    db_session.refresh(pay)
    assert pay.status == PaymentStatus.SUCCESSFUL


def test_human_approval_acceptance_resumes_and_commits_mutation(db_session: Session):
    """Verifies that when a human operator approves a gated action, the workflow
    resumes, executes the mutation with approval authorization, verifies the DB state,
    and finishes in COMPLETED.
    """
    seed_default_knowledge(db_session)
    _, order, pay = _setup_order(
        db_session, amount=Decimal("5500.00"), status=OrderStatus.DELIVERED
    )
    agent = OpsAgent()

    run = agent.run(
        input_text=f"I want a refund for my order {order.order_number} because it was defective",
        order_number=order.order_number,
        db=db_session,
    )
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL

    # Operator approves via ApprovalService
    approval_svc = ApprovalService(db_session)
    approval_svc.approve(
        uuid.UUID(run.approval_id),
        approver_identity="finance_head@opswingman.local",
    )

    # Resume workflow
    resumed = agent.resume(
        run_id=run.run_id,
        approved=True,
        reason="Verified customer receipt via phone support",
        db=db_session,
    )

    assert resumed.state == WorkflowState.COMPLETED

    # Verify approval status in DB
    appr_record = approval_svc.get_approval(uuid.UUID(run.approval_id))
    assert appr_record.status == ApprovalStatus.APPROVED

    # Verify payment status was mutated to REFUNDED
    db_session.refresh(pay)
    assert pay.status == PaymentStatus.REFUNDED


def test_resuming_finalized_workflow_rejected(db_session: Session):
    """Verifies that attempting to resume an already COMPLETED workflow raises
    a ValueError and performs zero second mutations.
    """
    seed_default_knowledge(db_session)
    _, order, _ = _setup_order(
        db_session, amount=Decimal("4500.00"), status=OrderStatus.DELIVERED
    )
    agent = OpsAgent()

    run = agent.run(
        input_text=f"I want a refund for my order {order.order_number} because it was defective",
        order_number=order.order_number,
        db=db_session,
    )
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL

    # First resume: approve
    resumed1 = agent.resume(
        run_id=run.run_id,
        approved=True,
        reason="Initial manager approval",
        db=db_session,
    )
    assert resumed1.state == WorkflowState.COMPLETED

    # Second resume must fail
    with pytest.raises(ValueError, match="is in state 'COMPLETED', not WAITING_FOR_APPROVAL"):
        agent.resume(
            run_id=run.run_id,
            approved=True,
            reason="Second redundant approval attempt",
            db=db_session,
        )
