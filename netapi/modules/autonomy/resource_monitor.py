"""
Resource Monitor
Tracks CPU, Memory, Disk and manages energy modes
Phase 11 - Autonomie
"""
import psutil
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum


class EnergyMode(str, Enum):
    SLEEP = "sleep"
    RUHE = "ruhe"
    FOKUS = "fokus"
    INTENSIV = "intensiv"


class ResourceMonitor:
    """Monitors system resources and manages energy modes"""
    
    def __init__(self):
        self.config = self._load_config()
        self.current_mode = EnergyMode.FOKUS
        self.last_mode_change = time.time()
        self.state_file = Path("/home/kiana/ki_ana/data/autonomy_state.json")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load autonomy config"""
        config_file = Path("/home/kiana/ki_ana/data/autonomy_config.json")
        
        if not config_file.exists():
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "available_mb": psutil.virtual_memory().available / (1024 * 1024)
            },
            "disk": {
                "percent": psutil.disk_usage('/').percent,
                "free_gb": psutil.disk_usage('/').free / (1024**3)
            },
            "timestamp": int(time.time())
        }
    
    def check_resources(self) -> Dict[str, Any]:
        """Check resources and determine if mode change needed"""
        usage = self.get_resource_usage()
        thresholds = self.config.get('resource_management', {}).get('thresholds', {})
        
        warnings = []
        critical = []
        
        # Check CPU
        cpu = usage['cpu_percent']
        cpu_thresh = thresholds.get('cpu_percent', {})
        
        if cpu >= cpu_thresh.get('sleep', 95):
            critical.append(f"CPU critical: {cpu}%")
            recommended_mode = EnergyMode.SLEEP
        elif cpu >= cpu_thresh.get('critical', 85):
            critical.append(f"CPU high: {cpu}%")
            recommended_mode = EnergyMode.RUHE
        elif cpu >= cpu_thresh.get('warn', 70):
            warnings.append(f"CPU elevated: {cpu}%")
            recommended_mode = self.current_mode
        else:
            recommended_mode = EnergyMode.FOKUS
        
        # Check Memory
        mem = usage['memory']['percent']
        mem_thresh = thresholds.get('memory_percent', {})
        
        if mem >= mem_thresh.get('sleep', 90):
            critical.append(f"Memory critical: {mem}%")
            recommended_mode = EnergyMode.SLEEP
        elif mem >= mem_thresh.get('critical', 85):
            critical.append(f"Memory high: {mem}%")
        elif mem >= mem_thresh.get('warn', 75):
            warnings.append(f"Memory elevated: {mem}%")
        
        return {
            "usage": usage,
            "warnings": warnings,
            "critical": critical,
            "current_mode": self.current_mode.value,
            "recommended_mode": recommended_mode.value,
            "mode_change_needed": recommended_mode != self.current_mode
        }
    
    def set_energy_mode(self, mode: EnergyMode) -> Dict[str, Any]:
        """Set energy mode"""
        old_mode = self.current_mode
        self.current_mode = mode
        self.last_mode_change = time.time()
        
        # Get mode config
        modes_config = self.config.get('resource_management', {}).get('energy_modes', {})
        mode_config = modes_config.get(mode.value, {})
        
        # Save state
        self._save_state()
        
        return {
            "old_mode": old_mode.value,
            "new_mode": mode.value,
            "disabled_features": mode_config.get('disabled_features', []),
            "cpu_limit": mode_config.get('cpu_limit', 100),
            "description": mode_config.get('description', '')
        }
    
    def _save_state(self):
        """Save current state"""
        state = {
            "current_mode": self.current_mode.value,
            "last_mode_change": self.last_mode_change,
            "timestamp": int(time.time())
        }
        
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics"""
        return {
            "mode": self.current_mode.value,
            "uptime_seconds": time.time() - psutil.boot_time(),
            "resources": self.get_resource_usage(),
            "process_count": len(psutil.pids()),
            "network_io": dict(psutil.net_io_counters()._asdict()) if psutil.net_io_counters() else {}
        }


# Singleton
_monitor = None


def get_resource_monitor() -> ResourceMonitor:
    """Get singleton resource monitor"""
    global _monitor
    if _monitor is None:
        _monitor = ResourceMonitor()
    return _monitor


if __name__ == "__main__":
    # Test
    monitor = ResourceMonitor()
    
    print("Resource Usage:")
    usage = monitor.get_resource_usage()
    print(json.dumps(usage, indent=2))
    
    print("\nResource Check:")
    check = monitor.check_resources()
    print(json.dumps(check, indent=2))
