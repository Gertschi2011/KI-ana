#!/usr/bin/env python3
"""
Test Workflow Engine - Task Automation
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.automation.workflow_engine import WorkflowEngine
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold cyan]⚙️ KI-ana OS - Workflow Engine Test[/bold cyan]\n"
        "[green]Testing Task Automation[/green]",
        title="Workflow Engine Test"
    ))
    
    # Initialize
    engine = WorkflowEngine()
    
    console.print("\n[bold yellow]Creating Workflows...[/bold yellow]\n")
    
    # Workflow 1: High CPU Alert
    engine.add_workflow(
        name="High CPU Alert",
        trigger="if:cpu>2",  # Low threshold for testing
        actions=[
            {"type": "log", "message": "⚠️ High CPU usage detected!"},
            {"type": "notify", "message": "CPU usage is high"}
        ]
    )
    
    # Workflow 2: Startup Tasks
    engine.add_workflow(
        name="Startup Tasks",
        trigger="event:startup",
        actions=[
            {"type": "log", "message": "🚀 System starting up..."},
            {"type": "scan"},
            {"type": "log", "message": "✅ Startup complete"}
        ]
    )
    
    # Workflow 3: Periodic Optimization
    engine.add_workflow(
        name="System Cleanup",
        trigger="event:manual",
        actions=[
            {"type": "log", "message": "🧹 Starting system cleanup..."},
            {"type": "optimize"},
            {"type": "log", "message": "✅ Cleanup complete"}
        ]
    )
    
    # Workflow 4: Command Execution
    engine.add_workflow(
        name="System Info",
        trigger="event:info",
        actions=[
            {"type": "command", "command": "Zeige System Info"}
        ]
    )
    
    # Show all workflows
    table = Table(title="Registered Workflows", show_header=True)
    table.add_column("Name", style="cyan", width=25)
    table.add_column("Trigger", style="yellow", width=25)
    table.add_column("Actions", style="green", width=15)
    table.add_column("Status", style="magenta", width=10)
    
    for workflow in engine.get_workflows():
        table.add_row(
            workflow["name"],
            workflow["trigger"],
            str(len(workflow["actions"])),
            "✅ Enabled" if workflow["enabled"] else "❌ Disabled"
        )
    
    console.print(table)
    
    # Test triggers
    console.print("\n[bold yellow]Testing Triggers...[/bold yellow]\n")
    
    # Test 1: High CPU trigger
    console.print("[cyan]Test 1: High CPU Alert (if:cpu>2)[/cyan]")
    await engine.monitor({})
    
    # Test 2: Startup event
    console.print("\n[cyan]Test 2: Startup Event[/cyan]")
    await engine.monitor({"event": "startup"})
    
    # Test 3: Manual trigger
    console.print("\n[cyan]Test 3: Manual Cleanup[/cyan]")
    await engine.monitor({"event": "manual"})
    
    # Test 4: System info command
    console.print("\n[cyan]Test 4: System Info Command[/cyan]")
    await engine.monitor({"event": "info"})
    
    console.print("\n[bold cyan]✅ Workflow Engine test complete![/bold cyan]\n")


if __name__ == "__main__":
    asyncio.run(main())
