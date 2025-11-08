"""
Advanced Process Manager

Deep system integration for process management.
"""

import psutil
from typing import List, Dict, Any
from loguru import logger


class ProcessManager:
    """
    Advanced Process Manager
    
    Deep system integration:
    - Process monitoring
    - Priority management
    - Resource limiting
    - Auto-termination
    """
    
    def __init__(self):
        self.monitored_processes: Dict[int, Dict] = {}
        
    def get_all_processes(self) -> List[Dict[str, Any]]:
        """Get all running processes"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = proc.info
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'cpu_percent': pinfo['cpu_percent'],
                    'memory_percent': round(pinfo['memory_percent'], 2),
                    'status': pinfo['status']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return processes
    
    def get_top_processes(self, by: str = 'cpu', limit: int = 10) -> List[Dict[str, Any]]:
        """Get top processes by CPU or memory"""
        processes = self.get_all_processes()
        
        sort_key = 'cpu_percent' if by == 'cpu' else 'memory_percent'
        sorted_procs = sorted(processes, key=lambda x: x[sort_key], reverse=True)
        
        return sorted_procs[:limit]
    
    def get_process_info(self, pid: int) -> Dict[str, Any]:
        """Get detailed process information"""
        try:
            proc = psutil.Process(pid)
            
            return {
                'pid': proc.pid,
                'name': proc.name(),
                'status': proc.status(),
                'cpu_percent': proc.cpu_percent(interval=0.1),
                'memory_percent': round(proc.memory_percent(), 2),
                'memory_mb': round(proc.memory_info().rss / (1024 * 1024), 2),
                'num_threads': proc.num_threads(),
                'create_time': proc.create_time()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return {'error': str(e)}
    
    def terminate_process(self, pid: int) -> bool:
        """Terminate a process"""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            logger.info(f"🛑 Terminated process: {pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to terminate {pid}: {e}")
            return False
    
    def set_process_priority(self, pid: int, priority: str) -> bool:
        """Set process priority (high, normal, low)"""
        try:
            proc = psutil.Process(pid)
            
            priority_map = {
                'high': psutil.HIGH_PRIORITY_CLASS if hasattr(psutil, 'HIGH_PRIORITY_CLASS') else -20,
                'normal': psutil.NORMAL_PRIORITY_CLASS if hasattr(psutil, 'NORMAL_PRIORITY_CLASS') else 0,
                'low': psutil.IDLE_PRIORITY_CLASS if hasattr(psutil, 'IDLE_PRIORITY_CLASS') else 19
            }
            
            proc.nice(priority_map.get(priority, 0))
            logger.info(f"⚙️ Set priority for {pid} to {priority}")
            return True
        except Exception as e:
            logger.error(f"Failed to set priority: {e}")
            return False


class PowerManager:
    """
    Power Management
    
    Manages system power settings.
    """
    
    def __init__(self):
        pass
    
    def get_battery_info(self) -> Dict[str, Any]:
        """Get battery information"""
        try:
            battery = psutil.sensors_battery()
            
            if battery:
                return {
                    'percent': battery.percent,
                    'plugged': battery.power_plugged,
                    'time_left': battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
                }
            else:
                return {'available': False}
        except:
            return {'available': False}
    
    def get_power_mode(self) -> str:
        """Get current power mode"""
        battery = self.get_battery_info()
        
        if not battery.get('available'):
            return 'desktop'
        
        if battery.get('plugged'):
            return 'performance'
        elif battery.get('percent', 100) < 20:
            return 'power_save'
        else:
            return 'balanced'
