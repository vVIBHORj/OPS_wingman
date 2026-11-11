"""
Customer API Router.
"""

import uuid
from decimal import Decimal
from typing import Optional

from database.models import Customer, Order, OrderStatus
from database.session import get_db
from fastapi import APIRouter, Depends, Query
from simulator.exceptions import EntityNotFoundError
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.api.schemas import (
    CustomerDetailResponse,
    CustomerListItemResponse,
    CustomerListResponse,
    OrderResponse,
    TicketResponse,
)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=CustomerListResponse)
def list_customers(
    search: Optional[str] = Query(default=None, description="Search name, email, phone, company"),
    city: Optional[str] = Query(default=None, description="Filter by city"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> CustomerListResponse:
    """List customers with search, city filter, lifetime spending, and order counts."""
    query = select(Customer)
    count_query = select(func.count(Customer.id))

    if city:
        query = query.where(Customer.city.ilike(city))
        count_query = count_query.where(Customer.city.ilike(city))

    if search:
        search_filter = or_(
            Customer.email.ilike(f"%{search}%"),
            Customer.first_name.ilike(f"%{search}%"),
            Customer.last_name.ilike(f"%{search}%"),
            Customer.phone.ilike(f"%{search}%"),
            Customer.company_name.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.scalar(count_query) or 0
    customers = db.scalars(
        query.order_by(desc(Customer.created_at)).offset(offset).limit(limit)
    ).all()

    # Aggregate spend and order count in a single query to avoid N+1
    customer_ids = [c.id for c in customers]
    spend_map = {}
    order_count_map = {}
    if customer_ids:
        aggregates = db.execute(
            select(
                Order.customer_id,
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_spend"),
            )
            .where(Order.customer_id.in_(customer_ids))
            .where(Order.status != OrderStatus.CANCELLED)
            .group_by(Order.customer_id)
        ).all()
        for row in aggregates:
            order_count_map[row.customer_id] = row.order_count
            spend_map[row.customer_id] = Decimal(str(row.total_spend))

    items = []
    for c in customers:
        item = CustomerListItemResponse.model_validate(c)
        item.order_count = order_count_map.get(c.id, 0)
        item.total_spend = spend_map.get(c.id, Decimal("0.00"))
        items.append(item)

    return CustomerListResponse(
        total=total,
        items=items,
        limit=limit,
        offset=offset,
    )


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
def get_customer_by_id(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CustomerDetailResponse:
    """Retrieve customer details by ID including recent orders, tickets, and lifetime spend."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise EntityNotFoundError(f"Customer {customer_id} not found.")

    # Calculate metrics
    agg = db.execute(
        select(
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_spend"),
        )
        .where(Order.customer_id == customer_id)
        .where(Order.status != OrderStatus.CANCELLED)
    ).first()

    order_count = agg.order_count if agg else 0
    total_spend = Decimal(str(agg.total_spend)) if agg else Decimal("0.00")

    # Recent orders
    recent_orders = db.scalars(
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(desc(Order.created_at))
        .limit(10)
    ).all()

    # Recent tickets
    recent_tickets = customer.tickets[:10] if customer.tickets else []

    detail = CustomerDetailResponse.model_validate(customer)
    detail.order_count = order_count
    detail.total_spend = total_spend
    detail.recent_orders = [OrderResponse.model_validate(o) for o in recent_orders]
    detail.recent_tickets = [TicketResponse.model_validate(t) for t in recent_tickets]

    return detail
