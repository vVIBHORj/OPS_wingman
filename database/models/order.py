"""
Order and OrderItem database models.
"""

import uuid
from decimal import Decimal
from typing import List, TYPE_CHECKING, Optional
from sqlalchemy import String, Text, Numeric, Integer, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, GUID
from database.models.enums import OrderStatus

if TYPE_CHECKING:
    from database.models.customer import Customer
    from database.models.product import Product
    from database.models.payment import Payment
    from database.models.shipment import Shipment
    from database.models.ticket import Ticket


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Represents a customer's purchase transaction.
    Central operational ground truth entity.
    """
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("customers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus, native_enum=False, length=50),
        default=OrderStatus.PENDING,
        index=True,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    # Shipping Address Details
    shipping_address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    shipping_address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    shipping_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    shipping_country: Mapped[Optional[str]] = mapped_column(String(100), default="IN", nullable=True)

    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    shipments: Mapped[List["Shipment"]] = relationship(
        "Shipment",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket",
        back_populates="order",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_orders_customer_status", "customer_id", "status"),
        Index("ix_orders_created_status", "created_at", "status"),
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, order_number='{self.order_number}', status='{self.status.value}', total={self.total_amount} {self.currency})>"


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Individual line item in an Order.
    """
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("products.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, sku='{self.sku}', qty={self.quantity}, total={self.total_price})>"
