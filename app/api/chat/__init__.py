"""
Chat API module - Conversation and feedback endpoints
"""
from fastapi import APIRouter

from .conversations import router as conversations_router
from .feedback import router as feedback_router

router = APIRouter()
router.include_router(conversations_router, tags=["conversations"])
router.include_router(feedback_router, prefix="/feedback", tags=["feedback"])

__all__ = ["router"]
