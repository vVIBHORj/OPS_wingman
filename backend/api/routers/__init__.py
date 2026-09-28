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

__all__ = [
    "customers_router",
    "products_router",
    "orders_router",
    "payments_router",
    "shipments_router",
    "events_router",
    "agent_router",
]
