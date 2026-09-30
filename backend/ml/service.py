"""High-level ML Risk Service for OpsWingman (Phase 4 - Deliverable D-13).

Provides a single unified interface for feature extraction, risk scoring,
anomaly detection, and model metadata inspection.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from backend.ml.features import FeatureExtractor
from backend.ml.model import OperationalRiskModel, operational_risk_model
from backend.ml.schemas import (
    ModelMetadata,
    RiskAssessmentResult,
    RiskFeatureVector,
)


class MLRiskService:
    """Service layer coordinating feature extraction, model scoring, and operational risk assessment."""

    def __init__(self, model: Optional[OperationalRiskModel] = None) -> None:
        self.model = model or operational_risk_model

    def get_model_metadata(self) -> ModelMetadata:
        """Returns metadata, version, and thresholds of the underlying risk model."""
        return self.model.get_metadata()

    def assess_risk(self, features: RiskFeatureVector) -> RiskAssessmentResult:
        """Calculates risk score and explains contributions directly from a feature vector."""
        return self.model.score(features)

    def assess_order(
        self,
        session: Session,
        order_id: str,
        now: Optional[datetime] = None,
    ) -> RiskAssessmentResult:
        """Extracts features from database entities and computes full operational risk assessment."""
        features = FeatureExtractor.extract_from_db(session=session, order_id=order_id, now=now)
        return self.model.score(features)


# Global default service instance
ml_risk_service = MLRiskService()
