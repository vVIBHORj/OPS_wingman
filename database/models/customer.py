"""
Customer database model.
"""

from typing import List, TYPE_CHECKING, Optional
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from database.models.order import Order
    from database.models.ticket import Ticket


class Customer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Represents an individual or business buyer.
    Ground truth entity for customer identification and contact history.
    """
    __tablename__ = "customers"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), index=True, nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Relationships
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_customers_name", "first_name", "last_name"),
    )

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, email='{self.email}', name='{self.first_name} {self.last_name}')>"
