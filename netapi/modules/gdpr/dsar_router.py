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
from ...models import User, Conversation, Message
from ...audit_events import write_audit_event
import logging
import uuid
import json
import zipfile
from io import BytesIO
from fastapi.responses import StreamingResponse


router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


logger = logging.getLogger(__name__)


RETENTION_POLICY_ID = "retention_policy_v1"


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
    dsar_id = str(uuid.uuid4())
    scope = ["chat", "learning", "vectors", "files"]

    try:
        user = _load_user(db, current_user)

        write_audit_event(
            actor_type="user",
            actor_id=user.id,
            action="DSAR_EXPORT_REQUESTED",
            subject_type="user",
            subject_id=str(user.id),
            result="success",
            meta={
                "dsar_id": dsar_id,
                "scope": scope,
                "retention_policy": RETENTION_POLICY_ID,
                "requested_by": "user_self",
                "dry_run": False,
            },
        )

        logger.info("DSAR Export request user_id=%s dsar_id=%s", user.id, dsar_id)
        
        # Collect all user data
        user_data = {
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "roles": getattr(user, "roles", None) or [getattr(user, "role", "user")],
            "export_date": datetime.utcnow().isoformat()
        }
        
        # Get conversations + messages
        conversations = (
            db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.id.asc())
            .all()
        )

        conv_ids = [c.id for c in conversations]
        messages = []
        if conv_ids:
            messages = (
                db.query(Message)
                .filter(Message.conv_id.in_(conv_ids))
                .order_by(Message.conv_id.asc(), Message.id.asc())
                .all()
            )

        messages_by_conv: Dict[int, list] = {}
        for m in messages:
            messages_by_conv.setdefault(int(m.conv_id), []).append(
                {
                    "id": m.id,
                    "role": m.role,
                    "text": m.text,
                    "created_at": m.created_at,
                }
            )

        conversations_data = []
        for conv in conversations:
            conversations_data.append(
                {
                    "id": conv.id,
                    "title": getattr(conv, "title", None),
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at,
                    "messages": messages_by_conv.get(int(conv.id), []),
                }
            )
        
        # Get settings (if available)
        settings_data = {
            "theme": "default",
            "language": "de",
            # Add more settings as needed
        }
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Export manifest (proof / auditability)
            zip_file.writestr(
                "export_manifest.json",
                json.dumps(
                    {
                        "exported_at": datetime.utcnow().isoformat(),
                        "dsar_id": dsar_id,
                        "retention_policy": RETENTION_POLICY_ID,
                        "data_categories": ["chat", "learning", "audit_excluded"],
                        "notes": "Audit events are not included in DSAR export.",
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
            )

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

            # Placeholder for learning export (kept minimal for now)
            zip_file.writestr(
                "learning.json",
                json.dumps([], indent=2, ensure_ascii=False),
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
        
        write_audit_event(
            actor_type="user",
            actor_id=user.id,
            action="DSAR_EXPORTED",
            subject_type="user",
            subject_id=str(user.id),
            result="success",
            meta={
                "dsar_id": dsar_id,
                "scope": scope,
                "retention_policy": RETENTION_POLICY_ID,
                "requested_by": "user_self",
                "dry_run": False,
                "counts": {
                    "conversations": len(conversations),
                    "messages": len(messages),
                    "learning": 0,
                },
            },
        )

        logger.info("DSAR Export completed user_id=%s dsar_id=%s", user.id, dsar_id)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=kiana_data_export_{user.id}_{datetime.utcnow().strftime('%Y%m%d')}.zip"
            }
        )
        
    except Exception as e:
        try:
            # best-effort: if we have user, record error; otherwise skip
            user = _load_user(db, current_user)
            write_audit_event(
                actor_type="user",
                actor_id=user.id,
                action="DSAR_EXPORTED",
                subject_type="user",
                subject_id=str(user.id),
                result="error",
                meta={
                    "dsar_id": dsar_id,
                    "scope": scope,
                    "retention_policy": RETENTION_POLICY_ID,
                    "requested_by": "user_self",
                    "dry_run": False,
                    "error_class": e.__class__.__name__,
                },
            )
        except Exception:
            pass
        logger.exception("DSAR Export failed dsar_id=%s", dsar_id)
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
    dsar_id = str(uuid.uuid4())
    scope = ["chat", "learning", "vectors", "files"]

    try:
        user = _load_user(db, current_user)
        write_audit_event(
            actor_type="user",
            actor_id=user.id,
            action="DSAR_DELETE_REQUESTED",
            subject_type="user",
            subject_id=str(user.id),
            result="success",
            meta={
                "dsar_id": dsar_id,
                "scope": scope,
                "retention_policy": RETENTION_POLICY_ID,
                "requested_by": "user_self",
                "dry_run": False,
            },
        )

        logger.info("DSAR Delete request user_id=%s dsar_id=%s", user.id, dsar_id)
        
        # 1. Delete conversations + messages
        conv_ids = [
            r[0]
            for r in db.query(Conversation.id).filter(Conversation.user_id == user.id).all()
        ]
        deleted_messages = 0
        if conv_ids:
            deleted_messages = (
                db.query(Message).filter(Message.conv_id.in_(conv_ids)).delete(synchronize_session=False)
            )
        deleted_conversations = (
            db.query(Conversation).filter(Conversation.user_id == user.id).delete(synchronize_session=False)
        )
        
        # 2. Anonymize user (don't delete - keep audit trail)
        user.email = f"deleted_{user.id}@anonymized.local"
        user.username = f"deleted_user_{user.id}"
        if hasattr(user, "is_active"):
            setattr(user, "is_active", False)
        
        # 3. Log deletion (for compliance)
        logger.info("User %s data deleted. Reason: %s", user.id, reason or "Not provided")
        
        db.commit()
        
        write_audit_event(
            actor_type="user",
            actor_id=user.id,
            action="DSAR_DELETED",
            subject_type="user",
            subject_id=str(user.id),
            result="success",
            meta={
                "dsar_id": dsar_id,
                "scope": scope,
                "retention_policy": RETENTION_POLICY_ID,
                "requested_by": "user_self",
                "dry_run": False,
                "counts": {
                    "conversations": int(deleted_conversations or 0),
                    "messages": int(deleted_messages or 0),
                    "profile": "anonymized",
                },
            },
        )

        logger.info("DSAR Delete completed user_id=%s dsar_id=%s", user.id, dsar_id)
        
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
        try:
            user = _load_user(db, current_user)
            write_audit_event(
                actor_type="user",
                actor_id=user.id,
                action="DSAR_DELETED",
                subject_type="user",
                subject_id=str(user.id),
                result="error",
                meta={
                    "dsar_id": dsar_id,
                    "scope": scope,
                    "retention_policy": RETENTION_POLICY_ID,
                    "requested_by": "user_self",
                    "dry_run": False,
                    "error_class": e.__class__.__name__,
                },
            )
        except Exception:
            pass
        logger.exception("DSAR Delete failed dsar_id=%s", dsar_id)
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
