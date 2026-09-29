"""
Input and Output schemas for the initial Tool Registry (Appendix B).
"""

import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from database.models.enums import TicketPriority, TicketChannel
from backend.workflows.state import StructuredAction


class GetCustomerInput(BaseModel):
    customer_id: Optional[uuid.UUID] = Field(default=None, description="Customer UUID")
    email: Optional[str] = Field(default=None, description="Customer email address")


class GetOrderInput(BaseModel):
    order_id: Optional[uuid.UUID] = Field(default=None, description="Order UUID")
    order_number: Optional[str] = Field(default=None, description="Order Number, e.g. ORD-20260927-XXXXXX")


class GetPaymentInput(BaseModel):
    payment_id: Optional[uuid.UUID] = Field(default=None, description="Payment UUID")
    payment_reference: Optional[str] = Field(default=None, description="Payment reference, e.g. PAY-UPI-XXXXXX")
    order_id: Optional[uuid.UUID] = Field(default=None, description="Order UUID to look up associated payment")


class GetShipmentInput(BaseModel):
    shipment_id: Optional[uuid.UUID] = Field(default=None, description="Shipment UUID")
    tracking_number: Optional[str] = Field(default=None, description="Courier tracking number")
    order_id: Optional[uuid.UUID] = Field(default=None, description="Order UUID to look up shipment")


class GetPolicyInput(BaseModel):
    policy_name: str = Field(..., description="Policy identifier name, e.g. 'cancellation_window', 'shipping_sla', 'refund_eligibility'")


class CreateTicketInput(BaseModel):
    customer_id: uuid.UUID = Field(..., description="Customer UUID")
    subject: str = Field(..., min_length=1, description="Ticket subject")
    description: str = Field(..., min_length=1, description="Ticket body/details")
    order_id: Optional[uuid.UUID] = Field(default=None, description="Associated Order UUID")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Ticket priority level")
    channel: TicketChannel = Field(default=TicketChannel.EMAIL, description="Communication channel")


class SendCustomerMessageInput(BaseModel):
    recipient: str = Field(..., description="Recipient email address or phone number")
    subject: str = Field(..., description="Message subject line")
    body: str = Field(..., description="Message content")
    channel: str = Field(default="EMAIL", description="Channel e.g. EMAIL, WHATSAPP, SMS")
    order_number: Optional[str] = Field(default=None, description="Associated order reference")


class CancelOrderInput(BaseModel):
    order_id: uuid.UUID = Field(..., description="UUID of order to cancel")
    reason: str = Field(..., min_length=3, description="Cancellation justification")


class RequestRefundInput(BaseModel):
    order_id: uuid.UUID = Field(..., description="UUID of order for refund request")
    reason: str = Field(..., min_length=3, description="Justification for refund")
    amount: Optional[float] = Field(default=None, description="Optional custom refund amount; defaults to order total")
    customer_id: Optional[uuid.UUID] = Field(default=None, description="Optional customer UUID")


class RequestHumanApprovalInput(BaseModel):
    workflow_id: str = Field(..., description="Workflow execution ID to pause")
    action: str = Field(..., description="Action name requiring human review")
    reason: str = Field(..., description="Business justification or policy rule triggering approval")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="Action payload or entity metadata")
    risk_level: str = Field(default="HIGH", description="Risk level of the pending action")


class UpdateWorkflowStateInput(BaseModel):
    workflow_id: str = Field(..., description="Workflow execution ID")
    state: str = Field(..., description="Target workflow state")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional state transition metadata")

