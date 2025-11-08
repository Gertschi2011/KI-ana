#!/usr/bin/env python3
"""
KI-ana OS - Smart Brain Entry Point

Interactive mode with LLM-powered intelligence.
"""

import asyncio
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from smart_brain import get_smart_brain

console = Console()


async def interactive_mode():
    """Run Smart Brain in interactive mode"""
    
    # Get Smart Brain
    brain = await get_smart_brain()
    
    # Check if LLM is available
    llm_status = "🤖 LLM Active" if brain.llm_intent_recognizer.llm and brain.llm_intent_recognizer.llm.is_available else "📝 Fallback Mode"
    
    console.print(Panel.fit(
        f"[bold cyan]🧠 KI-ana OS - Smart Brain[/bold cyan]\n"
        f"[green]{llm_status}[/green]\n\n"
        "Try:\n"
        "  • 'Wie viel RAM habe ich?'\n"
        "  • 'Mein Computer ist langsam'\n"
        "  • 'Welche GPU habe ich?'\n"
        "  • 'Optimiere mein System'\n"
        "  • 'Hallo, wie geht es dir?'\n\n"
        "Type 'exit' to quit",
        title="Welcome to KI-ana OS"
    ))
    
    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold yellow]You:[/bold yellow] ")
            
            if user_input.lower() in ['exit', 'quit', 'bye', 'tschüss']:
                console.print("[green]Auf Wiedersehen! 👋[/green]")
                break
            
            if not user_input.strip():
                continue
            
            # Process command
            console.print("[cyan]KI-ana:[/cyan] ", end="")
            result = await brain.process_command(user_input)
            
            if result["success"]:
                # Show response
                console.print(f"[white]{result['response']}[/white]")
                
                # Show intent info (optional, for demo)
                intent = result.get("intent", {})
                if intent.get("llm_used"):
                    console.print(f"[dim]  💡 LLM understood: {intent['action']} (confidence: {intent.get('confidence', 0):.2f})[/dim]")
                
            else:
                console.print(f"[red]{result.get('response', 'Error')}[/red]")
                
        except KeyboardInterrupt:
            console.print("\n[green]Auf Wiedersehen! 👋[/green]")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            console.print(f"[red]Error: {e}[/red]")
    
    # Shutdown
    await brain.shutdown()


def main():
    """Main entry point"""
    logger.info("🚀 Starting KI-ana OS Smart Brain...")
    
    try:
        asyncio.run(interactive_mode())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
