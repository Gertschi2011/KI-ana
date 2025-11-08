"""
Driver Detector

Detects which drivers are needed based on hardware.
"""

from typing import Dict, Any, List
from loguru import logger


class DriverDetector:
    """
    Intelligent Driver Detector
    
    Analyzes hardware and determines which drivers are needed.
    """
    
    def __init__(self):
        pass
    
    async def detect_needed_drivers(self, hardware_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect which drivers are needed
        
        Args:
            hardware_profile: Hardware profile from profiler
            
        Returns:
            List of needed drivers
        """
        logger.info("🔍 Detecting needed drivers...")
        
        needed_drivers = []
        
        # Check GPUs
        for gpu in hardware_profile.get("gpu", []):
            driver = await self._detect_gpu_driver(gpu)
            if driver:
                needed_drivers.append(driver)
        
        # Check other hardware (future)
        # - Network cards
        # - Audio devices
        # - Input devices
        
        logger.info(f"Found {len(needed_drivers)} drivers needed")
        return needed_drivers
    
    async def _detect_gpu_driver(self, gpu: Dict[str, Any]) -> Dict[str, Any]:
        """Detect GPU driver needs"""
        vendor = gpu.get("vendor", "").upper()
        model = gpu.get("model", "Unknown")
        
        if vendor == "NVIDIA":
            return {
                "device": model,
                "device_type": "GPU",
                "vendor": "NVIDIA",
                "driver_name": "nvidia-driver",
                "driver_package": "nvidia-driver-latest",
                "install_command": "sudo apt install nvidia-driver-latest",
                "priority": "high",
                "reason": "NVIDIA GPU requires proprietary driver for optimal performance"
            }
        elif vendor == "AMD":
            return {
                "device": model,
                "device_type": "GPU",
                "vendor": "AMD",
                "driver_name": "amdgpu",
                "driver_package": "firmware-amd-graphics",
                "install_command": "sudo apt install firmware-amd-graphics",
                "priority": "medium",
                "reason": "AMD GPU may benefit from latest firmware"
            }
        elif vendor == "INTEL":
            return {
                "device": model,
                "device_type": "GPU",
                "vendor": "Intel",
                "driver_name": "i915",
                "driver_package": "intel-media-va-driver",
                "install_command": "sudo apt install intel-media-va-driver",
                "priority": "low",
                "reason": "Intel integrated graphics - drivers usually included"
            }
        
        return None
    
    async def check_driver_installed(self, driver: Dict[str, Any]) -> bool:
        """Check if driver is already installed"""
        vendor = driver.get("vendor", "").upper()
        
        if vendor == "NVIDIA":
            # Check if NVIDIA driver is loaded
            try:
                import subprocess
                result = subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True,
                    timeout=5
                )
                return result.returncode == 0
            except:
                return False
        
        # For others, assume installed for now
        return True
