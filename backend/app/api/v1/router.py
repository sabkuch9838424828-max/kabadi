"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    collectors,
    lots,
    ml,
    prices,
    recycler_console,
    recyclers,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(collectors.router)
api_router.include_router(lots.router)
api_router.include_router(recyclers.router)
api_router.include_router(recycler_console.router)
api_router.include_router(prices.router)
api_router.include_router(ml.router)
api_router.include_router(admin.router)
