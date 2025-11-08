"""
Text-to-Speech using Coqui TTS

Converts text to natural-sounding speech.
"""

import asyncio
from typing import Optional
from loguru import logger
from pathlib import Path
import tempfile


class TextToSpeech:
    """
    Text-to-Speech using Coqui TTS
    
    Converts text to natural speech locally.
    No cloud needed!
    """
    
    def __init__(self, model_name: str = "tts_models/de/thorsten/tacotron2-DDC"):
        """
        Initialize TTS
        
        Args:
            model_name: TTS model to use
                       For German: tts_models/de/thorsten/tacotron2-DDC
                       For English: tts_models/en/ljspeech/tacotron2-DDC
        """
        self.model_name = model_name
        self.tts = None
        self.is_available = False
        
    async def initialize(self):
        """Load TTS model"""
        logger.info(f"🔊 Initializing Text-to-Speech ({self.model_name})...")
        
        # Try Coqui TTS first
        try:
            from TTS.api import TTS
            
            # Load model (downloads if needed)
            logger.info("Loading Coqui TTS model (this may take a moment)...")
            loop = asyncio.get_event_loop()
            self.tts = await loop.run_in_executor(
                None,
                lambda: TTS(model_name=self.model_name)
            )
            
            self.is_available = True
            self.tts_engine = "coqui"
            logger.success("✅ Text-to-Speech ready (Coqui TTS)")
            return
            
        except ImportError:
            logger.warning("Coqui TTS not installed, trying pyttsx3 fallback...")
        except Exception as e:
            logger.warning(f"Coqui TTS failed ({e}), trying pyttsx3 fallback...")
        
        # Fallback to pyttsx3 (no external dependencies)
        try:
            import pyttsx3
            
            logger.info("Loading pyttsx3 engine...")
            loop = asyncio.get_event_loop()
            self.tts = await loop.run_in_executor(
                None,
                lambda: pyttsx3.init()
            )
            
            # Set properties
            self.tts.setProperty('rate', 150)  # Speed
            self.tts.setProperty('volume', 0.9)  # Volume
            
            self.is_available = True
            self.tts_engine = "pyttsx3"
            logger.success("✅ Text-to-Speech ready (pyttsx3)")
            
        except Exception as e:
            logger.error(f"All TTS engines failed: {e}")
            self.is_available = False
            self.tts_engine = None
    
    async def speak(self, text: str, output_file: Optional[str] = None, play: bool = True) -> Optional[str]:
        """
        Convert text to speech and optionally play it
        
        Args:
            text: Text to speak
            output_file: Save to file (optional)
            play: Play audio immediately
            
        Returns:
            Path to audio file (if saved)
        """
        if not self.is_available:
            raise Exception("Text-to-Speech not available")
        
        if not text.strip():
            return None
        
        try:
            logger.info(f"🔊 Speaking: {text[:50]}...")
            
            loop = asyncio.get_event_loop()
            
            # Handle different engines
            if self.tts_engine == "coqui":
                # Coqui TTS - generate to file
                if output_file is None:
                    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    output_file = tmp.name
                    tmp.close()
                
                # Generate speech (run in executor to not block)
                await loop.run_in_executor(
                    None,
                    lambda: self.tts.tts_to_file(text=text, file_path=output_file)
                )
                
                logger.success("Speech generated (Coqui)")
                
                # Play audio if requested
                if play:
                    await self._play_audio(output_file)
                
                return output_file
                
            elif self.tts_engine == "pyttsx3":
                # pyttsx3 - direct speech (no file)
                if output_file:
                    # Save to file
                    await loop.run_in_executor(
                        None,
                        lambda: (self.tts.save_to_file(text, output_file), self.tts.runAndWait())
                    )
                    logger.success("Speech saved to file (pyttsx3)")
                    return output_file
                else:
                    # Just speak
                    await loop.run_in_executor(
                        None,
                        lambda: (self.tts.say(text), self.tts.runAndWait())
                    )
                    logger.success("Speech generated (pyttsx3)")
                    return None
            
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            raise
    
    async def _play_audio(self, audio_file: str):
        """Play audio file"""
        try:
            import sounddevice as sd
            import soundfile as sf
            
            # Load audio
            data, sample_rate = sf.read(audio_file)
            
            # Play (non-blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: sd.play(data, sample_rate)
            )
            
            # Wait for playback
            await loop.run_in_executor(None, sd.wait)
            
            logger.success("Playback finished")
            
        except ImportError:
            logger.warning("sounddevice not installed, cannot play audio")
            logger.info("Install: pip install sounddevice soundfile")
        except Exception as e:
            logger.error(f"Playback failed: {e}")


# Singleton
_tts_instance: Optional[TextToSpeech] = None


async def get_tts() -> TextToSpeech:
    """Get or create TTS singleton"""
    global _tts_instance
    
    if _tts_instance is None:
        _tts_instance = TextToSpeech()
        await _tts_instance.initialize()
    
    return _tts_instance
