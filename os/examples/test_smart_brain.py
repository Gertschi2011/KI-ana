#!/usr/bin/env python3
"""
Test Smart Brain (LLM-powered)

Full end-to-end test with LLM integration.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ai_engine.smart_brain import get_smart_brain
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold cyan]🧠 KI-ana OS - Smart Brain Test[/bold cyan]\n"
        "[green]Testing LLM-powered AI[/green]",
        title="Smart Brain Test"
    ))
    
    # Initialize
    brain = await get_smart_brain()
    
    # Check LLM status
    llm_available = brain.llm_intent_recognizer.llm and brain.llm_intent_recognizer.llm.is_available
    
    if llm_available:
        console.print("\n[bold green]✅ LLM is active! Using AI understanding.[/bold green]")
    else:
        console.print("\n[bold yellow]⚠️  LLM not available. Using fallback mode.[/bold yellow]")
        console.print("[dim]Install Ollama and run: ollama pull llama3.1:8b[/dim]")
    
    # Test commands
    test_commands = [
        "Wie viel RAM habe ich?",
        "Mein Computer ist sehr langsam",
        "Zeige mir meine GPU",
        "Scanne alle Geräte",
        "Hallo, wie geht es dir?",
        "Was kannst du alles?"
    ]
    
    console.print("\n[bold yellow]Running test commands:[/bold yellow]\n")
    
    # Create results table
    table = Table(title="Test Results", show_header=True)
    table.add_column("Command", style="cyan", width=40)
    table.add_column("Intent", style="yellow", width=20)
    table.add_column("LLM", style="magenta", width=10)
    table.add_column("Status", style="green", width=10)
    
    for cmd in test_commands:
        console.print(f"[cyan]→ {cmd}[/cyan]")
        
        result = await brain.process_command(cmd)
        
        intent = result.get("intent", {})
        llm_used = "🤖 Yes" if intent.get("llm_used") else "📝 No"
        status = "✅" if result["success"] else "❌"
        
        table.add_row(
            cmd,
            intent.get("action", "unknown"),
            llm_used,
            status
        )
        
        if result["success"]:
            console.print(f"[green]  {result['response']}[/green]")
        else:
            console.print(f"[red]  Error: {result.get('error', 'Unknown')}[/red]")
        
        console.print()
        
        # Small delay between commands
        await asyncio.sleep(0.5)
    
    # Show results table
    console.print(table)
    
    # Hardware summary
    console.print("\n[bold cyan]Hardware Summary:[/bold cyan]")
    hw = brain.hardware_profile
    
    if hw.get("cpu"):
        cpu = hw["cpu"]
        console.print(f"  CPU: {cpu.get('physical_cores', 0)} cores, {cpu.get('usage_percent', 0)}% used")
    
    if hw.get("memory"):
        mem = hw["memory"]
        console.print(f"  RAM: {mem.get('total_gb', 0)} GB total, {mem.get('percent_used', 0)}% used")
    
    if hw.get("gpu"):
        for i, gpu in enumerate(hw["gpu"]):
            console.print(f"  GPU {i+1}: [{gpu.get('vendor', 'Unknown')}] {gpu.get('model', 'Unknown')}")
    
    # Shutdown
    await brain.shutdown()
    
    console.print("\n[bold cyan]✅ Smart Brain test complete![/bold cyan]\n")


if __name__ == "__main__":
    asyncio.run(main())
