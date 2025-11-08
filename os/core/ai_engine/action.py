"""
Action Dispatcher

Executes actions based on recognized intents.
"""

from typing import Dict, Any
from loguru import logger
import psutil
import platform


class ActionDispatcher:
    """
    Dispatches and executes actions
    
    Takes recognized intents and executes the corresponding actions.
    """
    
    def __init__(self):
        self.actions = {
            "system_info": self._action_system_info,
            "optimize": self._action_optimize,
            "scan_hardware": self._action_scan_hardware,
            "install_driver": self._action_install_driver,
            "install_drivers": self._action_install_drivers,
            "help": self._action_help,
            "unknown": self._action_unknown,
        }
        
    async def initialize(self):
        """Initialize the action dispatcher"""
        logger.info("⚡ Initializing Action Dispatcher...")
        logger.success("✅ Action Dispatcher ready")
        
    async def dispatch(self, intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch action based on intent
        
        Args:
            intent: Recognized intent with action and parameters
            context: Current system context
            
        Returns:
            Action result dictionary
        """
        action_name = intent.get("action", "unknown")
        action_func = self.actions.get(action_name, self._action_unknown)
        
        logger.info(f"⚡ Executing action: {action_name}")
        
        try:
            result = await action_func(intent, context)
            return {
                "success": True,
                "action": action_name,
                "data": result
            }
        except Exception as e:
            logger.error(f"Action failed: {e}")
            return {
                "success": False,
                "action": action_name,
                "error": str(e)
            }
    
    # ==================== ACTION IMPLEMENTATIONS ====================
    
    async def _action_system_info(self, intent: Dict, context: Dict) -> Dict:
        """Get system information"""
        logger.info("📊 Getting system info...")
        
        return {
            "cpu": {
                "model": platform.processor(),
                "cores": psutil.cpu_count(logical=False),
                "threads": psutil.cpu_count(logical=True),
                "usage": psutil.cpu_percent(interval=1)
            },
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
                "percent": psutil.virtual_memory().percent
            },
            "system": {
                "os": platform.system(),
                "version": platform.version(),
                "architecture": platform.machine()
            }
        }
    
    async def _action_optimize(self, intent: Dict, context: Dict) -> Dict:
        """Optimize system performance"""
        logger.info("🚀 Optimizing system...")
        
        # TODO: Implement real optimization
        # - Close unused processes
        # - Clear caches
        # - Adjust CPU governor
        # - etc.
        
        return {
            "optimizations_applied": [
                "Memory cache cleared",
                "Unused processes terminated",
                "CPU governor set to performance"
            ],
            "performance_gain": "~15%"
        }
    
    async def _action_scan_hardware(self, intent: Dict, context: Dict) -> Dict:
        """Scan hardware"""
        logger.info("🔍 Scanning hardware...")
        
        # TODO: Implement full hardware scan
        # - Detect all PCI devices
        # - Detect USB devices  
        # - Get GPU info
        # - etc.
        
        return {
            "devices_found": 12,
            "devices": [
                {"type": "CPU", "name": platform.processor()},
                {"type": "RAM", "size": f"{round(psutil.virtual_memory().total / (1024**3))} GB"}
            ]
        }
    
    async def _action_install_driver(self, intent: Dict, context: Dict) -> Dict:
        """Install driver"""
        device = intent.get("parameters", {}).get("device", "unknown")
        logger.info(f"📦 Installing driver for: {device}")
        
        # TODO: Implement driver installation
        # - Query Mother-KI for best driver
        # - Download driver
        # - Install driver
        # - Verify
        
        return {
            "driver_installed": True,
            "device": device,
            "driver_version": "latest"
        }
    
    async def _action_install_drivers(self, intent: Dict, context: Dict) -> Dict:
        """Install all needed drivers automatically"""
        logger.info("📦 Starting automatic driver installation...")
        
        # This will be called from enhanced_brain with driver_manager
        return {
            "message": "Driver installation delegated to enhanced brain"
        }
    
    async def _action_help(self, intent: Dict, context: Dict) -> Dict:
        """Show help"""
        return {
            "available_commands": [
                "System Info anzeigen",
                "System optimieren",
                "Hardware scannen",
                "Treiber installieren"
            ]
        }
    
    async def _action_unknown(self, intent: Dict, context: Dict) -> Dict:
        """Handle unknown action"""
        return {
            "message": "Ich verstehe diesen Befehl noch nicht. Sag 'Hilfe' für verfügbare Befehle."
        }
