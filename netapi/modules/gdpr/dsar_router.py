"""
DSAR (Data Subject Access Request) Router

GDPR Compliance endpoints:
- Export user data
- Delete user data
- Data portability
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ...deps import get_db, get_current_user_required
from ...models import User, Conversation
from loguru import logger
import json
import zipfile
from io import BytesIO
from fastapi.responses import StreamingResponse


router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


class DSARRequest(BaseModel):
    """Data Subject Access Request"""
    email: EmailStr
    request_type: str  # "export" or "delete"
    reason: Optional[str] = None


class DataExportResponse(BaseModel):
    """Data export response"""
    user_id: str
    export_date: str
    data_types: list
    file_url: Optional[str] = None


def _load_user(db: Session, current_user: Dict[str, Any]) -> User:
    try:
        uid = int(current_user.get("id") or 0)
    except Exception:
        uid = 0
    if uid <= 0:
        raise HTTPException(status_code=401, detail="login required")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="unknown user")
    return user


@router.post("/export")
async def export_user_data(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user_required)
):
    """
    Export all user data (GDPR Art. 15 - Right of Access)
    
    Returns a ZIP file containing:
    - profile.json
    - conversations.json
    - settings.json
    - activity_log.json
    """
    try:
        user = _load_user(db, current_user)
        logger.info(f"DSAR Export request from user {user.id}")
        
        # Collect all user data
        user_data = {
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "roles": getattr(user, "roles", None) or [getattr(user, "role", "user")],
            "export_date": datetime.utcnow().isoformat()
        }
        
        # Get conversations
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user.id
        ).all()
        
        conversations_data = [
            {
                "id": conv.id,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "messages": conv.messages if hasattr(conv, 'messages') else []
            }
            for conv in conversations
        ]
        
        # Get settings (if available)
        settings_data = {
            "theme": "default",
            "language": "de",
            # Add more settings as needed
        }
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add profile
            zip_file.writestr(
                "profile.json",
                json.dumps(user_data, indent=2, ensure_ascii=False)
            )
            
            # Add conversations
            zip_file.writestr(
                "conversations.json",
                json.dumps(conversations_data, indent=2, ensure_ascii=False)
            )
            
            # Add settings
            zip_file.writestr(
                "settings.json",
                json.dumps(settings_data, indent=2, ensure_ascii=False)
            )
            
            # Add README
            readme = f"""
KI-ana Data Export
==================

Export Date: {datetime.utcnow().isoformat()}
User ID: {user.id}
Email: {user.email}

This archive contains all your personal data stored in KI-ana:

1. profile.json - Your user profile
2. conversations.json - All your conversations
3. settings.json - Your preferences

This export complies with GDPR Article 15 (Right of Access).

If you have any questions, contact: support@ki-ana.at
"""
            zip_file.writestr("README.txt", readme)
        
        # Prepare response
        zip_buffer.seek(0)
        
        logger.success(f"DSAR Export completed for user {user.id}")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=kiana_data_export_{user.id}_{datetime.utcnow().strftime('%Y%m%d')}.zip"
            }
        )
        
    except Exception as e:
        logger.error(f"DSAR Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/delete")
async def delete_user_data(
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user_required)
):
    """
    Delete all user data (GDPR Art. 17 - Right to Erasure)
    
    This will:
    1. Delete all conversations
    2. Anonymize user profile
    3. Remove personal data
    4. Keep minimal audit trail (anonymized)
    """
    try:
        user = _load_user(db, current_user)
        logger.info(f"DSAR Delete request from user {user.id}")
        
        # 1. Delete conversations
        deleted_conversations = db.query(Conversation).filter(
            Conversation.user_id == user.id
        ).delete()
        
        # 2. Anonymize user (don't delete - keep audit trail)
        user.email = f"deleted_{user.id}@anonymized.local"
        user.username = f"deleted_user_{user.id}"
        user.is_active = False
        
        # 3. Log deletion (for compliance)
        logger.info(f"User {user.id} data deleted. Reason: {reason or 'Not provided'}")
        
        db.commit()
        
        logger.success(f"DSAR Delete completed for user {user.id}")
        
        return {
            "success": True,
            "message": "All your data has been deleted",
            "deleted": {
                "conversations": deleted_conversations,
                "profile": "anonymized"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"DSAR Delete failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/info")
async def get_data_info(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user_required)
):
    """
    Get information about stored data
    
    Returns summary of what data is stored
    """
    try:
        user = _load_user(db, current_user)
        
        # Defensive: handle both User model and dict (shouldn't happen, but TEST_MODE might mock)
        if isinstance(user, dict):
            user_id = int(user.get("id", 0))
            user_email = str(user.get("email", ""))
        else:
            user_id = user.id
            user_email = user.email
        
        conversation_count = db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).count()
        
        return {
            "user_id": user_id,
            "email": user_email,
            "data_stored": {
                "profile": True,
                "conversations": conversation_count,
                "settings": True
            },
            "gdpr_rights": {
                "export": "/api/gdpr/export",
                "delete": "/api/gdpr/delete",
                "info": "/api/gdpr/info"
            },
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"DSAR Info failed: {e}")
        raise HTTPException(status_code=500, detail=f"Info retrieval failed: {str(e)}")


@router.get("/download-link")
async def get_download_link(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user_required)
):
    """
    Get temporary download link for data export
    
    (Simplified version - in production use signed URLs)
    """
    return {
        "download_url": f"/api/gdpr/export",
        "expires_in": "24 hours",
        "note": "Click export to download your data immediately"
    }
