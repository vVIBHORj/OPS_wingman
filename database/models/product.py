"""
Product database model.
"""

from decimal import Decimal
from typing import List, TYPE_CHECKING, Optional
from sqlalchemy import String, Text, Numeric, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from database.models.order import OrderItem


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Represents an item in the merchant's catalog.
    Ground truth entity for pricing, SKU, and inventory tracking.
    """
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    inventory_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_products_active_category", "is_active", "category"),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}', price={self.unit_price} {self.currency})>"
