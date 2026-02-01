"""
API package - Organized by domain

Structure:
- chat/         Conversation and feedback endpoints
- knowledge/    Knowledge Graph and GraphRAG endpoints  
- agents/       Agent registry, orchestration, approvals
- system/       Health, model status, RL metrics
"""
from fastapi import APIRouter

from .chat import router as chat_router
from .knowledge import router as knowledge_router
from .agents import router as agents_router
from .system import router as system_router

# Main API router that combines all domain routers
api_router = APIRouter()
api_router.include_router(chat_router, prefix="", tags=["chat"])
api_router.include_router(knowledge_router, prefix="/kg", tags=["knowledge"])
api_router.include_router(agents_router, prefix="", tags=["agents"])
api_router.include_router(system_router, prefix="", tags=["system"])

__all__ = ["api_router", "chat_router", "knowledge_router", "agents_router", "system_router"]
