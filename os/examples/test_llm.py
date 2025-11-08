#!/usr/bin/env python3
"""
Test LLM Integration

Test Ollama integration and LLM-based features.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.nlp.llm_client import get_llm_client
from core.nlp.intent_llm import LLMIntentRecognizer
from core.nlp.response_generator import ResponseGenerator
from rich.console import Console
from rich.panel import Panel

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold cyan]🤖 KI-ana OS - LLM Integration Test[/bold cyan]\n"
        "[green]Testing Ollama connection and LLM features[/green]",
        title="LLM Test"
    ))
    
    # 1. Test LLM Client
    console.print("\n[bold yellow]1. Testing LLM Client...[/bold yellow]")
    llm = await get_llm_client()
    
    if llm.is_available:
        console.print("[green]✅ Ollama is running![/green]")
        
        # Test generation
        console.print("\n[cyan]Testing generation...[/cyan]")
        response = await llm.generate("Say hello in German", temperature=0.7)
        console.print(f"[white]Response: {response}[/white]")
    else:
        console.print("[red]❌ Ollama not available[/red]")
        console.print("[yellow]Install: curl -fsSL https://ollama.com/install.sh | sh[/yellow]")
        console.print("[yellow]Then run: ollama pull llama3.1:8b[/yellow]")
        return
    
    # 2. Test Intent Recognition
    console.print("\n[bold yellow]2. Testing Intent Recognition...[/bold yellow]")
    recognizer = LLMIntentRecognizer()
    await recognizer.initialize()
    
    test_inputs = [
        "Zeige mir die CPU Info",
        "Mein System ist langsam",
        "Scanne meine Hardware",
        "Wie geht es dir?",
    ]
    
    for user_input in test_inputs:
        console.print(f"\n[cyan]→ \"{user_input}\"[/cyan]")
        intent = await recognizer.recognize(user_input, {})
        console.print(f"[green]  Action: {intent['action']} (confidence: {intent['confidence']})[/green]")
        if intent.get('reasoning'):
            console.print(f"[dim]  Reasoning: {intent['reasoning']}[/dim]")
    
    # 3. Test Response Generator
    console.print("\n[bold yellow]3. Testing Response Generator...[/bold yellow]")
    generator = ResponseGenerator()
    await generator.initialize()
    
    test_result = {
        "success": True,
        "data": {"cpu_cores": 8, "ram_gb": 16}
    }
    
    response = await generator.generate(
        {"action": "system_info"},
        test_result,
        {}
    )
    
    console.print(f"\n[cyan]Generated response:[/cyan]")
    console.print(f"[white]{response}[/white]")
    
    # Cleanup
    await llm.shutdown()
    
    console.print("\n[bold green]✅ All LLM tests completed![/bold green]\n")


if __name__ == "__main__":
    asyncio.run(main())
