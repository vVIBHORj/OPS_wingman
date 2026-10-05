"""
Audit and Observability API Router (Phase 4/5 - Deliverable D-16).
Provides read-only inspection of audit events, run histories, and chronological timelines.
"""

import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from backend.audit.schemas import AuditEventResponse, AuditTimelineResponse
from backend.audit.service import audit_service

router = APIRouter(prefix="/audit", tags=["Audit & Observability"])

# Safe identifier pattern: 1-128 alphanumeric characters, hyphens, and underscores
IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


def _validate_identifier(identifier: str, field_name: str = "run_id") -> None:
    """Validates that a path identifier conforms to safe alphanumeric syntax."""
    if not identifier or not IDENTIFIER_REGEX.match(identifier):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed {field_name}: '{identifier}'. Identifiers must be 1-128 characters containing only letters, numbers, hyphens, or underscores.",
        )


@router.get("/runs/{run_id}", response_model=List[AuditEventResponse], status_code=status.HTTP_200_OK)
def get_run_audit_events(
    run_id: str,
    db: Session = Depends(get_db),
) -> List[AuditEventResponse]:
    """
    Returns all audit events associated with a specific workflow run in chronological order.
    Strictly read-only.
    """
    _validate_identifier(run_id, "run_id")
    events = audit_service.get_run_events(run_id, session=db)
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit records found for run '{run_id}'.",
        )
    return events


@router.get("/events/{event_id}", response_model=AuditEventResponse, status_code=status.HTTP_200_OK)
def get_audit_event_by_id(
    event_id: str,
    db: Session = Depends(get_db),
) -> AuditEventResponse:
    """
    Returns a specific audit event by its unique event_id.
    Strictly read-only.
    """
    _validate_identifier(event_id, "event_id")
    event = audit_service.get_event(event_id, session=db)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event '{event_id}' not found.",
        )
    return event


@router.get("/runs/{run_id}/timeline", response_model=AuditTimelineResponse, status_code=status.HTTP_200_OK)
def get_run_audit_timeline(
    run_id: str,
    db: Session = Depends(get_db),
) -> AuditTimelineResponse:
    """
    Returns a structured chronological audit timeline summarizing tools, policy rules,
    ML risk scoring, verification results, and resilience interventions.
    Strictly read-only.
    """
    _validate_identifier(run_id, "run_id")
    events = audit_service.get_run_events(run_id, session=db)
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit records found for run '{run_id}'.",
        )
    return audit_service.get_timeline(run_id, session=db)
