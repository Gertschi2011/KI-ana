"""
Conversation Folders API
Allows users to organize conversations into folders
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, ForeignKey
from ...db import Base, get_db
from ...deps import get_current_user_required
import time

router = APIRouter(prefix="/api/folders", tags=["folders"])


# --- Models ---
class ConversationFolder(Base):
    __tablename__ = "conversation_folders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, default="#667eea")
    icon = Column(String, default="📁")
    sort_order = Column(Integer, default=0)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)


# --- Schemas ---
class FolderCreate(BaseModel):
    name: str
    color: Optional[str] = "#667eea"
    icon: Optional[str] = "📁"


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None


class FolderMove(BaseModel):
    conversation_ids: List[int]


# --- Routes ---
@router.get("")
def list_folders(
    current=Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """List all folders for current user"""
    uid = int(current["id"])
    folders = db.query(ConversationFolder).filter(
        ConversationFolder.user_id == uid
    ).order_by(ConversationFolder.sort_order, ConversationFolder.created_at).all()
    
    # Count conversations per folder
    from .router import Conversation
    result = []
    for f in folders:
        count = db.query(Conversation).filter(
            Conversation.user_id == uid,
            Conversation.folder_id == f.id
        ).count()
        result.append({
            "id": f.id,
            "name": f.name,
            "color": f.color,
            "icon": f.icon,
            "sort_order": f.sort_order,
            "conversation_count": count,
            "created_at": f.created_at,
            "updated_at": f.updated_at
        })
    
    return {"ok": True, "folders": result}


@router.post("")
def create_folder(
    payload: FolderCreate,
    current=Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Create a new folder"""
    uid = int(current["id"])
    
    # Check if folder name already exists
    existing = db.query(ConversationFolder).filter(
        ConversationFolder.user_id == uid,
        ConversationFolder.name == payload.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Folder with this name already exists")
    
    # Get max sort_order
    max_order = db.query(ConversationFolder).filter(
        ConversationFolder.user_id == uid
    ).count()
    
    now = int(time.time())
    folder = ConversationFolder(
        user_id=uid,
        name=payload.name,
        color=payload.color or "#667eea",
        icon=payload.icon or "📁",
        sort_order=max_order,
        created_at=now,
        updated_at=now
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    
    return {
        "ok": True,
        "folder": {
            "id": folder.id,
            "name": folder.name,
            "color": folder.color,
            "icon": folder.icon,
            "sort_order": folder.sort_order,
            "created_at": folder.created_at,
            "updated_at": folder.updated_at
        }
    }


@router.patch("/{folder_id}")
def update_folder(
    folder_id: int,
    payload: FolderUpdate,
    current=Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Update folder properties"""
    uid = int(current["id"])
    folder = db.query(ConversationFolder).filter(
        ConversationFolder.id == folder_id,
        ConversationFolder.user_id == uid
    ).first()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if payload.name is not None:
        # Check name uniqueness
        existing = db.query(ConversationFolder).filter(
            ConversationFolder.user_id == uid,
            ConversationFolder.name == payload.name,
            ConversationFolder.id != folder_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Folder with this name already exists")
        folder.name = payload.name
    
    if payload.color is not None:
        folder.color = payload.color
    if payload.icon is not None:
        folder.icon = payload.icon
    if payload.sort_order is not None:
        folder.sort_order = payload.sort_order
    
    folder.updated_at = int(time.time())
    db.commit()
    
    return {"ok": True}


@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    move_to: Optional[int] = None,
    current=Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Delete folder (optionally move conversations to another folder)"""
    uid = int(current["id"])
    folder = db.query(ConversationFolder).filter(
        ConversationFolder.id == folder_id,
        ConversationFolder.user_id == uid
    ).first()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Move conversations if target folder specified
    from .router import Conversation
    if move_to:
        target = db.query(ConversationFolder).filter(
            ConversationFolder.id == move_to,
            ConversationFolder.user_id == uid
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="Target folder not found")
        
        db.query(Conversation).filter(
            Conversation.folder_id == folder_id
        ).update({"folder_id": move_to})
    else:
        # Set to NULL (no folder)
        db.query(Conversation).filter(
            Conversation.folder_id == folder_id
        ).update({"folder_id": None})
    
    db.delete(folder)
    db.commit()
    
    return {"ok": True}


@router.post("/{folder_id}/conversations")
def move_conversations_to_folder(
    folder_id: int,
    payload: FolderMove,
    current=Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Move conversations into this folder"""
    uid = int(current["id"])
    
    # Verify folder exists and belongs to user
    folder = db.query(ConversationFolder).filter(
        ConversationFolder.id == folder_id,
        ConversationFolder.user_id == uid
    ).first()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Update conversations
    from .router import Conversation
    db.query(Conversation).filter(
        Conversation.id.in_(payload.conversation_ids),
        Conversation.user_id == uid
    ).update({"folder_id": folder_id}, synchronize_session=False)
    
    db.commit()
    
    return {"ok": True, "moved": len(payload.conversation_ids)}
