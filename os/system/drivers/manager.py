"""
Driver Manager

High-level driver management system.
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from .detector import DriverDetector
from .installer import DriverInstaller


class DriverManager:
    """
    Intelligent Driver Manager
    
    Manages the complete driver lifecycle:
    - Detection
    - Installation
    - Updates
    - Verification
    """
    
    def __init__(self):
        self.detector = DriverDetector()
        self.installer = DriverInstaller()
        self.current_drivers: List[Dict] = []
        
    async def auto_install_drivers(self, 
                                  hardware_profile: Dict[str, Any],
                                  auto_confirm: bool = False) -> Dict[str, Any]:
        """
        Automatically detect and install needed drivers
        
        Args:
            hardware_profile: Hardware profile
            auto_confirm: Auto-confirm installations
            
        Returns:
            Installation summary
        """
        logger.info("🚀 Starting automatic driver installation...")
        
        # Detect needed drivers
        needed_drivers = await self.detector.detect_needed_drivers(hardware_profile)
        
        if not needed_drivers:
            logger.info("✅ No drivers needed")
            return {
                "success": True,
                "message": "No drivers needed",
                "drivers_installed": 0
            }
        
        logger.info(f"Found {len(needed_drivers)} drivers to install:")
        for driver in needed_drivers:
            logger.info(f"  - {driver.get('driver_name')} for {driver.get('device')}")
            logger.info(f"    Priority: {driver.get('priority')}, Reason: {driver.get('reason')}")
        
        # Check which are already installed
        drivers_to_install = []
        for driver in needed_drivers:
            installed = await self.detector.check_driver_installed(driver)
            if not installed:
                drivers_to_install.append(driver)
            else:
                logger.info(f"✅ Already installed: {driver.get('driver_name')}")
        
        if not drivers_to_install:
            logger.success("✅ All drivers already installed")
            return {
                "success": True,
                "message": "All drivers already installed",
                "drivers_installed": 0
            }
        
        # Install drivers
        logger.info(f"Installing {len(drivers_to_install)} drivers...")
        summary = await self.installer.install_all_drivers(drivers_to_install, auto_confirm)
        
        self.current_drivers = needed_drivers
        
        result = {
            "success": summary["successful"] > 0,
            "message": f"Installed {summary['successful']}/{summary['attempted']} drivers",
            "drivers_installed": summary["successful"],
            "drivers_failed": summary["failed"],
            "details": summary
        }
        
        if summary["successful"] > 0:
            logger.success(f"✅ Installed {summary['successful']} drivers successfully!")
        
        return result
    
    async def get_driver_recommendations(self, hardware_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get driver recommendations without installing
        
        Args:
            hardware_profile: Hardware profile
            
        Returns:
            List of recommended drivers
        """
        return await self.detector.detect_needed_drivers(hardware_profile)
    
    async def verify_drivers(self) -> Dict[str, Any]:
        """Verify that installed drivers are working"""
        logger.info("🔍 Verifying drivers...")
        
        verified = []
        issues = []
        
        for driver in self.current_drivers:
            installed = await self.detector.check_driver_installed(driver)
            
            if installed:
                verified.append(driver.get("driver_name"))
            else:
                issues.append(driver.get("driver_name"))
        
        return {
            "verified": verified,
            "issues": issues,
            "all_ok": len(issues) == 0
        }
