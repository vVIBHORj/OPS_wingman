"""
Unit and Integration tests for Ops Agent and Stateful Workflows (Phase 2 - Deliverable D-08, D-09).
Verifies LangGraph execution, checkpoint state transitions, risk evaluation, and agent API routes.
"""

import os
import tempfile
import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database.base import Base
from database.session import get_db
from database.models import Customer, Product, OrderStatus, ShipmentStatus
from backend.main import app
from backend.agents.ops_agent import OpsAgent
from backend.workflows.state import WorkflowState
from backend.workflows.checkpoint import checkpoint_store
import simulator


@pytest.fixture(scope="function")
def test_db():
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    cust = Customer(
        id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        email="agent.user@example.com",
        first_name="Ananya",
        last_name="Deshmukh",
        city="Pune",
        state="Maharashtra",
        pincode="411004",
        phone="+919822001122",
    )
    prod = Product(
        id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        sku="SKU-AGENT-01",
        name="Ultra ANC Headphones",
        unit_price=Decimal("4999.00"),
        currency="INR",
        inventory_count=50,
        is_active=True,
    )
    session.add_all([cust, prod])
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def api_client():
    """Provides a TestClient with an isolated temporary SQLite database session."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{temp_db_path}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as session:
        cust = Customer(
            id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
            email="agent.api@example.com",
            first_name="Riya",
            last_name="Sen",
            city="Kolkata",
            state="West Bengal",
            pincode="700001",
        )
        prod = Product(
            id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
            sku="SKU-AGENT-API",
            name="Smart Fitness Band",
            unit_price=Decimal("1999.00"),
            currency="INR",
            inventory_count=25,
            is_active=True,
        )
        session.add_all([cust, prod])
        session.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass


# ==============================================================================
# Ops Agent LangGraph Execution Tests
# ==============================================================================

def test_agent_low_risk_order_status_workflow(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    agent = OpsAgent()
    run_record = agent.run(
        input_text=f"Hi, what is the status of my order {order.order_number}?",
        db=test_db,
    )

    assert run_record.state == WorkflowState.COMPLETED
    assert run_record.intent == "check_order_status"
    assert run_record.extracted_entities.get("order_number") == order.order_number
    assert run_record.final_response is not None
    assert order.order_number in run_record.final_response
    assert "PENDING" in run_record.final_response

    # Verify checkpoint trace steps recorded
    step_names = [s.step_name for s in run_record.steps]
    assert "interpret_request" in step_names
    assert "plan_tools" in step_names
    assert "execute_tool_get_order" in step_names
    assert "synthesize_response" in step_names


def test_agent_low_risk_shipment_tracking_workflow(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )
    payment = simulator.create_payment(session=test_db, order_id=order.id)
    simulator.capture_payment(session=test_db, payment_id=payment.id)
    shipment = simulator.create_shipment(session=test_db, order_id=order.id, carrier="Delhivery")
    simulator.update_shipment_status(session=test_db, shipment_id=shipment.id, new_status=ShipmentStatus.IN_TRANSIT, location="Pune Hub")

    agent = OpsAgent()
    run_record = agent.run(
        input_text=f"Please track my shipment for order {order.order_number}, where is it?",
        db=test_db,
    )

    assert run_record.state == WorkflowState.COMPLETED
    assert run_record.intent == "track_shipment"
    assert run_record.final_response is not None
    assert "Delhivery" in run_record.final_response
    assert "Pune Hub" in run_record.final_response
    assert shipment.tracking_number in run_record.final_response



def test_agent_high_risk_cancellation_workflow_pauses_for_approval(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    agent = OpsAgent()
    run_record = agent.run(
        input_text=f"I want to cancel my order {order.order_number} please.",
        db=test_db,
    )

    # Must transition to WAITING_FOR_APPROVAL and not silently execute cancellation without oversight
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run_record.intent == "cancel_order_request"
    assert len(run_record.proposed_actions) >= 1
    assert run_record.proposed_actions[0].action == "cancel_order"
    assert run_record.proposed_actions[0].requires_approval is True
    assert run_record.proposed_actions[0].risk == "HIGH"
    # Verify order is still PENDING in database
    assert order.status == OrderStatus.PENDING


def test_agent_high_risk_approval_and_resume_flow(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    agent = OpsAgent()
    run_record = agent.run(
        input_text=f"Please cancel my order {order.order_number}.",
        db=test_db,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL

    # Resume with approval
    resumed_record = agent.resume(
        run_id=run_record.run_id,
        approved=True,
        db=test_db,
        reason="Operator approved cancellation request",
    )

    assert resumed_record.state == WorkflowState.COMPLETED
    assert "Approved actions executed successfully" in str(resumed_record.final_response)

    # Verify side effect was executed on the order in database
    test_db.refresh(order)
    assert order.status == OrderStatus.CANCELLED


def test_agent_high_risk_rejection_flow(test_db: Session):
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    agent = OpsAgent()
    run_record = agent.run(
        input_text=f"Cancel my order {order.order_number}",
        db=test_db,
    )
    assert run_record.state == WorkflowState.WAITING_FOR_APPROVAL

    # Resume with rejection
    resumed_record = agent.resume(
        run_id=run_record.run_id,
        approved=False,
        db=test_db,
        reason="Cancellation window expired according to policy",
    )

    assert resumed_record.state == WorkflowState.CANCELLED
    assert "Action rejected" in str(resumed_record.final_response)

    # Verify side effect was NOT executed
    test_db.refresh(order)
    assert order.status == OrderStatus.PENDING


def test_durable_checkpoint_store_persistence(tmp_path):
    from backend.workflows.checkpoint import WorkflowCheckpointStore
    from backend.workflows.state import WorkflowRunRecord, WorkflowState

    store_dir = tmp_path / "checkpoints"
    store1 = WorkflowCheckpointStore(storage_dir=store_dir)

    run1 = WorkflowRunRecord(
        input_text="Check status for ORD-20260928-112233",
        state=WorkflowState.RUNNING,
    )
    store1.save(run1)
    store1.add_step(
        run_id=run1.run_id,
        step_name="interpret_request",
        state=WorkflowState.RUNNING,
        input_payload={"input": run1.input_text},
    )

    # Simulate fresh process initialization
    store2 = WorkflowCheckpointStore(storage_dir=store_dir)
    loaded_run = store2.get(run1.run_id)

    assert loaded_run is not None
    assert loaded_run.run_id == run1.run_id
    assert loaded_run.input_text == "Check status for ORD-20260928-112233"
    assert len(loaded_run.steps) == 1
    assert loaded_run.steps[0].step_name == "interpret_request"


# ==============================================================================
# Agent REST API Tests
# ==============================================================================

def test_api_agent_run_and_query_endpoints(api_client: TestClient):
    # 1. Create an order via API
    order_res = api_client.post(
        "/orders",
        json={
            "customer_id": "11111111-1111-4111-8111-111111111111",
            "items": [{"product_id": "22222222-2222-4222-8222-222222222222", "quantity": 1}],
        },
    )
    assert order_res.status_code == 201
    order_num = order_res.json()["order_number"]

    # 2. Trigger POST /agent/run
    agent_res = api_client.post(
        "/agent/run",
        json={
            "input_text": f"Can you check the status of {order_num}?",
        },
    )
    assert agent_res.status_code == 200
    run_data = agent_res.json()
    assert run_data["state"] == "COMPLETED"
    assert run_data["intent"] == "check_order_status"
    run_id = run_data["run_id"]

    # 3. GET /agent/runs/{run_id}
    single_run = api_client.get(f"/agent/runs/{run_id}")
    assert single_run.status_code == 200
    assert single_run.json()["run_id"] == run_id

    # 4. GET /agent/runs
    all_runs = api_client.get("/agent/runs")
    assert all_runs.status_code == 200
    assert len(all_runs.json()) >= 1

    # 5. GET /agent/tools
    tools_res = api_client.get("/agent/tools")
    assert tools_res.status_code == 200
    tool_names = [t["name"] for t in tools_res.json()]
    assert "get_order" in tool_names
    assert "cancel_order" in tool_names
    assert "request_refund" in tool_names
    assert "request_human_approval" in tool_names


def test_api_agent_approval_and_resume_endpoint(api_client: TestClient):
    # 1. Create an order via API
    order_res = api_client.post(
        "/orders",
        json={
            "customer_id": "11111111-1111-4111-8111-111111111111",
            "items": [{"product_id": "22222222-2222-4222-8222-222222222222", "quantity": 1}],
        },
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]
    order_num = order_res.json()["order_number"]

    # 2. Trigger POST /agent/run for cancellation -> pauses in WAITING_FOR_APPROVAL
    agent_res = api_client.post(
        "/agent/run",
        json={"input_text": f"Please cancel order {order_num}."},
    )
    assert agent_res.status_code == 200
    run_data = agent_res.json()
    assert run_data["state"] == "WAITING_FOR_APPROVAL"
    run_id = run_data["run_id"]

    # 3. Call POST /agent/runs/{run_id}/resume with approved=True
    resume_res = api_client.post(
        f"/agent/runs/{run_id}/resume",
        json={"approved": True, "reason": "Authorized by supervisor"},
    )
    assert resume_res.status_code == 200
    resumed_data = resume_res.json()
    assert resumed_data["state"] == "COMPLETED"

    # 4. Verify order is now cancelled via GET /orders/{order_id}
    order_check = api_client.get(f"/orders/{order_id}")
    assert order_check.status_code == 200
    assert order_check.json()["status"] == "CANCELLED"

