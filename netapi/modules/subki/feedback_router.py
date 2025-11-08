"""
Sub-KI Feedback API Router

API endpoints for Sub-KI to Mother-KI communication.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
from .feedback_queue import get_feedback_queue, FeedbackEvent
from loguru import logger


router = APIRouter(prefix="/api/subki/feedback", tags=["subki"])


class FeedbackSubmission(BaseModel):
    """Feedback submission from Sub-KI"""
    sub_ki_id: str
    event_type: str
    data: Dict[str, Any]
    priority: Optional[int] = 5


@router.post("/submit")
async def submit_feedback(submission: FeedbackSubmission):
    """
    Submit feedback from Sub-KI to Mother-KI
    
    Event Types:
    - learning: Learning data/patterns
    - error: Error reports
    - success: Success metrics
    - block_share: Blockchain block sharing
    """
    try:
        queue = get_feedback_queue()
        
        event = FeedbackEvent(
            sub_ki_id=submission.sub_ki_id,
            event_type=submission.event_type,
            timestamp=datetime.now().isoformat(),
            data=submission.data,
            priority=submission.priority
        )
        
        await queue.enqueue(event)
        
        logger.info(f"Feedback received from {submission.sub_ki_id}")
        
        return {
            "success": True,
            "message": "Feedback received",
            "event_id": f"{submission.sub_ki_id}_{datetime.now().timestamp()}"
        }
        
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_queue_status():
    """Get feedback queue status"""
    try:
        queue = get_feedback_queue()
        stats = queue.get_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Status retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def process_queue():
    """
    Manually trigger queue processing
    (Normally runs on schedule)
    """
    try:
        queue = get_feedback_queue()
        await queue.process_queue()
        
        return {
            "success": True,
            "message": "Queue processed",
            "processed": queue.processed_count
        }
        
    except Exception as e:
        logger.error(f"Queue processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
