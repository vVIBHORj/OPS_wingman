"""
Unified Business Simulator Service & Scenario Engine.
Provides a clean interface over orders, payments, shipments, and domain events.
"""

import uuid
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from database.models import (
    Customer,
    Product,
    Order,
    Payment,
    Shipment,
    DomainEvent,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    ShipmentStatus,
    EventType,
)
from database.session import SessionLocal
from simulator.orders import create_order, get_order, update_order_status, cancel_order
from simulator.payments import create_payment, get_payment, capture_payment, fail_payment
from simulator.shipments import (
    create_shipment,
    get_shipment,
    update_shipment_status,
    delay_shipment,
    deliver_shipment,
)
from simulator.events import (
    record_event,
    get_event,
    list_events,
    list_events_for_entity,
    list_events_by_type,
)


class BusinessSimulator:
    """
    Deterministic Business Simulator Service.
    Wraps domain actions and scenario execution against a database session.
    """

    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._owns_session = False

    @property
    def session(self) -> Session:
        if self._session is None:
            self._session = SessionLocal()
            self._owns_session = True
        return self._session

    def close(self):
        if self._owns_session and self._session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # --- Order Operations ---
    def create_order(
        self,
        customer_id: uuid.UUID,
        items: List[Dict[str, Any]],
        order_number: Optional[str] = None,
        shipping_address: Optional[Dict[str, str]] = None,
        tax_rate: Decimal = Decimal("0.18"),
        shipping_amount: Decimal = Decimal("0.00"),
        discount_amount: Decimal = Decimal("0.00"),
        order_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> Order:
        return create_order(
            session=self.session,
            customer_id=customer_id,
            items=items,
            order_number=order_number,
            shipping_address=shipping_address,
            tax_rate=tax_rate,
            shipping_amount=shipping_amount,
            discount_amount=discount_amount,
            order_id=order_id,
            correlation_id=correlation_id,
        )

    def get_order(
        self,
        order_id: Optional[uuid.UUID] = None,
        order_number: Optional[str] = None,
    ) -> Order:
        return get_order(self.session, order_id=order_id, order_number=order_number)

    def update_order_status(
        self,
        order_id: uuid.UUID,
        new_status: OrderStatus,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Order:
        return update_order_status(
            self.session,
            order_id=order_id,
            new_status=new_status,
            reason=reason,
            correlation_id=correlation_id,
        )

    def cancel_order(
        self,
        order_id: uuid.UUID,
        reason: str,
        correlation_id: Optional[str] = None,
    ) -> Order:
        return cancel_order(
            self.session,
            order_id=order_id,
            reason=reason,
            correlation_id=correlation_id,
        )

    # --- Payment Operations ---
    def create_payment(
        self,
        order_id: uuid.UUID,
        amount: Optional[Decimal] = None,
        payment_method: PaymentMethod = PaymentMethod.UPI,
        payment_reference: Optional[str] = None,
        payment_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> Payment:
        return create_payment(
            session=self.session,
            order_id=order_id,
            amount=amount,
            payment_method=payment_method,
            payment_reference=payment_reference,
            payment_id=payment_id,
            correlation_id=correlation_id,
        )

    def get_payment(
        self,
        payment_id: Optional[uuid.UUID] = None,
        payment_reference: Optional[str] = None,
    ) -> Payment:
        return get_payment(self.session, payment_id=payment_id, payment_reference=payment_reference)

    def capture_payment(
        self,
        payment_id: uuid.UUID,
        gateway_transaction_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Payment:
        return capture_payment(
            session=self.session,
            payment_id=payment_id,
            gateway_transaction_id=gateway_transaction_id,
            correlation_id=correlation_id,
        )

    def fail_payment(
        self,
        payment_id: uuid.UUID,
        error_code: str,
        error_message: str,
        correlation_id: Optional[str] = None,
    ) -> Payment:
        return fail_payment(
            session=self.session,
            payment_id=payment_id,
            error_code=error_code,
            error_message=error_message,
            correlation_id=correlation_id,
        )

    # --- Shipment Operations ---
    def create_shipment(
        self,
        order_id: uuid.UUID,
        carrier: str = "Delhivery",
        tracking_number: Optional[str] = None,
        estimated_days: int = 3,
        status: ShipmentStatus = ShipmentStatus.MANIFESTED,
        shipment_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> Shipment:
        return create_shipment(
            session=self.session,
            order_id=order_id,
            carrier=carrier,
            tracking_number=tracking_number,
            estimated_days=estimated_days,
            status=status,
            shipment_id=shipment_id,
            correlation_id=correlation_id,
        )

    def get_shipment(
        self,
        shipment_id: Optional[uuid.UUID] = None,
        tracking_number: Optional[str] = None,
    ) -> Shipment:
        return get_shipment(self.session, shipment_id=shipment_id, tracking_number=tracking_number)

    def update_shipment_status(
        self,
        shipment_id: uuid.UUID,
        new_status: ShipmentStatus,
        location: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Shipment:
        return update_shipment_status(
            self.session,
            shipment_id=shipment_id,
            new_status=new_status,
            location=location,
            correlation_id=correlation_id,
        )

    def delay_shipment(
        self,
        shipment_id: uuid.UUID,
        delay_reason: str,
        updated_eta: Optional[datetime] = None,
        current_location: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Shipment:
        return delay_shipment(
            session=self.session,
            shipment_id=shipment_id,
            delay_reason=delay_reason,
            updated_eta=updated_eta,
            current_location=current_location,
            correlation_id=correlation_id,
        )

    def deliver_shipment(
        self,
        shipment_id: uuid.UUID,
        actual_delivery_date: Optional[datetime] = None,
        recipient_notes: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Shipment:
        return deliver_shipment(
            session=self.session,
            shipment_id=shipment_id,
            actual_delivery_date=actual_delivery_date,
            recipient_notes=recipient_notes,
            correlation_id=correlation_id,
        )

    # --- Domain Event Operations ---
    def get_event(self, event_id: uuid.UUID) -> DomainEvent:
        return get_event(self.session, event_id=event_id)

    def list_events(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        event_type: Optional[Union[EventType, str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DomainEvent]:
        return list_events(
            self.session,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )

    def list_events_for_entity(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        limit: int = 100,
    ) -> List[DomainEvent]:
        return list_events_for_entity(self.session, entity_type=entity_type, entity_id=entity_id, limit=limit)

    def list_events_by_type(
        self,
        event_type: Union[EventType, str],
        limit: int = 100,
    ) -> List[DomainEvent]:
        return list_events_by_type(self.session, event_type=event_type, limit=limit)

    # --- Scenario Runners ---
    def run_normal_order_flow(
        self,
        customer_id: uuid.UUID,
        items: List[Dict[str, Any]],
        carrier: str = "Delhivery",
    ) -> Tuple[Order, Payment, Shipment]:
        """
        Executes a canonical full lifecycle order flow:
        Create Order -> Create & Capture Payment -> Create & Deliver Shipment.
        """
        order = self.create_order(customer_id=customer_id, items=items)
        payment = self.create_payment(order_id=order.id, payment_method=PaymentMethod.UPI)
        payment = self.capture_payment(payment_id=payment.id)
        shipment = self.create_shipment(order_id=order.id, carrier=carrier, status=ShipmentStatus.IN_TRANSIT)
        shipment = self.deliver_shipment(shipment_id=shipment.id, recipient_notes="Signed by customer")
        return order, payment, shipment

    def run_delayed_order_flow(
        self,
        customer_id: uuid.UUID,
        items: List[Dict[str, Any]],
        carrier: str = "BlueDart",
        delay_reason: str = "Weather disruption at regional transit hub",
    ) -> Tuple[Order, Payment, Shipment]:
        """
        Executes a delayed order scenario:
        Create Order -> Capture Payment -> Create Shipment -> Mark Delayed.
        """
        order = self.create_order(customer_id=customer_id, items=items)
        payment = self.create_payment(order_id=order.id, payment_method=PaymentMethod.CARD)
        payment = self.capture_payment(payment_id=payment.id)
        shipment = self.create_shipment(order_id=order.id, carrier=carrier, status=ShipmentStatus.IN_TRANSIT)
        new_eta = datetime.now(timezone.utc) + timedelta(days=4)
        shipment = self.delay_shipment(
            shipment_id=shipment.id,
            delay_reason=delay_reason,
            updated_eta=new_eta,
            current_location=f"{carrier} Transit Hub - Delayed",
        )
        return order, payment, shipment
