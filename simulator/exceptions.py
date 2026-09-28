"""
Exceptions for the OpsWingman Business Simulator.
"""


from typing import Optional


class SimulatorError(Exception):
    """Base exception for all business simulator errors."""
    pass


class EntityNotFoundError(SimulatorError):
    """Raised when an entity (Order, Customer, Product, Payment, Shipment) is not found."""
    pass


class InvalidStateTransitionError(SimulatorError):
    """Raised when an illegal or unsupported domain state transition is attempted."""
    def __init__(self, entity_type: str, entity_id: str, current_status: str, target_status: str, message: Optional[str] = None):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.current_status = current_status
        self.target_status = target_status
        msg = message or f"Cannot transition {entity_type} {entity_id} from {current_status} to {target_status}."
        super().__init__(msg)



class BusinessRuleViolationError(SimulatorError):
    """Raised when a business constraint or rule is violated."""
    pass
