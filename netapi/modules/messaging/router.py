"""
P2P Messaging API Router

REST API für verschlüsselte P2P-Nachrichten.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from p2p_messaging import get_p2p_messaging, PlainMessage
    MESSAGING_AVAILABLE = True
except Exception as e:
    print(f"Warning: P2P Messaging not available: {e}")
    MESSAGING_AVAILABLE = False

router = APIRouter(prefix="/api/messaging", tags=["messaging"])


# Request/Response Models
class SendMessageRequest(BaseModel):
    """Request to send a message."""
    recipient_id: str = Field(..., description="Recipient device ID")
    text: str = Field(..., description="Message text")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class MessageResponse(BaseModel):
    """Message response."""
    message_id: str
    status: str


# Endpoints
@router.post("/send")
async def send_message(request: SendMessageRequest):
    """
    Send encrypted message to peer.
    
    Message is E2E encrypted with NaCl and queued for delivery.
    """
    if not MESSAGING_AVAILABLE:
        raise HTTPException(503, "P2P Messaging not available")
    
    try:
        messaging = get_p2p_messaging()
        
        message_id = messaging.send_message(
            recipient_id=request.recipient_id,
            text=request.text,
            metadata=request.metadata
        )
        
        return {
            "ok": True,
            "message_id": message_id,
            "status": "sent"
        }
    
    except Exception as e:
        raise HTTPException(500, f"Send error: {e}")


@router.post("/retry")
async def retry_pending():
    """
    Retry sending pending messages.
    
    Useful after network reconnection.
    """
    if not MESSAGING_AVAILABLE:
        raise HTTPException(503, "P2P Messaging not available")
    
    try:
        messaging = get_p2p_messaging()
        messaging.retry_pending_messages()
        
        return {
            "ok": True,
            "message": "Retry initiated"
        }
    
    except Exception as e:
        raise HTTPException(500, f"Retry error: {e}")


@router.get("/stats")
async def get_stats():
    """Get messaging statistics."""
    if not MESSAGING_AVAILABLE:
        raise HTTPException(503, "P2P Messaging not available")
    
    try:
        messaging = get_p2p_messaging()
        stats = messaging.get_stats()
        
        return {
            "ok": True,
            "stats": stats
        }
    
    except Exception as e:
        raise HTTPException(500, f"Stats error: {e}")


@router.get("/public-key")
async def get_public_key():
    """Get this device's public encryption key."""
    if not MESSAGING_AVAILABLE:
        raise HTTPException(503, "P2P Messaging not available")
    
    try:
        messaging = get_p2p_messaging()
        
        return {
            "ok": True,
            "public_key": messaging.get_public_key(),
            "device_id": messaging.device_id
        }
    
    except Exception as e:
        raise HTTPException(500, f"Error: {e}")


@router.get("/health")
async def health_check():
    """Check if messaging service is healthy."""
    return {
        "ok": True,
        "available": MESSAGING_AVAILABLE,
        "service": "P2P Messaging (E2E Encrypted)"
    }
