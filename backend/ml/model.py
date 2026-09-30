"""Operational Risk Model and Deterministic Scoring Engine (Phase 4 - Deliverable D-13).

Provides explainable risk scoring, anomaly detection, and decision categorization
calibrated for e-commerce order management and agent operations.
"""

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from backend.ml.schemas import (
    AnomalyInfo,
    FeatureContribution,
    ModelMetadata,
    RiskBand,
    RiskAssessmentResult,
    RiskFeatureVector,
)


class OperationalRiskModel:
    """Deterministic, explainable operational risk model (v1.0.0)."""

    MODEL_VERSION: str = "v1.0.0"
    MODEL_NAME: str = "OperationalRiskModel"

    # Decision Thresholds
    LOW_RISK_THRESHOLD: float = 0.35
    MEDIUM_RISK_THRESHOLD: float = 0.70

    # Feature Weights (sum to 1.0)
    WEIGHT_ORDER_AMOUNT: float = 0.30
    WEIGHT_REFUND_HISTORY: float = 0.25
    WEIGHT_ACCOUNT_AGE: float = 0.15
    WEIGHT_DELIVERY_DELAY: float = 0.15
    WEIGHT_PAYMENT_FRICTION: float = 0.15

    # Normalization Constants
    REFERENCE_HIGH_AMOUNT: float = 12000.0   # INR 12,000 represents high risk scale
    REFERENCE_MATURE_AGE_DAYS: float = 60.0  # 60 days to reach mature low-risk account baseline
    REFERENCE_MAX_DELAY_HOURS: float = 72.0  # 72 hours represents severe delay threshold

    def get_metadata(self) -> ModelMetadata:
        """Returns structured metadata and configuration parameters for this model version."""
        return ModelMetadata(
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            model_type="DeterministicCalibratedScorer",
            description="Deterministic operational risk scoring and anomaly detection model for e-commerce orders and agent actions.",
            feature_names=[
                "order_amount",
                "refund_history",
                "account_age",
                "delivery_delay",
                "payment_friction",
            ],
            thresholds={
                "low_max": self.LOW_RISK_THRESHOLD,
                "medium_max": self.MEDIUM_RISK_THRESHOLD,
            },
            created_at="2026-09-30",
        )

    def evaluate_anomalies(self, features: RiskFeatureVector) -> AnomalyInfo:
        """Evaluates operational features against compound anomaly detection rules."""
        flags: List[str] = []
        descriptions: List[str] = []

        # Compound Anomaly 1: New Account + High Order Value
        if (features.is_first_order or features.account_age_days < 7.0) and features.order_amount >= 10000.0:
            flags.append("NEW_ACCOUNT_HIGH_VALUE")
            descriptions.append(f"High-value order (₹{features.order_amount:,.2f}) on new account (<7 days old).")

        # Compound Anomaly 2: High Refund Ratio with multiple refunds
        if features.refund_ratio >= 0.50 and features.refund_count >= 2:
            flags.append("HIGH_REFUND_RATIO")
            descriptions.append(f"Abnormal refund frequency ({features.refund_count} refunds, {features.refund_ratio:.0%} of orders).")

        # Compound Anomaly 3: Repeated Payment Failures
        if features.failed_payment_count >= 2:
            flags.append("REPEATED_PAYMENT_FAILURES")
            descriptions.append(f"Multiple failed payment attempts ({features.failed_payment_count} failures).")

        # Compound Anomaly 4: Severe Logistics Delay
        if features.delivery_delay_hours >= 96.0:
            flags.append("SEVERE_LOGISTICS_DELAY")
            descriptions.append(f"Critical shipment delay ({features.delivery_delay_hours:.1f} hours past estimate).")

        if not flags:
            return AnomalyInfo(is_anomaly=False, anomaly_score=0.0, anomaly_flags=[], description=None)

        # Compute anomaly severity score
        base_severity = min(1.0, 0.30 * len(flags))
        if "NEW_ACCOUNT_HIGH_VALUE" in flags:
            base_severity = max(base_severity, 0.75)
        if "HIGH_REFUND_RATIO" in flags:
            base_severity = max(base_severity, 0.80)

        return AnomalyInfo(
            is_anomaly=True,
            anomaly_score=min(1.0, max(0.0, base_severity)),
            anomaly_flags=flags,
            description="; ".join(descriptions),
        )

    def score(self, features: RiskFeatureVector) -> RiskAssessmentResult:
        """Computes calibrated operational risk score, feature contributions, and risk band."""
        contributions: List[FeatureContribution] = []
        risk_factors: List[str] = []

        # 1. Order Amount Component
        norm_amount = min(1.0, max(0.0, features.order_amount / self.REFERENCE_HIGH_AMOUNT))
        amount_contrib = norm_amount * self.WEIGHT_ORDER_AMOUNT
        amount_exp = (
            f"High order value of ₹{features.order_amount:,.2f} contributes significantly to financial risk."
            if features.order_amount >= 5000.0
            else f"Order amount of ₹{features.order_amount:,.2f} is within standard operational range."
        )
        contributions.append(
            FeatureContribution(
                feature_name="order_amount",
                feature_value=features.order_amount,
                normalized_value=norm_amount,
                weight=self.WEIGHT_ORDER_AMOUNT,
                contribution_score=amount_contrib,
                explanation=amount_exp,
            )
        )
        if norm_amount >= 0.40:
            risk_factors.append(f"Order value: ₹{features.order_amount:,.2f}")

        # 2. Refund History Component
        norm_refund = min(1.0, max(0.0, (features.refund_ratio * 0.70) + (features.refund_count * 0.15)))
        refund_contrib = norm_refund * self.WEIGHT_REFUND_HISTORY
        refund_exp = (
            f"Customer has {features.refund_count} prior refunds ({features.refund_ratio:.0%} refund rate)."
            if features.refund_count > 0
            else "Clean customer history with no previous refunds."
        )
        contributions.append(
            FeatureContribution(
                feature_name="refund_history",
                feature_value=float(features.refund_count),
                normalized_value=norm_refund,
                weight=self.WEIGHT_REFUND_HISTORY,
                contribution_score=refund_contrib,
                explanation=refund_exp,
            )
        )
        if norm_refund >= 0.30:
            risk_factors.append(f"Prior refunds: {features.refund_count} ({features.refund_ratio:.0%})")

        # 3. Account Age Component (New accounts receive higher penalty)
        norm_account_age = max(0.0, min(1.0, 1.0 - (features.account_age_days / self.REFERENCE_MATURE_AGE_DAYS)))
        if features.is_first_order and features.account_age_days < 7.0:
            norm_account_age = max(norm_account_age, 0.80)
        age_contrib = norm_account_age * self.WEIGHT_ACCOUNT_AGE
        age_exp = (
            f"New customer account ({features.account_age_days:.1f} days old) has limited trust history."
            if features.account_age_days < 30.0
            else f"Established account ({features.account_age_days:.1f} days old)."
        )
        contributions.append(
            FeatureContribution(
                feature_name="account_age",
                feature_value=features.account_age_days,
                normalized_value=norm_account_age,
                weight=self.WEIGHT_ACCOUNT_AGE,
                contribution_score=age_contrib,
                explanation=age_exp,
            )
        )
        if norm_account_age >= 0.50:
            risk_factors.append(f"New account age: {features.account_age_days:.1f} days")

        # 4. Delivery Delay Component
        norm_delay = min(1.0, max(0.0, features.delivery_delay_hours / self.REFERENCE_MAX_DELAY_HOURS))
        delay_contrib = norm_delay * self.WEIGHT_DELIVERY_DELAY
        delay_exp = (
            f"Shipment is delayed by {features.delivery_delay_hours:.1f} hours past estimated delivery."
            if features.delivery_delay_hours > 0.0
            else "Shipment is on schedule or no delay recorded."
        )
        contributions.append(
            FeatureContribution(
                feature_name="delivery_delay",
                feature_value=features.delivery_delay_hours,
                normalized_value=norm_delay,
                weight=self.WEIGHT_DELIVERY_DELAY,
                contribution_score=delay_contrib,
                explanation=delay_exp,
            )
        )
        if norm_delay >= 0.30:
            risk_factors.append(f"Delivery delay: {features.delivery_delay_hours:.1f}h")

        # 5. Payment Friction Component
        norm_payment = min(
            1.0,
            max(0.0, (features.failed_payment_count * 0.50) + (max(0, features.payment_attempts - 1) * 0.20)),
        )
        payment_contrib = norm_payment * self.WEIGHT_PAYMENT_FRICTION
        payment_exp = (
            f"Order experienced {features.failed_payment_count} failed payment attempts across {features.payment_attempts} tries."
            if features.failed_payment_count > 0 or features.payment_attempts > 1
            else "Single successful payment without friction."
        )
        contributions.append(
            FeatureContribution(
                feature_name="payment_friction",
                feature_value=float(features.failed_payment_count),
                normalized_value=norm_payment,
                weight=self.WEIGHT_PAYMENT_FRICTION,
                contribution_score=payment_contrib,
                explanation=payment_exp,
            )
        )
        if norm_payment >= 0.30:
            risk_factors.append(f"Payment friction: {features.failed_payment_count} failures")

        # Compute weighted sum
        raw_score = sum(c.contribution_score for c in contributions)

        # Evaluate anomalies
        anomaly_info = self.evaluate_anomalies(features)
        if anomaly_info.is_anomaly:
            # If critical anomaly is present, elevate risk score to reflect anomaly severity
            raw_score = max(raw_score, anomaly_info.anomaly_score)
            for flag in anomaly_info.anomaly_flags:
                risk_factors.insert(0, f"Anomaly Trigger: {flag}")

        # Final score bounding
        final_score = round(min(1.0, max(0.0, float(raw_score))), 4)

        # Map to Risk Band
        if final_score < self.LOW_RISK_THRESHOLD:
            risk_band = RiskBand.LOW
        elif final_score < self.MEDIUM_RISK_THRESHOLD:
            risk_band = RiskBand.MEDIUM
        else:
            risk_band = RiskBand.HIGH

        # Sort contributions by contribution_score descending for explainability
        contributions.sort(key=lambda c: c.contribution_score, reverse=True)

        return RiskAssessmentResult(
            model_version=self.MODEL_VERSION,
            risk_score=final_score,
            risk_band=risk_band,
            is_high_risk=(risk_band == RiskBand.HIGH or final_score >= self.MEDIUM_RISK_THRESHOLD),
            features=features,
            contributions=contributions,
            top_risk_factors=risk_factors[:4],
            anomaly=anomaly_info,
            evaluated_at=datetime.now(timezone.utc),
        )


# Global default model instance
operational_risk_model = OperationalRiskModel()
