"""
Hardware Scanner

Intelligently scans and detects all hardware components.
"""

import platform
import subprocess
from typing import Dict, Any, List
from loguru import logger
import psutil


class HardwareScanner:
    """
    Intelligent Hardware Scanner
    
    Detects and profiles all hardware components:
    - CPU (model, cores, features)
    - GPU (NVIDIA, AMD, Intel)
    - RAM (size, speed, type)
    - Storage (SSDs, HDDs)
    - Network devices
    - USB devices
    - Audio devices
    """
    
    def __init__(self):
        self.system_info: Dict[str, Any] = {}
        
    async def full_scan(self) -> Dict[str, Any]:
        """
        Perform complete hardware scan
        
        Returns comprehensive hardware profile
        """
        logger.info("🔍 Starting full hardware scan...")
        
        self.system_info = {
            "cpu": await self._scan_cpu(),
            "gpu": await self._scan_gpu(),
            "memory": await self._scan_memory(),
            "storage": await self._scan_storage(),
            "network": await self._scan_network(),
            "usb": await self._scan_usb(),
            "audio": await self._scan_audio(),
            "system": await self._scan_system(),
        }
        
        logger.success(f"✅ Hardware scan complete! Found {self._count_devices()} devices")
        return self.system_info
    
    async def _scan_cpu(self) -> Dict[str, Any]:
        """Scan CPU details"""
        logger.debug("Scanning CPU...")
        
        cpu_info = {
            "model": platform.processor() or "Unknown",
            "architecture": platform.machine(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "max_frequency_mhz": 0,
            "current_frequency_mhz": 0,
            "usage_percent": psutil.cpu_percent(interval=0.5),
            "features": [],
        }
        
        # Get CPU frequency
        try:
            freq = psutil.cpu_freq()
            if freq:
                cpu_info["max_frequency_mhz"] = freq.max
                cpu_info["current_frequency_mhz"] = freq.current
        except:
            pass
        
        # Try to get more details on Linux
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                if "flags" in cpuinfo:
                    # Extract CPU features
                    for line in cpuinfo.split("\n"):
                        if line.startswith("flags"):
                            flags = line.split(":")[1].strip().split()
                            cpu_info["features"] = flags[:20]  # First 20 features
                            break
        except:
            pass
        
        return cpu_info
    
    async def _scan_gpu(self) -> List[Dict[str, Any]]:
        """Scan GPU(s)"""
        logger.debug("Scanning GPU...")
        
        gpus = []
        
        # Try NVIDIA
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        gpus.append({
                            "vendor": "NVIDIA",
                            "model": parts[0],
                            "memory": parts[1],
                            "driver": parts[2],
                            "type": "discrete"
                        })
        except:
            pass
        
        # Try AMD (lspci)
        try:
            result = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "VGA" in line or "3D" in line or "Display" in line:
                        if "AMD" in line or "ATI" in line:
                            gpus.append({
                                "vendor": "AMD",
                                "model": line.split(":")[-1].strip(),
                                "type": "discrete"
                            })
                        elif "Intel" in line:
                            gpus.append({
                                "vendor": "Intel",
                                "model": line.split(":")[-1].strip(),
                                "type": "integrated"
                            })
        except:
            pass
        
        if not gpus:
            gpus.append({
                "vendor": "Unknown",
                "model": "No GPU detected",
                "type": "unknown"
            })
        
        return gpus
    
    async def _scan_memory(self) -> Dict[str, Any]:
        """Scan RAM"""
        logger.debug("Scanning memory...")
        
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent_used": mem.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
        }
    
    async def _scan_storage(self) -> List[Dict[str, Any]]:
        """Scan storage devices"""
        logger.debug("Scanning storage...")
        
        devices = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                devices.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent_used": usage.percent,
                })
            except:
                pass
        
        return devices
    
    async def _scan_network(self) -> List[Dict[str, Any]]:
        """Scan network devices"""
        logger.debug("Scanning network...")
        
        devices = []
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        
        for interface, addrs in net_if_addrs.items():
            device = {
                "interface": interface,
                "addresses": [],
                "is_up": False,
                "speed_mbps": 0
            }
            
            # Get stats
            if interface in net_if_stats:
                stats = net_if_stats[interface]
                device["is_up"] = stats.isup
                device["speed_mbps"] = stats.speed
            
            # Get addresses
            for addr in addrs:
                if addr.family == 2:  # IPv4
                    device["addresses"].append({
                        "type": "IPv4",
                        "address": addr.address
                    })
            
            devices.append(device)
        
        return devices
    
    async def _scan_usb(self) -> List[Dict[str, Any]]:
        """Scan USB devices"""
        logger.debug("Scanning USB devices...")
        
        devices = []
        
        try:
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        devices.append({
                            "description": line
                        })
        except:
            pass
        
        return devices
    
    async def _scan_audio(self) -> List[Dict[str, Any]]:
        """Scan audio devices"""
        logger.debug("Scanning audio devices...")
        
        # Placeholder - would use ALSA/PulseAudio on Linux
        return [{"info": "Audio detection not yet implemented"}]
    
    async def _scan_system(self) -> Dict[str, Any]:
        """Scan system info"""
        logger.debug("Scanning system info...")
        
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "hostname": platform.node(),
            "architecture": platform.machine(),
            "boot_time": psutil.boot_time(),
        }
    
    def _count_devices(self) -> int:
        """Count total devices detected"""
        count = 0
        if "cpu" in self.system_info:
            count += 1
        if "gpu" in self.system_info:
            count += len(self.system_info["gpu"])
        if "storage" in self.system_info:
            count += len(self.system_info["storage"])
        if "network" in self.system_info:
            count += len(self.system_info["network"])
        return count


# Singleton
_scanner_instance = None


async def get_scanner() -> HardwareScanner:
    """Get or create scanner singleton"""
    global _scanner_instance
    
    if _scanner_instance is None:
        _scanner_instance = HardwareScanner()
    
    return _scanner_instance
