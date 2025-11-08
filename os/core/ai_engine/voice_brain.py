#!/usr/bin/env python3
"""
Voice-Enabled Smart Brain

Smart Brain with voice interaction capabilities.
"""

import asyncio
from typing import Optional
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from .smart_brain import SmartBrain, get_smart_brain
from ..voice.voice_controller import VoiceController

console = Console()


class VoiceBrain:
    """
    Voice-enabled AI Brain
    
    Combines Smart Brain with Voice Controller for
    natural voice conversations with the OS.
    """
    
    def __init__(self):
        self.brain: Optional[SmartBrain] = None
        self.voice: Optional[VoiceController] = None
        self.is_ready = False
        
    async def initialize(self):
        """Initialize brain and voice"""
        logger.info("🎙️ Initializing Voice-Enabled Brain...")
        
        # Initialize Smart Brain
        self.brain = await get_smart_brain()
        
        # Initialize Voice Controller
        self.voice = VoiceController()
        await self.voice.initialize()
        
        self.is_ready = self.brain and self.voice and self.voice.is_ready
        
        if self.is_ready:
            logger.success("✅ Voice Brain ready! You can now talk to your OS!")
        else:
            logger.warning("⚠️  Voice Brain partially ready")
            
    async def voice_mode(self):
        """
        Interactive voice mode
        
        Listen → Process → Respond (voice)
        """
        if not self.is_ready:
            console.print("[red]❌ Voice mode not available[/red]")
            if not (self.voice and self.voice.is_ready):
                console.print("[yellow]Install voice dependencies:[/yellow]")
                console.print("  pip install openai-whisper TTS sounddevice soundfile")
            return
        
        console.print(Panel.fit(
            "[bold cyan]🎙️ KI-ana OS - Voice Mode[/bold cyan]\n"
            "[green]Speak to interact with your OS![/green]\n\n"
            "Commands:\n"
            "  • Say 'beenden' or 'stop' to exit\n"
            "  • Speak naturally\n"
            "  • Press Enter when ready to speak",
            title="Voice Mode Active"
        ))
        
        while True:
            try:
                # Wait for user to press enter
                console.input("\n[bold yellow]Press Enter and speak (or type 'exit'):[/bold yellow] ")
                
                # Listen
                console.print("[cyan]🎤 Listening...[/cyan]")
                user_text = await self.voice.listen(duration=5)
                
                if not user_text:
                    console.print("[yellow]⚠️  Didn't catch that. Try again.[/yellow]")
                    continue
                
                console.print(f"[green]You said: \"{user_text}\"[/green]")
                
                # Check for exit
                if any(word in user_text.lower() for word in ["beenden", "stop", "tschüss", "ende"]):
                    await self.voice.speak("Auf Wiedersehen!")
                    break
                
                # Process with brain
                console.print("[cyan]KI-ana:[/cyan] ", end="")
                result = await self.brain.process_command(user_text)
                
                if result["success"]:
                    response = result["response"]
                    console.print(f"[white]{response}[/white]")
                    
                    # Speak response
                    await self.voice.speak(response)
                else:
                    error_msg = f"Es gab einen Fehler: {result.get('error', 'Unbekannt')}"
                    console.print(f"[red]{error_msg}[/red]")
                    await self.voice.speak(error_msg)
                    
            except KeyboardInterrupt:
                console.print("\n[green]Auf Wiedersehen! 👋[/green]")
                await self.voice.speak("Auf Wiedersehen!")
                break
            except Exception as e:
                logger.error(f"Voice interaction error: {e}")
                console.print(f"[red]Error: {e}[/red]")
    
    async def quick_test(self):
        """Quick test of voice capabilities"""
        if not self.is_ready:
            console.print("[red]❌ Voice Brain not ready[/red]")
            return
        
        console.print("[bold cyan]🎙️ Quick Voice Test[/bold cyan]\n")
        
        # Test TTS
        await self.voice.speak("Hallo! Ich bin KI-ana. Dein intelligentes Betriebssystem.")
        
        console.print("\n[green]✅ Voice test complete![/green]")
    
    async def shutdown(self):
        """Cleanup"""
        if self.brain:
            await self.brain.shutdown()


async def main():
    """Main entry point for voice mode"""
    voice_brain = VoiceBrain()
    await voice_brain.initialize()
    
    if voice_brain.is_ready:
        # Quick test
        await voice_brain.quick_test()
        
        # Enter voice mode
        await voice_brain.voice_mode()
    else:
        console.print("\n[yellow]Voice mode not fully available.[/yellow]")
        console.print("[dim]Install dependencies: pip install openai-whisper TTS sounddevice soundfile[/dim]")
    
    await voice_brain.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
