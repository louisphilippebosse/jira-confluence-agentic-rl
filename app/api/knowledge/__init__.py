"""
Knowledge API module - Knowledge Graph and GraphRAG endpoints
"""
from fastapi import APIRouter

from .graph import router as graph_router
from .maintenance import router as maintenance_router

router = APIRouter()
router.include_router(graph_router, tags=["knowledge-graph"])
router.include_router(maintenance_router, prefix="/maintenance", tags=["kg-maintenance"])

__all__ = ["router"]
