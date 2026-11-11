"""
Support Ticket API Router.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from database.models import Customer, Ticket, TicketChannel, TicketPriority, TicketStatus
from database.session import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from simulator.exceptions import EntityNotFoundError
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.api.schemas import (
    TicketCreateRequest,
    TicketListResponse,
    TicketResponse,
    TicketStatusUpdateRequest,
)

router = APIRouter(prefix="/tickets", tags=["Support Tickets"])


@router.get("", response_model=TicketListResponse)
def list_tickets(
    status: Optional[TicketStatus] = Query(default=None, description="Filter by ticket status"),
    priority: Optional[TicketPriority] = Query(default=None, description="Filter by priority"),
    channel: Optional[TicketChannel] = Query(default=None, description="Filter by channel"),
    customer_id: Optional[uuid.UUID] = Query(default=None, description="Filter by customer ID"),
    order_id: Optional[uuid.UUID] = Query(default=None, description="Filter by order ID"),
    search: Optional[str] = Query(default=None, description="Search title, description or number"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> TicketListResponse:
    """List customer support tickets with filters, search, and pagination."""
    query = select(Ticket)
    count_query = select(func.count(Ticket.id))

    if status:
        query = query.where(Ticket.status == status)
        count_query = count_query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)
        count_query = count_query.where(Ticket.priority == priority)
    if channel:
        query = query.where(Ticket.channel == channel)
        count_query = count_query.where(Ticket.channel == channel)
    if customer_id:
        query = query.where(Ticket.customer_id == customer_id)
        count_query = count_query.where(Ticket.customer_id == customer_id)
    if order_id:
        query = query.where(Ticket.order_id == order_id)
        count_query = count_query.where(Ticket.order_id == order_id)

    if search:
        search_filter = or_(
            Ticket.ticket_number.ilike(f"%{search}%"),
            Ticket.title.ilike(f"%{search}%"),
            Ticket.description.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.scalar(count_query) or 0
    tickets = db.scalars(
        query.order_by(desc(Ticket.created_at)).offset(offset).limit(limit)
    ).all()

    return TicketListResponse(
        total=total,
        items=[TicketResponse.model_validate(t) for t in tickets],
        limit=limit,
        offset=offset,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket_by_id(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> TicketResponse:
    """Retrieve ticket details by UUID."""
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise EntityNotFoundError(f"Ticket {ticket_id} not found.")
    return TicketResponse.model_validate(ticket)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreateRequest,
    db: Session = Depends(get_db),
) -> TicketResponse:
    """Create a new support ticket."""
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {payload.customer_id} not found.",
        )

    now = datetime.now(timezone.utc)
    ticket_number = f"TCK-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number=ticket_number,
        customer_id=payload.customer_id,
        order_id=payload.order_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        channel=payload.channel,
        category=payload.category,
        status=TicketStatus.OPEN,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return TicketResponse.model_validate(ticket)


@router.post("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: uuid.UUID,
    payload: TicketStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> TicketResponse:
    """Update ticket resolution status."""
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise EntityNotFoundError(f"Ticket {ticket_id} not found.")

    ticket.status = payload.status
    if payload.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        ticket.resolved_at = datetime.now(timezone.utc)
    if payload.resolution_notes:
        ticket.description += f"\n\n[Resolution Note]: {payload.resolution_notes}"

    db.commit()
    db.refresh(ticket)
    return TicketResponse.model_validate(ticket)

