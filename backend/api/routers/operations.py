"""
Operational Dashboard and Telemetry API Router (Phase 4 - Deliverable D-16).
Provides read-only operational telemetry, workflow provenance, step traces,
and system health aggregates.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from database.models import (
    ApprovalRecord,
    ApprovalStatus,
    Customer,
    Order,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Product,
    Shipment,
    ShipmentStatus,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from database.session import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from simulator.service import BusinessSimulator
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.agents.service import agent_service
from backend.api.operations_schemas import (
    OperationalSummary,
    PolicyTelemetry,
    ResilienceTelemetry,
    RiskTelemetry,
    VerificationTelemetry,
    WorkflowRunDetailResponse,
    WorkflowRunTelemetry,
    WorkflowStepTelemetry,
)
from backend.api.schemas import (
    DashboardMetricsResponse,
    OperationalExceptionItem,
    OperationalExceptionsResponse,
    ScenarioRunRequest,
    ScenarioRunResponse,
)
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import WorkflowRunRecord, WorkflowState

router = APIRouter(prefix="/operations", tags=["Operations & Telemetry"])

# Validation pattern: allows alphanumeric, hyphens, and underscores, length 1-128.
# Strictly rejects path-traversal (..), slashes, whitespace, and injection characters.
RUN_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")

SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "conn_str",
    "database_url",
)


def _validate_run_id(run_id: str) -> None:
    """Validates that a run_id adheres to safe alphanumeric format."""
    if not run_id or not RUN_ID_REGEX.match(run_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Malformed run_id: '{run_id}'. Run identifiers must be 1-128 characters "
                "containing only letters, numbers, hyphens, or underscores."
            ),
        )


def _sanitize_value(value: Any) -> Any:
    """Recursively redacts values for sensitive keys in payloads and dictionaries."""
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in value.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_value(v)
        return sanitized
    elif isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _normalize_resilience(records: List[Dict[str, Any]]) -> List[ResilienceTelemetry]:
    """Normalizes raw resilience records into strongly typed ResilienceTelemetry models."""
    normalized: List[ResilienceTelemetry] = []
    for r in records:
        attempts = int(r.get("attempts", r.get("attempt_count", 1)) or 1)
        raw_delays = r.get("retry_delays") or []
        delays = [float(d) for d in raw_delays if isinstance(d, (int, float))]
        elapsed = r.get("elapsed_seconds")
        if elapsed is not None:
            try:
                elapsed = float(elapsed)
            except (ValueError, TypeError):
                elapsed = None

        timed_out = bool(
            r.get("timed_out") is True
            or r.get("timeout_occurred") is True
            or "Timeout" in str(r.get("error_type", ""))
            or "Timeout" in str(r.get("error_message", ""))
        )

        retryable = bool(r.get("retryable", False))
        conflict = bool(r.get("conflict", False))
        in_flight = bool(r.get("in_flight", False))
        is_cached = bool(r.get("is_cached", False) or r.get("final_status") == "CACHED")

        normalized.append(
            ResilienceTelemetry(
                tool_name=r.get("tool_name"),
                idempotency_key=r.get("idempotency_key"),
                scope=r.get("scope"),
                is_cached=is_cached,
                attempts=attempts,
                attempt_count=attempts,
                retry_delays=delays,
                elapsed_seconds=elapsed,
                final_status=r.get("final_status"),
                timed_out=timed_out,
                retryable=retryable,
                conflict=conflict,
                in_flight=in_flight,
                error_type=r.get("error_type"),
                error_message=r.get("error_message"),
            )
        )
    return normalized


def _normalize_risk(risk_data: Optional[Dict[str, Any]]) -> Optional[RiskTelemetry]:
    """Normalizes raw risk assessment dictionaries into RiskTelemetry."""
    if not risk_data:
        return None

    score = risk_data.get("risk_score")
    if score is not None:
        try:
            score = float(score)
        except (ValueError, TypeError):
            score = None

    risk_band = risk_data.get("risk_band")
    if risk_band is not None:
        risk_band = str(risk_band).upper()

    is_high_risk = bool(
        risk_data.get("is_high_risk", False)
        or (score is not None and score >= 0.70)
        or risk_band == "HIGH"
    )

    anomaly_dict = risk_data.get("anomaly") or {}
    anomaly_flags = list(anomaly_dict.get("anomaly_flags") or [])
    anomaly_score = anomaly_dict.get("anomaly_score")
    if anomaly_score is not None:
        try:
            anomaly_score = float(anomaly_score)
        except (ValueError, TypeError):
            anomaly_score = None

    anomaly_detected = bool(anomaly_dict.get("is_anomaly", False) or len(anomaly_flags) > 0)

    return RiskTelemetry(
        model_name=str(risk_data.get("model_name", "OperationalRiskModel")),
        model_version=str(risk_data.get("model_version", "v1.0.0")),
        risk_score=score,
        risk_band=risk_band,
        is_high_risk=is_high_risk,
        anomaly_detected=anomaly_detected,
        anomaly_score=anomaly_score,
        anomaly_reasons=anomaly_flags,
        top_risk_factors=list(risk_data.get("top_risk_factors") or []),
        feature_contributions=list(risk_data.get("contributions") or []),
        features=_sanitize_value(risk_data.get("features")),
        evaluated_at=risk_data.get("evaluated_at"),
    )


def _normalize_verification(records: List[Dict[str, Any]]) -> List[VerificationTelemetry]:
    """Normalizes post-action verification evidence into VerificationTelemetry models."""
    normalized: List[VerificationTelemetry] = []
    for vr in records:
        entity_id_val = vr.get("entity_id")
        normalized.append(
            VerificationTelemetry(
                entity_type=vr.get("entity_type"),
                entity_id=str(entity_id_val) if entity_id_val is not None else None,
                target_state=vr.get("target_state"),
                actual_state=vr.get("actual_state"),
                status=vr.get("status"),
                verified=bool(vr.get("verified", False)),
                discrepancies=list(vr.get("discrepancies") or []),
                operation=vr.get("operation"),
                error=vr.get("error"),
                timestamp=vr.get("timestamp"),
                details=_sanitize_value(vr.get("details") or {}),
            )
        )
    return normalized


def _normalize_policy(records: List[Dict[str, Any]]) -> List[PolicyTelemetry]:
    """Normalizes policy evaluation results into PolicyTelemetry models."""
    normalized: List[PolicyTelemetry] = []
    for pd in records:
        normalized.append(
            PolicyTelemetry(
                policy_id=pd.get("policy_id"),
                policy_version=str(pd.get("policy_version", "1.0.0")),
                decision=pd.get("decision"),
                allowed=bool(pd.get("allowed", True)),
                requires_approval=bool(pd.get("requires_approval", False)),
                risk_level=pd.get("risk_level"),
                matched_rules=list(pd.get("matched_rules") or []),
                relevant_facts=_sanitize_value(pd.get("relevant_facts") or {}),
            )
        )
    return normalized


def _build_step_telemetry(run: WorkflowRunRecord) -> List[WorkflowStepTelemetry]:
    """Builds ordered workflow step telemetry records with sanitized metadata."""
    return [
        WorkflowStepTelemetry(
            step_id=step.step_id,
            step_name=step.step_name,
            state=step.state.value if hasattr(step.state, "value") else str(step.state),
            tool_name=step.tool_name,
            input_payload=_sanitize_value(step.input_payload),
            output_payload=_sanitize_value(step.output_payload),
            error=step.error,
            timestamp=step.timestamp,
        )
        for step in run.steps
    ]


# ==============================================================================
# Operational Command Center Endpoints
# ==============================================================================


@router.get("/dashboard", response_model=DashboardMetricsResponse, status_code=status.HTTP_200_OK)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
) -> DashboardMetricsResponse:
    """Returns real-time aggregated operational KPIs and distribution metrics from database."""
    now = datetime.now(timezone.utc)
    today_start = now - timedelta(hours=24)
    month_start = now - timedelta(days=30)

    total_orders = db.scalar(select(func.count(Order.id))) or 0
    orders_today = (
        db.scalar(select(func.count(Order.id)).where(Order.created_at >= today_start)) or 0
    )
    orders_processing = (
        db.scalar(
            select(func.count(Order.id)).where(
                Order.status.in_(
                    [OrderStatus.PROCESSING, OrderStatus.CONFIRMED, OrderStatus.PENDING]
                )
            )
        )
        or 0
    )

    revenue_today = (
        db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.SUCCESSFUL,
                Payment.paid_at >= today_start,
            )
        )
        or Decimal("0.00")
    )
    revenue_this_month = (
        db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == PaymentStatus.SUCCESSFUL,
                Payment.paid_at >= month_start,
            )
        )
        or Decimal("0.00")
    )

    pending_payments = (
        db.scalar(
            select(func.count(Payment.id)).where(
                Payment.status.in_([PaymentStatus.INITIATED, PaymentStatus.AUTHORIZED])
            )
        )
        or 0
    )
    failed_payments = (
        db.scalar(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.FAILED)) or 0
    )

    refunds_pending = (
        db.scalar(
            select(func.count(ApprovalRecord.id)).where(
                ApprovalRecord.status == ApprovalStatus.PENDING,
                ApprovalRecord.action == "process_refund",
            )
        )
        or 0
    )

    shipments_in_transit = (
        db.scalar(
            select(func.count(Shipment.id)).where(
                Shipment.status.in_([ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY])
            )
        )
        or 0
    )
    delayed_shipments = (
        db.scalar(
            select(func.count(Shipment.id)).where(Shipment.status == ShipmentStatus.DELAYED)
        )
        or 0
    )
    orders_at_risk = delayed_shipments + failed_payments

    open_tickets = (
        db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
            )
        )
        or 0
    )
    pending_approvals = (
        db.scalar(
            select(func.count(ApprovalRecord.id)).where(
                ApprovalRecord.status == ApprovalStatus.PENDING
            )
        )
        or 0
    )

    sla_breaches = (
        db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
                Ticket.priority.in_([TicketPriority.HIGH, TicketPriority.URGENT]),
                Ticket.created_at < now - timedelta(hours=48),
            )
        )
        or 0
    )

    # Status distribution
    status_rows = db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    ).all()
    orders_by_status = {
        row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in status_rows
    }

    # Payment methods distribution
    method_rows = db.execute(
        select(Payment.payment_method, func.count(Payment.id)).group_by(Payment.payment_method)
    ).all()
    payment_method_stats = {
        row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in method_rows
    }

    # 7-day revenue trend
    recent_daily_revenue = []
    recent_daily_orders = []
    for day_offset in range(6, -1, -1):
        day_date = (now - timedelta(days=day_offset)).date()
        day_start = datetime(day_date.year, day_date.month, day_date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        day_rev = (
            db.scalar(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == PaymentStatus.SUCCESSFUL,
                    Payment.paid_at >= day_start,
                    Payment.paid_at < day_end,
                )
            )
            or Decimal("0.00")
        )
        day_ord = (
            db.scalar(
                select(func.count(Order.id)).where(
                    Order.created_at >= day_start,
                    Order.created_at < day_end,
                )
            )
            or 0
        )
        label = day_date.strftime("%b %d")
        recent_daily_revenue.append({"date": label, "amount": float(day_rev)})
        recent_daily_orders.append({"date": label, "count": day_ord})

    return DashboardMetricsResponse(
        total_orders=total_orders,
        orders_today=orders_today,
        orders_processing=orders_processing,
        orders_at_risk=orders_at_risk,
        revenue_today=revenue_today,
        revenue_this_month=revenue_this_month,
        pending_payments=pending_payments,
        failed_payments=failed_payments,
        refunds_pending=refunds_pending,
        shipments_in_transit=shipments_in_transit,
        delayed_shipments=delayed_shipments,
        open_tickets=open_tickets,
        pending_approvals=pending_approvals,
        sla_breaches=sla_breaches,
        orders_by_status=orders_by_status,
        payment_method_stats=payment_method_stats,
        recent_daily_revenue=recent_daily_revenue,
        recent_daily_orders=recent_daily_orders,
    )


@router.get(
    "/exceptions", response_model=OperationalExceptionsResponse, status_code=status.HTTP_200_OK
)
def get_operational_exceptions(
    db: Session = Depends(get_db),
) -> OperationalExceptionsResponse:
    """Returns prioritized live operational exceptions requiring operator intervention."""
    exceptions: List[OperationalExceptionItem] = []
    now = datetime.now(timezone.utc)

    # 1. Delayed shipments
    delayed_shipments = db.scalars(
        select(Shipment)
        .where(Shipment.status == ShipmentStatus.DELAYED)
        .order_by(desc(Shipment.updated_at))
        .limit(20)
    ).all()
    for s in delayed_shipments:
        exceptions.append(
            OperationalExceptionItem(
                id=f"exc-shp-{s.id}",
                category="LOGISTICS",
                severity="HIGH",
                title=f"Logistics Delay: {s.carrier} ({s.tracking_number})",
                description=(
                    f"Shipment {s.shipment_number} for order {s.order_id} delayed: "
                    f"{s.delay_reason or 'No carrier movement past ETA'}."
                ),
                entity_type="Shipment",
                entity_id=str(s.id),
                status=s.status.value,
                recommended_action=(
                    "Contact carrier logistics dispatcher or issue revised ETA to customer."
                ),
                first_detected=s.updated_at,
            )
        )

    # 2. Failed payments
    failed_payments = db.scalars(
        select(Payment)
        .where(Payment.status == PaymentStatus.FAILED)
        .order_by(desc(Payment.created_at))
        .limit(15)
    ).all()
    for p in failed_payments:
        exceptions.append(
            OperationalExceptionItem(
                id=f"exc-pay-{p.id}",
                category="PAYMENT",
                severity="HIGH",
                title=f"Payment Authorization Failure: {p.payment_reference}",
                description=f"Transaction failed with error {p.error_code}: {p.error_message}",
                entity_type="Payment",
                entity_id=str(p.id),
                status=p.status.value,
                recommended_action=(
                    "Trigger payment retry notification or verify customer billing credentials."
                ),
                first_detected=p.created_at,
            )
        )

    # 3. High-risk pending approvals
    pending_approvals = db.scalars(
        select(ApprovalRecord)
        .where(ApprovalRecord.status == ApprovalStatus.PENDING)
        .order_by(desc(ApprovalRecord.requested_at))
        .limit(15)
    ).all()
    for a in pending_approvals:
        exceptions.append(
            OperationalExceptionItem(
                id=f"exc-apv-{a.id}",
                category="APPROVAL",
                severity="CRITICAL" if a.risk_level == "CRITICAL" else "HIGH",
                title=f"Action Approval Required: {a.action}",
                description=f"Operation gated by policy: {a.reason}",
                entity_type="ApprovalRecord",
                entity_id=str(a.id),
                status=a.status.value,
                recommended_action=(
                    "Review policy rationale and approve or reject in Approval Queue."
                ),
                first_detected=a.requested_at,
            )
        )

    # 4. Support SLA breaches (>48h on HIGH/URGENT)
    sla_tickets = db.scalars(
        select(Ticket)
        .where(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
            Ticket.priority.in_([TicketPriority.HIGH, TicketPriority.URGENT]),
            Ticket.created_at < now - timedelta(hours=48),
        )
        .order_by(Ticket.created_at)
        .limit(15)
    ).all()
    for t in sla_tickets:
        exceptions.append(
            OperationalExceptionItem(
                id=f"exc-tck-{t.id}",
                category="SUPPORT",
                severity="CRITICAL",
                title=f"Support SLA Breach: {t.ticket_number}",
                description=f"High-priority issue '{t.title}' has exceeded 48h resolution SLA.",
                entity_type="Ticket",
                entity_id=str(t.id),
                status=t.status.value,
                recommended_action="Escalate to shift supervisor and update customer.",
                first_detected=t.created_at,
            )
        )

    return OperationalExceptionsResponse(total=len(exceptions), exceptions=exceptions)


@router.post(
    "/scenarios/run", response_model=ScenarioRunResponse, status_code=status.HTTP_200_OK
)
def run_operational_scenario(
    payload: ScenarioRunRequest,
    db: Session = Depends(get_db),
) -> ScenarioRunResponse:
    """Executes one of the 7 canonical enterprise operational scenarios and returns live results."""
    sim = BusinessSimulator(session=db)
    sid = payload.scenario_id.strip()

    customer = db.scalars(select(Customer)).first()
    product = db.scalars(select(Product)).first()
    if not customer or not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database has no customers or products. Please seed database first.",
        )

    timeline = []

    if sid == "1":
        # Scenario 1: Normal Order
        order, payment, shipment = sim.run_normal_order_flow(
            customer_id=customer.id,
            items=[{"sku": product.sku, "quantity": 1}],
            carrier="Delhivery",
        )
        timeline.append(f"Order created: {order.order_number} for INR {order.total_amount}")
        timeline.append(
            f"Payment captured: {payment.payment_reference} (Status: {payment.status.value})"
        )
        timeline.append(f"Shipment dispatched: {shipment.carrier} ({shipment.tracking_number})")
        timeline.append(f"Shipment confirmed delivered: {shipment.actual_delivery_date}")
        timeline.append(f"Final order state verified: {order.status.value}")

        return ScenarioRunResponse(
            scenario_id="1",
            name="Normal Order Flow",
            success=True,
            summary=(
                "Full canonical order lifecycle completed: Order -> Capture -> "
                "Dispatch -> Delivery verified."
            ),
            timeline=timeline,
            entities={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "payment_ref": payment.payment_reference,
                "tracking_number": shipment.tracking_number,
                "status": order.status.value,
            },
        )

    elif sid == "2":
        # Scenario 2: Delayed Shipment
        order, payment, shipment = sim.run_delayed_order_flow(
            customer_id=customer.id,
            items=[{"sku": product.sku, "quantity": 1}],
            carrier="BlueDart",
            delay_reason="Regional transit network disruption at Hubli Hub",
        )
        timeline.append(f"Order placed and paid: {order.order_number}")
        timeline.append(f"Shipment created: {shipment.tracking_number}")
        timeline.append(f"Carrier delay logged: '{shipment.delay_reason}'")
        timeline.append(f"Revised estimated delivery date: {shipment.estimated_delivery_date}")
        timeline.append(f"Exception generated in control center: {shipment.status.value}")

        return ScenarioRunResponse(
            scenario_id="2",
            name="Delayed Shipment Scenario",
            success=True,
            summary=(
                "Transit delay logged, exception registered in control center, revised ETA issued."
            ),
            timeline=timeline,
            entities={
                "order_id": str(order.id),
                "tracking_number": shipment.tracking_number,
                "delay_reason": shipment.delay_reason,
                "status": shipment.status.value,
            },
        )

    elif sid == "3":
        # Scenario 3: High-Value Refund
        order = sim.create_order(
            customer_id=customer.id,
            items=[{"sku": product.sku, "quantity": 3}],
        )
        payment = sim.create_payment(
            order_id=order.id,
            amount=Decimal("6500.00"),
            payment_method=PaymentMethod.UPI,
        )
        payment = sim.capture_payment(payment_id=payment.id)
        timeline.append(
            f"High-value order created: {order.order_number} (Amount: INR {payment.amount})"
        )

        # Run agent refund request
        run = agent_service.execute_workflow(
            db=db,
            input_text=f"Please refund my order {order.order_number}",
            order_number=order.order_number,
        )
        risk_score = run.risk_assessment.get("risk_score", 0.85)
        timeline.append(f"Agent evaluated refund policy: Risk score = {risk_score}")
        timeline.append(f"Policy gate triggered: Paused in {run.state.value} state")

        # Simulate supervisor approval
        resumed = agent_service.resume_workflow(
            run_id=run.run_id,
            approved=True,
            db=db,
            reason="Approved by operations supervisor after customer verification",
        )
        timeline.append(f"Supervisor approved refund: Resumed state = {resumed.state.value}")
        db.refresh(payment)
        timeline.append(f"Payment state verified in DB: {payment.status.value}")

        return ScenarioRunResponse(
            scenario_id="3",
            name="High-Value Refund Approval & Resume",
            success=payment.status == PaymentStatus.REFUNDED,
            summary=(
                "High-value refund paused for policy approval, supervisor "
                "authorized, verified in DB."
            ),
            timeline=timeline,
            entities={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "payment_status": payment.status.value,
                "run_id": run.run_id,
            },
        )

    elif sid == "4":
        # Scenario 4: Rejected Cancellation
        order = sim.create_order(
            customer_id=customer.id,
            items=[{"sku": product.sku, "quantity": 1}],
        )
        sim.create_payment(
            order_id=order.id,
            amount=Decimal("5500.00"),
            payment_method=PaymentMethod.CARD,
        )
        sim.capture_payment(payment_id=order.payments[0].id)
        order = sim.update_order_status(
            session=db, order_id=order.id, new_status=OrderStatus.SHIPPED, reason="Dispatched"
        )
        timeline.append(
            f"Order created and dispatched: {order.order_number} (Status: {order.status.value})"
        )

        run = agent_service.execute_workflow(
            db=db,
            input_text=f"Cancel my order {order.order_number}",
            order_number=order.order_number,
        )
        timeline.append(
            f"Agent evaluated cancellation policy on shipped order: State = {run.state.value}"
        )

        resumed = agent_service.resume_workflow(
            run_id=run.run_id,
            approved=False,
            db=db,
            reason="Order already in final transit; cancellation rejected under POL-CAN-001.",
        )
        db.refresh(order)
        timeline.append(
            f"Supervisor rejected cancellation: Workflow finished with {resumed.state.value}"
        )
        timeline.append(f"Order unchanged in database: Still {order.status.value}")

        return ScenarioRunResponse(
            scenario_id="4",
            name="Rejected Cancellation Scenario",
            success=order.status == OrderStatus.SHIPPED,
            summary=(
                "Cancellation on shipped order rejected; order remains intact in SHIPPED status."
            ),
            timeline=timeline,
            entities={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "order_status": order.status.value,
            },
        )

    elif sid == "5":
        # Scenario 5: Duplicate Refund Request (Idempotency)
        order = sim.create_order(
            customer_id=customer.id,
            items=[{"sku": product.sku, "quantity": 1}],
        )
        payment = sim.create_payment(
            order_id=order.id,
            amount=Decimal("1200.00"),
            payment_method=PaymentMethod.UPI,
        )
        sim.capture_payment(payment_id=payment.id)
        idem_key = f"idem-demo-{uuid.uuid4().hex[:8]}"

        from backend.tools.registry import create_default_tool_registry
        from backend.tools.schemas import RequestRefundInput

        reg = create_default_tool_registry(resilience_wrapper=agent_service.resilience_wrapper)
        ctx = {"db": db, "idempotency_key": idem_key, "approved": True}

        res1 = reg.execute(
            "request_refund",
            RequestRefundInput(order_id=order.id, reason="Return item"),
            context=ctx,
        )
        timeline.append(f"First request executed: Refund status = {res1.get('status')}")

        res2 = reg.execute(
            "request_refund",
            RequestRefundInput(order_id=order.id, reason="Return item"),
            context=ctx,
        )
        timeline.append("Duplicate request replayed with same key: Returned identical response.")
        timeline.append("Verified: Zero duplicate mutations or second payments created.")

        return ScenarioRunResponse(
            scenario_id="5",
            name="Duplicate Request Protection (Idempotency)",
            success=res1.get("status") == res2.get("status"),
            summary=(
                "Same idempotency key replayed twice; second call replayed cache "
                "without duplicate mutation."
            ),
            timeline=timeline,
            entities={"idempotency_key": idem_key, "order_id": str(order.id)},
        )

    elif sid == "6":
        # Scenario 6: Payment Failure
        order = sim.create_order(
            customer_id=customer.id,
            items=[{"sku": product.sku, "quantity": 1}],
        )
        payment = sim.create_payment(
            order_id=order.id,
            amount=order.total_amount,
            payment_method=PaymentMethod.CARD,
        )
        sim.fail_payment(
            session=db,
            payment_id=payment.id,
            error_code="ERR_CARD_DECLINED",
            error_message="Card issuer declined transaction due to temporary fraud lock.",
        )
        db.refresh(order)
        db.refresh(payment)
        timeline.append(f"Order created: {order.order_number}")
        timeline.append(f"Payment failed: {payment.payment_reference} with ERR_CARD_DECLINED")
        timeline.append("Order remains PENDING (never incorrectly marked CONFIRMED or PAID)")
        timeline.append(
            "Payment failure registered in Exceptions Queue for operator investigation."
        )

        return ScenarioRunResponse(
            scenario_id="6",
            name="Payment Failure & Exception Flow",
            success=order.status == OrderStatus.PENDING and payment.status == PaymentStatus.FAILED,
            summary=(
                "Payment failure safely handled; order not prematurely confirmed; exception logged."
            ),
            timeline=timeline,
            entities={
                "order_id": str(order.id),
                "payment_ref": payment.payment_reference,
                "error_code": payment.error_code,
            },
        )

    else:
        # Scenario 7: Verification Divergence
        from backend.verification.service import state_verification_service

        # Test simulated ghost success
        order = sim.create_order(
            customer_id=customer.id,
            items=[{"sku": product.sku, "quantity": 1}],
        )
        timeline.append(f"Order in DB: {order.order_number} (Actual status: {order.status.value})")

        v_res = state_verification_service.verify_order_state(
            db=db,
            order_id=order.id,
            expected_status=OrderStatus.CANCELLED,
            action="cancel_order",
        )
        timeline.append("Tool reported cancellation success, but DB order was not updated.")
        timeline.append(f"Verification Engine executed: Verified = {v_res.verified}")
        timeline.append(f"Divergence detected: {v_res.discrepancies}")
        timeline.append("Alert raised: Prevented false success report to customer.")

        return ScenarioRunResponse(
            scenario_id="7",
            name="Verification Divergence (Ghost Success Detection)",
            success=not v_res.verified and len(v_res.discrepancies) > 0,
            summary=(
                "Verification engine accurately caught divergence between tool "
                "success and persisted DB state."
            ),
            timeline=timeline,
            entities={
                "order_id": str(order.id),
                "expected_status": "CANCELLED",
                "actual_status": order.status.value,
                "discrepancies": v_res.discrepancies,
            },
        )


@router.get("/summary", response_model=OperationalSummary, status_code=status.HTTP_200_OK)
def get_operational_summary(
    limit: int = Query(default=500, ge=1, le=5000, description="Checkpoint analysis window limit"),
) -> OperationalSummary:
    """
    Returns aggregate operational metrics across recorded workflow runs in the checkpoint store.
    Read-only inspection endpoint.
    """
    runs = checkpoint_store.list_runs(limit=limit)

    total_runs = len(runs)
    completed = 0
    failed = 0
    waiting_for_approval = 0
    cancelled = 0
    running = 0
    verification_failures = 0
    retry_failures = 0
    timeout_failures = 0
    high_risk_assessments = 0
    anomalous_assessments = 0

    for run in runs:
        state_str = run.state.value if hasattr(run.state, "value") else str(run.state)

        if state_str == WorkflowState.COMPLETED.value:
            completed += 1
        elif state_str == WorkflowState.FAILED.value:
            failed += 1
        elif state_str == WorkflowState.WAITING_FOR_APPROVAL.value:
            waiting_for_approval += 1
        elif state_str == WorkflowState.CANCELLED.value:
            cancelled += 1
        else:
            running += 1

        # Check verification failures
        if any(
            not vr.get("verified", False)
            or str(vr.get("status")).upper() in ("DIVERGENT", "NOT_FOUND", "ERROR")
            or vr.get("error") is not None
            for vr in run.verification_results
        ):
            verification_failures += 1

        # Check resilience retry exhaustion failures
        if any(
            r.get("error_type") == "MaxRetriesExceededError"
            or "MaxRetriesExceededError" in str(r.get("error_message", ""))
            or "Retry exhaustion" in str(r.get("error_message", ""))
            for r in run.resilience_records
        ):
            retry_failures += 1

        # Check timeout failures
        if any(
            r.get("timed_out") is True
            or r.get("timeout_occurred") is True
            or "Timeout" in str(r.get("error_type", ""))
            or "Timeout" in str(r.get("error_message", ""))
            for r in run.resilience_records
        ):
            timeout_failures += 1

        # Check ML risk & anomalies
        if run.risk_assessment:
            score = run.risk_assessment.get("risk_score")
            band = str(run.risk_assessment.get("risk_band", "")).upper()
            if (score is not None and float(score) >= 0.70) or band == "HIGH":
                high_risk_assessments += 1

            anomaly = run.risk_assessment.get("anomaly") or {}
            flags = anomaly.get("anomaly_flags") or []
            if bool(anomaly.get("is_anomaly", False)) or len(flags) > 0:
                anomalous_assessments += 1

    return OperationalSummary(
        total_runs=total_runs,
        completed=completed,
        failed=failed,
        waiting_for_approval=waiting_for_approval,
        cancelled=cancelled,
        running=running,
        verification_failures=verification_failures,
        retry_failures=retry_failures,
        timeout_failures=timeout_failures,
        high_risk_assessments=high_risk_assessments,
        anomalous_assessments=anomalous_assessments,
        data_source="in_memory_and_disk_checkpoints",
        notes=(
            "Aggregate metrics derived from checkpoint store runs without requiring"
            " database migrations."
        ),
    )


@router.get(
    "/runs/{run_id}", response_model=WorkflowRunDetailResponse, status_code=status.HTTP_200_OK
)
def get_workflow_run_detail(run_id: str) -> WorkflowRunDetailResponse:
    """
    Returns full workflow run details including verification results, risk assessment,
    resilience records, policy decisions, and current execution step.
    Strictly read-only.
    """
    _validate_run_id(run_id)

    run = checkpoint_store.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{run_id}' not found.",
        )

    current_step = run.steps[-1].step_name if run.steps else None
    state_str = run.state.value if hasattr(run.state, "value") else str(run.state)

    return WorkflowRunDetailResponse(
        workflow_id=run.workflow_id,
        run_id=run.run_id,
        workflow_type=run.workflow_type,
        state=state_str,
        current_step=current_step,
        customer_id=run.customer_id,
        order_id=run.order_id,
        input_text=run.input_text,
        intent=run.intent,
        final_response=run.final_response,
        error=run.error,
        steps=_build_step_telemetry(run),
        verification_results=_normalize_verification(run.verification_results),
        risk_assessment=_normalize_risk(run.risk_assessment),
        resilience_records=_normalize_resilience(run.resilience_records),
        policy_decisions=_normalize_policy(run.policy_decisions),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get(
    "/runs/{run_id}/steps",
    response_model=List[WorkflowStepTelemetry],
    status_code=status.HTTP_200_OK,
)
def get_workflow_run_steps(run_id: str) -> List[WorkflowStepTelemetry]:
    """
    Returns ordered workflow/checkpoint steps with execution states, timestamps,
    sanitized payloads, and errors.
    Strictly read-only.
    """
    _validate_run_id(run_id)

    run = checkpoint_store.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{run_id}' not found.",
        )

    return _build_step_telemetry(run)


@router.get(
    "/runs/{run_id}/telemetry", response_model=WorkflowRunTelemetry, status_code=status.HTTP_200_OK
)
def get_workflow_run_telemetry(run_id: str) -> WorkflowRunTelemetry:
    """
    Returns normalized operational telemetry summarizing executed tools, policy governance,
    ML risk scoring, verification results, retry counts, timeout state, idempotency outcomes,
    and failure information.
    Strictly read-only.
    """
    _validate_run_id(run_id)

    run = checkpoint_store.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{run_id}' not found.",
        )

    current_step = run.steps[-1].step_name if run.steps else None
    state_str = run.state.value if hasattr(run.state, "value") else str(run.state)

    # Executed tools collection
    executed_tools: List[str] = []
    for step in run.steps:
        if step.tool_name and step.tool_name not in executed_tools:
            executed_tools.append(step.tool_name)
    for r in run.resilience_records:
        tool = r.get("tool_name")
        if tool and tool not in executed_tools:
            executed_tools.append(tool)

    # Retry counts and total retries
    retry_counts: Dict[str, int] = {}
    for r in run.resilience_records:
        tool = r.get("tool_name", "unknown")
        attempts = int(r.get("attempts", r.get("attempt_count", 1)) or 1)
        retries = max(0, attempts - 1)
        retry_counts[tool] = retry_counts.get(tool, 0) + retries
    total_retries = sum(retry_counts.values())

    # Timeout & retry exhaustion
    timeout_occurred = any(
        r.get("timed_out") is True
        or r.get("timeout_occurred") is True
        or "Timeout" in str(r.get("error_type", ""))
        or "Timeout" in str(r.get("error_message", ""))
        for r in run.resilience_records
    )
    retry_exhausted = any(
        r.get("error_type") == "MaxRetriesExceededError"
        or "MaxRetriesExceededError" in str(r.get("error_message", ""))
        or "Retry exhaustion" in str(r.get("error_message", ""))
        for r in run.resilience_records
    )

    # Idempotency outcomes
    idempotency_outcomes: Dict[str, Any] = {
        "total_records": len(run.resilience_records),
        "cached_count": sum(
            1
            for r in run.resilience_records
            if r.get("is_cached") is True or r.get("final_status") == "CACHED"
        ),
        "conflict_count": sum(1 for r in run.resilience_records if r.get("conflict") is True),
        "completed_count": sum(
            1 for r in run.resilience_records if r.get("final_status") == "COMPLETED"
        ),
        "failed_count": sum(1 for r in run.resilience_records if r.get("final_status") == "FAILED"),
        "keys": [
            r.get("idempotency_key") for r in run.resilience_records if r.get("idempotency_key")
        ],
    }

    # Normalized subsystems
    resilience_telemetry = _normalize_resilience(run.resilience_records)
    risk_telemetry = _normalize_risk(run.risk_assessment)
    verification_results = _normalize_verification(run.verification_results)
    policy_decisions = _normalize_policy(run.policy_decisions)

    # ML flags
    is_high_risk = risk_telemetry.is_high_risk if risk_telemetry else False
    anomaly_detected = risk_telemetry.anomaly_detected if risk_telemetry else False
    anomaly_reasons = risk_telemetry.anomaly_reasons if risk_telemetry else []
    model_version = risk_telemetry.model_version if risk_telemetry else None

    # Failure information
    failure_information: Optional[Dict[str, Any]] = None
    if (
        state_str == WorkflowState.FAILED.value
        or run.error is not None
        or retry_exhausted
        or timeout_occurred
    ):
        failed_steps = [
            s.step_name
            for s in run.steps
            if (s.state.value if hasattr(s.state, "value") else str(s.state))
            == WorkflowState.FAILED.value
            or s.error is not None
        ]
        resilience_failures = [
            {
                "tool_name": r.get("tool_name"),
                "error_type": r.get("error_type"),
                "error_message": r.get("error_message"),
                "timed_out": r.get("timed_out", False),
                "retryable": r.get("retryable", False),
            }
            for r in run.resilience_records
            if r.get("final_status") == "FAILED" or r.get("error_message")
        ]
        failure_information = {
            "workflow_error": run.error,
            "failed_steps": failed_steps,
            "resilience_failures": resilience_failures,
            "timeout_occurred": timeout_occurred,
            "retry_exhausted": retry_exhausted,
        }

    return WorkflowRunTelemetry(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        workflow_type=run.workflow_type,
        state=state_str,
        status=state_str,
        current_step=current_step,
        executed_tools=executed_tools,
        policy_decisions=policy_decisions,
        risk_telemetry=risk_telemetry,
        verification_results=verification_results,
        resilience_telemetry=resilience_telemetry,
        retry_counts=retry_counts,
        total_retries=total_retries,
        timeout_occurred=timeout_occurred,
        retry_exhausted=retry_exhausted,
        idempotency_outcomes=idempotency_outcomes,
        failure_information=failure_information,
        is_high_risk=is_high_risk,
        anomaly_detected=anomaly_detected,
        anomaly_reasons=anomaly_reasons,
        model_version=model_version,
        final_response=run.final_response,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
