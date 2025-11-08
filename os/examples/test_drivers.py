#!/usr/bin/env python3
"""
Test Driver Management System

Test automatic driver detection and recommendations.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from system.drivers.manager import DriverManager
from core.hardware.scanner import HardwareScanner
from core.hardware.profiler import HardwareProfiler
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold cyan]🔧 KI-ana OS - Driver Management Test[/bold cyan]\n"
        "[green]Testing automatic driver detection[/green]",
        title="Driver Test"
    ))
    
    # 1. Scan hardware
    console.print("\n[yellow]1. Scanning hardware...[/yellow]")
    scanner = HardwareScanner()
    hardware = await scanner.full_scan()
    
    # 2. Create profile
    console.print("[yellow]2. Creating hardware profile...[/yellow]")
    profiler = HardwareProfiler()
    profile = await profiler.create_profile(hardware)
    
    # Display GPUs
    console.print("\n[bold green]Detected GPUs:[/bold green]")
    for i, gpu in enumerate(profile.get("gpu", [])):
        console.print(f"  {i+1}. [{gpu.get('vendor')}] {gpu.get('model')}")
        console.print(f"     Type: {gpu.get('type')}")
        console.print(f"     Needs driver: {gpu.get('needs_driver')}")
    
    # 3. Get driver recommendations
    console.print("\n[yellow]3. Getting driver recommendations...[/yellow]")
    manager = DriverManager()
    recommendations = await manager.get_driver_recommendations(profile)
    
    if not recommendations:
        console.print("[green]✅ No drivers needed![/green]")
        return
    
    # Display recommendations
    console.print(f"\n[bold cyan]Found {len(recommendations)} driver recommendations:[/bold cyan]\n")
    
    table = Table(title="Driver Recommendations", show_header=True)
    table.add_column("Device", style="cyan", width=30)
    table.add_column("Driver", style="yellow", width=20)
    table.add_column("Priority", style="magenta", width=10)
    table.add_column("Reason", style="white", width=40)
    
    for rec in recommendations:
        table.add_row(
            rec.get("device", "Unknown"),
            rec.get("driver_name", "Unknown"),
            rec.get("priority", "unknown"),
            rec.get("reason", "")
        )
    
    console.print(table)
    
    # 4. Installation info
    console.print("\n[bold yellow]Installation Commands:[/bold yellow]")
    for rec in recommendations:
        console.print(f"  • {rec.get('install_command', 'N/A')}")
    
    console.print("\n[dim]Note: Actual installation requires root privileges[/dim]")
    console.print("[dim]Run with sudo to install drivers automatically[/dim]")
    
    console.print("\n[bold cyan]✅ Driver detection test complete![/bold cyan]\n")


if __name__ == "__main__":
    asyncio.run(main())
