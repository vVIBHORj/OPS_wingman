"""
OpsWingman - Backend Application Entry Point (Phase 1.3 Operational REST API)

Exposes the deterministic Business Simulator and operational domain via FastAPI REST endpoints.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.config import get_settings
from database.session import SessionLocal, dispose_engines
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
    audit_router,
)

logger = logging.getLogger("opswingman.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle hook: verify database connectivity
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        logger.info("Database connectivity check succeeded during startup.")
    except Exception as exc:
        logger.warning("Database connectivity check failed during startup: %s", exc)

    yield

    # Shutdown lifecycle hook: cleanly dispose all connection pools
    logger.info("Shutting down OpsWingman API: disposing database engine pools.")
    try:
        dispose_engines()
    except Exception as exc:
        logger.warning("Error disposing database pools: %s", exc)


app = FastAPI(
    title=settings.app_name,
    description="Deterministic runtime & Intelligent Operations Platform for modern businesses",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
)

# Correlation ID Middleware (X-Request-ID)
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
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
app.include_router(audit_router)


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
    """Basic health check endpoint for liveness verification."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "services": {
            "api": "ok",
        },
    }


@app.get("/health/live", tags=["Monitoring"])
async def liveness_probe() -> Dict[str, Any]:
    """Kubernetes/Container liveness probe to verify process is alive."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Monitoring"])
@app.get("/ready", tags=["Monitoring"])
async def readiness_probe():
    """Readiness probe checking database dependency health before serving traffic."""
    db_status = "ok"
    error_msg = None
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "unavailable"
        error_msg = str(exc)
        logger.error("Readiness probe database check failed: %s", exc)

    is_ready = (db_status == "ok")
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "unready",
            "environment": settings.environment,
            "services": {
                "api": "ok",
                "database": db_status,
            },
            "error": error_msg,
        },
    )
