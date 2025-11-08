#!/usr/bin/env python3
"""
Test Hardware Intelligence Module

Quick test to verify hardware scanning works.
"""

import asyncio
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.hardware.scanner import HardwareScanner
from core.hardware.optimizer import HardwareOptimizer
from core.hardware.profiler import HardwareProfiler
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


async def main():
    console.print("\n[bold cyan]🔍 KI-ana OS - Hardware Intelligence Test[/bold cyan]\n")
    
    # 1. Scan Hardware
    console.print("[yellow]Scanning hardware...[/yellow]")
    scanner = HardwareScanner()
    hardware = await scanner.full_scan()
    
    # Display CPU
    console.print("\n[bold green]CPU:[/bold green]")
    cpu = hardware.get("cpu", {})
    table = Table()
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Model", cpu.get("model", "Unknown"))
    table.add_row("Cores", f"{cpu.get('physical_cores', 0)} physical / {cpu.get('logical_cores', 0)} logical")
    table.add_row("Usage", f"{cpu.get('usage_percent', 0)}%")
    console.print(table)
    
    # Display GPU
    console.print("\n[bold green]GPU:[/bold green]")
    for i, gpu in enumerate(hardware.get("gpu", [])):
        console.print(f"  {i+1}. [{gpu.get('vendor', 'Unknown')}] {gpu.get('model', 'Unknown')}")
    
    # Display Memory
    console.print("\n[bold green]Memory:[/bold green]")
    mem = hardware.get("memory", {})
    console.print(f"  Total: {mem.get('total_gb', 0)} GB")
    console.print(f"  Used: {mem.get('used_gb', 0)} GB ({mem.get('percent_used', 0)}%)")
    console.print(f"  Available: {mem.get('available_gb', 0)} GB")
    
    # 2. Optimize
    console.print("\n[yellow]Optimizing system...[/yellow]")
    optimizer = HardwareOptimizer()
    result = await optimizer.optimize(hardware)
    
    console.print(f"\n[bold green]✅ Applied {len(result['optimizations_applied'])} optimizations:[/bold green]")
    for opt in result['optimizations_applied']:
        console.print(f"  • {opt}")
    
    # 3. Create Profile
    console.print("\n[yellow]Creating hardware profile...[/yellow]")
    profiler = HardwareProfiler()
    profile = await profiler.create_profile(hardware)
    
    console.print("\n[bold green]Profile created![/bold green]")
    rprint(profile)
    
    console.print("\n[bold cyan]✅ Test completed successfully![/bold cyan]\n")


if __name__ == "__main__":
    asyncio.run(main())
