"""
OpsWingman - Backend Application Entry Point (Phase 0 Baseline)

This is the foundational FastAPI service entry point for OpsWingman.
Business workflows, AI agents, RAG, and simulator endpoints will be added
in their respective milestones according to the project blueprint.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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


@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint providing platform identification and Phase 0 status."""
    return {
        "name": "OpsWingman API",
        "phase": "Phase 0 - Foundation",
        "status": "operational",
        "version": "0.1.0",
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Monitoring"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for Docker container orchestration and liveness checks."""
    return {
        "status": "healthy",
        "services": {
            "api": "ok",
        },
    }
