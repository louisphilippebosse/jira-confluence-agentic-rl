"""
Conversations API - Chat and session management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime
import logging

from app.config import settings
from app.models.schemas import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from app.models.database import get_db, Conversation, Session as SessionModel
from app.services.graphrag.rl_service import rl_service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_orchestrator():
    """Get the agent orchestrator"""
    from app.services.core.agent_orchestrator import agent_orchestrator
    logger.info("📦 Using AgentOrchestrator (tool-agnostic)")
    return agent_orchestrator


def generate_session_title(message: str) -> str:
    """Generate a meaningful title from the first message"""
    prefixes = ['show me', 'find', 'search for', 'get', 'list', 'what', 'how', 'can you', 'please']
    msg_lower = message.lower()
    
    for prefix in prefixes:
        if msg_lower.startswith(prefix):
            message = message[len(prefix):].strip()
            break
    
    title = message.strip()
    if len(title) > 50:
        title = title[:47] + "..."
    
    return title.capitalize() if title else "New Conversation"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Send a message to the AI agent and get a response"""
    session_id = request.session_id or str(uuid.uuid4())
    is_new_session = not request.session_id
    
    try:
        # Create or update session metadata
        session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if not session:
            session_title = generate_session_title(request.message)
            session = SessionModel(
                session_id=session_id,
                title=session_title,
                message_count=0
            )
            db.add(session)
            logger.info(f"📝 Created new session: {session_id} - '{session_title}'")
        
        session.message_count += 2
        session.updated_at = datetime.utcnow()
        
        # Save user message
        user_message = Conversation(
            session_id=session_id,
            role="user",
            content=request.message,
            timestamp=datetime.utcnow()
        )
        db.add(user_message)
        db.flush()
        
        # Get conversation history
        history = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.timestamp.asc()).all()
        
        history_dicts = [{"role": h.role, "content": h.content} for h in history]
        
        # Get RL recommendation
        state_vector = rl_service.encode_state(request.message, history_dicts)
        recommended_action = rl_service.recommend_action(
            request.message, history_dicts, 
            {"message_count": session.message_count, "avg_feedback": 0.0}
        )
        
        # Get AI response
        orchestrator = get_orchestrator()
        response_text = await orchestrator.chat(
            message=request.message,
            session_id=session_id,
            conversation_history=history,
            recommended_action=recommended_action,
            context_modes=request.context_modes
        )
        
        # Save response
        assistant_message = Conversation(
            session_id=session_id,
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow()
        )
        db.add(assistant_message)
        db.flush()
        
        # Record RL interaction
        rl_service.record_interaction(
            db, session_id, assistant_message.id, state_vector, recommended_action
        )
        
        db.commit()
        db.refresh(assistant_message)
        
        return ChatResponse(
            message=response_text,
            session_id=session_id,
            timestamp=datetime.utcnow(),
            message_id=assistant_message.id
        )
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=ConversationHistory)
async def get_conversation_history(session_id: str, db: Session = Depends(get_db)):
    """Retrieve conversation history for a specific session"""
    try:
        messages = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.timestamp.asc()).all()
        
        return ConversationHistory(
            session_id=session_id,
            messages=[
                ChatMessage(role=msg.role, content=msg.content, timestamp=msg.timestamp)
                for msg in messages
            ]
        )
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_sessions(db: Session = Depends(get_db)):
    """Get all sessions with metadata"""
    try:
        sessions = db.query(SessionModel).order_by(SessionModel.updated_at.desc()).all()
        return [
            {
                "session_id": session.session_id,
                "title": session.title or "New Conversation",
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "message_count": session.message_count
            }
            for session in sessions
        ]
    except Exception as e:
        logger.error(f"Error retrieving sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_conversation(session_id: str, db: Session = Depends(get_db)):
    """Delete a conversation history and session"""
    try:
        db.query(Conversation).filter(Conversation.session_id == session_id).delete()
        db.query(SessionModel).filter(SessionModel.session_id == session_id).delete()
        db.commit()
        logger.info(f"🗑️ Deleted session: {session_id}")
        return {"message": "Conversation deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, request: dict, db: Session = Depends(get_db)):
    """Update session metadata (e.g., title)"""
    try:
        session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if "title" in request:
            session.title = request["title"]
            session.updated_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"✏️ Updated session {session_id}: title='{request.get('title')}'")
        return {"message": "Session updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
