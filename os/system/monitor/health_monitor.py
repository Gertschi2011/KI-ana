"""
Health Monitor

Monitors system health and predicts issues.
"""

import asyncio
from typing import Dict, Any, List
from loguru import logger
import psutil
from datetime import datetime, timedelta


class HealthMonitor:
    """
    System Health Monitor
    
    Monitors system health and predicts potential issues.
    """
    
    def __init__(self):
        self.health_history: List[Dict] = []
        self.alerts: List[Dict] = []
        
    async def check_health(self) -> Dict[str, Any]:
        """
        Complete system health check
        
        Returns:
            Health status report
        """
        logger.info("🏥 Performing health check...")
        
        checks = {
            "cpu": await self._check_cpu_health(),
            "memory": await self._check_memory_health(),
            "disk": await self._check_disk_health(),
            "temperature": await self._check_temperature(),
            "processes": await self._check_processes(),
        }
        
        # Overall health score (0-100)
        health_score = self._calculate_health_score(checks)
        
        # Generate warnings
        warnings = self._generate_warnings(checks)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "health_score": health_score,
            "status": self._get_health_status(health_score),
            "checks": checks,
            "warnings": warnings,
            "recommendations": self._get_recommendations(checks)
        }
        
        # Store history
        self.health_history.append(report)
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        logger.info(f"Health check complete: {health_score}/100 ({report['status']})")
        return report
    
    async def _check_cpu_health(self) -> Dict[str, Any]:
        """Check CPU health"""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()
        load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
        
        return {
            "usage_percent": cpu_percent,
            "frequency_mhz": cpu_freq.current if cpu_freq else 0,
            "load_average": {
                "1min": load_avg[0],
                "5min": load_avg[1],
                "15min": load_avg[2]
            },
            "healthy": cpu_percent < 80,
            "score": max(0, 100 - cpu_percent)
        }
    
    async def _check_memory_health(self) -> Dict[str, Any]:
        """Check memory health"""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "usage_percent": mem.percent,
            "available_gb": round(mem.available / (1024**3), 2),
            "swap_used_percent": swap.percent,
            "healthy": mem.percent < 85 and swap.percent < 50,
            "score": max(0, 100 - mem.percent)
        }
    
    async def _check_disk_health(self) -> Dict[str, Any]:
        """Check disk health"""
        disk_usage = []
        min_score = 100
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                score = max(0, 100 - usage.percent)
                min_score = min(min_score, score)
                
                disk_usage.append({
                    "mountpoint": partition.mountpoint,
                    "usage_percent": usage.percent,
                    "free_gb": round(usage.free / (1024**3), 2),
                    "healthy": usage.percent < 90
                })
            except:
                pass
        
        return {
            "partitions": disk_usage,
            "healthy": all(d["healthy"] for d in disk_usage),
            "score": min_score
        }
    
    async def _check_temperature(self) -> Dict[str, Any]:
        """Check system temperature (if available)"""
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                max_temp = 0
                for name, entries in temps.items():
                    for entry in entries:
                        max_temp = max(max_temp, entry.current)
                
                return {
                    "max_temp_celsius": max_temp,
                    "healthy": max_temp < 80,
                    "score": max(0, 100 - (max_temp / 100 * 100))
                }
        except:
            pass
        
        return {
            "available": False,
            "healthy": True,
            "score": 100
        }
    
    async def _check_processes(self) -> Dict[str, Any]:
        """Check process health"""
        try:
            process_count = len(psutil.pids())
            zombie_count = len([p for p in psutil.process_iter(['status']) if p.info['status'] == 'zombie'])
            
            return {
                "total_processes": process_count,
                "zombie_processes": zombie_count,
                "healthy": zombie_count == 0,
                "score": 100 if zombie_count == 0 else 70
            }
        except:
            return {
                "healthy": True,
                "score": 100
            }
    
    def _calculate_health_score(self, checks: Dict[str, Any]) -> int:
        """Calculate overall health score"""
        scores = [check.get("score", 100) for check in checks.values()]
        return int(sum(scores) / len(scores)) if scores else 100
    
    def _get_health_status(self, score: int) -> str:
        """Get health status from score"""
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 40:
            return "Poor"
        else:
            return "Critical"
    
    def _generate_warnings(self, checks: Dict[str, Any]) -> List[str]:
        """Generate warnings based on checks"""
        warnings = []
        
        # CPU warnings
        cpu = checks.get("cpu", {})
        if cpu.get("usage_percent", 0) > 80:
            warnings.append(f"High CPU usage: {cpu['usage_percent']}%")
        
        # Memory warnings
        mem = checks.get("memory", {})
        if mem.get("usage_percent", 0) > 85:
            warnings.append(f"High memory usage: {mem['usage_percent']}%")
        if mem.get("swap_used_percent", 0) > 50:
            warnings.append(f"High swap usage: {mem['swap_used_percent']}%")
        
        # Disk warnings
        disk = checks.get("disk", {})
        for partition in disk.get("partitions", []):
            if partition["usage_percent"] > 90:
                warnings.append(f"Disk almost full: {partition['mountpoint']} ({partition['usage_percent']}%)")
        
        # Temperature warnings
        temp = checks.get("temperature", {})
        if temp.get("max_temp_celsius", 0) > 80:
            warnings.append(f"High temperature: {temp['max_temp_celsius']}°C")
        
        return warnings
    
    def _get_recommendations(self, checks: Dict[str, Any]) -> List[str]:
        """Get recommendations for improving health"""
        recommendations = []
        
        cpu = checks.get("cpu", {})
        if cpu.get("usage_percent", 0) > 80:
            recommendations.append("Close unused applications to reduce CPU load")
        
        mem = checks.get("memory", {})
        if mem.get("usage_percent", 0) > 85:
            recommendations.append("Close memory-intensive applications or add more RAM")
        
        disk = checks.get("disk", {})
        for partition in disk.get("partitions", []):
            if partition["usage_percent"] > 90:
                recommendations.append(f"Free up disk space on {partition['mountpoint']}")
        
        if not recommendations:
            recommendations.append("System is healthy! No actions needed.")
        
        return recommendations
