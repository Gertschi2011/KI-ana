#!/usr/bin/env python3
"""
Test Enhanced AI Brain

Interactive test of the full AI Brain with hardware intelligence.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ai_engine.enhanced_brain import get_enhanced_brain
from rich.console import Console
from rich.panel import Panel

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold cyan]🧠 KI-ana OS - Enhanced AI Brain Test[/bold cyan]\n"
        "[green]Initializing...[/green]",
        title="Starting"
    ))
    
    # Get Enhanced AI Brain
    brain = await get_enhanced_brain()
    
    console.print("\n[bold green]✅ Enhanced AI Brain ready![/bold green]\n")
    
    # Test commands
    test_commands = [
        "Zeige System Info",
        "Scanne Hardware",
        "Optimiere System",
        "Zeige Treiber Empfehlungen"
    ]
    
    console.print("[bold yellow]Running test commands:[/bold yellow]\n")
    
    for cmd in test_commands:
        console.print(f"[cyan]→ {cmd}[/cyan]")
        
        result = await brain.process_command(cmd)
        
        if result["success"]:
            console.print(f"[green]  ✅ {result['response']}[/green]\n")
        else:
            console.print(f"[red]  ❌ Error: {result.get('error', 'Unknown')}[/red]\n")
    
    # Shutdown
    await brain.shutdown()
    
    console.print("[bold cyan]✅ All tests passed![/bold cyan]\n")


if __name__ == "__main__":
    asyncio.run(main())
