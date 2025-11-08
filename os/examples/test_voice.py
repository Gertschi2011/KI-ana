#!/usr/bin/env python3
"""
Test Voice Interface

Test Speech-to-Text and Text-to-Speech.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.voice.speech_to_text import get_stt
from core.voice.text_to_speech import get_tts
from core.voice.voice_controller import VoiceController
from rich.console import Console
from rich.panel import Panel

console = Console()


async def main():
    console.print(Panel.fit(
        "[bold cyan]🎙️ KI-ana OS - Voice Interface Test[/bold cyan]\n"
        "[green]Testing STT and TTS[/green]",
        title="Voice Test"
    ))
    
    # 1. Test Text-to-Speech
    console.print("\n[bold yellow]1. Testing Text-to-Speech...[/bold yellow]")
    tts = await get_tts()
    
    if tts.is_available:
        console.print("[green]✅ TTS is available![/green]")
        
        # Test speaking
        test_text = "Hallo! Ich bin KI-ana, dein intelligentes Betriebssystem."
        console.print(f"\n[cyan]Speaking: {test_text}[/cyan]")
        
        try:
            await tts.speak(test_text, play=True)
            console.print("[green]✅ Speech generated and played![/green]")
        except Exception as e:
            console.print(f"[red]❌ TTS failed: {e}[/red]")
    else:
        console.print("[red]❌ TTS not available[/red]")
        console.print("[yellow]Install: pip install TTS sounddevice soundfile[/yellow]")
    
    # 2. Test Speech-to-Text
    console.print("\n[bold yellow]2. Testing Speech-to-Text...[/bold yellow]")
    stt = await get_stt()
    
    if stt.is_available:
        console.print("[green]✅ STT is available![/green]")
        
        # Ask user if they want to test recording
        console.print("\n[cyan]Do you want to test voice recording? (requires microphone)[/cyan]")
        console.print("[dim]This will record for 5 seconds[/dim]")
        
        response = console.input("[yellow]Test recording? (y/n):[/yellow] ")
        
        if response.lower() == 'y':
            try:
                console.print("\n[bold green]🎤 Recording in 3...[/bold green]")
                await asyncio.sleep(1)
                console.print("[bold green]🎤 Recording in 2...[/bold green]")
                await asyncio.sleep(1)
                console.print("[bold green]🎤 Recording in 1...[/bold green]")
                await asyncio.sleep(1)
                console.print("[bold green]🎤 RECORDING NOW! Speak...[/bold green]")
                
                text = await stt.listen_and_transcribe(duration=5)
                
                console.print(f"\n[bold green]✅ You said: \"{text}\"[/bold green]")
                
            except Exception as e:
                console.print(f"[red]❌ Recording failed: {e}[/red]")
                console.print("[yellow]Make sure you have a microphone connected[/yellow]")
        else:
            console.print("[dim]Skipping recording test[/dim]")
    else:
        console.print("[red]❌ STT not available[/red]")
        console.print("[yellow]Install: pip install openai-whisper[/yellow]")
    
    # 3. Test Voice Controller
    console.print("\n[bold yellow]3. Testing Voice Controller...[/bold yellow]")
    controller = VoiceController()
    await controller.initialize()
    
    if controller.is_ready:
        console.print("[green]✅ Voice Controller ready (STT + TTS)![/green]")
    else:
        console.print("[yellow]⚠️  Voice Controller partially ready[/yellow]")
        if not (controller.stt and controller.stt.is_available):
            console.print("[dim]  - STT not available[/dim]")
        if not (controller.tts and controller.tts.is_available):
            console.print("[dim]  - TTS not available[/dim]")
    
    console.print("\n[bold cyan]✅ Voice interface test complete![/bold cyan]\n")
    console.print("[dim]Note: Full voice interaction requires both STT and TTS[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
