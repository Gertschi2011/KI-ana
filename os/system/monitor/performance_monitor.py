"""
Performance Monitor

Real-time performance monitoring.
"""

import asyncio
from typing import Dict, Any, List
from loguru import logger
import psutil
from datetime import datetime
import time


class PerformanceMonitor:
    """
    Real-time Performance Monitor
    
    Monitors system performance metrics in real-time.
    """
    
    def __init__(self):
        self.monitoring = False
        self.metrics_history: List[Dict] = []
        
    async def start_monitoring(self, interval: int = 1, duration: int = 60):
        """
        Start monitoring for a duration
        
        Args:
            interval: Seconds between measurements
            duration: Total monitoring duration
        """
        logger.info(f"📊 Starting performance monitoring ({duration}s)...")
        
        self.monitoring = True
        self.metrics_history = []
        
        start_time = time.time()
        
        while self.monitoring and (time.time() - start_time) < duration:
            metrics = await self.get_current_metrics()
            self.metrics_history.append(metrics)
            
            await asyncio.sleep(interval)
        
        self.monitoring = False
        logger.info("📊 Monitoring stopped")
        
        return self.get_summary()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=0.1),
                "per_cpu": psutil.cpu_percent(interval=0.1, percpu=True)
            },
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2)
            },
            "disk_io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
            "network_io": psutil.net_io_counters()._asdict(),
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.metrics_history:
            return {"error": "No data collected"}
        
        cpu_values = [m["cpu"]["percent"] for m in self.metrics_history]
        mem_values = [m["memory"]["percent"] for m in self.metrics_history]
        
        return {
            "duration_seconds": len(self.metrics_history),
            "measurements": len(self.metrics_history),
            "cpu": {
                "avg": round(sum(cpu_values) / len(cpu_values), 2),
                "min": round(min(cpu_values), 2),
                "max": round(max(cpu_values), 2)
            },
            "memory": {
                "avg": round(sum(mem_values) / len(mem_values), 2),
                "min": round(min(mem_values), 2),
                "max": round(max(mem_values), 2)
            }
        }
