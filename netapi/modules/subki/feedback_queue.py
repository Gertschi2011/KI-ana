"""
Sub-KI Feedback Queue

Handles feedback and learning data from Sub-KIs (Kind → Mutter).
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
from loguru import logger
import json
from pathlib import Path


class FeedbackEvent(BaseModel):
    """Feedback event from Sub-KI"""
    sub_ki_id: str
    event_type: str  # "learning", "error", "success", "block_share"
    timestamp: str
    data: Dict[str, Any]
    priority: int = 5  # 1-10 (10 = highest)


class FeedbackQueue:
    """
    Queue for Sub-KI feedback events
    
    Handles:
    - Learning feedback
    - Error reports
    - Success metrics
    - Block sharing
    - Bidirectional sync
    """
    
    def __init__(self, queue_dir: str = "/tmp/kiana_feedback"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        self.queue: List[FeedbackEvent] = []
        self.processed_count = 0
        
    async def enqueue(self, event: FeedbackEvent):
        """Add event to queue"""
        try:
            # Add to in-memory queue
            self.queue.append(event)
            
            # Persist to disk (for reliability)
            event_file = self.queue_dir / f"event_{datetime.now().timestamp()}_{event.sub_ki_id}.json"
            with open(event_file, 'w') as f:
                json.dump(event.dict(), f, indent=2)
            
            logger.info(f"Feedback enqueued from {event.sub_ki_id}: {event.event_type}")
            
            # Process high-priority events immediately
            if event.priority >= 8:
                await self._process_event(event)
            
        except Exception as e:
            logger.error(f"Failed to enqueue feedback: {e}")
    
    async def process_queue(self):
        """Process all queued events"""
        logger.info(f"Processing {len(self.queue)} feedback events...")
        
        # Sort by priority
        self.queue.sort(key=lambda e: e.priority, reverse=True)
        
        for event in self.queue:
            await self._process_event(event)
        
        self.processed_count += len(self.queue)
        self.queue.clear()
        
        logger.success(f"Processed {self.processed_count} total events")
    
    async def _process_event(self, event: FeedbackEvent):
        """Process single feedback event"""
        try:
            if event.event_type == "learning":
                await self._process_learning(event)
            elif event.event_type == "error":
                await self._process_error(event)
            elif event.event_type == "success":
                await self._process_success(event)
            elif event.event_type == "block_share":
                await self._process_block_share(event)
            else:
                logger.warning(f"Unknown event type: {event.event_type}")
                
        except Exception as e:
            logger.error(f"Event processing failed: {e}")
    
    async def _process_learning(self, event: FeedbackEvent):
        """Process learning feedback"""
        logger.info(f"Learning feedback from {event.sub_ki_id}")
        
        # Extract learning data
        data = event.data
        
        # Store in learning hub (if available)
        try:
            from netapi.learning.hub import get_learning_hub
            hub = get_learning_hub()
            
            await hub.record_interaction(
                user_input=data.get("user_input", ""),
                system_response=data.get("system_response", ""),
                user_feedback_score=data.get("feedback_score"),
                metadata={
                    "sub_ki_id": event.sub_ki_id,
                    "timestamp": event.timestamp
                }
            )
        except Exception as e:
            logger.warning(f"Learning hub not available: {e}")
    
    async def _process_error(self, event: FeedbackEvent):
        """Process error report"""
        logger.warning(f"Error reported by {event.sub_ki_id}: {event.data.get('error')}")
        
        # Log error for analysis
        error_log = self.queue_dir / "errors.log"
        with open(error_log, 'a') as f:
            f.write(json.dumps({
                "sub_ki_id": event.sub_ki_id,
                "timestamp": event.timestamp,
                "error": event.data
            }) + "\n")
    
    async def _process_success(self, event: FeedbackEvent):
        """Process success metrics"""
        logger.success(f"Success metric from {event.sub_ki_id}")
        
        # Update Sub-KI stats
        # (Could be stored in database)
    
    async def _process_block_share(self, event: FeedbackEvent):
        """Process block sharing from Sub-KI"""
        logger.info(f"Block shared by {event.sub_ki_id}")
        
        # Add block to Mother-KI blockchain
        try:
            from netapi.blockchain.chain import get_chain
            chain = get_chain()
            
            block_data = event.data
            chain.add_block(block_data)
            
            logger.success(f"Block added to chain from {event.sub_ki_id}")
        except Exception as e:
            logger.warning(f"Blockchain not available: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "queued_events": len(self.queue),
            "processed_total": self.processed_count,
            "queue_by_priority": self._count_by_priority(),
            "queue_by_type": self._count_by_type()
        }
    
    def _count_by_priority(self) -> Dict[int, int]:
        """Count events by priority"""
        counts = {}
        for event in self.queue:
            counts[event.priority] = counts.get(event.priority, 0) + 1
        return counts
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count events by type"""
        counts = {}
        for event in self.queue:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts


# Singleton
_feedback_queue_instance = None


def get_feedback_queue() -> FeedbackQueue:
    """Get or create feedback queue singleton"""
    global _feedback_queue_instance
    
    if _feedback_queue_instance is None:
        _feedback_queue_instance = FeedbackQueue()
    
    return _feedback_queue_instance
