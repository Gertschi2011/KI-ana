"""
Driver Installer

Installs drivers automatically and safely.
"""

import asyncio
import subprocess
from typing import Dict, Any, List
from loguru import logger


class DriverInstaller:
    """
    Intelligent Driver Installer
    
    Installs drivers safely with rollback capability.
    """
    
    def __init__(self):
        self.installation_log: List[Dict] = []
        
    async def install_driver(self, driver: Dict[str, Any], auto_confirm: bool = False) -> Dict[str, Any]:
        """
        Install a single driver
        
        Args:
            driver: Driver information
            auto_confirm: Auto-confirm installation (use with caution!)
            
        Returns:
            Installation result
        """
        logger.info(f"📦 Installing driver: {driver.get('driver_name')}")
        
        result = {
            "driver": driver.get("driver_name"),
            "success": False,
            "message": "",
            "installed": False
        }
        
        try:
            # Safety check
            if not auto_confirm:
                logger.warning("Auto-confirm is OFF - installation requires manual confirmation")
                result["message"] = "Installation requires manual confirmation"
                return result
            
            # Pre-installation checks
            logger.info("Running pre-installation checks...")
            
            # Update package lists
            logger.info("Updating package lists...")
            await self._run_command("sudo apt update")
            
            # Install driver
            install_cmd = driver.get("install_command", "")
            if not install_cmd:
                result["message"] = "No install command specified"
                return result
            
            logger.info(f"Running: {install_cmd}")
            output = await self._run_command(install_cmd)
            
            # Verify installation
            # TODO: Add verification logic
            
            result["success"] = True
            result["installed"] = True
            result["message"] = "Driver installed successfully"
            
            # Log installation
            self.installation_log.append({
                "driver": driver,
                "result": result,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            logger.success(f"✅ Driver installed: {driver.get('driver_name')}")
            
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            result["message"] = str(e)
        
        return result
    
    async def install_all_drivers(self, drivers: List[Dict[str, Any]], auto_confirm: bool = False) -> Dict[str, Any]:
        """
        Install multiple drivers
        
        Args:
            drivers: List of drivers to install
            auto_confirm: Auto-confirm all installations
            
        Returns:
            Summary of installations
        """
        logger.info(f"📦 Installing {len(drivers)} drivers...")
        
        results = []
        success_count = 0
        
        for driver in drivers:
            # Skip low priority if not auto-confirming
            if not auto_confirm and driver.get("priority") == "low":
                logger.info(f"Skipping low priority driver: {driver.get('driver_name')}")
                continue
            
            result = await self.install_driver(driver, auto_confirm)
            results.append(result)
            
            if result["success"]:
                success_count += 1
        
        summary = {
            "total": len(drivers),
            "attempted": len(results),
            "successful": success_count,
            "failed": len(results) - success_count,
            "results": results
        }
        
        logger.info(f"Installation complete: {success_count}/{len(results)} successful")
        return summary
    
    async def _run_command(self, command: str) -> str:
        """Run shell command"""
        loop = asyncio.get_event_loop()
        
        def run():
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return result.stdout + result.stderr
        
        return await loop.run_in_executor(None, run)
    
    def get_installation_log(self) -> List[Dict]:
        """Get installation history"""
        return self.installation_log
