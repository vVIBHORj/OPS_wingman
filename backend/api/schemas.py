"""
Pydantic Request and Response Schemas for OpsWingman Operational REST API.
"""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from database.models.enums import (
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    ShipmentStatus,
)


# ==============================================================================
# Customer Schemas
# ==============================================================================

class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# Product Schemas
# ==============================================================================

class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit_price: Decimal
    currency: str
    inventory_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# Order Schemas
# ==============================================================================

class OrderItemCreate(BaseModel):
    sku: Optional[str] = None
    product_id: Optional[uuid.UUID] = None
    quantity: int = Field(default=1, gt=0)
    unit_price: Optional[Decimal] = None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    created_at: datetime
    updated_at: Optional[datetime] = None


class OrderCreateRequest(BaseModel):
    customer_id: uuid.UUID
    items: List[OrderItemCreate]
    order_number: Optional[str] = None
    shipping_address: Optional[Dict[str, str]] = None
    tax_rate: Decimal = Field(default=Decimal("0.18"), ge=Decimal("0.00"))
    shipping_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus
    reason: Optional[str] = None


class OrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID
    status: OrderStatus
    currency: str
    subtotal_amount: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    shipping_address_line1: Optional[str] = None
    shipping_address_line2: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None
    shipping_pincode: Optional[str] = None
    shipping_country: Optional[str] = None
    cancellation_reason: Optional[str] = None
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# Payment Schemas
# ==============================================================================

class PaymentCreateRequest(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=Decimal("0.00"))
    payment_method: PaymentMethod = PaymentMethod.UPI
    payment_reference: Optional[str] = None


class PaymentCaptureRequest(BaseModel):
    gateway_transaction_id: Optional[str] = None


class PaymentFailRequest(BaseModel):
    error_code: str = Field(..., min_length=1)
    error_message: str = Field(..., min_length=1)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_reference: str
    order_id: uuid.UUID
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    status: PaymentStatus
    gateway_transaction_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# Shipment Schemas
# ==============================================================================

class ShipmentCreateRequest(BaseModel):
    carrier: str = Field(default="Delhivery", min_length=1)
    tracking_number: Optional[str] = None
    estimated_days: int = Field(default=3, gt=0)
    status: ShipmentStatus = ShipmentStatus.MANIFESTED


class ShipmentStatusUpdateRequest(BaseModel):
    status: ShipmentStatus
    location: Optional[str] = None


class ShipmentDelayRequest(BaseModel):
    delay_reason: str = Field(..., min_length=1)
    updated_eta: Optional[datetime] = None
    current_location: Optional[str] = None


class ShipmentDeliverRequest(BaseModel):
    actual_delivery_date: Optional[datetime] = None
    recipient_notes: Optional[str] = None


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shipment_number: str
    order_id: uuid.UUID
    carrier: str
    tracking_number: str
    status: ShipmentStatus
    estimated_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    current_location: Optional[str] = None
    delay_reason: Optional[str] = None
    shipped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# Domain Event Schemas
# ==============================================================================

class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    entity_type: str
    entity_id: uuid.UUID
    occurred_at: datetime
    payload: Dict[str, Any]
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    created_at: datetime


# ==============================================================================
# Agent & Workflow Schemas (Phase 2)
# ==============================================================================

class AgentRunRequest(BaseModel):
    input_text: str = Field(..., min_length=1, description="Customer request or operational input text")
    order_number: Optional[str] = Field(default=None, description="Optional explicit order number")
    customer_id: Optional[str] = Field(default=None, description="Optional customer ID")
    workflow_id: Optional[str] = Field(default=None, description="Optional parent workflow ID")


class WorkflowResumeRequest(BaseModel):
    approved: bool = Field(..., description="Approval decision: True to execute, False to reject")
    reason: Optional[str] = Field(default=None, description="Operator comment or justification")



class ToolMetadataResponse(BaseModel):
    name: str
    description: str
    tool_type: str
    risk_level: str


class WorkflowStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: str
    step_name: str
    state: str
    tool_name: Optional[str] = None
    input_payload: Optional[Dict[str, Any]] = None
    output_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime


class StructuredActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    parameters: Dict[str, Any]
    reason: str
    risk: str
    requires_approval: bool


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_id: str
    run_id: str
    workflow_type: str
    state: str
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    input_text: str
    intent: Optional[str] = None
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    steps: List[WorkflowStepResponse] = Field(default_factory=list)
    proposed_actions: List[StructuredActionResponse] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    policy_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    verification_results: List[Dict[str, Any]] = Field(default_factory=list)
    approval_id: Optional[str] = None
    final_response: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# Operational Dashboard & Telemetry Schemas (Phase 4 - Deliverable D-16)
# ==============================================================================

from backend.api.operations_schemas import (
    ResilienceTelemetry,
    RiskTelemetry,
    VerificationTelemetry,
    PolicyTelemetry,
    WorkflowStepTelemetry,
    WorkflowRunDetailResponse,
    WorkflowRunTelemetry,
    OperationalSummary,
)


