"""
Feedback API - User feedback collection endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import logging

from app.models.database import get_db, Feedback, Conversation
from app.models.schemas import FeedbackCreate, FeedbackResponse
from app.services.graphrag.rl_service import rl_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    """Submit user feedback on an AI response"""
    try:
        message = db.query(Conversation).filter(Conversation.id == feedback.message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        existing = db.query(Feedback).filter(Feedback.message_id == feedback.message_id).first()
        
        if existing:
            existing.feedback_value = feedback.feedback_value
            existing.comment = feedback.comment
            db.commit()
            db.refresh(existing)
            logger.info(f"📝 Updated feedback for message {feedback.message_id}: {feedback.feedback_value}")
            rl_service.update_reward_from_feedback(db, feedback.message_id, feedback.feedback_value)
            return existing
        else:
            db_feedback = Feedback(
                session_id=feedback.session_id,
                message_id=feedback.message_id,
                feedback_value=feedback.feedback_value,
                comment=feedback.comment
            )
            db.add(db_feedback)
            db.commit()
            db.refresh(db_feedback)
            logger.info(f"👍 New feedback for message {feedback.message_id}: {feedback.feedback_value}")
            rl_service.update_reward_from_feedback(db, feedback.message_id, feedback.feedback_value)
            return db_feedback
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error submitting feedback: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=List[FeedbackResponse])
async def get_session_feedback(session_id: str, db: Session = Depends(get_db)):
    """Get all feedback for a session"""
    try:
        feedback = db.query(Feedback).filter(Feedback.session_id == session_id).all()
        return feedback
    except Exception as e:
        logger.error(f"❌ Error getting session feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/message/{message_id}", response_model=FeedbackResponse)
async def get_message_feedback(message_id: int, db: Session = Depends(get_db)):
    """Get feedback for a specific message"""
    try:
        feedback = db.query(Feedback).filter(Feedback.message_id == message_id).first()
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        return feedback
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting message feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{feedback_id}")
async def delete_feedback(feedback_id: int, db: Session = Depends(get_db)):
    """Delete feedback"""
    try:
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        
        db.delete(feedback)
        db.commit()
        logger.info(f"🗑️ Deleted feedback {feedback_id}")
        return {"message": "Feedback deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting feedback: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
