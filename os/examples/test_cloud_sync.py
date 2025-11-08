#!/usr/bin/env python3
"""
Test Cloud Sync between OS and Mutter-KI
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sync.cloud_sync import CloudSync
from rich.console import Console
from rich.panel import Panel

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold cyan]☁️ KI-ana OS - Cloud Sync Test[/bold cyan]\n"
        "[green]Testing OS ↔ Mutter-KI Synchronization[/green]",
        title="Cloud Sync Test"
    ))
    
    # Initialize
    sync = CloudSync()
    
    console.print(f"\n[cyan]Device ID:[/cyan] {sync.device_id}")
    console.print(f"[cyan]Sync URL:[/cyan] {sync.sync_url}")
    console.print(f"[cyan]Sync Enabled:[/cyan] {sync.sync_enabled}\n")
    
    # Test 1: Push settings
    console.print("[bold yellow]Test 1: Push Settings[/bold yellow]")
    
    test_settings = {
        "theme": "dark",
        "language": "de",
        "voice_enabled": True,
        "ai_model": "llama3.1:8b"
    }
    
    result = await sync.sync_settings(test_settings)
    
    if result:
        console.print("[green]✅ Settings pushed successfully[/green]")
    else:
        console.print("[red]❌ Settings push failed[/red]")
    
    # Test 2: Pull settings
    console.print("\n[bold yellow]Test 2: Pull Settings[/bold yellow]")
    
    pulled = await sync.pull_settings()
    
    if pulled:
        console.print("[green]✅ Settings pulled successfully[/green]")
        console.print(f"[dim]Data: {pulled}[/dim]")
    else:
        console.print("[red]❌ Settings pull failed[/red]")
    
    # Test 3: Sync conversations
    console.print("\n[bold yellow]Test 3: Sync Conversations[/bold yellow]")
    
    test_conversations = [
        {"user": "Hallo", "assistant": "Hallo! Wie kann ich dir helfen?", "timestamp": "2025-10-26T08:00:00"},
        {"user": "Wie viel RAM habe ich?", "assistant": "Du hast 7.74 GB RAM.", "timestamp": "2025-10-26T08:01:00"}
    ]
    
    result = await sync.sync_conversations(test_conversations)
    
    if result:
        console.print("[green]✅ Conversations synced successfully[/green]")
    else:
        console.print("[red]❌ Conversations sync failed[/red]")
    
    # Test 4: Auto-sync all
    console.print("\n[bold yellow]Test 4: Auto-Sync All Data[/bold yellow]")
    
    all_data = {
        "settings": test_settings,
        "conversations": test_conversations
    }
    
    result = await sync.auto_sync(all_data)
    
    if result:
        console.print("[green]✅ Auto-sync successful[/green]")
    else:
        console.print("[yellow]⚠️  Auto-sync partially successful[/yellow]")
    
    # Status
    console.print("\n[bold cyan]Sync Status:[/bold cyan]")
    status = sync.get_sync_status()
    
    for key, value in status.items():
        console.print(f"  {key}: {value}")
    
    console.print("\n[bold cyan]✅ Cloud Sync test complete![/bold cyan]\n")


if __name__ == "__main__":
    asyncio.run(main())
