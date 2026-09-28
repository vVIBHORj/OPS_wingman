"""
Product API Router.
"""

import uuid
from typing import Optional, List, Union
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import Product
from backend.api.schemas import ProductResponse
from simulator.exceptions import EntityNotFoundError

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=Union[ProductResponse, List[ProductResponse]])
def get_products(
    sku: Optional[str] = Query(default=None, description="Search product by exact SKU"),
    db: Session = Depends(get_db),
) -> Union[ProductResponse, List[ProductResponse]]:
    """Retrieve products or search by SKU."""
    if sku:
        product = db.scalar(select(Product).where(Product.sku == sku))
        if not product:
            raise EntityNotFoundError(f"Product with SKU '{sku}' not found.")
        return ProductResponse.model_validate(product)

    products = list(db.scalars(select(Product)).all())
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product_by_id(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductResponse:
    """Retrieve product details by ID."""
    product = db.get(Product, product_id)
    if not product:
        raise EntityNotFoundError(f"Product {product_id} not found.")
    return ProductResponse.model_validate(product)

