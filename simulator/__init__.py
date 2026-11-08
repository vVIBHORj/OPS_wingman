"""
OpsWingman Business Simulator Package.
Provides deterministic, verified state simulation and domain events across orders,
payments, and shipments.
"""

from simulator.events import (
    get_event,
    list_events,
    list_events_by_type,
    list_events_for_entity,
    record_event,
)
from simulator.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    SimulatorError,
)
from simulator.orders import (
    ORDER_TRANSITIONS,
    cancel_order,
    create_order,
    get_order,
    update_order_status,
)
from simulator.payments import (
    PAYMENT_TRANSITIONS,
    capture_payment,
    create_payment,
    fail_payment,
    get_payment,
    refund_payment,
)
from simulator.service import BusinessSimulator
from simulator.shipments import (
    SHIPMENT_TRANSITIONS,
    create_shipment,
    delay_shipment,
    deliver_shipment,
    get_shipment,
    update_shipment_status,
)

__all__ = [
    "SimulatorError",
    "EntityNotFoundError",
    "InvalidStateTransitionError",
    "BusinessRuleViolationError",
    "create_order",
    "get_order",
    "update_order_status",
    "cancel_order",
    "ORDER_TRANSITIONS",
    "create_payment",
    "get_payment",
    "capture_payment",
    "fail_payment",
    "refund_payment",
    "PAYMENT_TRANSITIONS",
    "create_shipment",
    "get_shipment",
    "update_shipment_status",
    "delay_shipment",
    "deliver_shipment",
    "SHIPMENT_TRANSITIONS",
    "record_event",
    "get_event",
    "list_events",
    "list_events_for_entity",
    "list_events_by_type",
    "BusinessSimulator",
]
