"""
Customer API Router.
"""

import uuid

from database.models import Customer
from database.session import get_db
from fastapi import APIRouter, Depends
from simulator.exceptions import EntityNotFoundError
from sqlalchemy.orm import Session

from backend.api.schemas import CustomerResponse

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer_by_id(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CustomerResponse:
    """Retrieve customer details by ID."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise EntityNotFoundError(f"Customer {customer_id} not found.")
    return CustomerResponse.model_validate(customer)
