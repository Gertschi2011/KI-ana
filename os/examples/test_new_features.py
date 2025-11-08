#!/usr/bin/env python3
"""
Test New Features (F)

Tests: System Updater, Plugin System, Performance Dashboard
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.system.updater import get_updater
from core.plugins.plugin_manager import get_plugin_manager
from core.monitoring.performance_dashboard import get_dashboard
from rich.console import Console
from rich.panel import Panel

console = Console()


async def test_updater():
    """Test 1: System Updater"""
    console.print(Panel.fit(
        "[bold cyan]📦 Feature 1: System Updater[/bold cyan]",
        title="System Update Mechanism"
    ))
    
    updater = await get_updater()
    
    # Get version info
    console.print("\n[yellow]Current Version Info:[/yellow]")
    version_info = updater.get_version_info()
    for key, value in version_info.items():
        console.print(f"  {key}: {value}")
    
    # Check for updates
    console.print("\n[yellow]Checking for updates...[/yellow]")
    updates = await updater.check_updates()
    
    console.print(f"  Updates available: {updates['total_updates']}")
    
    if updates['total_updates'] > 0:
        console.print("\n[dim]Outdated packages:[/dim]")
        for pkg in updates['component_updates'][:5]:  # Show first 5
            console.print(f"  - {pkg['name']}: {pkg['version']} → {pkg['latest_version']}")
    
    console.print("\n[green]✅ System Updater test complete[/green]\n")


def test_plugins():
    """Test 2: Plugin System"""
    console.print(Panel.fit(
        "[bold cyan]🔌 Feature 2: Plugin System[/bold cyan]",
        title="Extensible Plugin Architecture"
    ))
    
    manager = get_plugin_manager()
    
    # Discover plugins
    console.print("\n[yellow]Discovering plugins...[/yellow]")
    plugins = manager.discover_plugins()
    console.print(f"  Found: {plugins}")
    
    # Load all plugins
    console.print("\n[yellow]Loading plugins...[/yellow]")
    manager.load_all_plugins()
    
    # List loaded plugins
    console.print("\n[yellow]Loaded Plugins:[/yellow]")
    for plugin_info in manager.list_plugins():
        console.print(f"  ✅ {plugin_info['name']} v{plugin_info['version']}")
        console.print(f"     {plugin_info['description']}")
    
    # Execute plugin
    if "hello_plugin" in manager.plugins:
        console.print("\n[yellow]Executing Hello Plugin:[/yellow]")
        result = manager.execute_plugin("hello_plugin", name="KI-ana")
        console.print(f"  {result}")
    
    console.print("\n[green]✅ Plugin System test complete[/green]\n")


def test_dashboard():
    """Test 3: Performance Dashboard"""
    console.print(Panel.fit(
        "[bold cyan]📊 Feature 3: Performance Dashboard[/bold cyan]",
        title="Real-time Performance Monitoring"
    ))
    
    dashboard = get_dashboard()
    
    # Collect metrics
    console.print("\n[yellow]Collecting performance metrics...[/yellow]\n")
    
    # Print formatted dashboard
    dashboard.print_dashboard()
    
    # Get top processes
    console.print("\n[yellow]Top Processes:[/yellow]")
    top = dashboard.get_top_processes(n=3)
    
    console.print("\n[cyan]By CPU:[/cyan]")
    for proc in top["by_cpu"]:
        console.print(f"  {proc['name']}: {proc.get('cpu_percent', 0):.1f}%")
    
    console.print("\n[cyan]By Memory:[/cyan]")
    for proc in top["by_memory"]:
        console.print(f"  {proc['name']}: {proc.get('memory_percent', 0):.1f}%")
    
    console.print("\n[green]✅ Performance Dashboard test complete[/green]\n")


async def main():
    console.print(Panel.fit(
        "[bold cyan]✨ KI-ana OS - New Features Test (F)[/bold cyan]\n"
        "[green]Testing 3 Bonus Features[/green]",
        title="New Features Test"
    ))
    
    # Test all features
    await test_updater()
    test_plugins()
    test_dashboard()
    
    console.print(Panel.fit(
        "[bold green]✅ All 3 New Features Tested Successfully![/bold green]\n"
        "[cyan]1. System Updater ✅\n"
        "2. Plugin System ✅\n"
        "3. Performance Dashboard ✅[/cyan]",
        title="Test Complete"
    ))


if __name__ == "__main__":
    asyncio.run(main())
