#!/usr/bin/env python3
"""
KI-ana OS - Comprehensive Test Suite

Tests all major components.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def test_ai_core():
    """Test AI Core"""
    try:
        from core.ai_engine.smart_brain import get_smart_brain
        brain = await get_smart_brain()
        result = await brain.process_command("test")
        return result is not None
    except Exception as e:
        console.print(f"[red]AI Core Error: {e}[/red]")
        return False


async def test_hardware():
    """Test Hardware"""
    try:
        from core.hardware.scanner import HardwareScanner
        scanner = HardwareScanner()
        hw = await scanner.full_scan()
        return "cpu" in hw and "memory" in hw
    except Exception as e:
        console.print(f"[red]Hardware Error: {e}[/red]")
        return False


async def test_drivers():
    """Test Driver System"""
    try:
        from system.drivers.manager import DriverManager
        manager = DriverManager()
        return manager is not None
    except Exception as e:
        console.print(f"[red]Driver Error: {e}[/red]")
        return False


async def test_monitor():
    """Test System Monitor"""
    try:
        from system.monitor.health_monitor import HealthMonitor
        monitor = HealthMonitor()
        report = await monitor.check_health()
        return "health_score" in report
    except Exception as e:
        console.print(f"[red]Monitor Error: {e}[/red]")
        return False


async def test_memory_system():
    """Test Memory System"""
    try:
        from core.ai_engine.memory_system import MemorySystem
        memory = MemorySystem()
        memory.add_conversation("test", "test", "test", True)
        return len(memory.get_conversation_history()) > 0
    except Exception as e:
        console.print(f"[red]Memory Error: {e}[/red]")
        return False


async def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold cyan]🧪 KI-ana OS - Test Suite[/bold cyan]\n"
        "[green]Running comprehensive tests...[/green]",
        title="Test Suite"
    ))
    
    tests = [
        ("AI Core Engine", test_ai_core),
        ("Hardware Scanner", test_hardware),
        ("Driver System", test_drivers),
        ("System Monitor", test_monitor),
        ("Memory System", test_memory_system),
    ]
    
    results = []
    
    for name, test_func in tests:
        console.print(f"\n[yellow]Testing {name}...[/yellow]")
        try:
            result = await test_func()
            results.append((name, result))
            
            if result:
                console.print(f"[green]✅ {name} passed[/green]")
            else:
                console.print(f"[red]❌ {name} failed[/red]")
        except Exception as e:
            console.print(f"[red]❌ {name} crashed: {e}[/red]")
            results.append((name, False))
    
    # Summary
    console.print("\n" + "="*50)
    
    table = Table(title="Test Results", show_header=True)
    table.add_column("Test", style="cyan")
    table.add_column("Result", style="white")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        color = "green" if result else "red"
        table.add_row(name, f"[{color}]{status}[/{color}]")
    
    console.print(table)
    
    console.print(f"\n[bold]Results: {passed}/{total} tests passed[/bold]")
    
    if passed == total:
        console.print("[bold green]🎉 ALL TESTS PASSED![/bold green]")
    else:
        console.print(f"[bold yellow]⚠️  {total - passed} tests failed[/bold yellow]")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
