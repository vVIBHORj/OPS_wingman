"""
API Routers for OpsWingman.
"""

from backend.api.routers.customers import router as customers_router
from backend.api.routers.products import router as products_router
from backend.api.routers.orders import router as orders_router
from backend.api.routers.payments import router as payments_router
from backend.api.routers.shipments import router as shipments_router
from backend.api.routers.events import router as events_router
from backend.api.routers.agent import router as agent_router
from backend.api.routers.knowledge import router as knowledge_router
from backend.api.routers.approvals import router as approvals_router
from backend.api.routers.ml import router as ml_router
from backend.api.routers.operations import router as operations_router
from backend.api.routers.audit import router as audit_router

__all__ = [
    "customers_router",
    "products_router",
    "orders_router",
    "payments_router",
    "shipments_router",
    "events_router",
    "agent_router",
    "knowledge_router",
    "approvals_router",
    "ml_router",
    "operations_router",
    "audit_router",
]
