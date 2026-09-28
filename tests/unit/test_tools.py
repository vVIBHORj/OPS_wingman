"""
Unit tests for the OpsWingman Tool Registry (Phase 2 - Deliverable D-07).
Validates schema validation, risk tiering, tool execution, and error handling.
"""

import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database.base import Base
from database.models import Customer, Product, Order, Payment, Shipment, OrderStatus, PaymentStatus, PaymentMethod, ShipmentStatus
from backend.tools.base import ToolRegistry, RiskLevel, ToolType
from backend.tools.registry import create_default_tool_registry
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
        email="tools.test@example.com",
        first_name="Vikram",
        last_name="Malhotra",
        city="Pune",
        state="Maharashtra",
        pincode="411001",
        phone="+919876543210",
    )
    prod = Product(
        id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        sku="SKU-TOOL-01",
        name="Mechanical Keyboard",
        unit_price=Decimal("4500.00"),
        currency="INR",
        inventory_count=40,
        is_active=True,
    )
    session.add_all([cust, prod])
    session.commit()

    try:
        yield session
    finally:
        session.close()


def test_tool_registry_initialization_and_metadata():
    registry = create_default_tool_registry()
    tools = registry.list_tools()

    assert len(tools) == 11
    tool_names = {t.name for t in tools}
    expected_tools = {
        "get_customer",
        "get_order",
        "get_payment",
        "get_shipment",
        "get_policy",
        "create_ticket",
        "send_customer_message",
        "request_refund",
        "cancel_order",
        "request_human_approval",
        "update_workflow_state",
    }
    assert expected_tools.issubset(tool_names)

    # Verify risk levels
    cancel_tool = registry.get("cancel_order")
    assert cancel_tool is not None
    assert cancel_tool.risk_level == RiskLevel.HIGH

    refund_tool = registry.get("request_refund")
    assert refund_tool is not None
    assert refund_tool.risk_level == RiskLevel.HIGH

    approval_tool = registry.get("request_human_approval")
    assert approval_tool is not None
    assert approval_tool.risk_level == RiskLevel.MEDIUM

    order_tool = registry.get("get_order")
    assert order_tool is not None
    assert order_tool.risk_level == RiskLevel.LOW
    assert order_tool.tool_type == ToolType.READ


def test_get_customer_tool(test_db: Session):
    registry = create_default_tool_registry()
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")

    # By customer_id
    res = registry.execute("get_customer", {"customer_id": str(customer_id)}, context={"db": test_db})
    assert res.success is True
    assert res.data is not None
    assert res.data["email"] == "tools.test@example.com"
    assert res.data["first_name"] == "Vikram"

    # By email
    res_email = registry.execute("get_customer", {"email": "tools.test@example.com"}, context={"db": test_db})
    assert res_email.success is True
    assert res_email.data is not None
    assert res_email.data["city"] == "Pune"


def test_get_order_and_shipment_tools(test_db: Session):
    registry = create_default_tool_registry()
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )
    payment = simulator.create_payment(session=test_db, order_id=order.id)
    simulator.capture_payment(session=test_db, payment_id=payment.id)
    shipment = simulator.create_shipment(session=test_db, order_id=order.id, carrier="BlueDart")

    # 1. get_order by order_number
    res_ord = registry.execute("get_order", {"order_number": order.order_number}, context={"db": test_db})
    assert res_ord.success is True
    assert res_ord.data is not None
    assert res_ord.data["order_number"] == order.order_number
    assert res_ord.data["status"] == OrderStatus.SHIPPED.value

    # 2. get_payment by order_id
    res_pay = registry.execute("get_payment", {"order_id": str(order.id)}, context={"db": test_db})
    assert res_pay.success is True
    assert res_pay.data is not None
    assert res_pay.data["status"] == PaymentStatus.SUCCESSFUL.value

    # 3. get_shipment by tracking_number
    res_shp = registry.execute("get_shipment", {"tracking_number": shipment.tracking_number}, context={"db": test_db})
    assert res_shp.success is True
    assert res_shp.data is not None
    assert res_shp.data["carrier"] == "BlueDart"


def test_get_policy_tool():
    registry = create_default_tool_registry()

    res = registry.execute("get_policy", {"policy_name": "cancellation_window"})
    assert res.success is True
    assert res.data is not None
    assert res.data["risk_level"] == "HIGH"
    assert "PENDING" in str(res.data["rule"])

    res_sla = registry.execute("get_policy", {"policy_name": "shipping_sla"})
    assert res_sla.success is True
    assert res_sla.data is not None
    assert res_sla.data["risk_level"] == "LOW"


def test_create_ticket_tool(test_db: Session):
    registry = create_default_tool_registry()
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")

    res = registry.execute(
        "create_ticket",
        {
            "customer_id": str(customer_id),
            "subject": "Delay in delivery",
            "description": "Package is delayed beyond 3 days.",
            "priority": "HIGH",
            "channel": "EMAIL",
        },
        context={"db": test_db},
    )
    assert res.success is True
    assert res.data is not None
    assert str(res.data["ticket_number"]).startswith("TCK-")
    assert res.data["subject"] == "Delay in delivery"


def test_high_risk_authorization_boundary_enforcement(test_db: Session):
    """
    Verifies that calling a HIGH-risk tool without explicit approval authorization
    is blocked directly at the ToolRegistry boundary.
    """
    registry = create_default_tool_registry()
    customer_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    order = simulator.create_order(
        session=test_db,
        customer_id=customer_id,
        items=[{"product_id": product_id, "quantity": 1}],
    )

    # 1. Direct call to cancel_order without approval -> BLOCKED
    res_unauthorized = registry.execute(
        "cancel_order",
        {"order_id": str(order.id), "reason": "Customer changed mind"},
        context={"db": test_db},
    )
    assert res_unauthorized.success is False
    assert res_unauthorized.error is not None
    assert "Execution blocked: HIGH-risk tool 'cancel_order' requires explicit approval authorization" in res_unauthorized.error

    # 2. Direct call to request_refund without approval -> BLOCKED
    res_refund_unauth = registry.execute(
        "request_refund",
        {"order_id": str(order.id), "reason": "Defective item"},
        context={"db": test_db},
    )
    assert res_refund_unauth.success is False
    assert res_refund_unauth.error is not None
    assert "Execution blocked: HIGH-risk tool 'request_refund' requires explicit approval authorization" in res_refund_unauth.error

    # 3. Call cancel_order with explicit approval -> SUCCESS
    res_authorized = registry.execute(
        "cancel_order",
        {"order_id": str(order.id), "reason": "Approved cancellation"},
        context={"db": test_db, "approved": True},
    )
    assert res_authorized.success is True
    assert res_authorized.data is not None
    assert res_authorized.data["status"] == OrderStatus.CANCELLED.value


def test_request_human_approval_tool():
    registry = create_default_tool_registry()
    wf_id = str(uuid.uuid4())

    res = registry.execute(
        "request_human_approval",
        {
            "workflow_id": wf_id,
            "action": "cancel_order",
            "reason": "Order value > INR 10,000",
            "risk_level": "HIGH",
            "payload": {"order_number": "ORD-20260928-123456"},
        },
    )
    assert res.success is True
    assert res.data is not None
    assert res.data["status"] == "WAITING_FOR_APPROVAL"
    assert str(res.data["approval_id"]).startswith("APV-")
    assert res.data["workflow_id"] == wf_id


def test_tool_validation_error():
    registry = create_default_tool_registry()

    # Missing required 'reason' parameter for cancel_order (when authorized)
    res = registry.execute(
        "cancel_order",
        {"order_id": str(uuid.uuid4())},
        context={"approved": True},
    )
    assert res.success is False
    assert res.error is not None
    assert "Field required" in res.error or "validation error" in res.error.lower()


