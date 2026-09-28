"""
OpsWingman Business Simulator Package.
Provides deterministic, verified state simulation and domain events across orders, payments, and shipments.
"""

from simulator.exceptions import (
    SimulatorError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    BusinessRuleViolationError,
)
from simulator.orders import (
    create_order,
    get_order,
    update_order_status,
    cancel_order,
    ORDER_TRANSITIONS,
)
from simulator.payments import (
    create_payment,
    get_payment,
    capture_payment,
    fail_payment,
    PAYMENT_TRANSITIONS,
)
from simulator.shipments import (
    create_shipment,
    get_shipment,
    update_shipment_status,
    delay_shipment,
    deliver_shipment,
    SHIPMENT_TRANSITIONS,
)
from simulator.events import (
    record_event,
    get_event,
    list_events,
    list_events_for_entity,
    list_events_by_type,
)
from simulator.service import BusinessSimulator

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
