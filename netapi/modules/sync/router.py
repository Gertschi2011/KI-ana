"""
Device Sync API Router

Handles synchronization between KI_ana OS devices and Mutter-KI backend.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ...deps import get_db
from ...models import User
import json

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncPushRequest(BaseModel):
    device_id: str
    type: str  # settings, conversations, preferences
    data: Dict[str, Any]
    timestamp: str


class SyncPullRequest(BaseModel):
    device_id: str
    type: str


# In-memory storage for demo (replace with DB in production)
sync_storage: Dict[str, Dict[str, Any]] = {}


@router.post("/push")
async def push_data(request: SyncPushRequest):
    """
    Push data from OS device to Mutter-KI
    """
    try:
        # Create storage key
        key = f"{request.device_id}_{request.type}"
        
        # Store data
        sync_storage[key] = {
            "device_id": request.device_id,
            "type": request.type,
            "data": request.data,
            "timestamp": request.timestamp,
            "synced_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "message": f"Data synced successfully",
            "device_id": request.device_id,
            "type": request.type
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pull")
async def pull_data(device_id: str, type: str):
    """
    Pull data from Mutter-KI to OS device
    """
    try:
        # Get storage key
        key = f"{device_id}_{type}"
        
        if key not in sync_storage:
            return {
                "success": False,
                "message": "No data found for this device",
                "data": None
            }
        
        stored = sync_storage[key]
        
        return {
            "success": True,
            "data": stored["data"],
            "timestamp": stored["timestamp"],
            "synced_at": stored["synced_at"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def sync_status(device_id: str):
    """
    Get sync status for a device
    """
    try:
        device_keys = [k for k in sync_storage.keys() if k.startswith(device_id)]
        
        return {
            "device_id": device_id,
            "synced_types": [k.split("_", 1)[1] for k in device_keys],
            "total_syncs": len(device_keys),
            "last_sync": max([sync_storage[k]["synced_at"] for k in device_keys]) if device_keys else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_sync_data(device_id: str):
    """
    Clear sync data for a device
    """
    try:
        device_keys = [k for k in sync_storage.keys() if k.startswith(device_id)]
        
        for key in device_keys:
            del sync_storage[key]
        
        return {
            "success": True,
            "message": f"Cleared {len(device_keys)} sync entries",
            "device_id": device_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
