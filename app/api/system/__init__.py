"""
System API module - Health, status, and metrics endpoints
"""
from fastapi import APIRouter

from .health import router as health_router
from .model import router as model_router
from .metrics import router as metrics_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(model_router, tags=["model-status"])
router.include_router(metrics_router, prefix="/rl", tags=["rl-metrics"])

__all__ = ["router"]
