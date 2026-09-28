"""
Agent API Router (Phase 2 - Deliverables D-07, D-08, D-09).
Exposes the LangGraph Ops Agent, Workflow Run Checkpoints, and Tool Registry.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from backend.agents.service import agent_service
from backend.api.schemas import (
    AgentRunRequest,
    WorkflowResumeRequest,
    WorkflowRunResponse,
    ToolMetadataResponse,
)

router = APIRouter(prefix="/agent", tags=["Agent & Workflows"])


@router.post("/run", response_model=WorkflowRunResponse, status_code=status.HTTP_200_OK)
def run_agent_workflow(
    payload: AgentRunRequest,
    db: Session = Depends(get_db),
) -> WorkflowRunResponse:
    """
    Triggers the LangGraph Ops Agent on an input request or operational event.
    """
    run_record = agent_service.execute_workflow(
        db=db,
        input_text=payload.input_text,
        order_number=payload.order_number,
        customer_id=payload.customer_id,
        workflow_id=payload.workflow_id,
    )
    return WorkflowRunResponse.model_validate(run_record)


@router.post("/runs/{run_id}/resume", response_model=WorkflowRunResponse, status_code=status.HTTP_200_OK)
def resume_workflow_run(
    run_id: str,
    payload: WorkflowResumeRequest,
    db: Session = Depends(get_db),
) -> WorkflowRunResponse:
    """
    Resumes an approval-gated workflow execution with operator decision.
    """
    try:
        run_record = agent_service.resume_workflow(
            run_id=run_id,
            db=db,
            approved=payload.approved,
            reason=payload.reason,
        )
        return WorkflowRunResponse.model_validate(run_record)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/runs", response_model=List[WorkflowRunResponse])
def list_workflow_runs() -> List[WorkflowRunResponse]:
    """
    Lists recent workflow execution checkpoints.
    """
    runs = agent_service.list_runs()
    return [WorkflowRunResponse.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(run_id: str) -> WorkflowRunResponse:
    """
    Retrieves the execution status and trace history of a workflow run.
    """
    run_record = agent_service.get_run(run_id)
    if not run_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{run_id}' not found.",
        )
    return WorkflowRunResponse.model_validate(run_record)



@router.get("/tools", response_model=List[ToolMetadataResponse])
def list_tools() -> List[ToolMetadataResponse]:
    """
    Lists all registered operational tools, schemas, and risk tiers.
    """
    tools = agent_service.list_tools()
    return [
        ToolMetadataResponse(
            name=t.name,
            description=t.description,
            tool_type=t.tool_type.value,
            risk_level=t.risk_level.value,
        )
        for t in tools
    ]
