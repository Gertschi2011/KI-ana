"""
Feedback Sender - OS to Mother-KI

Sends feedback events from KI-ana OS (Sub-KI) to Mother-KI backend.
"""

import aiohttp
from typing import Dict, Any
from loguru import logger
from datetime import datetime


class FeedbackSender:
    """
    Sends feedback to Mother-KI
    
    Event Types:
    - learning: User interactions, patterns
    - error: System errors
    - success: Success metrics
    - block_share: Share blockchain blocks
    """
    
    def __init__(self, mother_ki_url: str = "http://localhost:8080"):
        self.mother_ki_url = mother_ki_url
        self.sub_ki_id = "kiana-os-local"  # Can be made configurable
        
    async def send_learning(self, user_input: str, system_response: str, feedback_score: float = None):
        """Send learning feedback"""
        await self._send_feedback(
            event_type="learning",
            data={
                "user_input": user_input,
                "system_response": system_response,
                "feedback_score": feedback_score,
                "timestamp": datetime.now().isoformat()
            },
            priority=6
        )
    
    async def send_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Send error report"""
        await self._send_feedback(
            event_type="error",
            data={
                "error_type": error_type,
                "error": error_message,
                "context": context or {},
                "timestamp": datetime.now().isoformat()
            },
            priority=8  # High priority for errors
        )
    
    async def send_success(self, metric_name: str, value: float, metadata: Dict[str, Any] = None):
        """Send success metric"""
        await self._send_feedback(
            event_type="success",
            data={
                "metric": metric_name,
                "value": value,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            },
            priority=4
        )
    
    async def share_block(self, block_data: Dict[str, Any]):
        """Share blockchain block with Mother-KI"""
        await self._send_feedback(
            event_type="block_share",
            data=block_data,
            priority=7
        )
    
    async def _send_feedback(self, event_type: str, data: Dict[str, Any], priority: int = 5):
        """Send feedback to Mother-KI"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "sub_ki_id": self.sub_ki_id,
                    "event_type": event_type,
                    "data": data,
                    "priority": priority
                }
                
                async with session.post(
                    f"{self.mother_ki_url}/api/subki/feedback/submit",
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logger.success(f"Feedback sent to Mother-KI: {event_type}")
                    else:
                        logger.warning(f"Feedback failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to send feedback: {e}")


# Singleton
_feedback_sender_instance = None


async def get_feedback_sender() -> FeedbackSender:
    """Get or create feedback sender singleton"""
    global _feedback_sender_instance
    
    if _feedback_sender_instance is None:
        _feedback_sender_instance = FeedbackSender()
    
    return _feedback_sender_instance
