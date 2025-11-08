"""
Speech-to-Text using Whisper

Converts voice to text locally.
"""

import asyncio
from typing import Optional
from loguru import logger
from pathlib import Path
import tempfile


class SpeechToText:
    """
    Speech-to-Text using OpenAI Whisper
    
    Converts audio to text locally (no cloud needed).
    Supports multiple languages.
    """
    
    def __init__(self, model_size: str = "base"):
        """
        Initialize STT
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
                       tiny = fastest, least accurate
                       base = good balance
                       small = better accuracy
                       medium/large = best accuracy, slower
        """
        self.model_size = model_size
        self.model = None
        self.is_available = False
        
    async def initialize(self):
        """Load Whisper model"""
        logger.info(f"🎤 Initializing Speech-to-Text (Whisper {self.model_size})...")
        
        try:
            import whisper
            
            # Load model (downloads if needed)
            logger.info("Loading Whisper model (this may take a moment)...")
            self.model = whisper.load_model(self.model_size)
            
            self.is_available = True
            logger.success(f"✅ Speech-to-Text ready (Whisper {self.model_size})")
            
        except ImportError:
            logger.warning("Whisper not installed. Install: pip install openai-whisper")
            self.is_available = False
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            self.is_available = False
    
    async def transcribe_file(self, audio_file: str, language: str = "de") -> str:
        """
        Transcribe audio file to text
        
        Args:
            audio_file: Path to audio file (wav, mp3, etc.)
            language: Language code (de, en, etc.)
            
        Returns:
            Transcribed text
        """
        if not self.is_available:
            raise Exception("Speech-to-Text not available")
        
        if not Path(audio_file).exists():
            raise Exception(f"Audio file not found: {audio_file}")
        
        try:
            logger.info(f"Transcribing {audio_file}...")
            
            # Transcribe (runs in thread pool to not block)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(audio_file, language=language)
            )
            
            text = result["text"].strip()
            logger.success(f"Transcribed: {text}")
            
            return text
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    async def transcribe_audio_data(self, audio_data: bytes, language: str = "de") -> str:
        """
        Transcribe audio data (bytes) to text
        
        Args:
            audio_data: Raw audio bytes
            language: Language code
            
        Returns:
            Transcribed text
        """
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        
        try:
            return await self.transcribe_file(tmp_path, language)
        finally:
            # Cleanup
            Path(tmp_path).unlink(missing_ok=True)
    
    async def listen_and_transcribe(self, duration: int = 5, language: str = "de") -> str:
        """
        Record audio from microphone and transcribe
        
        Args:
            duration: Recording duration in seconds
            language: Language code
            
        Returns:
            Transcribed text
        """
        if not self.is_available:
            raise Exception("Speech-to-Text not available")
        
        try:
            import sounddevice as sd
            import soundfile as sf
            import numpy as np
            
            logger.info(f"🎤 Recording for {duration} seconds...")
            
            # Record audio
            sample_rate = 16000  # Whisper expects 16kHz
            loop = asyncio.get_event_loop()
            recording = await loop.run_in_executor(
                None,
                lambda: sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype=np.float32
                )
            )
            
            # Wait for recording
            await loop.run_in_executor(None, sd.wait)
            logger.info("Recording finished")
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                sf.write(tmp.name, recording, sample_rate)
                tmp_path = tmp.name
            
            try:
                return await self.transcribe_file(tmp_path, language)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
                
        except ImportError as e:
            logger.error("sounddevice not installed. Install: pip install sounddevice soundfile")
            raise
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            raise


# Singleton
_stt_instance: Optional[SpeechToText] = None


async def get_stt() -> SpeechToText:
    """Get or create STT singleton"""
    global _stt_instance
    
    if _stt_instance is None:
        _stt_instance = SpeechToText(model_size="base")
        await _stt_instance.initialize()
    
    return _stt_instance
