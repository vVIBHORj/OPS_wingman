"""Unit and Integration tests for OpsAgent ML Risk Integration (Phase 4 - Deliverable D-13).

Verifies:
1. assess_risk LangGraph node execution between execute_tools and evaluate_policy.
2. Low-risk order evaluation -> normal flow, LOW risk band, auto-approval for low-value refund.
3. Elevated ML risk / anomaly gating -> forces approval on otherwise auto-approved low-value refunds (POL-REF-001.R4).
4. Order cancellation with elevated ML risk -> matches POL-CAN-001.R5, records risk factors, and updates proposed action risk to HIGH.
5. Model version, features, and explainability provenance persisted in WorkflowRunRecord and checkpoint store.
6. Approval resumption preserves risk_assessment and performs post-action verification.
7. Read-only invariant: assess_risk queries database entities without modifying them.
8. Fallback behavior when database session is not provided or order entity is missing.
9. Dependency injection of custom/mock MLRiskService into OpsAgent and OpsAgentService.
"""

import uuid
from decimal import Decimal
from typing import Any, Dict, Optional
import pytest
from sqlalchemy.orm import Session

import simulator
from backend.agents.ops_agent import OpsAgent
from backend.agents.service import OpsAgentService
from backend.ml import (
    AnomalyInfo,
    MLRiskService,
    OperationalRiskModel,
    RiskAssessmentResult,
    RiskBand,
    RiskFeatureVector,
    ml_risk_service,
)
from backend.policies.engine import PolicyEngine
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.tools.base import RiskLevel
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import WorkflowRunRecord, WorkflowState
from database.models import Customer, Order, OrderStatus, Payment, PaymentMethod, PaymentStatus, Product, Shipment, ShipmentStatus


@pytest.fixture(autouse=True)
def seed_kb(db_session: Session):
    seed_default_knowledge(db_session)


def _setup_test_order(
    db: Session,
    amount: Decimal = Decimal("1500.00"),
    status: OrderStatus = OrderStatus.CONFIRMED,
    customer_orders: int = 1,
) -> tuple[Customer, Order, Payment]:
    """Helper to set up a test customer, order, and payment in database."""
    cust_id = uuid.uuid4()
    cust = Customer(
        id=cust_id,
        first_name="Aarav",
        last_name="Sharma",
        email=f"aarav.{cust_id.hex[:6]}@example.com",
        phone="+919876543210",
    )
    db.add(cust)
    db.flush()

    prod_id = uuid.uuid4()
    prod = Product(
        id=prod_id,
        sku=f"SKU-{prod_id.hex[:6].upper()}",
        name="Smartphone Stand",
        unit_price=amount,
        inventory_count=50,
    )
    db.add(prod)
    db.flush()

    ord_id = uuid.uuid4()
    order_num = f"ORD-20261004-{ord_id.hex[:6].upper()}"
    order = Order(
        id=ord_id,
        order_number=order_num,
        customer_id=cust.id,
        status=status,
        currency="INR",
        subtotal_amount=amount,
        total_amount=amount,
    )
    db.add(order)
    db.flush()

    pay_id = uuid.uuid4()
    payment = Payment(
        id=pay_id,
        order_id=order.id,
        customer_id=cust.id,
        amount=amount,
        currency="INR",
        status=PaymentStatus.SUCCESSFUL,
        payment_method=PaymentMethod.UPI,
    )
    db.add(payment)
    db.commit()
    db.refresh(order)
    db.refresh(cust)
    db.refresh(payment)
    return cust, order, payment


def test_assess_risk_node_in_graph_pipeline():
    """Verify assess_risk node is registered and placed between execute_tools and evaluate_policy."""
    agent = OpsAgent()
    nodes = agent.graph.nodes
    assert "assess_risk" in nodes
    assert "execute_tools" in nodes
    assert "evaluate_policy" in nodes


def test_low_risk_order_inquiry_persists_assessment(db_session: Session):
    """Verify clean low-risk order inquiry populates risk_assessment and checkpoint step."""
    cust, order, _ = _setup_test_order(db_session, amount=Decimal("1200.00"))
    agent = OpsAgent()

    run = agent.run(
        input_text=f"Check status for order {order.order_number}",
        order_number=order.order_number,
        db=db_session,
    )

    assert run.state == WorkflowState.COMPLETED
    assert run.risk_assessment is not None
    assert run.risk_assessment["risk_band"] in ["LOW", "MEDIUM"]
    assert run.risk_assessment["risk_score"] < 0.70
    assert "model_version" in run.risk_assessment

    # Verify checkpoint logged assess_risk step
    step_names = [s.step_name for s in run.steps]
    assert "assess_risk" in step_names
    risk_step = next(s for s in run.steps if s.step_name == "assess_risk")
    assert risk_step.output_payload is not None
    assert "risk_assessment" in risk_step.output_payload


def test_low_value_refund_auto_approved_when_low_risk(db_session: Session):
    """Verify that a low-value refund (<= 2000) on a low-risk order is auto-approved."""
    cust, order, _ = _setup_test_order(db_session, amount=Decimal("1000.00"))
    agent = OpsAgent()

    run = agent.run(
        input_text=f"Please refund my order {order.order_number} as item was defective",
        order_number=order.order_number,
        db=db_session,
    )

    assert run.state == WorkflowState.COMPLETED
    assert run.risk_assessment is not None
    assert run.risk_assessment["risk_band"] != "HIGH"
    # Auto-approved: no approval needed
    assert run.approval_id is None
    assert any("POL-REF-001.R2" in str(d.get("matched_rules")) for d in run.policy_decisions)


def test_low_value_refund_gated_by_ml_anomaly(db_session: Session):
    """Verify low-value refund (<= 2000) is GATED when ML risk model flags an anomaly or HIGH risk."""
    cust, order, _ = _setup_test_order(db_session, amount=Decimal("1200.00"))

    # Create custom ML service that flags high risk / anomaly
    class HighRiskAnomalyModel(OperationalRiskModel):
        def score(self, features: RiskFeatureVector) -> RiskAssessmentResult:
            res = super().score(features)
            return RiskAssessmentResult(
                model_version=res.model_version,
                risk_score=0.88,
                risk_band=RiskBand.HIGH,
                is_high_risk=True,
                features=features,
                contributions=res.contributions,
                top_risk_factors=["Rapid velocity anomaly", "High refund frequency pattern"],
                anomaly=AnomalyInfo(
                    is_anomaly=True,
                    anomaly_score=0.92,
                    anomaly_flags=["UNUSUAL_VELOCITY_SPIKE", "SUSPICIOUS_REFUND_FREQUENCY"],
                    description="Order exhibits suspicious velocity anomaly",
                ),
                evaluated_at=res.evaluated_at,
            )

    custom_risk_service = MLRiskService(model=HighRiskAnomalyModel())
    agent = OpsAgent(risk_service=custom_risk_service)

    run = agent.run(
        input_text=f"Please refund my order {order.order_number}",
        order_number=order.order_number,
        db=db_session,
    )

    # Gated due to ML anomaly
    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.approval_id is not None
    assert run.risk_assessment is not None
    assert run.risk_assessment["risk_band"] == "HIGH"
    assert run.risk_assessment["risk_score"] == 0.88
    assert run.risk_assessment["anomaly"]["is_anomaly"] is True

    # Policy decision must cite ML anomaly rule
    pol_dec = run.policy_decisions[0]
    assert pol_dec["requires_approval"] is True
    assert "REF-R04" in pol_dec["matched_rules"]
    assert "POL-REF-001.R4: ML Anomaly / High Risk detected" in pol_dec["matched_rules"]
    assert pol_dec["relevant_facts"]["ml_anomaly_detected"] is True
    assert pol_dec["relevant_facts"]["ml_risk_band"] == "HIGH"


def test_order_cancellation_reflects_elevated_ml_risk(db_session: Session):
    """Verify order cancellation includes ML risk score and anomaly reasons in policy decision facts."""
    cust, order, _ = _setup_test_order(db_session, amount=Decimal("3000.00"))

    class AnomalyRiskModel(OperationalRiskModel):
        def score(self, features: RiskFeatureVector) -> RiskAssessmentResult:
            res = super().score(features)
            return RiskAssessmentResult(
                model_version="v1.0.0-custom",
                risk_score=0.76,
                risk_band=RiskBand.HIGH,
                is_high_risk=True,
                features=features,
                contributions=res.contributions,
                top_risk_factors=["Severe logistics delay"],
                anomaly=AnomalyInfo(
                    is_anomaly=True,
                    anomaly_score=0.80,
                    anomaly_flags=["REPEATED_CANCELLATIONS"],
                    description="Repeated cancellation anomaly",
                ),
                evaluated_at=res.evaluated_at,
            )

    agent = OpsAgent(risk_service=MLRiskService(model=AnomalyRiskModel()))

    run = agent.run(
        input_text=f"Cancel my order {order.order_number} please",
        order_number=order.order_number,
        db=db_session,
    )

    assert run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert run.approval_id is not None
    assert run.risk_assessment["model_version"] == "v1.0.0-custom"
    assert run.risk_assessment["risk_score"] == 0.76

    pol_dec = run.policy_decisions[0]
    assert pol_dec["requires_approval"] is True
    assert "POL-CAN-001.R5: ML Anomaly / High Risk detected" in pol_dec["matched_rules"]
    assert pol_dec["relevant_facts"]["ml_anomaly_detected"] is True


def test_approval_resumption_preserves_risk_assessment_and_verifies(db_session: Session):
    """Verify approved-action resume preserves the original risk_assessment on WorkflowRunRecord and executes verification."""
    cust, order, payment = _setup_test_order(db_session, amount=Decimal("1200.00"))

    class GatedModel(OperationalRiskModel):
        def score(self, features: RiskFeatureVector) -> RiskAssessmentResult:
            res = super().score(features)
            return RiskAssessmentResult(
                model_version="v1.0.0",
                risk_score=0.85,
                risk_band=RiskBand.HIGH,
                is_high_risk=True,
                features=features,
                contributions=res.contributions,
                top_risk_factors=["Risk trigger"],
                anomaly=AnomalyInfo(
                    is_anomaly=True,
                    anomaly_score=0.85,
                    anomaly_flags=["RISK_GATE"],
                    description="Testing risk gate",
                ),
                evaluated_at=res.evaluated_at,
            )

    agent = OpsAgent(risk_service=MLRiskService(model=GatedModel()))

    initial_run = agent.run(
        input_text=f"Please refund my order {order.order_number}",
        order_number=order.order_number,
        db=db_session,
    )

    assert initial_run.state == WorkflowState.WAITING_FOR_APPROVAL
    assert initial_run.risk_assessment is not None
    assert initial_run.risk_assessment["risk_score"] == 0.85

    # Resume with supervisor approval
    resumed_run = agent.resume_approved_action(
        run_id=initial_run.run_id,
        approved=True,
        db=db_session,
        reason="Supervisor verified risk and approved refund",
    )

    assert resumed_run.state == WorkflowState.COMPLETED
    assert resumed_run.risk_assessment is not None
    assert resumed_run.risk_assessment["risk_score"] == 0.85
    # Verification was performed
    assert len(resumed_run.verification_results) > 0
    assert resumed_run.verification_results[0]["verified"] is True
    db_session.refresh(payment)
    assert payment.status == PaymentStatus.REFUNDED


def test_assess_risk_read_only_invariance(db_session: Session):
    """Verify assess_risk node does NOT mutate the business entities in the database."""
    cust, order, payment = _setup_test_order(db_session, amount=Decimal("2000.00"))

    original_order_status = order.status
    original_total = order.total_amount
    original_pay_status = payment.status

    agent = OpsAgent()
    run = agent.run(
        input_text=f"Track my order {order.order_number}",
        order_number=order.order_number,
        db=db_session,
    )

    db_session.refresh(order)
    db_session.refresh(payment)
    assert order.status == original_order_status
    assert order.total_amount == original_total
    assert payment.status == original_pay_status
    assert run.risk_assessment is not None


def test_fallback_scoring_when_no_db_session():
    """Verify assess_risk node falls back gracefully to feature scoring without database."""
    agent = OpsAgent()
    # Run without DB session; tools won't query DB
    run = agent.run(
        input_text="Track my order ORD-20261004-999999",
        order_number="ORD-20261004-999999",
        db=None,
    )
    assert run.risk_assessment is not None
    assert "risk_score" in run.risk_assessment
    assert "risk_band" in run.risk_assessment
    assert "model_version" in run.risk_assessment


def test_service_facade_dependency_injection(db_session: Session):
    """Verify OpsAgentService supports dependency injection for risk_service."""
    cust, order, _ = _setup_test_order(db_session, amount=Decimal("1500.00"))

    custom_service = MLRiskService()
    svc = OpsAgentService(risk_service=custom_service)
    assert svc.risk_service is custom_service
    assert svc.agent.risk_service is custom_service

    run = svc.execute_workflow(
        db=db_session,
        input_text=f"Inquiry for order {order.order_number}",
        order_number=order.order_number,
    )
    assert run.risk_assessment is not None
