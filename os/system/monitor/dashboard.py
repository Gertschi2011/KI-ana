"""
System Dashboard

Visual dashboard for system monitoring.
"""

from typing import Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from .health_monitor import HealthMonitor
from .performance_monitor import PerformanceMonitor
import asyncio


class SystemDashboard:
    """
    System Monitoring Dashboard
    
    Displays real-time system information in a beautiful dashboard.
    """
    
    def __init__(self):
        self.console = Console()
        self.health_monitor = HealthMonitor()
        self.perf_monitor = PerformanceMonitor()
        
    async def show_health_report(self):
        """Show health report"""
        report = await self.health_monitor.check_health()
        
        # Create health panel
        health_status = report["status"]
        health_score = report["health_score"]
        
        status_emoji = {
            "Excellent": "✅",
            "Good": "👍",
            "Fair": "⚠️",
            "Poor": "🔶",
            "Critical": "❌"
        }
        
        emoji = status_emoji.get(health_status, "❓")
        
        self.console.print(Panel.fit(
            f"[bold]Health Score: {health_score}/100[/bold]\n"
            f"Status: {emoji} {health_status}",
            title="System Health",
            border_style="green" if health_score >= 75 else "yellow" if health_score >= 50 else "red"
        ))
        
        # Show checks
        self.console.print("\n[bold cyan]Health Checks:[/bold cyan]")
        
        table = Table(show_header=True)
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Score", style="yellow")
        
        for name, check in report["checks"].items():
            status_icon = "✅" if check.get("healthy", True) else "❌"
            table.add_row(
                name.upper(),
                status_icon,
                f"{check.get('score', 0)}/100"
            )
        
        self.console.print(table)
        
        # Show warnings
        if report["warnings"]:
            self.console.print("\n[bold yellow]⚠️  Warnings:[/bold yellow]")
            for warning in report["warnings"]:
                self.console.print(f"  • {warning}")
        
        # Show recommendations
        if report["recommendations"]:
            self.console.print("\n[bold green]💡 Recommendations:[/bold green]")
            for rec in report["recommendations"]:
                self.console.print(f"  • {rec}")
        
        return report
    
    async def show_performance_summary(self):
        """Show performance summary"""
        self.console.print("\n[bold cyan]📊 Performance Summary (last 10 seconds):[/bold cyan]")
        
        # Monitor for 10 seconds
        await self.perf_monitor.start_monitoring(interval=1, duration=10)
        
        summary = self.perf_monitor.get_summary()
        
        table = Table(show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Average", style="yellow")
        table.add_column("Min", style="green")
        table.add_column("Max", style="red")
        
        table.add_row(
            "CPU Usage",
            f"{summary['cpu']['avg']}%",
            f"{summary['cpu']['min']}%",
            f"{summary['cpu']['max']}%"
        )
        
        table.add_row(
            "Memory Usage",
            f"{summary['memory']['avg']}%",
            f"{summary['memory']['min']}%",
            f"{summary['memory']['max']}%"
        )
        
        self.console.print(table)
        
        return summary
