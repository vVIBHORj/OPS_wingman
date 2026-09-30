"""Schemas for Operational Risk and ML Subsystem (Phase 4 - Deliverable D-13)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RiskBand(str, Enum):
    """Standardized operational risk categories."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ModelMetadata(BaseModel):
    """Metadata describing the operational risk model, version, and parameters."""
    model_config = ConfigDict(from_attributes=True)

    model_name: str = Field(default="OperationalRiskModel", description="Name of the scoring model")
    model_version: str = Field(default="v1.0.0", description="Strict semantic version of the model")
    model_type: str = Field(default="DeterministicCalibratedScorer", description="Algorithm or model classification")
    description: str = Field(
        default="Deterministic operational risk scoring and anomaly detection model for e-commerce orders and actions.",
        description="Model summary",
    )
    feature_names: List[str] = Field(description="Names of input features consumed by the model")
    thresholds: Dict[str, float] = Field(description="Decision thresholds for risk bands")
    created_at: str = Field(default="2026-09-30", description="Release date of model version")


class RiskFeatureVector(BaseModel):
    """Normalized operational feature vector extracted from business entities."""
    model_config = ConfigDict(from_attributes=True)

    order_amount: float = Field(default=0.0, ge=0.0, description="Total monetary value of the order in INR")
    account_age_days: float = Field(default=0.0, ge=0.0, description="Age of customer account in days")
    refund_count: int = Field(default=0, ge=0, description="Total historical refunds requested by customer")
    refund_ratio: float = Field(default=0.0, ge=0.0, le=1.0, description="Ratio of refunded/cancelled orders to total orders [0.0, 1.0]")
    delivery_delay_hours: float = Field(default=0.0, ge=0.0, description="Shipment delay in hours past estimated delivery")
    payment_attempts: int = Field(default=1, ge=1, description="Number of payment attempts made for the order")
    failed_payment_count: int = Field(default=0, ge=0, description="Number of failed payment attempts for the order")
    is_first_order: bool = Field(default=False, description="Whether this is the customer's first order")


class FeatureContribution(BaseModel):
    """Contribution and explainability breakdown for a single input feature."""
    model_config = ConfigDict(from_attributes=True)

    feature_name: str = Field(description="Name of the feature")
    feature_value: float = Field(description="Observed value of the feature")
    normalized_value: float = Field(description="Normalized feature score in [0.0, 1.0]")
    weight: float = Field(description="Model weight assigned to this feature")
    contribution_score: float = Field(description="Weighted contribution (normalized_value * weight)")
    explanation: str = Field(description="Human-readable explanation of the contribution")


class AnomalyInfo(BaseModel):
    """Detailed anomaly evaluation result detecting unusual operational patterns."""
    model_config = ConfigDict(from_attributes=True)

    is_anomaly: bool = Field(default=False, description="True if an operational anomaly was detected")
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Anomaly severity score [0.0, 1.0]")
    anomaly_flags: List[str] = Field(default_factory=list, description="Specific anomaly trigger tags")
    description: Optional[str] = Field(default=None, description="Summary explanation of the anomaly")


class RiskAssessmentRequest(BaseModel):
    """Request payload to assess risk for an order, customer, or custom feature vector."""
    model_config = ConfigDict(from_attributes=True)

    order_id: Optional[str] = Field(default=None, description="UUID or order number of the target order")
    customer_id: Optional[str] = Field(default=None, description="UUID of the target customer")
    action_name: Optional[str] = Field(default=None, description="Target action name, e.g. refund_order, cancel_order")
    custom_features: Optional[RiskFeatureVector] = Field(default=None, description="Direct feature vector override")


class RiskAssessmentResult(BaseModel):
    """Comprehensive, explainable operational risk assessment result."""
    model_config = ConfigDict(from_attributes=True)

    model_version: str = Field(default="v1.0.0", description="Model version used for scoring")
    risk_score: float = Field(ge=0.0, le=1.0, description="Calibrated operational risk score [0.0, 1.0]")
    risk_band: RiskBand = Field(description="Categorical risk band (LOW, MEDIUM, HIGH)")
    is_high_risk: bool = Field(description="True if risk_band is HIGH or risk_score >= 0.70")
    features: RiskFeatureVector = Field(description="Raw input feature values")
    contributions: List[FeatureContribution] = Field(description="Explainability breakdown per feature")
    top_risk_factors: List[str] = Field(default_factory=list, description="Top human-readable risk drivers")
    anomaly: AnomalyInfo = Field(description="Anomaly detection breakdown")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Evaluation timestamp")
