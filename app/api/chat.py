from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from app.models.schemas import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from app.models.database import get_db, Conversation, Session as SessionModel
from app.services.ai_agent_service import ai_agent_service
from app.services.rl_service import rl_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def generate_session_title(message: str) -> str:
    """Generate a meaningful title from the first message"""
    # Remove common prefixes
    prefixes = ['show me', 'find', 'search for', 'get', 'list', 'what', 'how', 'can you', 'please']
    msg_lower = message.lower()
    
    for prefix in prefixes:
        if msg_lower.startswith(prefix):
            message = message[len(prefix):].strip()
            break
    
    # Capitalize and truncate
    title = message.strip()
    if len(title) > 50:
        title = title[:47] + "..."
    
    return title.capitalize() if title else "New Conversation"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a message to the AI agent and get a response
    """
    # Generate session ID if not provided
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
        
        session.message_count += 2  # user + assistant
        session.updated_at = datetime.utcnow()
        
        # Save user message to database
        user_message = Conversation(
            session_id=session_id,
            role="user",
            content=request.message,
            timestamp=datetime.utcnow()
        )
        db.add(user_message)
        db.flush()  # Get the message ID
        
        # Get conversation history for context
        history = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.timestamp.asc()).all()
        
        # Convert to dict format for RL service
        history_dicts = [{"role": h.role, "content": h.content} for h in history]
        
        # Get RL recommendation for action
        state_vector = rl_service.encode_state(request.message, history_dicts)
        recommended_action = rl_service.recommend_action(
            request.message, history_dicts, 
            {"message_count": session.message_count, "avg_feedback": 0.0}
        )
        
        # Get AI response with history
        response_text = await ai_agent_service.chat(
            message=request.message,
            session_id=session_id,
            conversation_history=history,
            recommended_action=recommended_action
        )
        
        # Save assistant response to database
        assistant_message = Conversation(
            session_id=session_id,
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow()
        )
        db.add(assistant_message)
        db.flush()  # Get the message ID
        
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


@router.get("/conversation/{session_id}", response_model=ConversationHistory)
async def get_conversation_history(session_id: str, db: Session = Depends(get_db)):
    """
    Retrieve conversation history for a specific session
    """
    try:
        messages = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.timestamp.asc()).all()
        
        return ConversationHistory(
            session_id=session_id,
            messages=[
                ChatMessage(
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.timestamp
                )
                for msg in messages
            ]
        )
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_sessions(db: Session = Depends(get_db)):
    """
    Get all sessions with metadata
    """
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


@router.delete("/conversation/{session_id}")
async def delete_conversation(session_id: str, db: Session = Depends(get_db)):
    """
    Delete a conversation history and session
    """
    try:
        # Delete all conversation messages
        db.query(Conversation).filter(Conversation.session_id == session_id).delete()
        
        # Delete the session itself
        db.query(SessionModel).filter(SessionModel.session_id == session_id).delete()
        
        db.commit()
        logger.info(f"🗑️ Deleted session: {session_id}")
        return {"message": "Conversation deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
