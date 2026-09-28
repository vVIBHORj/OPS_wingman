"""
Domain status and type enums for OpsWingman business models.
"""

from enum import Enum


class OrderStatus(str, Enum):
    """Lifecycle statuses for an Order."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


class PaymentStatus(str, Enum):
    """Lifecycle statuses for a Payment."""
    INITIATED = "INITIATED"
    AUTHORIZED = "AUTHORIZED"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, Enum):
    """Supported payment methods for transactions."""
    UPI = "UPI"
    CARD = "CARD"
    NETBANKING = "NETBANKING"
    COD = "COD"
    WALLET = "WALLET"


class ShipmentStatus(str, Enum):
    """Lifecycle statuses for a Shipment."""
    MANIFESTED = "MANIFESTED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    DELAYED = "DELAYED"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"
    RETURNED = "RETURNED"


class TicketStatus(str, Enum):
    """Lifecycle statuses for a Customer Support Ticket."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_CUSTOMER = "WAITING_ON_CUSTOMER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, Enum):
    """Priority levels for support tickets."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketChannel(str, Enum):
    """Originating channel for support tickets."""
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    PORTAL = "PORTAL"
    PHONE = "PHONE"
