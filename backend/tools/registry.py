"""
Tool implementations and standard registry builder for OpsWingman.
Connects tools with the deterministic simulator and database layer.
"""

import uuid
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Customer, Order, Payment, Shipment, Ticket
from backend.tools.base import ToolRegistry, ToolDefinition, ToolType, RiskLevel
from backend.tools.schemas import (
    GetCustomerInput,
    GetOrderInput,
    GetPaymentInput,
    GetShipmentInput,
    GetPolicyInput,
    CreateTicketInput,
    SendCustomerMessageInput,
    CancelOrderInput,
    RequestRefundInput,
    RequestHumanApprovalInput,
    UpdateWorkflowStateInput,
)

import simulator


# ==============================================================================
# Deterministic Tool Handlers
# ==============================================================================

def handle_get_customer(inputs: GetCustomerInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db: Optional[Session] = context.get("db") if context else None
    if not db:
        raise ValueError("Database session required in tool context.")

    if inputs.customer_id:
        customer = db.get(Customer, inputs.customer_id)
    elif inputs.email:
        customer = db.scalar(select(Customer).where(Customer.email == inputs.email))
    else:
        raise ValueError("Must provide either customer_id or email.")

    if not customer:
        raise ValueError(f"Customer not found for query: id={inputs.customer_id}, email={inputs.email}")

    return {
        "id": str(customer.id),
        "email": customer.email,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "city": customer.city,
        "state": customer.state,
        "pincode": customer.pincode,
        "phone": customer.phone,
    }


def handle_get_order(inputs: GetOrderInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db: Optional[Session] = context.get("db") if context else None
    if not db:
        raise ValueError("Database session required in tool context.")

    order = simulator.get_order(session=db, order_id=inputs.order_id, order_number=inputs.order_number)
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "customer_id": str(order.customer_id),
        "status": order.status.value,
        "subtotal_amount": str(order.subtotal_amount),
        "tax_amount": str(order.tax_amount),
        "shipping_amount": str(order.shipping_amount),
        "total_amount": str(order.total_amount),
        "currency": order.currency,
        "cancellation_reason": order.cancellation_reason,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "id": str(item.id),
                "product_id": str(item.product_id),
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "total_price": str(item.total_price),
            }
            for item in order.items
        ],
    }


def handle_get_payment(inputs: GetPaymentInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db: Optional[Session] = context.get("db") if context else None
    if not db:
        raise ValueError("Database session required in tool context.")

    if inputs.order_id:
        payment = db.scalar(select(Payment).where(Payment.order_id == inputs.order_id))
        if not payment:
            raise ValueError(f"Payment for order {inputs.order_id} not found.")
    else:
        payment = simulator.get_payment(session=db, payment_id=inputs.payment_id, payment_reference=inputs.payment_reference)

    return {
        "id": str(payment.id),
        "payment_reference": payment.payment_reference,
        "order_id": str(payment.order_id),
        "amount": str(payment.amount),
        "currency": payment.currency,
        "payment_method": payment.payment_method.value,
        "status": payment.status.value,
        "gateway_transaction_id": payment.gateway_transaction_id,
        "error_code": payment.error_code,
        "error_message": payment.error_message,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
    }


def handle_get_shipment(inputs: GetShipmentInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db: Optional[Session] = context.get("db") if context else None
    if not db:
        raise ValueError("Database session required in tool context.")

    if inputs.order_id:
        shipment = db.scalar(select(Shipment).where(Shipment.order_id == inputs.order_id))
        if not shipment:
            raise ValueError(f"Shipment for order {inputs.order_id} not found.")
    else:
        shipment = simulator.get_shipment(session=db, shipment_id=inputs.shipment_id, tracking_number=inputs.tracking_number)

    return {
        "id": str(shipment.id),
        "shipment_number": shipment.shipment_number,
        "order_id": str(shipment.order_id),
        "carrier": shipment.carrier,
        "tracking_number": shipment.tracking_number,
        "status": shipment.status.value,
        "estimated_delivery_date": shipment.estimated_delivery_date.isoformat() if shipment.estimated_delivery_date else None,
        "actual_delivery_date": shipment.actual_delivery_date.isoformat() if shipment.actual_delivery_date else None,
        "current_location": shipment.current_location,
        "delay_reason": shipment.delay_reason,
    }


def handle_get_policy(inputs: GetPolicyInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    policies = {
        "cancellation_window": {
            "policy_name": "cancellation_window",
            "rule": "Orders can only be cancelled while in PENDING or CONFIRMED state. Once SHIPPED or IN_TRANSIT, cancellation is disallowed and a return must be initiated after delivery.",
            "auto_approval_allowed": False,
            "risk_level": "HIGH",
        },
        "shipping_sla": {
            "policy_name": "shipping_sla",
            "rule": "Standard delivery timeframe is 3-5 business days from order confirmation. Delay notifications are automatically dispatched if transit exceeds 48 hours without hub movement.",
            "auto_approval_allowed": True,
            "risk_level": "LOW",
        },
        "refund_eligibility": {
            "policy_name": "refund_eligibility",
            "rule": "Refunds are processed to the original payment method within 5-7 business days upon confirmed cancellation or return receipt. High-value refunds (> INR 5000) strictly require supervisor approval.",
            "auto_approval_allowed": False,
            "risk_level": "HIGH",
        },
    }

    key = inputs.policy_name.strip().lower()
    if key in policies:
        return policies[key]

    return {
        "policy_name": inputs.policy_name,
        "rule": f"Standard operational policy for '{inputs.policy_name}': check operational guidelines or escalate to supervisor.",
        "auto_approval_allowed": False,
        "risk_level": "MEDIUM",
    }


def handle_create_ticket(inputs: CreateTicketInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db: Optional[Session] = context.get("db") if context else None
    if not db:
        raise ValueError("Database session required in tool context.")

    ticket_number = f"TCK-{datetime_stamp()}-{uuid.uuid4().hex[:6].upper()}"
    ticket = Ticket(
        id=uuid.uuid4(),
        ticket_number=ticket_number,
        customer_id=inputs.customer_id,
        order_id=inputs.order_id,
        title=inputs.subject,
        description=inputs.description,
        priority=inputs.priority,
        channel=inputs.channel,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "customer_id": str(ticket.customer_id),
        "order_id": str(ticket.order_id) if ticket.order_id else None,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "channel": ticket.channel.value,
        "subject": ticket.title,
    }


def handle_send_customer_message(inputs: SendCustomerMessageInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Deterministic mock communication dispatcher
    dispatch_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"
    return {
        "dispatch_id": dispatch_id,
        "recipient": inputs.recipient,
        "channel": inputs.channel,
        "subject": inputs.subject,
        "order_number": inputs.order_number,
        "delivered": True,
        "status": "SENT",
    }


def handle_cancel_order(inputs: CancelOrderInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db: Optional[Session] = context.get("db") if context else None
    if not db:
        raise ValueError("Database session required in tool context.")

    order = simulator.cancel_order(session=db, order_id=inputs.order_id, reason=inputs.reason)
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "status": order.status.value,
        "cancellation_reason": order.cancellation_reason,
    }


def handle_request_refund(inputs: RequestRefundInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db: Optional[Session] = context.get("db") if context else None
    if not db:
        raise ValueError("Database session required in tool context.")

    order = db.get(Order, inputs.order_id)
    if not order:
        raise ValueError(f"Order {inputs.order_id} not found.")

    refund_ref = f"REF-{datetime_stamp()}-{uuid.uuid4().hex[:6].upper()}"
    amount = str(inputs.amount if inputs.amount is not None else order.total_amount)

    return {
        "refund_reference": refund_ref,
        "order_id": str(order.id),
        "order_number": order.order_number,
        "amount": amount,
        "currency": order.currency,
        "reason": inputs.reason,
        "status": "REFUND_REQUESTED",
    }


def handle_request_human_approval(inputs: RequestHumanApprovalInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    approval_id = f"APV-{datetime_stamp()}-{uuid.uuid4().hex[:6].upper()}"
    return {
        "approval_id": approval_id,
        "workflow_id": inputs.workflow_id,
        "action": inputs.action,
        "reason": inputs.reason,
        "risk_level": inputs.risk_level,
        "status": "WAITING_FOR_APPROVAL",
        "payload": inputs.payload or {},
    }


def handle_update_workflow_state(inputs: UpdateWorkflowStateInput, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "workflow_id": inputs.workflow_id,
        "state": inputs.state,
        "updated": True,
        "metadata": inputs.metadata or {},
    }


def datetime_stamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# ==============================================================================
# Registry Builder
# ==============================================================================

def create_default_tool_registry() -> ToolRegistry:
    """Builds and returns the canonical Tool Registry loaded with Phase 2 tools."""
    registry = ToolRegistry()

    registry.register(ToolDefinition(
        name="get_customer",
        description="Retrieve customer profile, contact details and location by customer_id or email.",
        tool_type=ToolType.READ,
        risk_level=RiskLevel.LOW,
        input_schema=GetCustomerInput,
        handler=handle_get_customer,
    ))

    registry.register(ToolDefinition(
        name="get_order",
        description="Retrieve order details, line items, amounts, and lifecycle status by order_id or order_number.",
        tool_type=ToolType.READ,
        risk_level=RiskLevel.LOW,
        input_schema=GetOrderInput,
        handler=handle_get_order,
    ))

    registry.register(ToolDefinition(
        name="get_payment",
        description="Retrieve transaction details, payment status, amounts, and references by payment_id, reference or order_id.",
        tool_type=ToolType.READ,
        risk_level=RiskLevel.LOW,
        input_schema=GetPaymentInput,
        handler=handle_get_payment,
    ))

    registry.register(ToolDefinition(
        name="get_shipment",
        description="Retrieve courier tracking details, location, and shipment status by shipment_id, tracking_number or order_id.",
        tool_type=ToolType.READ,
        risk_level=RiskLevel.LOW,
        input_schema=GetShipmentInput,
        handler=handle_get_shipment,
    ))

    registry.register(ToolDefinition(
        name="get_policy",
        description="Retrieve business policy rules (e.g. cancellation_window, shipping_sla, refund_eligibility).",
        tool_type=ToolType.READ,
        risk_level=RiskLevel.LOW,
        input_schema=GetPolicyInput,
        handler=handle_get_policy,
    ))

    registry.register(ToolDefinition(
        name="create_ticket",
        description="Create an internal operational support ticket for exceptions or customer requests.",
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
        input_schema=CreateTicketInput,
        handler=handle_create_ticket,
    ))

    registry.register(ToolDefinition(
        name="send_customer_message",
        description="Send a formal customer communication (email, WhatsApp, SMS).",
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
        input_schema=SendCustomerMessageInput,
        handler=handle_send_customer_message,
    ))

    registry.register(ToolDefinition(
        name="request_refund",
        description="Create refund request for an order. High-risk operation gated by approval policies.",
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.HIGH,
        input_schema=RequestRefundInput,
        handler=handle_request_refund,
    ))

    registry.register(ToolDefinition(
        name="cancel_order",
        description="Cancel an active order in the business simulator. Gated by high-risk approval policies.",
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.HIGH,
        input_schema=CancelOrderInput,
        handler=handle_cancel_order,
    ))

    registry.register(ToolDefinition(
        name="request_human_approval",
        description="Pause workflow execution and generate human review ticket.",
        tool_type=ToolType.WRITE,
        risk_level=RiskLevel.MEDIUM,
        input_schema=RequestHumanApprovalInput,
        handler=handle_request_human_approval,
    ))

    registry.register(ToolDefinition(
        name="update_workflow_state",
        description="Persist intermediate workflow execution state.",
        tool_type=ToolType.SYSTEM,
        risk_level=RiskLevel.LOW,
        input_schema=UpdateWorkflowStateInput,
        handler=handle_update_workflow_state,
    ))

    return registry

