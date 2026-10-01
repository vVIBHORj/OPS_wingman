"""Operational Risk & ML API Router for OpsWingman Phase 4 (D-13).

Exposes REST endpoints for model metadata inspection and operational risk assessment.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.ml.schemas import (
    ModelMetadata,
    RiskAssessmentRequest,
    RiskAssessmentResult,
)
from backend.ml.service import ml_risk_service
from database.session import get_db

router = APIRouter(prefix="/risk", tags=["Operational Risk & ML"])


@router.post("/assess", response_model=RiskAssessmentResult, status_code=status.HTTP_200_OK)
def assess_risk(
    request: RiskAssessmentRequest,
    db: Session = Depends(get_db),
) -> RiskAssessmentResult:
    """Assess operational risk for an order, customer, or raw feature vector."""
    if request.custom_features is not None:
        return ml_risk_service.assess_risk(request.custom_features)

    if request.order_id is not None:
        return ml_risk_service.assess_order(session=db, order_id=request.order_id)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Must provide either 'order_id' or 'custom_features' for operational risk assessment.",
    )


@router.get("/model-info", response_model=ModelMetadata, status_code=status.HTTP_200_OK)
def get_model_info() -> ModelMetadata:
    """Retrieve metadata, decision thresholds, and feature schema of the active operational risk model."""
    return ml_risk_service.get_model_metadata()
