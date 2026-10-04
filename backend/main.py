"""
OpsWingman - Backend Application Entry Point (Phase 1.3 Operational REST API)

Exposes the deterministic Business Simulator and operational domain via FastAPI REST endpoints.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from simulator.exceptions import (
    EntityNotFoundError,
    InvalidStateTransitionError,
    BusinessRuleViolationError,
    SimulatorError,
)
from backend.api.routers import (
    customers_router,
    products_router,
    orders_router,
    payments_router,
    shipments_router,
    events_router,
    agent_router,
    knowledge_router,
    approvals_router,
    ml_router,
    operations_router,
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle hook
    yield
    # Shutdown lifecycle hook


app = FastAPI(
    title="OpsWingman API",
    description="Deterministic runtime & Intelligent Operations Platform for modern businesses",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Domain Exception Handlers (Mapping Simulator Errors to Standard HTTP Statuses)
# ==============================================================================

@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "EntityNotFoundError", "detail": str(exc)},
    )


@app.exception_handler(InvalidStateTransitionError)
async def invalid_state_transition_handler(request: Request, exc: InvalidStateTransitionError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "InvalidStateTransitionError",
            "detail": str(exc),
            "entity_type": exc.entity_type,
            "entity_id": exc.entity_id,
            "current_status": exc.current_status,
            "target_status": exc.target_status,
        },
    )


@app.exception_handler(BusinessRuleViolationError)
async def business_rule_violation_handler(request: Request, exc: BusinessRuleViolationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "BusinessRuleViolationError", "detail": str(exc)},
    )


@app.exception_handler(SimulatorError)
async def generic_simulator_error_handler(request: Request, exc: SimulatorError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "SimulatorError", "detail": str(exc)},
    )


# ==============================================================================
# Include Operational API Routers
# ==============================================================================

app.include_router(customers_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(shipments_router)
app.include_router(events_router)
app.include_router(agent_router)
app.include_router(knowledge_router)
app.include_router(approvals_router)
app.include_router(ml_router)
app.include_router(operations_router)


# ==============================================================================
# Base Endpoints
# ==============================================================================

@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint providing platform identification and Phase 1 status."""
    return {
        "name": "OpsWingman API",
        "phase": "Phase 1 - Operational REST API & Business Simulator",
        "status": "operational",
        "version": "0.1.0",
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Monitoring"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for container orchestration and liveness checks."""
    return {
        "status": "healthy",
        "services": {
            "api": "ok",
        },
    }
