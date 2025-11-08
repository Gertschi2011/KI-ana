"""
Enhanced AI Brain with Hardware Intelligence & Mother-KI

Integrates all core components for full AI OS functionality.
"""

import asyncio
from typing import Dict, Any
from loguru import logger
from .brain import AIBrain
from ..hardware.scanner import HardwareScanner
from ..hardware.optimizer import HardwareOptimizer
from ..hardware.profiler import HardwareProfiler
from ..mother_ki.connection import MotherKIConnection
from ..memory.memory_manager import get_memory_manager
import uuid
import sys
from pathlib import Path
# Add system path for driver imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from system.drivers.manager import DriverManager


class EnhancedAIBrain(AIBrain):
    """
    Enhanced AI Brain with full hardware intelligence
    
    Extends the base AI Brain with:
    - Hardware scanning & optimization
    - Mother-KI connection
    - Driver management
    - System profiling
    """
    
    def __init__(self):
        super().__init__()
        
        # Hardware components
        self.hardware_scanner = HardwareScanner()
        self.hardware_optimizer = HardwareOptimizer()
        self.hardware_profiler = HardwareProfiler()
        
        # Mother-KI connection
        self.mother_ki = MotherKIConnection()
        
        # Driver management
        self.driver_manager = DriverManager()
        
        # Memory management
        self.memory_manager = None  # Initialized async in initialize()
        
        # System state
        self.hardware_profile: Dict[str, Any] = {}
        self.system_id = str(uuid.uuid4())
        
    async def initialize(self):
        """Initialize all components including hardware intelligence"""
        logger.info("🚀 Initializing Enhanced AI Brain...")
        
        # Initialize base components
        await super().initialize()
        
        # Initialize memory manager
        logger.info("🧠 Initializing memory system...")
        self.memory_manager = await get_memory_manager()
        
        # Perform initial hardware scan
        logger.info("🔍 Performing initial hardware scan...")
        self.hardware_profile = await self.hardware_scanner.full_scan()
        
        # Connect to Mother-KI
        try:
            await self.mother_ki.initialize(self.system_id)
        except Exception as e:
            logger.warning(f"Mother-KI connection failed, running offline: {e}")
        
        # Create hardware profile for Mother-KI
        profile = await self.hardware_profiler.create_profile(self.hardware_profile)
        
        # Get recommendations from Mother-KI
        if self.mother_ki.is_connected:
            try:
                recommendations = await self.mother_ki.query_drivers(profile)
                logger.info(f"📦 Received {len(recommendations.get('recommendations', []))} driver recommendations")
            except Exception as e:
                logger.warning(f"Failed to get recommendations: {e}")
        
        logger.success("✅ Enhanced AI Brain ready!")
        
    async def process_command(self, user_input: str) -> Dict[str, Any]:
        """
        Process command with enhanced hardware intelligence and memory
        """
        # Get context from memory if available
        context = None
        if self.memory_manager:
            try:
                context = await self.memory_manager.get_context_for_query(user_input)
                logger.debug(f"Retrieved context with {len(context.get('recent_conversations', []))} conversations")
            except Exception as e:
                logger.warning(f"Failed to get memory context: {e}")
        
        # Check for hardware-specific commands first
        if self._is_hardware_command(user_input):
            result = await self._handle_hardware_command(user_input)
        else:
            # Fall back to base AI Brain
            result = await super().process_command(user_input)
        
        # Store conversation in memory
        if self.memory_manager and result.get("success"):
            try:
                response_text = result.get("response", "")
                await self.memory_manager.store_conversation(
                    user_input=user_input,
                    ai_response=response_text,
                    context={"command_type": "hardware" if self._is_hardware_command(user_input) else "general"},
                    metadata={"success": True, "has_data": bool(result.get("result", {}).get("data"))}
                )
            except Exception as e:
                logger.warning(f"Failed to store conversation: {e}")
        
        return result
    
    def _is_hardware_command(self, user_input: str) -> bool:
        """Check if command is hardware-related"""
        hw_keywords = ["hardware", "treiber", "driver", "gpu", "cpu", "optimier", "scan"]
        return any(keyword in user_input.lower() for keyword in hw_keywords)
    
    async def _handle_hardware_command(self, user_input: str) -> Dict[str, Any]:
        """Handle hardware-specific commands"""
        user_input_lower = user_input.lower()
        
        try:
            if "scan" in user_input_lower or "hardware" in user_input_lower:
                # Rescan hardware
                logger.info("🔍 Rescanning hardware...")
                self.hardware_profile = await self.hardware_scanner.full_scan()
                
                return {
                    "success": True,
                    "result": {"data": self.hardware_profile},
                    "response": f"Hardware-Scan abgeschlossen! Gefunden: {self._summarize_hardware()}"
                }
                
            elif "optimier" in user_input_lower:
                # Optimize system
                logger.info("🚀 Optimizing system...")
                result = await self.hardware_optimizer.optimize(self.hardware_profile)
                
                return {
                    "success": True,
                    "result": {"data": result},
                    "response": f"System optimiert! {len(result['optimizations_applied'])} Optimierungen angewendet."
                }
                
            elif "treiber" in user_input_lower or "driver" in user_input_lower:
                # Auto-install drivers or show recommendations
                if "installier" in user_input_lower or "install" in user_input_lower:
                    logger.info("📦 Auto-installing drivers...")
                    profile = await self.hardware_profiler.create_profile(self.hardware_profile)
                    result = await self.driver_manager.auto_install_drivers(profile, auto_confirm=False)
                    
                    if result["success"]:
                        msg = f"Treiber-Installation abgeschlossen! {result['drivers_installed']} Treiber installiert."
                    else:
                        msg = f"Treiber-Installation: {result['message']}"
                    
                    return {
                        "success": result["success"],
                        "result": {"data": result},
                        "response": msg
                    }
                else:
                    # Just show recommendations
                    logger.info("📦 Getting driver recommendations...")
                    profile = await self.hardware_profiler.create_profile(self.hardware_profile)
                    recommendations = await self.driver_manager.get_driver_recommendations(profile)
                    
                    return {
                        "success": True,
                        "result": {"data": {"recommendations": recommendations}},
                        "response": f"Treiber-Empfehlungen: {len(recommendations)} Treiber gefunden."
                    }
            
        except Exception as e:
            logger.error(f"Hardware command failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"Fehler bei Hardware-Befehl: {e}"
            }
        
        # Unknown hardware command
        return await super().process_command(user_input)
    
    def _summarize_hardware(self) -> str:
        """Create human-readable hardware summary"""
        summary = []
        
        if "cpu" in self.hardware_profile:
            cpu = self.hardware_profile["cpu"]
            summary.append(f"{cpu.get('physical_cores', 0)} CPU cores")
        
        if "gpu" in self.hardware_profile:
            gpu_count = len(self.hardware_profile["gpu"])
            summary.append(f"{gpu_count} GPU(s)")
        
        if "memory" in self.hardware_profile:
            ram = self.hardware_profile["memory"].get("total_gb", 0)
            summary.append(f"{ram}GB RAM")
        
        return ", ".join(summary) if summary else "Hardware erkannt"
    
    async def shutdown(self):
        """Graceful shutdown with cleanup"""
        logger.info("Shutting down Enhanced AI Brain...")
        
        # Shutdown Mother-KI connection
        if self.mother_ki:
            await self.mother_ki.shutdown()
        
        # Base shutdown
        await super().shutdown()


# Singleton instance
_enhanced_brain_instance = None


async def get_enhanced_brain() -> EnhancedAIBrain:
    """Get or create Enhanced AI Brain singleton"""
    global _enhanced_brain_instance
    
    if _enhanced_brain_instance is None:
        _enhanced_brain_instance = EnhancedAIBrain()
        await _enhanced_brain_instance.initialize()
    
    return _enhanced_brain_instance
