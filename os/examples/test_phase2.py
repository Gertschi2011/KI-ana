#!/usr/bin/env python3
"""
Test Phase 2 Features

Test multi-model and RAG systems.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.nlp.model_manager import get_model_manager
from core.nlp.rag_system import get_rag_system
from rich.console import Console
from rich.table import Table

console = Console()


async def test_model_manager():
    """Test model manager"""
    console.print("\n[bold cyan]🤖 Testing Model Manager[/bold cyan]\n")
    
    manager = await get_model_manager()
    
    # List models
    console.print("[yellow]Available models:[/yellow]")
    
    table = Table(show_header=True)
    table.add_column("Model", style="cyan")
    table.add_column("Speed", style="yellow")
    table.add_column("Quality", style="green")
    table.add_column("Size", style="white")
    
    for model in manager.list_models():
        table.add_row(
            model["name"],
            model["speed"],
            model["quality"],
            f"{model['size_gb']} GB"
        )
    
    console.print(table)
    
    # Current model
    console.print(f"\n[green]Current model: {manager.get_current_model()}[/green]")
    
    # Recommendations
    console.print("\n[yellow]Recommendations:[/yellow]")
    console.print(f"  Quick tasks: {manager.recommend_model('quick')}")
    console.print(f"  Complex tasks: {manager.recommend_model('complex')}")
    console.print(f"  Coding: {manager.recommend_model('code')}")


def test_rag_system():
    """Test RAG system"""
    console.print("\n[bold cyan]📚 Testing RAG System[/bold cyan]\n")
    
    rag = get_rag_system()
    
    # Add some documents
    rag.add_document(
        "KI-ana OS is an AI-first operating system that learns from you.",
        {"title": "About KI-ana", "type": "info"}
    )
    
    rag.add_document(
        "The system can optimize performance, install drivers, and predict issues.",
        {"title": "Features", "type": "info"}
    )
    
    # Search
    console.print("[yellow]Searching knowledge base...[/yellow]")
    results = rag.search("optimize", limit=2)
    
    console.print(f"\n[green]Found {len(results)} documents:[/green]")
    for doc in results:
        console.print(f"  • {doc.metadata.get('title')}: {doc.content[:50]}...")
    
    # Stats
    stats = rag.get_stats()
    console.print(f"\n[cyan]Knowledge base stats:[/cyan]")
    console.print(f"  Documents: {stats['total_documents']}")
    console.print(f"  Location: {stats['kb_path']}")


async def main():
    """Run all tests"""
    console.print("\n[bold]🚀 Phase 2 Features Test[/bold]\n")
    
    await test_model_manager()
    test_rag_system()
    
    console.print("\n[bold green]✅ Phase 2 tests complete![/bold green]\n")


if __name__ == "__main__":
    asyncio.run(main())
