"""
Monitoring System für KI_ana

Features:
- Health Checks
- Prometheus Metrics
- Uptime Tracking
- Performance Metrics
- Alert System
"""
from __future__ import annotations
import time
import psutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))


@dataclass
class HealthStatus:
    """System health status."""
    status: str  # healthy, degraded, unhealthy
    uptime: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_peers: int
    blocks_count: int
    messages_count: int
    last_check: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PrometheusMetric:
    """Prometheus metric."""
    name: str
    value: float
    labels: Dict[str, str]
    metric_type: str  # counter, gauge, histogram
    help_text: str


class MonitoringService:
    """
    Monitoring Service for KI_ana.
    
    Singleton pattern.
    """
    
    _instance: Optional['MonitoringService'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Start time
        self.start_time = time.time()
        
        # Metrics
        self.metrics: Dict[str, PrometheusMetric] = {}
        
        # Health history
        self.health_history: List[HealthStatus] = []
        
        # Alert thresholds
        self.thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0
        }
        
        print(f"✅ Monitoring Service initialized")
    
    def get_health_status(self) -> HealthStatus:
        """Get current health status."""
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Application metrics
        try:
            from p2p_connection import get_connection_manager
            from block_sync import get_block_sync_manager
            from p2p_messaging import get_p2p_messaging
            
            peers = len(get_connection_manager().get_connected_peers())
            blocks = len(get_block_sync_manager().blocks)
            messages = get_p2p_messaging().get_stats()["delivered_messages"]
        except:
            peers = 0
            blocks = 0
            messages = 0
        
        # Determine status
        status = "healthy"
        if (cpu_percent > self.thresholds["cpu_percent"] or
            memory.percent > self.thresholds["memory_percent"] or
            disk.percent > self.thresholds["disk_percent"]):
            status = "degraded"
        
        if (cpu_percent > 95 or memory.percent > 95 or disk.percent > 95):
            status = "unhealthy"
        
        health = HealthStatus(
            status=status,
            uptime=time.time() - self.start_time,
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            active_peers=peers,
            blocks_count=blocks,
            messages_count=messages,
            last_check=time.time()
        )
        
        # Store in history
        self.health_history.append(health)
        if len(self.health_history) > 1000:
            self.health_history.pop(0)
        
        return health
    
    def get_prometheus_metrics(self) -> str:
        """
        Get metrics in Prometheus format.
        
        Returns metrics as text for Prometheus scraping.
        """
        health = self.get_health_status()
        
        metrics = []
        
        # System metrics
        metrics.append(f"# HELP kiana_uptime_seconds System uptime in seconds")
        metrics.append(f"# TYPE kiana_uptime_seconds gauge")
        metrics.append(f"kiana_uptime_seconds {health.uptime:.2f}")
        
        metrics.append(f"# HELP kiana_cpu_percent CPU usage percentage")
        metrics.append(f"# TYPE kiana_cpu_percent gauge")
        metrics.append(f"kiana_cpu_percent {health.cpu_percent:.2f}")
        
        metrics.append(f"# HELP kiana_memory_percent Memory usage percentage")
        metrics.append(f"# TYPE kiana_memory_percent gauge")
        metrics.append(f"kiana_memory_percent {health.memory_percent:.2f}")
        
        metrics.append(f"# HELP kiana_disk_percent Disk usage percentage")
        metrics.append(f"# TYPE kiana_disk_percent gauge")
        metrics.append(f"kiana_disk_percent {health.disk_percent:.2f}")
        
        # Application metrics
        metrics.append(f"# HELP kiana_active_peers Number of active P2P peers")
        metrics.append(f"# TYPE kiana_active_peers gauge")
        metrics.append(f"kiana_active_peers {health.active_peers}")
        
        metrics.append(f"# HELP kiana_blocks_total Total number of blocks")
        metrics.append(f"# TYPE kiana_blocks_total counter")
        metrics.append(f"kiana_blocks_total {health.blocks_count}")
        
        metrics.append(f"# HELP kiana_messages_total Total number of messages")
        metrics.append(f"# TYPE kiana_messages_total counter")
        metrics.append(f"kiana_messages_total {health.messages_count}")
        
        # Health status (0=unhealthy, 1=degraded, 2=healthy)
        status_value = {"unhealthy": 0, "degraded": 1, "healthy": 2}[health.status]
        metrics.append(f"# HELP kiana_health_status Health status (0=unhealthy, 1=degraded, 2=healthy)")
        metrics.append(f"# TYPE kiana_health_status gauge")
        metrics.append(f"kiana_health_status {status_value}")
        
        return "\n".join(metrics)
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for alert conditions."""
        health = self.get_health_status()
        alerts = []
        
        if health.cpu_percent > self.thresholds["cpu_percent"]:
            alerts.append({
                "severity": "warning",
                "metric": "cpu_percent",
                "value": health.cpu_percent,
                "threshold": self.thresholds["cpu_percent"],
                "message": f"High CPU usage: {health.cpu_percent:.1f}%"
            })
        
        if health.memory_percent > self.thresholds["memory_percent"]:
            alerts.append({
                "severity": "warning",
                "metric": "memory_percent",
                "value": health.memory_percent,
                "threshold": self.thresholds["memory_percent"],
                "message": f"High memory usage: {health.memory_percent:.1f}%"
            })
        
        if health.disk_percent > self.thresholds["disk_percent"]:
            alerts.append({
                "severity": "critical",
                "metric": "disk_percent",
                "value": health.disk_percent,
                "threshold": self.thresholds["disk_percent"],
                "message": f"High disk usage: {health.disk_percent:.1f}%"
            })
        
        if health.status == "unhealthy":
            alerts.append({
                "severity": "critical",
                "metric": "health_status",
                "value": health.status,
                "message": "System is unhealthy!"
            })
        
        return alerts
    
    def get_uptime_string(self) -> str:
        """Get uptime as human-readable string."""
        uptime = time.time() - self.start_time
        
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        
        return " ".join(parts)


# Singleton
_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """Get singleton monitoring service."""
    global _service
    if _service is None:
        _service = MonitoringService()
    return _service


if __name__ == "__main__":
    print("📊 Monitoring Service Test\n")
    
    service = get_monitoring_service()
    
    # Get health status
    print("🏥 Health Status:")
    health = service.get_health_status()
    print(f"   Status: {health.status}")
    print(f"   Uptime: {service.get_uptime_string()}")
    print(f"   CPU: {health.cpu_percent:.1f}%")
    print(f"   Memory: {health.memory_percent:.1f}%")
    print(f"   Disk: {health.disk_percent:.1f}%")
    print(f"   Peers: {health.active_peers}")
    print(f"   Blocks: {health.blocks_count}")
    
    # Check alerts
    print("\n🚨 Alerts:")
    alerts = service.check_alerts()
    if alerts:
        for alert in alerts:
            print(f"   [{alert['severity'].upper()}] {alert['message']}")
    else:
        print("   No alerts")
    
    # Prometheus metrics
    print("\n📈 Prometheus Metrics (sample):")
    metrics = service.get_prometheus_metrics()
    for line in metrics.split('\n')[:10]:
        print(f"   {line}")
    print("   ...")
    
    print("\n✅ Monitoring Service test complete!")
