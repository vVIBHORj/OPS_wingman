"""
Database models export package for OpsWingman.
"""

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.approval import ApprovalRecord
from database.models.audit import AuditEventRecord
from database.models.customer import Customer
from database.models.enums import (
    ApprovalStatus,
    AuditEventType,
    DocumentStatus,
    DocumentType,
    IdempotencyStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ShipmentStatus,
    TicketChannel,
    TicketPriority,
    TicketStatus,
)
from database.models.event import DomainEvent, EventType
from database.models.idempotency import IdempotencyRecord
from database.models.knowledge import KnowledgeChunk, KnowledgeDocument
from database.models.order import Order, OrderItem
from database.models.payment import Payment
from database.models.product import Product
from database.models.shipment import Shipment
from database.models.ticket import Ticket

__all__ = [
    "Base",
    "GUID",
    "UUIDPrimaryKeyMixin",
    "TimestampMixin",
    "OrderStatus",
    "PaymentStatus",
    "PaymentMethod",
    "ShipmentStatus",
    "TicketStatus",
    "TicketPriority",
    "TicketChannel",
    "DocumentType",
    "DocumentStatus",
    "ApprovalStatus",
    "IdempotencyStatus",
    "AuditEventType",
    "EventType",
    "DomainEvent",
    "Customer",
    "Product",
    "Order",
    "OrderItem",
    "Payment",
    "Shipment",
    "Ticket",
    "KnowledgeDocument",
    "KnowledgeChunk",
    "ApprovalRecord",
    "IdempotencyRecord",
    "AuditEventRecord",
]
