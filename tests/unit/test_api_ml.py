"""API integration tests for Operational Risk & ML Endpoints (Phase 4 - Deliverable D-13)."""

import os
import tempfile
import uuid
from decimal import Decimal
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base
from database.session import get_db
from database.models import (
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Product,
)
from backend.main import app


@pytest.fixture(scope="function")
def ml_api_db() -> Generator[Session, None, None]:
    """Provides an isolated SQLite file DB session for ML API tests."""
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
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


@pytest.fixture(scope="function")
def client(ml_api_db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database session dependency."""
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield ml_api_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_model_info_endpoint(client: TestClient):
    """Verifies GET /risk/model-info returns metadata for model version v1.0.0."""
    response = client.get("/risk/model-info")

    assert response.status_code == 200
    data = response.json()

    assert data["model_version"] == "v1.0.0"
    assert data["model_name"] == "OperationalRiskModel"
    assert data["model_type"] == "DeterministicCalibratedScorer"
    assert "order_amount" in data["feature_names"]
    assert data["thresholds"]["low_max"] == 0.35
    assert data["thresholds"]["medium_max"] == 0.70


def test_assess_risk_custom_features_low_risk(client: TestClient):
    """Verifies POST /risk/assess classifies clean mature account features as LOW risk."""
    payload = {
        "custom_features": {
            "order_amount": 500.0,
            "account_age_days": 180.0,
            "refund_count": 0,
            "refund_ratio": 0.0,
            "delivery_delay_hours": 0.0,
            "payment_attempts": 1,
            "failed_payment_count": 0,
            "is_first_order": False,
        }
    }

    response = client.post("/risk/assess", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["model_version"] == "v1.0.0"
    assert data["risk_band"] == "LOW"
    assert data["is_high_risk"] is False
    assert data["risk_score"] < 0.35
    assert len(data["contributions"]) == 5
    assert data["anomaly"]["is_anomaly"] is False


def test_assess_risk_custom_features_medium_risk(client: TestClient):
    """Verifies POST /risk/assess classifies moderate parameters as MEDIUM risk."""
    payload = {
        "custom_features": {
            "order_amount": 6500.0,
            "account_age_days": 15.0,
            "refund_count": 1,
            "refund_ratio": 0.25,
            "delivery_delay_hours": 12.0,
            "payment_attempts": 1,
            "failed_payment_count": 0,
            "is_first_order": False,
        }
    }

    response = client.post("/risk/assess", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["risk_band"] == "MEDIUM"
    assert data["is_high_risk"] is False
    assert 0.35 <= data["risk_score"] < 0.70


def test_assess_risk_custom_features_high_risk(client: TestClient):
    """Verifies POST /risk/assess classifies risky parameters as HIGH risk with explanations."""
    payload = {
        "custom_features": {
            "order_amount": 22000.0,
            "account_age_days": 3.0,
            "refund_count": 4,
            "refund_ratio": 0.80,
            "delivery_delay_hours": 48.0,
            "payment_attempts": 3,
            "failed_payment_count": 2,
            "is_first_order": False,
        }
    }

    response = client.post("/risk/assess", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["risk_band"] == "HIGH"
    assert data["is_high_risk"] is True
    assert data["risk_score"] >= 0.70
    assert len(data["top_risk_factors"]) >= 1


def test_assess_risk_anomaly_detection(client: TestClient):
    """Verifies POST /risk/assess returns compound anomaly information."""
    payload = {
        "custom_features": {
            "order_amount": 16000.0,
            "account_age_days": 1.0,
            "is_first_order": True,
        }
    }

    response = client.post("/risk/assess", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["risk_band"] == "HIGH"
    assert data["anomaly"]["is_anomaly"] is True
    assert "NEW_ACCOUNT_HIGH_VALUE" in data["anomaly"]["anomaly_flags"]
    assert data["anomaly"]["anomaly_score"] >= 0.75


def test_assess_risk_by_order_id(client: TestClient, ml_api_db: Session):
    """Verifies POST /risk/assess extracting features from a real persisted order."""
    # 1. Seed customer and product
    cust = Customer(
        id=uuid.uuid4(),
        email="api.risk@example.com",
        first_name="Rohan",
        last_name="Verma",
        city="Delhi",
        state="Delhi",
        pincode="110001",
        phone="+919777788888",
    )
    prod = Product(
        id=uuid.uuid4(),
        sku="SKU-ML-API-01",
        name="Noise Cancelling Headphones",
        unit_price=Decimal("7999.00"),
        currency="INR",
        inventory_count=50,
        is_active=True,
    )
    ml_api_db.add_all([cust, prod])
    ml_api_db.commit()

    # 2. Seed order
    order = Order(
        id=uuid.uuid4(),
        order_number="ORD-20261001-RISK01",
        customer_id=cust.id,
        status=OrderStatus.CONFIRMED,
        subtotal_amount=Decimal("7999.00"),
        tax_amount=Decimal("1439.82"),
        shipping_amount=Decimal("0.00"),
        total_amount=Decimal("9438.82"),
        currency="INR",
    )
    item = OrderItem(
        id=uuid.uuid4(),
        order_id=order.id,
        product_id=prod.id,
        sku=prod.sku,
        product_name=prod.name,
        quantity=1,
        unit_price=Decimal("7999.00"),
        total_price=Decimal("7999.00"),
    )
    order.items.append(item)
    ml_api_db.add(order)
    ml_api_db.commit()

    # 3. Call API with order_id
    response = client.post("/risk/assess", json={"order_id": str(order.id)})
    assert response.status_code == 200
    data = response.json()

    assert data["model_version"] == "v1.0.0"
    assert data["features"]["order_amount"] == 9438.82
    assert data["risk_band"] in ["LOW", "MEDIUM", "HIGH"]
    assert len(data["contributions"]) == 5


def test_assess_risk_missing_identifiers_returns_400(client: TestClient):
    """Verifies POST /risk/assess returns 400 Bad Request when neither order_id nor custom_features is provided."""
    response = client.post("/risk/assess", json={"action_name": "refund_order"})

    assert response.status_code == 400
    assert "Must provide either 'order_id' or 'custom_features'" in response.json()["detail"]


def test_assess_risk_invalid_feature_values_returns_422(client: TestClient):
    """Verifies POST /risk/assess returns 422 Unprocessable Entity on validation violations."""
    payload = {
        "custom_features": {
            "order_amount": -500.0,  # Invalid negative amount
        }
    }

    response = client.post("/risk/assess", json=payload)
    assert response.status_code == 422
