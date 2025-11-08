"""
Cloud Synchronization

Syncs data across devices via cloud.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional
from loguru import logger
import json
from pathlib import Path
from datetime import datetime


class CloudSync:
    """
    Cloud Synchronization System
    
    Syncs data across devices:
    - Settings
    - Conversations
    - Preferences
    - Knowledge base
    """
    
    def __init__(self, 
                 sync_url: str = "http://localhost:8080/api/sync",
                 device_id: Optional[str] = None):
        self.sync_url = sync_url
        self.device_id = device_id or self._generate_device_id()
        self.sync_enabled = True
        self.last_sync = None
        
        self.local_data_path = Path("~/.kiana_sync").expanduser()
        self.local_data_path.mkdir(parents=True, exist_ok=True)
        
    def _generate_device_id(self) -> str:
        """Generate unique device ID"""
        import uuid
        return str(uuid.uuid4())
    
    async def sync_settings(self, settings: Dict[str, Any]) -> bool:
        """Sync settings to cloud"""
        if not self.sync_enabled:
            return False
        
        logger.info("☁️ Syncing settings to cloud...")
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "device_id": self.device_id,
                    "type": "settings",
                    "data": settings,
                    "timestamp": datetime.now().isoformat()
                }
                
                async with session.post(
                    f"{self.sync_url}/push",
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logger.success("✅ Settings synced")
                        self.last_sync = datetime.now()
                        return True
                    else:
                        logger.warning(f"Sync failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False
    
    async def pull_settings(self) -> Optional[Dict[str, Any]]:
        """Pull settings from cloud"""
        if not self.sync_enabled:
            return None
        
        logger.info("☁️ Pulling settings from cloud...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.sync_url}/pull",
                    params={"device_id": self.device_id, "type": "settings"},
                    timeout=10
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.success("✅ Settings pulled")
                        return data.get("data")
                    else:
                        return None
                        
        except Exception as e:
            logger.error(f"Pull error: {e}")
            return None
    
    async def sync_conversations(self, conversations: list) -> bool:
        """Sync conversation history"""
        if not self.sync_enabled:
            return False
        
        logger.info("☁️ Syncing conversations...")
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "device_id": self.device_id,
                    "type": "conversations",
                    "data": conversations[-100:],  # Last 100
                    "timestamp": datetime.now().isoformat()
                }
                
                async with session.post(
                    f"{self.sync_url}/push",
                    json=payload,
                    timeout=10
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False
    
    async def auto_sync(self, data: Dict[str, Any]) -> bool:
        """Auto-sync all data"""
        logger.info("🔄 Auto-syncing data...")
        
        results = []
        
        if "settings" in data:
            results.append(await self.sync_settings(data["settings"]))
        
        if "conversations" in data:
            results.append(await self.sync_conversations(data["conversations"]))
        
        return all(results)
    
    def enable_sync(self):
        """Enable cloud sync"""
        self.sync_enabled = True
        logger.info("✅ Cloud sync enabled")
    
    def disable_sync(self):
        """Disable cloud sync"""
        self.sync_enabled = False
        logger.info("⚠️ Cloud sync disabled")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status"""
        return {
            "enabled": self.sync_enabled,
            "device_id": self.device_id,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_url": self.sync_url
        }
