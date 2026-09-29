"""Deterministic Policy Engine for OpsWingman (Phase 3 - Deliverable D-11).

Enforces business rules, permission boundaries, and approval triggers outside the LLM context.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.policies.schemas import PolicyEvaluationResult
from backend.rag.schemas import KnowledgeCitation


class PolicyEngine:
    """Deterministic rule evaluator that enforces ground-truth domain policies.

    Guarantees policy precedence, versioning, and prompt-injection immunity.
    """

    HIGH_VALUE_ORDER_THRESHOLD = Decimal("5000.00")
    AUTO_REFUND_THRESHOLD = Decimal("2000.00")

    def evaluate(
        self,
        action: Any,
        facts: Dict[str, Any],
        citations: Optional[List[KnowledgeCitation]] = None,
    ) -> PolicyEvaluationResult:
        """Evaluates a proposed action against governing operational policies using verified facts."""
        cits = citations or []

        # Extract action name from string or StructuredAction
        if hasattr(action, "action") and action.action:
            action_name = action.action
        elif hasattr(action, "action_name") and action.action_name:
            action_name = action.action_name
        else:
            action_name = str(action)

        if action_name == "cancel_order":
            return self._evaluate_cancellation(facts, cits)
        elif action_name in ["request_refund", "process_refund", "refund"]:
            return self._evaluate_refund(facts, cits)
        elif action_name in ["track_shipment", "notify_delay", "create_ticket", "get_shipment"]:
            return self._evaluate_shipping(facts, cits)
        else:
            return self._evaluate_default(action_name, facts, cits)

    def _evaluate_cancellation(
        self,
        facts: Dict[str, Any],
        citations: List[KnowledgeCitation],
    ) -> PolicyEvaluationResult:
        """Governed by POL-CAN-001 (Order Cancellation Policy v1.0.0)."""
        order_status = str(facts.get("order_status", "UNKNOWN")).upper()
        total_amount_val = facts.get("order_total_amount") or facts.get("order_total") or "0.00"
        try:
            total_amount = Decimal(str(total_amount_val))
        except Exception:
            total_amount = Decimal("0.00")

        # Disallow cancellation if already dispatched/in-transit/delivered
        if order_status in ["PROCESSING", "SHIPPED", "IN_TRANSIT", "DELIVERED"]:
            return PolicyEvaluationResult(
                allowed=False,
                requires_approval=False,
                decision=(
                    f"Dispatched orders cannot be cancelled directly under POL-CAN-001 (Status: '{order_status}'). "
                    f"A return request may be initiated after delivery."
                ),
                policy_id="POL-CAN-001",
                policy_version="1.0.0",
                matched_rules=["CAN-R02", "POL-CAN-001.R2: Disallowed post-dispatch cancellation"],
                relevant_facts={"order_status": order_status, "order_total_amount": str(total_amount)},
                citations=citations,
            )

        if order_status == "CANCELLED":
            return PolicyEvaluationResult(
                allowed=False,
                requires_approval=False,
                decision="Order is already cancelled.",
                policy_id="POL-CAN-001",
                policy_version="1.0.0",
                matched_rules=["CAN-R04", "POL-CAN-001.R4: Idempotent cancellation prevention"],
                relevant_facts={"order_status": order_status},
                citations=citations,
            )

        # Eligible orders (PENDING, CONFIRMED)
        if order_status in ["PENDING", "CONFIRMED"]:
            if total_amount > self.HIGH_VALUE_ORDER_THRESHOLD:
                decision_msg = (
                    f"High-value order cancellation (INR {total_amount:.2f} > INR {self.HIGH_VALUE_ORDER_THRESHOLD:.2f}) "
                    f"requires human supervisor approval under POL-CAN-001."
                )
                matched = [
                    "CAN-R01",
                    "CAN-R03",
                    "POL-CAN-001.R1: Eligible pre-dispatch cancellation",
                    "POL-CAN-001.R3: High-value cancellation approval threshold",
                ]
            else:
                decision_msg = (
                    f"Order cancellation is eligible under POL-CAN-001 (Status: {order_status}). "
                    f"Action classified as HIGH risk and requires operator approval."
                )
                matched = ["CAN-R01", "POL-CAN-001.R1: Eligible pre-dispatch cancellation"]

            return PolicyEvaluationResult(
                allowed=True,
                requires_approval=True,
                decision=decision_msg,
                policy_id="POL-CAN-001",
                policy_version="1.0.0",
                matched_rules=matched,
                relevant_facts={"order_status": order_status, "order_total_amount": str(total_amount)},
                citations=citations,
            )

        return PolicyEvaluationResult(
            allowed=False,
            requires_approval=False,
            decision=f"Cannot cancel order in state '{order_status}'.",
            policy_id="POL-CAN-001",
            policy_version="1.0.0",
            matched_rules=["CAN-R00", "POL-CAN-001.R0: Default state restriction"],
            relevant_facts={"order_status": order_status},
            citations=citations,
        )

    def _evaluate_refund(
        self,
        facts: Dict[str, Any],
        citations: List[KnowledgeCitation],
    ) -> PolicyEvaluationResult:
        """Governed by POL-REF-001 (Refund & Payment Policy v1.0.0)."""
        payment_status = str(facts.get("payment_status", "UNKNOWN")).upper()
        refund_amount_val = facts.get("refund_amount") or facts.get("payment_amount") or facts.get("amount") or "0.00"
        try:
            refund_amount = Decimal(str(refund_amount_val))
        except Exception:
            refund_amount = Decimal("0.00")

        # 1. Prerequisite: Must have captured successful payment
        if payment_status != "SUCCESSFUL":
            return PolicyEvaluationResult(
                allowed=False,
                requires_approval=False,
                decision=(
                    f"Refund rejected: Original payment was not successful (Status: '{payment_status}'). "
                    f"Refunds strictly require a confirmed captured transaction."
                ),
                policy_id="POL-REF-001",
                policy_version="1.0.0",
                matched_rules=["REF-R01", "POL-REF-001.R1: Valid captured payment prerequisite"],
                relevant_facts={"payment_status": payment_status, "refund_amount": str(refund_amount)},
                citations=citations,
            )

        # 2. Check value threshold
        if refund_amount > self.AUTO_REFUND_THRESHOLD:
            return PolicyEvaluationResult(
                allowed=True,
                requires_approval=True,
                decision=(
                    f"High-value refund of INR {refund_amount:.2f} exceeds auto-approval limit (INR {self.AUTO_REFUND_THRESHOLD:.2f}). "
                    f"Human supervisor approval is required under POL-REF-001 before processing."
                ),
                policy_id="POL-REF-001",
                policy_version="1.0.0",
                matched_rules=["REF-R03", "POL-REF-001.R2: High-value refund supervisor approval gate"],
                relevant_facts={"payment_status": payment_status, "refund_amount": str(refund_amount)},
                citations=citations,
            )
        else:
            return PolicyEvaluationResult(
                allowed=True,
                requires_approval=False,
                decision=(
                    f"Low-value refund of INR {refund_amount:.2f} is within auto-approval threshold (<= INR {self.AUTO_REFUND_THRESHOLD:.2f}) "
                    f"and complies with POL-REF-001."
                ),
                policy_id="POL-REF-001",
                policy_version="1.0.0",
                matched_rules=["REF-R02", "POL-REF-001.R2: Low-value refund auto-approval"],
                relevant_facts={"payment_status": payment_status, "refund_amount": str(refund_amount)},
                citations=citations,
            )

    def _evaluate_shipping(
        self,
        facts: Dict[str, Any],
        citations: List[KnowledgeCitation],
    ) -> PolicyEvaluationResult:
        """Governed by POL-SHP-001 (Shipping & Logistics SLA Policy v1.0.0)."""
        shipment_status = str(facts.get("shipment_status", "UNKNOWN")).upper()
        delay_reason = facts.get("delay_reason") or facts.get("is_delayed")

        if shipment_status == "DELAYED" or delay_reason:
            return PolicyEvaluationResult(
                allowed=True,
                requires_approval=False,
                decision="Logistics transit delay verified under POL-SHP-001. Proactive customer notification and ticket creation authorized.",
                policy_id="POL-SHP-001",
                policy_version="1.0.0",
                matched_rules=["SHP-R02", "POL-SHP-001.R2: Proactive transit delay escalation"],
                relevant_facts={"shipment_status": shipment_status, "delay_reason": delay_reason},
                citations=citations,
            )

        return PolicyEvaluationResult(
            allowed=True,
            requires_approval=False,
            decision="Standard shipment tracking inquiry permitted under POL-SHP-001.",
            policy_id="POL-SHP-001",
            policy_version="1.0.0",
            matched_rules=["SHP-R01", "POL-SHP-001.R1: Standard tracking disclosure"],
            relevant_facts={"shipment_status": shipment_status},
            citations=citations,
        )

    def _evaluate_default(
        self,
        action: str,
        facts: Dict[str, Any],
        citations: List[KnowledgeCitation],
    ) -> PolicyEvaluationResult:
        """Default policy evaluation for general read tools and safe operations."""
        return PolicyEvaluationResult(
            allowed=True,
            requires_approval=False,
            decision=f"Operation '{action}' complies with standard operational policies.",
            policy_id="POL-GEN-001",
            policy_version="1.0.0",
            matched_rules=["POL-GEN-001.R1: General safe operations"],
            relevant_facts=facts,
            citations=citations,
        )


# Global singleton policy engine instance
policy_engine = PolicyEngine()
