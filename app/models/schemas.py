from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatMessage(BaseModel):
    """Schema for chat messages"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None
    message_id: Optional[int] = None


class ChatRequest(BaseModel):
    """Schema for incoming chat requests"""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    context_modes: Optional[List[str]] = Field(None, description="Optional list of context modes: ['jira', 'confluence', 'web']. If None or empty, auto-detect is used")


class ChatResponse(BaseModel):
    """Schema for chat responses"""
    message: str
    session_id: str
    timestamp: datetime
    message_id: int


class ConversationHistory(BaseModel):
    """Schema for conversation history"""
    session_id: str
    messages: List[ChatMessage]


class FeedbackCreate(BaseModel):
    session_id: str
    message_id: int
    feedback_value: int = Field(..., ge=-1, le=1, description="1 for thumbs up, -1 for thumbs down, 0 for neutral")
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    session_id: str
    message_id: int
    feedback_value: int
    timestamp: datetime
    comment: Optional[str] = None

    class Config:
        from_attributes = True


class SkillCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    function_name: str
    parameters_schema: Optional[str] = None  # JSON string
    returns_schema: Optional[str] = None  # JSON string
    enabled: bool = True


class SkillUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    parameters_schema: Optional[str] = None
    returns_schema: Optional[str] = None
    enabled: Optional[bool] = None


class SkillResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    function_name: str
    parameters_schema: Optional[str]
    returns_schema: Optional[str]
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    model_name: str = "llama3.2:latest"
    system_prompt: Optional[str] = None
    is_active: bool = True
    skill_ids: Optional[List[int]] = []


class AgentUpdate(BaseModel):
    description: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    model_name: str
    system_prompt: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    skills: List[SkillResponse] = []

    class Config:
        from_attributes = True


class AgentSkillAdd(BaseModel):
    skill_id: int
    priority: int = 0
    enabled: bool = True


class GraphData(BaseModel):
    """Schema for knowledge graph visualization data"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    stats: Dict[str, Any]
