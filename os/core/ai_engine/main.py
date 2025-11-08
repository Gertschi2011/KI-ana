#!/usr/bin/env python3
"""
KI-ana OS - AI Core Engine Entry Point

This is the main entry point for the AI Core Engine.
Run this to start the AI brain.
"""

import asyncio
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from brain import get_brain

console = Console()


async def interactive_mode():
    """Run AI Core in interactive mode (for testing)"""
    
    # Get AI Brain
    brain = await get_brain()
    
    console.print(Panel.fit(
        "[bold cyan]🧠 KI-ana OS - AI Core Engine[/bold cyan]\n"
        "[green]Ready for commands![/green]\n\n"
        "Try:\n"
        "  • 'Zeige System Info'\n"
        "  • 'Optimiere System'\n"
        "  • 'Scanne Hardware'\n"
        "  • 'Hilfe'\n\n"
        "Type 'exit' to quit",
        title="Welcome"
    ))
    
    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold yellow]You:[/bold yellow] ")
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                console.print("[green]Auf Wiedersehen! 👋[/green]")
                break
            
            if not user_input.strip():
                continue
            
            # Process command
            console.print("[cyan]KI-ana:[/cyan] Verarbeite...", end="")
            result = await brain.process_command(user_input)
            console.print("\r" + " " * 50 + "\r", end="")  # Clear line
            
            if result["success"]:
                # Show response
                console.print(f"[cyan]KI-ana:[/cyan] {result['response']}")
                
                # Show data if available
                if result.get("result", {}).get("data"):
                    console.print("\n[dim]Details:[/dim]")
                    console.print(result["result"]["data"])
            else:
                console.print(f"[red]Error:[/red] {result.get('error', 'Unknown error')}")
                
        except KeyboardInterrupt:
            console.print("\n[green]Auf Wiedersehen! 👋[/green]")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            console.print(f"[red]Error:[/red] {e}")
    
    # Shutdown
    await brain.shutdown()


def main():
    """Main entry point"""
    logger.info("🚀 Starting KI-ana OS AI Core Engine...")
    
    try:
        asyncio.run(interactive_mode())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
