"""
Folders Management for Chat Conversations
Professional folder organization system
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import time
from sqlalchemy import select, func
from ...db import get_db
from ...models import Conversation
from ...deps import get_current_user_required

router = APIRouter(prefix="/api/folders", tags=["folders"])

# Folder Model (dynamically created if not exists)
try:
    from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime
    from sqlalchemy.sql import func as sql_func
    from ...db import Base, engine
    
    class Folder(Base):
        __tablename__ = 'folders'
        
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
        name = Column(String(100), nullable=False)
        color = Column(String(20), default='#667eea')
        icon = Column(String(10), default='📁')
        position = Column(Integer, default=0)
        created_at = Column(DateTime, default=sql_func.now())
        updated_at = Column(DateTime, default=sql_func.now(), onupdate=sql_func.now())
except Exception:
    Folder = None

# Pydantic models
class FolderCreate(BaseModel):
    name: str
    color: Optional[str] = '#667eea'
    icon: Optional[str] = '📁'

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    position: Optional[int] = None

class FolderResponse(BaseModel):
    id: int
    name: str
    color: str
    icon: str
    position: int
    conversation_count: int = 0

class MoveToFolderRequest(BaseModel):
    conversation_ids: List[int]
    folder_id: Optional[int] = None  # None = remove from folder

@router.get("")
async def list_folders(db=Depends(get_db), current=Depends(get_current_user_required)):
    """List all folders for current user with conversation counts"""
    if not Folder:
        return {"ok": True, "folders": []}
    
    user_id = int(current["id"])
    
    # Get folders
    folders = db.execute(
        select(Folder).where(Folder.user_id == user_id).order_by(Folder.position, Folder.created_at)
    ).scalars().all()
    
    # Get conversation counts per folder
    count_query = select(
        Conversation.folder_id,
        func.count(Conversation.id).label('count')
    ).where(
        Conversation.user_id == user_id
    ).group_by(Conversation.folder_id)
    
    counts = {}
    for row in db.execute(count_query):
        folder_id = row[0]
        count = row[1]
        if folder_id:
            counts[folder_id] = count
    
    # Count conversations without folder
    no_folder_count = db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.user_id == user_id,
            Conversation.folder_id.is_(None)
        )
    ).scalar()
    
    result = []
    for folder in folders:
        result.append({
            "id": folder.id,
            "name": folder.name,
            "color": folder.color,
            "icon": folder.icon,
            "position": folder.position,
            "conversation_count": counts.get(folder.id, 0)
        })
    
    return {
        "ok": True,
        "folders": result,
        "no_folder_count": no_folder_count
    }

@router.post("")
async def create_folder(
    payload: FolderCreate,
    db=Depends(get_db),
    current=Depends(get_current_user_required)
):
    """Create a new folder"""
    if not Folder:
        raise HTTPException(500, "Folders not supported")
    
    user_id = int(current["id"])
    
    # Check if folder name already exists
    existing = db.execute(
        select(Folder).where(
            Folder.user_id == user_id,
            Folder.name == payload.name
        )
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(400, f"Folder '{payload.name}' already exists")
    
    # Get max position
    max_pos = db.execute(
        select(func.max(Folder.position)).where(Folder.user_id == user_id)
    ).scalar() or 0
    
    # Create folder
    folder = Folder(
        user_id=user_id,
        name=payload.name,
        color=payload.color,
        icon=payload.icon,
        position=max_pos + 1
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
            "position": folder.position,
            "conversation_count": 0
        }
    }

@router.patch("/{folder_id}")
async def update_folder(
    folder_id: int,
    payload: FolderUpdate,
    db=Depends(get_db),
    current=Depends(get_current_user_required)
):
    """Update folder properties"""
    if not Folder:
        raise HTTPException(500, "Folders not supported")
    
    user_id = int(current["id"])
    
    folder = db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.user_id == user_id
        )
    ).scalar_one_or_none()
    
    if not folder:
        raise HTTPException(404, "Folder not found")
    
    if payload.name is not None:
        folder.name = payload.name
    if payload.color is not None:
        folder.color = payload.color
    if payload.icon is not None:
        folder.icon = payload.icon
    if payload.position is not None:
        folder.position = payload.position
    
    db.commit()
    db.refresh(folder)
    
    return {"ok": True, "folder": {"id": folder.id, "name": folder.name}}

@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: int,
    db=Depends(get_db),
    current=Depends(get_current_user_required)
):
    """Delete folder (conversations will be moved to 'no folder')"""
    if not Folder:
        raise HTTPException(500, "Folders not supported")
    
    user_id = int(current["id"])
    
    folder = db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.user_id == user_id
        )
    ).scalar_one_or_none()
    
    if not folder:
        raise HTTPException(404, "Folder not found")
    
    # Move all conversations to no folder
    db.execute(
        Conversation.__table__.update().where(
            Conversation.folder_id == folder_id
        ).values(folder_id=None)
    )
    
    db.delete(folder)
    db.commit()
    
    return {"ok": True, "message": "Folder deleted"}

@router.post("/move")
async def move_conversations_to_folder(
    payload: MoveToFolderRequest,
    db=Depends(get_db),
    current=Depends(get_current_user_required)
):
    """Move multiple conversations to a folder (or remove from folder)"""
    user_id = int(current["id"])
    
    if payload.folder_id and Folder:
        # Verify folder exists and belongs to user
        folder = db.execute(
            select(Folder).where(
                Folder.id == payload.folder_id,
                Folder.user_id == user_id
            )
        ).scalar_one_or_none()
        
        if not folder:
            raise HTTPException(404, "Folder not found")
    
    # Update conversations
    updated = 0
    for conv_id in payload.conversation_ids:
        conv = db.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.user_id == user_id
            )
        ).scalar_one_or_none()
        
        if conv:
            conv.folder_id = payload.folder_id
            updated += 1
    
    db.commit()
    
    return {
        "ok": True,
        "updated": updated,
        "folder_id": payload.folder_id
    }
