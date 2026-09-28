"""
Customer API Router.
"""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import Customer
from backend.api.schemas import CustomerResponse
from simulator.exceptions import EntityNotFoundError

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

