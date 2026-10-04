"""Feature extraction for operational risk scoring (Phase 4 - Deliverable D-13)."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Customer, Order, OrderStatus, Payment, PaymentStatus, Shipment, ShipmentStatus
from backend.ml.schemas import RiskFeatureVector


class FeatureExtractor:
    """Extracts normalized risk feature vectors from business entities and database state."""

    @staticmethod
    def extract_from_entities(
        order: Optional[Order] = None,
        customer: Optional[Customer] = None,
        now: Optional[datetime] = None,
        total_customer_orders: int = 1,
        customer_refund_count: int = 0,
    ) -> RiskFeatureVector:
        """Extracts RiskFeatureVector directly from entity instances without requiring active DB session."""
        current_time = now or datetime.now(timezone.utc)

        # 1. Order Amount
        order_amount = float(order.total_amount) if order is not None else 0.0

        # 2. Account Age
        account_age_days = 0.0
        if customer is not None and customer.created_at is not None:
            # Normalize to UTC for timezone safe subtraction
            created_at = customer.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            delta = (current_time - created_at).total_seconds() / 86400.0
            account_age_days = max(0.0, float(delta))

        # 3. Refund Metrics
        refund_ratio = 0.0
        if total_customer_orders > 0:
            refund_ratio = min(1.0, max(0.0, float(customer_refund_count) / float(total_customer_orders)))

        # 4. Delivery Delay Hours
        delivery_delay_hours = 0.0
        if order is not None and order.shipments:
            for shp in order.shipments:
                if shp.status == ShipmentStatus.DELAYED:
                    # Estimate delay duration based on created_at or estimated_delivery_date
                    ref_time = shp.estimated_delivery_date or shp.created_at
                    if ref_time is not None:
                        if ref_time.tzinfo is None:
                            ref_time = ref_time.replace(tzinfo=timezone.utc)
                        delay_seconds = (current_time - ref_time).total_seconds()
                        delivery_delay_hours = max(delivery_delay_hours, max(0.0, delay_seconds / 3600.0))
                elif shp.status == ShipmentStatus.IN_TRANSIT and shp.estimated_delivery_date is not None:
                    est_time = shp.estimated_delivery_date
                    if est_time.tzinfo is None:
                        est_time = est_time.replace(tzinfo=timezone.utc)
                    if current_time > est_time:
                        delay_seconds = (current_time - est_time).total_seconds()
                        delivery_delay_hours = max(delivery_delay_hours, max(0.0, delay_seconds / 3600.0))

        # 5. Payment Attempts & Failures
        payment_attempts = 1
        failed_payment_count = 0
        if order is not None and order.payments:
            payment_attempts = max(1, len(order.payments))
            failed_payment_count = sum(1 for p in order.payments if p.status == PaymentStatus.FAILED)

        # 6. First Order Flag
        is_first_order = total_customer_orders <= 1

        return RiskFeatureVector(
            order_amount=max(0.0, order_amount),
            account_age_days=account_age_days,
            refund_count=max(0, customer_refund_count),
            refund_ratio=refund_ratio,
            delivery_delay_hours=delivery_delay_hours,
            payment_attempts=payment_attempts,
            failed_payment_count=failed_payment_count,
            is_first_order=is_first_order,
        )

    @classmethod
    def extract_from_db(
        cls,
        session: Session,
        order_id: str,
        now: Optional[datetime] = None,
    ) -> RiskFeatureVector:
        """Extracts RiskFeatureVector by querying database entities for the given order_id."""
        order = None
        try:
            val_uuid = uuid.UUID(str(order_id))
            order = session.get(Order, val_uuid)
        except (ValueError, TypeError):
            pass

        if order is None:
            order = session.scalar(
                select(Order).where(Order.order_number == str(order_id))
            )
        if order is None:
            # Return neutral baseline vector if order not found
            return RiskFeatureVector()

        customer = session.get(Customer, order.customer_id) if order.customer_id else None

        # Compute customer history
        total_orders = 1
        refund_count = 0
        if customer is not None:
            customer_orders = session.scalars(
                select(Order).where(Order.customer_id == customer.id)
            ).all()
            total_orders = max(1, len(customer_orders))
            refund_count = sum(
                1 for o in customer_orders if o.status == OrderStatus.CANCELLED
            )

        return cls.extract_from_entities(
            order=order,
            customer=customer,
            now=now,
            total_customer_orders=total_orders,
            customer_refund_count=refund_count,
        )
