from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from app.models.schemas import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from app.models.database import get_db, Conversation
from app.services.ai_agent_service import ai_agent_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a message to the AI agent and get a response
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Save user message to database
        user_message = Conversation(
            session_id=session_id,
            role="user",
            content=request.message,
            timestamp=datetime.utcnow()
        )
        db.add(user_message)
        db.commit()
        
        # Get AI response
        response_text = await ai_agent_service.chat(request.message, session_id)
        
        # Save assistant response to database
        assistant_message = Conversation(
            session_id=session_id,
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow()
        )
        db.add(assistant_message)
        db.commit()
        
        return ChatResponse(
            message=response_text,
            session_id=session_id,
            timestamp=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
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


@router.get("/sessions", response_model=List[str])
async def get_sessions(db: Session = Depends(get_db)):
    """
    Get all session IDs
    """
    try:
        sessions = db.query(Conversation.session_id).distinct().all()
        return [session[0] for session in sessions]
    except Exception as e:
        logger.error(f"Error retrieving sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversation/{session_id}")
async def delete_conversation(session_id: str, db: Session = Depends(get_db)):
    """
    Delete a conversation history
    """
    try:
        db.query(Conversation).filter(Conversation.session_id == session_id).delete()
        db.commit()
        return {"message": "Conversation deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
