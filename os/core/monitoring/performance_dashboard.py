"""
Performance Dashboard

Real-time system performance monitoring and visualization.
"""

import psutil
import time
from typing import Dict, Any, List
from loguru import logger
from collections import deque
from datetime import datetime


class PerformanceDashboard:
    """
    Real-time Performance Monitor
    
    Tracks:
    - CPU usage history
    - Memory usage history
    - Disk I/O
    - Network I/O
    - Process statistics
    """
    
    def __init__(self, history_size: int = 60):
        self.history_size = history_size
        
        # Time series data
        self.cpu_history = deque(maxlen=history_size)
        self.memory_history = deque(maxlen=history_size)
        self.disk_history = deque(maxlen=history_size)
        self.network_history = deque(maxlen=history_size)
        
        self.start_time = time.time()
        self.last_network = psutil.net_io_counters()
        self.last_disk = psutil.disk_io_counters()
        
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current performance metrics"""
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1, percpu=False)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        
        # Memory
        memory = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        
        # Network
        network_io = psutil.net_io_counters()
        
        # Calculate rates
        time_delta = time.time() - self.start_time
        
        if time_delta > 0:
            network_recv_rate = (network_io.bytes_recv - self.last_network.bytes_recv) / time_delta
            network_sent_rate = (network_io.bytes_sent - self.last_network.bytes_sent) / time_delta
            
            disk_read_rate = (disk_io.read_bytes - self.last_disk.read_bytes) / time_delta
            disk_write_rate = (disk_io.write_bytes - self.last_disk.write_bytes) / time_delta
        else:
            network_recv_rate = 0
            network_sent_rate = 0
            disk_read_rate = 0
            disk_write_rate = 0
        
        self.last_network = network_io
        self.last_disk = disk_io
        self.start_time = time.time()
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "per_core": cpu_per_core,
                "cores": psutil.cpu_count()
            },
            "memory": {
                "percent": memory.percent,
                "used_gb": memory.used / (1024**3),
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3)
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": disk.used / (1024**3),
                "total_gb": disk.total / (1024**3),
                "read_rate_mb": disk_read_rate / (1024**2),
                "write_rate_mb": disk_write_rate / (1024**2)
            },
            "network": {
                "recv_rate_mb": network_recv_rate / (1024**2),
                "sent_rate_mb": network_sent_rate / (1024**2),
                "total_recv_gb": network_io.bytes_recv / (1024**3),
                "total_sent_gb": network_io.bytes_sent / (1024**3)
            }
        }
        
        # Update history
        self.cpu_history.append(cpu_percent)
        self.memory_history.append(memory.percent)
        self.disk_history.append(disk.percent)
        self.network_history.append(network_recv_rate + network_sent_rate)
        
        return metrics
    
    def get_top_processes(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N processes by CPU and memory"""
        
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU
        by_cpu = sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:n]
        
        # Sort by memory
        by_memory = sorted(processes, key=lambda x: x.get('memory_percent', 0), reverse=True)[:n]
        
        return {
            "by_cpu": by_cpu,
            "by_memory": by_memory
        }
    
    def get_history(self) -> Dict[str, List]:
        """Get historical data"""
        return {
            "cpu": list(self.cpu_history),
            "memory": list(self.memory_history),
            "disk": list(self.disk_history),
            "network": list(self.network_history)
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health assessment"""
        metrics = self.collect_metrics()
        
        # Health scores (0-100)
        cpu_health = 100 - metrics["cpu"]["percent"]
        memory_health = 100 - metrics["memory"]["percent"]
        disk_health = 100 - metrics["disk"]["percent"]
        
        overall_health = (cpu_health + memory_health + disk_health) / 3
        
        # Status
        if overall_health >= 70:
            status = "healthy"
            emoji = "✅"
        elif overall_health >= 40:
            status = "warning"
            emoji = "⚠️"
        else:
            status = "critical"
            emoji = "❌"
        
        return {
            "status": status,
            "emoji": emoji,
            "overall_health": overall_health,
            "cpu_health": cpu_health,
            "memory_health": memory_health,
            "disk_health": disk_health,
            "metrics": metrics
        }
    
    def print_dashboard(self):
        """Print formatted dashboard (for CLI)"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        
        console = Console()
        
        health = self.get_system_health()
        metrics = health["metrics"]
        
        # Health Panel
        console.print(Panel.fit(
            f"[bold]{health['emoji']} System Status: {health['status'].upper()}[/bold]\n"
            f"Overall Health: {health['overall_health']:.1f}%",
            title="System Health"
        ))
        
        # Metrics Table
        table = Table(title="Performance Metrics")
        table.add_column("Resource", style="cyan")
        table.add_column("Current", style="yellow")
        table.add_column("Details", style="green")
        
        table.add_row(
            "CPU",
            f"{metrics['cpu']['percent']:.1f}%",
            f"{metrics['cpu']['cores']} cores"
        )
        
        table.add_row(
            "Memory",
            f"{metrics['memory']['percent']:.1f}%",
            f"{metrics['memory']['used_gb']:.2f} / {metrics['memory']['total_gb']:.2f} GB"
        )
        
        table.add_row(
            "Disk",
            f"{metrics['disk']['percent']:.1f}%",
            f"{metrics['disk']['used_gb']:.1f} / {metrics['disk']['total_gb']:.1f} GB"
        )
        
        table.add_row(
            "Network",
            f"↓ {metrics['network']['recv_rate_mb']:.2f} MB/s",
            f"↑ {metrics['network']['sent_rate_mb']:.2f} MB/s"
        )
        
        console.print(table)


# Singleton
_dashboard_instance = None


def get_dashboard() -> PerformanceDashboard:
    """Get or create dashboard singleton"""
    global _dashboard_instance
    
    if _dashboard_instance is None:
        _dashboard_instance = PerformanceDashboard()
    
    return _dashboard_instance
