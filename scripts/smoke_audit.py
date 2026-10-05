import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import uuid
from decimal import Decimal

from database.session import SessionLocal
from database.models import Customer, Order, Product
from database.models.enums import OrderStatus
from backend.agents.ops_agent import OpsAgent
from backend.audit import audit_service


def run_smoke_test():
    session = SessionLocal()
    try:
        # Check or seed customer
        cust = session.query(Customer).first()
        if not cust:
            cust = Customer(
                email="smoke.user@example.com",
                first_name="Smoke",
                last_name="Tester",
                city="Bengaluru",
                state="Karnataka",
                pincode="560001",
                phone="+919111122223",
            )
            session.add(cust)
            session.commit()
            session.refresh(cust)

        # Seed test order
        order_num = f"ORD-SMOKE-{uuid.uuid4().hex[:6].upper()}"
        order = Order(
            customer_id=cust.id,
            order_number=order_num,
            status=OrderStatus.PENDING,
            total_amount=Decimal("12500.00"),
            currency="INR",
            shipping_city="Bengaluru",
            shipping_pincode="560001",
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        print(f"[SMOKE] Created Order: {order_num} (ID: {order.id})")

        # 1. Execute agent run
        agent = OpsAgent()
        run_id = f"smoke-run-{uuid.uuid4()}"
        print(f"[SMOKE] Running OpsAgent with run_id={run_id}...")

        run_record = agent.run(
            input_text=f"Please cancel my order {order_num} immediately.",
            order_number=order_num,
            customer_id=str(cust.id),
            db=session,
            run_id=run_id,
        )
        print(f"[SMOKE] Agent Run State: {run_record.state.value}")

        # If approval required, simulate supervisor approval resume
        if run_record.state.value == "WAITING_FOR_APPROVAL":
            print(f"[SMOKE] Workflow paused for approval. Resuming with approval...")
            resumed_record = agent.resume(
                run_id=run_id,
                approved=True,
                db=session,
                reason="Smoke test approval granted by test operator.",
            )
            print(f"[SMOKE] Resumed State: {resumed_record.state.value}")

        # 2. Retrieve audit timeline
        timeline = audit_service.get_timeline(run_id=run_id, session=session)
        print("\n" + "=" * 80)
        print(f"AUDIT TIMELINE FOR RUN: {timeline.run_id}")
        print(f"Total Events: {timeline.total_events}")
        print("=" * 80)

        all_correlated = True
        for i, ev in enumerate(timeline.events, 1):
            is_match = (ev.run_id == run_id)
            if not is_match:
                all_correlated = False
            print(
                f"{i:2d}. [{ev.timestamp.strftime('%H:%M:%S.%f')[:-3]}] "
                f"Type: {ev.event_type.value:<24} | "
                f"Actor: {ev.actor:<12} | "
                f"Success: {str(ev.success):<5} | "
                f"RunID: {ev.run_id}"
            )
            if ev.risk_assessment_summary:
                print(f"    -> ML Risk Provenance: model={ev.risk_assessment_summary.get('model_name')} v{ev.risk_assessment_summary.get('model_version')}, score={ev.risk_assessment_summary.get('risk_score')}, band={ev.risk_assessment_summary.get('risk_band')}")
            if ev.policy_decision:
                print(f"    -> Policy Decision: policy_id={ev.policy_decision.get('policy_id')}, decision={ev.policy_decision.get('decision')}, allowed={ev.policy_decision.get('allowed')}")
            if ev.verification_status:
                print(f"    -> Verification: status={ev.verification_status}, target={ev.metadata_provenance.get('target_state')}, actual={ev.metadata_provenance.get('actual_state')}")

        print("=" * 80)
        print(f"All {timeline.total_events} events correlated by run_id: {all_correlated}")
        assert all_correlated, "Mismatch in event run_id correlation!"
        print("[SMOKE] TEST PASSED SUCCESSFULLY!\n")

    finally:
        session.close()


if __name__ == "__main__":
    run_smoke_test()
