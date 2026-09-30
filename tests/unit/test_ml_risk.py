"""Unit tests for Standalone Risk / ML Subsystem (Phase 4 - Deliverable D-13)."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Customer, Order, OrderItem, OrderStatus, Payment, PaymentStatus, Product, Shipment, ShipmentStatus
from backend.ml.schemas import (
    RiskBand,
    RiskFeatureVector,
    ModelMetadata,
    RiskAssessmentResult,
)
from backend.ml.features import FeatureExtractor
from backend.ml.model import OperationalRiskModel
from backend.ml.service import MLRiskService


@pytest.fixture
def model() -> OperationalRiskModel:
    return OperationalRiskModel()


@pytest.fixture
def service(model: OperationalRiskModel) -> MLRiskService:
    return MLRiskService(model=model)


def test_model_version_and_metadata(model: OperationalRiskModel, service: MLRiskService):
    """6. Verifies model version is strictly v1.0.0 and metadata structure is complete."""
    metadata = service.get_model_metadata()

    assert metadata.model_version == "v1.0.0"
    assert metadata.model_name == "OperationalRiskModel"
    assert metadata.model_type == "DeterministicCalibratedScorer"
    assert "order_amount" in metadata.feature_names
    assert metadata.thresholds["low_max"] == 0.35
    assert metadata.thresholds["medium_max"] == 0.70


def test_low_risk_assessment(model: OperationalRiskModel):
    """1. Verifies a mature account with a low-value order and no refund/delay history produces LOW risk."""
    features = RiskFeatureVector(
        order_amount=800.0,
        account_age_days=180.0,  # Mature account >60 days -> 0 penalty
        refund_count=0,
        refund_ratio=0.0,
        delivery_delay_hours=0.0,
        payment_attempts=1,
        failed_payment_count=0,
        is_first_order=False,
    )

    result = model.score(features)

    assert result.risk_band == RiskBand.LOW
    assert result.is_high_risk is False
    assert result.risk_score < 0.35
    assert result.anomaly.is_anomaly is False


def test_medium_risk_assessment(model: OperationalRiskModel):
    """2. Verifies intermediate values produce a MEDIUM risk assessment."""
    features = RiskFeatureVector(
        order_amount=6500.0,
        account_age_days=15.0,  # Newer account
        refund_count=1,
        refund_ratio=0.25,
        delivery_delay_hours=12.0,
        payment_attempts=1,
        failed_payment_count=0,
        is_first_order=False,
    )

    result = model.score(features)

    assert result.risk_band == RiskBand.MEDIUM
    assert result.is_high_risk is False
    assert 0.35 <= result.risk_score < 0.70


def test_high_risk_assessment(model: OperationalRiskModel):
    """3. Verifies high order value, extensive refund history, and payment failures produce HIGH risk."""
    features = RiskFeatureVector(
        order_amount=18000.0,
        account_age_days=5.0,
        refund_count=3,
        refund_ratio=0.60,
        delivery_delay_hours=48.0,
        payment_attempts=3,
        failed_payment_count=2,
        is_first_order=False,
    )

    result = model.score(features)

    assert result.risk_band == RiskBand.HIGH
    assert result.is_high_risk is True
    assert result.risk_score >= 0.70
    assert len(result.top_risk_factors) >= 1


def test_exact_threshold_behavior(model: OperationalRiskModel):
    """4. Verifies decision boundaries: < 0.35 is LOW, 0.35 <= score < 0.70 is MEDIUM, >= 0.70 is HIGH."""
    # Low boundary check
    low_feat = RiskFeatureVector(order_amount=500.0, account_age_days=200.0)
    res_low = model.score(low_feat)
    assert res_low.risk_score < 0.35
    assert res_low.risk_band == RiskBand.LOW

    # High boundary check
    high_feat = RiskFeatureVector(
        order_amount=25000.0,
        account_age_days=1.0,
        refund_count=4,
        refund_ratio=0.80,
        failed_payment_count=3,
    )
    res_high = model.score(high_feat)
    assert res_high.risk_score >= 0.70
    assert res_high.risk_band == RiskBand.HIGH


def test_deterministic_scoring(model: OperationalRiskModel):
    """5. Verifies scoring is 100% deterministic and reproducible across repeated runs."""
    features = RiskFeatureVector(
        order_amount=3500.0,
        account_age_days=45.0,
        refund_count=1,
        refund_ratio=0.20,
        delivery_delay_hours=10.0,
        payment_attempts=2,
        failed_payment_count=1,
    )

    score_1 = model.score(features)
    score_2 = model.score(features)

    assert score_1.risk_score == score_2.risk_score
    assert score_1.risk_band == score_2.risk_band
    assert len(score_1.contributions) == len(score_2.contributions)
    assert score_1.contributions[0].contribution_score == score_2.contributions[0].contribution_score


def test_feature_extraction_from_entities():
    """7. Verifies feature extraction calculations from mock entity instances."""
    now = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
    cust_created = now - timedelta(days=90)
    customer = Customer(created_at=cust_created)
    order = Order(total_amount=Decimal("4999.00"))

    features = FeatureExtractor.extract_from_entities(
        order=order,
        customer=customer,
        now=now,
        total_customer_orders=5,
        customer_refund_count=1,
    )

    assert features.order_amount == 4999.0
    assert pytest.approx(features.account_age_days, 0.1) == 90.0
    assert features.refund_count == 1
    assert features.refund_ratio == 0.20
    assert features.is_first_order is False


def test_feature_validation_constraints():
    """8. & 12. Verifies Pydantic rejects invalid/negative inputs."""
    # Negative order amount
    with pytest.raises(ValidationError):
        RiskFeatureVector(order_amount=-100.0)

    # Negative account age
    with pytest.raises(ValidationError):
        RiskFeatureVector(account_age_days=-5.0)

    # Refund ratio > 1.0
    with pytest.raises(ValidationError):
        RiskFeatureVector(refund_ratio=1.5)

    # Payment attempts < 1
    with pytest.raises(ValidationError):
        RiskFeatureVector(payment_attempts=0)


def test_explanation_and_contribution_generation(model: OperationalRiskModel):
    """9. Verifies feature contributions are computed, sorted, and contain human-readable explanations."""
    features = RiskFeatureVector(
        order_amount=12000.0,
        account_age_days=10.0,
        refund_count=2,
        refund_ratio=0.50,
    )

    result = model.score(features)

    assert len(result.contributions) == 5
    # Verify contributions are sorted in descending order of impact
    for i in range(len(result.contributions) - 1):
        assert result.contributions[i].contribution_score >= result.contributions[i + 1].contribution_score

    # Check that descriptions are populated
    for contrib in result.contributions:
        assert len(contrib.explanation) > 0
        assert contrib.weight > 0.0
        assert 0.0 <= contrib.normalized_value <= 1.0


def test_anomaly_detection(model: OperationalRiskModel):
    """10. Verifies compound anomaly detection triggers on new accounts with high order value."""
    # Trigger 1: High Value on New Account
    feat_anomaly = RiskFeatureVector(
        order_amount=15000.0,
        account_age_days=2.0,
        is_first_order=True,
    )
    res = model.score(feat_anomaly)

    assert res.anomaly.is_anomaly is True
    assert "NEW_ACCOUNT_HIGH_VALUE" in res.anomaly.anomaly_flags
    assert res.anomaly.anomaly_score >= 0.75
    assert res.risk_band == RiskBand.HIGH

    # Trigger 2: High Refund Ratio
    feat_refund_anomaly = RiskFeatureVector(
        order_amount=2000.0,
        account_age_days=100.0,
        refund_count=3,
        refund_ratio=0.75,
    )
    res2 = model.score(feat_refund_anomaly)
    assert res2.anomaly.is_anomaly is True
    assert "HIGH_REFUND_RATIO" in res2.anomaly.anomaly_flags


def test_zero_and_edge_case_inputs(model: OperationalRiskModel):
    """11. Verifies scoring gracefully handles zero/baseline inputs without division by zero."""
    zero_features = RiskFeatureVector(
        order_amount=0.0,
        account_age_days=0.0,
        refund_count=0,
        refund_ratio=0.0,
        delivery_delay_hours=0.0,
        payment_attempts=1,
        failed_payment_count=0,
        is_first_order=True,
    )

    result = model.score(zero_features)

    assert 0.0 <= result.risk_score <= 1.0
    assert result.risk_band in [RiskBand.LOW, RiskBand.MEDIUM]
    assert len(result.contributions) == 5


def test_score_bounds(model: OperationalRiskModel):
    """13. Verifies risk scores are strictly clamped between 0.0 and 1.0 under extreme inputs."""
    extreme_features = RiskFeatureVector(
        order_amount=1_000_000.0,
        account_age_days=0.0,
        refund_count=100,
        refund_ratio=1.0,
        delivery_delay_hours=500.0,
        payment_attempts=10,
        failed_payment_count=8,
        is_first_order=True,
    )

    result = model.score(extreme_features)

    assert result.risk_score == 1.0
    assert result.risk_band == RiskBand.HIGH
    assert result.is_high_risk is True


def test_invalid_inputs_rejection():
    """12. Verifies that invalid types or out-of-bound numerical states fail fast."""
    with pytest.raises(ValidationError):
        RiskFeatureVector(order_amount="not_a_number")  # type: ignore

    with pytest.raises(ValidationError):
        RiskFeatureVector(refund_ratio=-0.1)


def test_risk_band_mapping_exhaustive(model: OperationalRiskModel):
    """14. Verifies exhaustive mapping from continuous scores to categorical RiskBand enums."""
    # Score < 0.35 -> LOW
    low_res = model.score(RiskFeatureVector(order_amount=200.0, account_age_days=120.0))
    assert low_res.risk_band == RiskBand.LOW
    assert low_res.is_high_risk is False

    # Score in [0.35, 0.70) -> MEDIUM
    med_res = model.score(
        RiskFeatureVector(
            order_amount=6500.0,
            account_age_days=15.0,
            refund_count=1,
            refund_ratio=0.25,
            delivery_delay_hours=12.0,
        )
    )
    assert med_res.risk_band == RiskBand.MEDIUM
    assert med_res.is_high_risk is False

    # Score >= 0.70 -> HIGH
    high_res = model.score(
        RiskFeatureVector(order_amount=20000.0, account_age_days=2.0, refund_count=3, refund_ratio=0.75)
    )
    assert high_res.risk_band == RiskBand.HIGH
    assert high_res.is_high_risk is True



def test_service_level_db_assessment(db_session: Session, service: MLRiskService):
    """15. Verifies end-to-end service assessment extracting features from a real DB session."""
    # 1. Create a customer
    cust = Customer(
        id=uuid.uuid4(),
        email="ml.test@example.com",
        first_name="Priya",
        last_name="Sharma",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        phone="+919888877777",
    )
    db_session.add(cust)
    db_session.commit()

    # 2. Create an order with items
    prod = db_session.scalars(select(Product)).first()
    assert prod is not None

    order = Order(
        id=uuid.uuid4(),
        order_number="ORD-20260930-ML0001",
        customer_id=cust.id,
        status=OrderStatus.CONFIRMED,
        subtotal_amount=Decimal("3998.00"),
        tax_amount=Decimal("719.64"),
        shipping_amount=Decimal("100.00"),
        total_amount=Decimal("4817.64"),
        currency="INR",
    )
    item = OrderItem(
        id=uuid.uuid4(),
        order_id=order.id,
        product_id=prod.id,
        sku=prod.sku,
        product_name=prod.name,
        quantity=2,
        unit_price=Decimal("1999.00"),
        total_price=Decimal("3998.00"),
    )
    order.items.append(item)
    db_session.add(order)
    db_session.commit()

    # 3. Assess risk using MLRiskService
    assessment = service.assess_order(db_session, order_id=str(order.id))

    assert assessment.model_version == "v1.0.0"
    assert assessment.features.order_amount == 4817.64
    assert 0.0 <= assessment.risk_score <= 1.0
    assert assessment.risk_band in [RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH]
    assert len(assessment.contributions) == 5
