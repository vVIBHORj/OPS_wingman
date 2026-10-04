"""
Ops Agent Service Facade.
Provides service methods for running workflows, retrieving runs, and discovering tools.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.agents.ops_agent import OpsAgent
from backend.ml import MLRiskService, ml_risk_service
from backend.resilience import (
    IdempotencyService,
    RetryExecutor,
    ResilientToolExecutor,
    idempotency_service as default_idempotency_service,
    resilient_tool_executor as default_resilient_tool_executor,
)
from backend.tools.base import ToolDefinition, ToolRegistry
from backend.tools.registry import create_default_tool_registry
from backend.verification import StateVerificationService, state_verification_service
from backend.workflows.state import WorkflowRunRecord
from backend.workflows.checkpoint import checkpoint_store


class OpsAgentService:
    """Service facade for managing agent executions and workflow lifecycle."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        verification_service: Optional[StateVerificationService] = None,
        risk_service: Optional[MLRiskService] = None,
        idempotency_service: Optional[IdempotencyService] = None,
        retry_executor: Optional[RetryExecutor] = None,
        resilience_wrapper: Optional[ResilientToolExecutor] = None,
    ) -> None:
        self.tool_registry = tool_registry or create_default_tool_registry()
        self.verification_service = verification_service or state_verification_service
        self.risk_service = risk_service or ml_risk_service
        self.idempotency_service = idempotency_service or default_idempotency_service
        self.retry_executor = retry_executor
        self.resilience_wrapper = resilience_wrapper or default_resilient_tool_executor
        self.agent = OpsAgent(
            tool_registry=self.tool_registry,
            verification_service=self.verification_service,
            risk_service=self.risk_service,
            idempotency_service=self.idempotency_service,
            retry_executor=self.retry_executor,
            resilience_wrapper=self.resilience_wrapper,
        )

    def execute_workflow(
        self,
        db: Session,
        input_text: str,
        order_number: Optional[str] = None,
        customer_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> WorkflowRunRecord:
        """Executes a workflow run synchronously within the database session."""
        return self.agent.run(
            input_text=input_text,
            order_number=order_number,
            customer_id=customer_id,
            db=db,
            workflow_id=workflow_id,
        )

    def get_run(self, run_id: str) -> Optional[WorkflowRunRecord]:
        """Retrieves a workflow run record by run ID."""
        return checkpoint_store.get(run_id)

    def list_runs(self, limit: int = 50) -> List[WorkflowRunRecord]:
        """Lists recent workflow run checkpoints."""
        return checkpoint_store.list_runs(limit=limit)

    def resume_workflow(
        self,
        run_id: str,
        db: Session,
        approved: bool,
        reason: Optional[str] = None,
    ) -> WorkflowRunRecord:
        """Resumes a paused workflow run with an approval decision."""
        return self.agent.resume(
            run_id=run_id,
            approved=approved,
            db=db,
            reason=reason,
        )

    def resume_approved_action(
        self,
        run_id: str,
        db: Session,
        approved: bool = True,
        reason: Optional[str] = None,
    ) -> WorkflowRunRecord:
        """Resumes an approved action with post-action verification."""
        return self.agent.resume_approved_action(
            run_id=run_id,
            approved=approved,
            db=db,
            reason=reason,
        )

    def list_tools(self) -> List[ToolDefinition]:
        """Lists all registered tools."""
        return self.tool_registry.list_tools()


# Default singleton service instance
agent_service = OpsAgentService()

