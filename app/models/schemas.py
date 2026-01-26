from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatMessage(BaseModel):
    """Schema for chat messages"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    """Schema for incoming chat requests"""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Schema for chat responses"""
    message: str
    session_id: str
    timestamp: datetime


class ConversationHistory(BaseModel):
    """Schema for conversation history"""
    session_id: str
    messages: List[ChatMessage]
