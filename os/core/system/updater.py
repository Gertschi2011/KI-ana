"""
System Update Mechanism

Handles OS updates and component upgrades.
"""

import subprocess
import asyncio
from typing import Dict, Any, List
from loguru import logger
from pathlib import Path
import json


class SystemUpdater:
    """
    System Update Manager
    
    Handles:
    - OS core updates
    - Component updates
    - Dependency updates
    - Version tracking
    """
    
    def __init__(self):
        self.version_file = Path("~/.kiana/version.json").expanduser()
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_version = self._load_version()
        
    def _load_version(self) -> Dict[str, Any]:
        """Load current version info"""
        if self.version_file.exists():
            with open(self.version_file, 'r') as f:
                return json.load(f)
        return {
            "os_version": "0.1.0",
            "components": {},
            "last_check": None,
            "last_update": None
        }
    
    def _save_version(self):
        """Save version info"""
        with open(self.version_file, 'w') as f:
            json.dump(self.current_version, f, indent=2)
    
    async def check_updates(self) -> Dict[str, Any]:
        """Check for available updates"""
        logger.info("🔍 Checking for updates...")
        
        updates = {
            "os_update_available": False,
            "component_updates": [],
            "total_updates": 0
        }
        
        # Check pip packages
        try:
            result = subprocess.run(
                ['pip', 'list', '--outdated', '--format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                outdated = json.loads(result.stdout)
                updates["component_updates"] = outdated
                updates["total_updates"] = len(outdated)
                
        except Exception as e:
            logger.error(f"Failed to check updates: {e}")
        
        from datetime import datetime
        self.current_version["last_check"] = datetime.now().isoformat()
        self._save_version()
        
        return updates
    
    async def update_components(self, components: List[str] = None) -> Dict[str, Any]:
        """Update specific components or all"""
        logger.info("📦 Updating components...")
        
        results = {
            "success": [],
            "failed": [],
            "total": 0
        }
        
        if components is None:
            # Update all outdated packages
            logger.info("Updating all packages...")
            try:
                result = subprocess.run(
                    ['pip', 'install', '--upgrade', 'pip'],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    results["success"].append("pip")
                else:
                    results["failed"].append("pip")
                    
            except Exception as e:
                logger.error(f"Update failed: {e}")
                results["failed"].append("pip")
        else:
            # Update specific packages
            for component in components:
                try:
                    logger.info(f"Updating {component}...")
                    result = subprocess.run(
                        ['pip', 'install', '--upgrade', component],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    
                    if result.returncode == 0:
                        results["success"].append(component)
                    else:
                        results["failed"].append(component)
                        
                except Exception as e:
                    logger.error(f"Failed to update {component}: {e}")
                    results["failed"].append(component)
        
        results["total"] = len(results["success"]) + len(results["failed"])
        
        from datetime import datetime
        self.current_version["last_update"] = datetime.now().isoformat()
        self._save_version()
        
        return results
    
    def get_version_info(self) -> Dict[str, Any]:
        """Get current version information"""
        return self.current_version
    
    async def auto_update(self) -> Dict[str, Any]:
        """Automatically check and update"""
        logger.info("🔄 Starting auto-update...")
        
        # Check for updates
        updates = await self.check_updates()
        
        if updates["total_updates"] == 0:
            logger.success("✅ System is up to date!")
            return {"status": "up_to_date", "updates": 0}
        
        # Update available components
        logger.info(f"Found {updates['total_updates']} updates")
        results = await self.update_components()
        
        return {
            "status": "updated",
            "updates_found": updates["total_updates"],
            "successful": len(results["success"]),
            "failed": len(results["failed"])
        }


# Singleton
_updater_instance = None


async def get_updater() -> SystemUpdater:
    """Get or create updater singleton"""
    global _updater_instance
    
    if _updater_instance is None:
        _updater_instance = SystemUpdater()
    
    return _updater_instance
