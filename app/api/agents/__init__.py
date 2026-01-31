"""
Agents API module - Agent, Skills, and Approvals endpoints
"""
from fastapi import APIRouter

from .registry import router as registry_router
from .orchestration import router as orchestration_router
from .approvals import router as approvals_router

router = APIRouter()
router.include_router(registry_router, tags=["agent-registry"])
router.include_router(orchestration_router, tags=["orchestration"])
router.include_router(approvals_router, prefix="/approvals", tags=["approvals"])

__all__ = ["router"]
