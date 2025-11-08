"""
Hardware Profiler

Creates detailed hardware profiles for driver recommendations.
"""

from typing import Dict, Any, List
from loguru import logger


class HardwareProfiler:
    """
    Hardware Profiler
    
    Creates comprehensive hardware profiles that can be sent to Mother-KI
    for optimal driver and configuration recommendations.
    """
    
    def __init__(self):
        pass
        
    async def create_profile(self, hardware_scan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create hardware profile for Mother-KI
        
        Args:
            hardware_scan: Complete hardware scan results
            
        Returns:
            Structured hardware profile
        """
        logger.info("📋 Creating hardware profile...")
        
        profile = {
            "cpu": self._profile_cpu(hardware_scan.get("cpu", {})),
            "gpu": self._profile_gpus(hardware_scan.get("gpu", [])),
            "memory": self._profile_memory(hardware_scan.get("memory", {})),
            "system": self._profile_system(hardware_scan.get("system", {})),
        }
        
        logger.success("✅ Hardware profile created")
        return profile
    
    def _profile_cpu(self, cpu_info: Dict[str, Any]) -> Dict[str, Any]:
        """Profile CPU for recommendations"""
        return {
            "model": cpu_info.get("model", "Unknown"),
            "cores": cpu_info.get("physical_cores", 0),
            "threads": cpu_info.get("logical_cores", 0),
            "architecture": cpu_info.get("architecture", "Unknown"),
            "supports_avx": "avx" in str(cpu_info.get("features", [])).lower(),
            "supports_avx2": "avx2" in str(cpu_info.get("features", [])).lower(),
        }
    
    def _profile_gpus(self, gpus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Profile GPUs for driver recommendations"""
        profiles = []
        
        for gpu in gpus:
            vendor = gpu.get("vendor", "Unknown").upper()
            
            profile = {
                "vendor": vendor,
                "model": gpu.get("model", "Unknown"),
                "type": gpu.get("type", "unknown"),
                "needs_driver": vendor in ["NVIDIA", "AMD"],
                "driver_installed": "driver" in gpu,
            }
            
            if vendor == "NVIDIA":
                profile["recommended_driver"] = "nvidia-driver-latest"
            elif vendor == "AMD":
                profile["recommended_driver"] = "amdgpu"
                
            profiles.append(profile)
        
        return profiles
    
    def _profile_memory(self, memory_info: Dict[str, Any]) -> Dict[str, Any]:
        """Profile memory"""
        total_gb = memory_info.get("total_gb", 0)
        
        return {
            "total_gb": total_gb,
            "category": self._categorize_memory(total_gb),
            "swap_recommended": total_gb < 16,
        }
    
    def _profile_system(self, system_info: Dict[str, Any]) -> Dict[str, Any]:
        """Profile system"""
        return {
            "os": system_info.get("os", "Unknown"),
            "architecture": system_info.get("architecture", "Unknown"),
            "is_laptop": self._detect_laptop(system_info),
        }
    
    def _categorize_memory(self, total_gb: float) -> str:
        """Categorize memory amount"""
        if total_gb < 8:
            return "low"
        elif total_gb < 16:
            return "medium"
        elif total_gb < 32:
            return "high"
        else:
            return "very_high"
    
    def _detect_laptop(self, system_info: Dict[str, Any]) -> bool:
        """Detect if system is a laptop"""
        # TODO: Better laptop detection
        # Check for battery, laptop-specific hardware, etc.
        return False
