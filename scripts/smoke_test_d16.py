import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.agents.ops_agent import OpsAgent
from backend.workflows.checkpoint import checkpoint_store
from backend.workflows.state import WorkflowRunRecord, WorkflowState, WorkflowStepRecord

client = TestClient(app)

print("=== 1. RISK ENDPOINTS SMOKE TEST ===")
r_info = client.get("/risk/model-info")
print(f"GET /risk/model-info -> status: {r_info.status_code}, model_version: {r_info.json().get('model_version')}")

r_assess = client.post("/risk/assess", json={
    "custom_features": {
        "order_amount": 25000.0,
        "account_age_days": 5.0,
        "refund_count": 3,
        "refund_ratio": 0.6,
        "delivery_delay_hours": 0.0,
        "payment_attempts": 2,
        "failed_payment_count": 1,
        "is_first_order": False,
    }
})
data = r_assess.json()
print(f"POST /risk/assess -> status: {r_assess.status_code}, risk_score: {data.get('risk_score')}, risk_band: {data.get('risk_band')}, is_high_risk: {data.get('is_high_risk')}")

print("\n=== 2. OPERATIONS ENDPOINTS SMOKE TEST ===")
r_summary = client.get("/operations/summary")
print(f"GET /operations/summary -> status: {r_summary.status_code}, total_runs: {r_summary.json().get('total_runs')}")

# Create a sample run record
run_id = str(uuid.uuid4())
run = WorkflowRunRecord(
    run_id=run_id,
    workflow_id="wf-smoke-test",
    state=WorkflowState.COMPLETED,
    input_text="Smoke test order check",
    final_response="Order ord-smoke is CONFIRMED.",
    steps=[
        WorkflowStepRecord(step_name="interpret_request", state=WorkflowState.RUNNING),
        WorkflowStepRecord(step_name="execute_tools", tool_name="get_order", state=WorkflowState.RUNNING),
        WorkflowStepRecord(step_name="synthesize_response", state=WorkflowState.COMPLETED),
    ],
    resilience_records=[
        {"tool_name": "get_order", "attempts": 1, "final_status": "COMPLETED", "timed_out": False, "is_cached": False}
    ],
    verification_results=[
        {"entity_type": "order", "entity_id": "ord-smoke", "target_state": "CONFIRMED", "actual_state": "CONFIRMED", "status": "VERIFIED", "verified": True}
    ],
    risk_assessment={
        "model_name": "OperationalRiskModel",
        "model_version": "v1.0.0",
        "risk_score": 0.15,
        "risk_band": "LOW",
        "is_high_risk": False,
        "anomaly": {"is_anomaly": False, "anomaly_flags": []}
    }
)
checkpoint_store.save(run)

r_detail = client.get(f"/operations/runs/{run_id}")
print(f"GET /operations/runs/{{run_id}} -> status: {r_detail.status_code}, current_step: {r_detail.json().get('current_step')}, state: {r_detail.json().get('state')}")

r_steps = client.get(f"/operations/runs/{run_id}/steps")
print(f"GET /operations/runs/{{run_id}}/steps -> status: {r_steps.status_code}, step_count: {len(r_steps.json())}")

r_telem = client.get(f"/operations/runs/{run_id}/telemetry")
print(f"GET /operations/runs/{{run_id}}/telemetry -> status: {r_telem.status_code}, executed_tools: {r_telem.json().get('executed_tools')}, risk_score: {r_telem.json().get('risk_telemetry', {}).get('risk_score')}")

print("\n=== 3. OPSAGENT GRAPH INSTANTIATION & NODES ===")
agent = OpsAgent()
print(f"OpsAgent graph type: {type(agent.graph).__name__}")
print("OpsAgent graph nodes:")
for node in agent.graph.nodes:
    print(f"  - {node}")
