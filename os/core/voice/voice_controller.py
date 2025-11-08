"""
Voice Controller

High-level voice interface combining STT and TTS.
"""

from typing import Optional, Callable
from loguru import logger
from .speech_to_text import get_stt
from .text_to_speech import get_tts


class VoiceController:
    """
    Voice Controller
    
    High-level interface for voice interaction.
    Combines Speech-to-Text and Text-to-Speech.
    """
    
    def __init__(self):
        self.stt = None
        self.tts = None
        self.is_ready = False
        self.language = "de"
        
    async def initialize(self, language: str = "de"):
        """
        Initialize voice controller
        
        Args:
            language: Language code (de, en, etc.)
        """
        logger.info("🎙️ Initializing Voice Controller...")
        
        self.language = language
        
        # Initialize STT
        try:
            self.stt = await get_stt()
        except Exception as e:
            logger.warning(f"STT initialization failed: {e}")
        
        # Initialize TTS
        try:
            self.tts = await get_tts()
        except Exception as e:
            logger.warning(f"TTS initialization failed: {e}")
        
        # Check if ready
        self.is_ready = (
            self.stt and self.stt.is_available and
            self.tts and self.tts.is_available
        )
        
        if self.is_ready:
            logger.success("✅ Voice Controller ready (STT + TTS)")
        else:
            logger.warning("⚠️  Voice Controller partially available")
            if not (self.stt and self.stt.is_available):
                logger.warning("  - Speech-to-Text not available")
            if not (self.tts and self.tts.is_available):
                logger.warning("  - Text-to-Speech not available")
    
    async def listen(self, duration: int = 5) -> Optional[str]:
        """
        Listen to microphone and transcribe
        
        Args:
            duration: Recording duration in seconds
            
        Returns:
            Transcribed text or None
        """
        if not self.stt or not self.stt.is_available:
            logger.error("Speech-to-Text not available")
            return None
        
        try:
            text = await self.stt.listen_and_transcribe(duration, self.language)
            return text
        except Exception as e:
            logger.error(f"Listen failed: {e}")
            return None
    
    async def speak(self, text: str, play: bool = True) -> bool:
        """
        Convert text to speech and play
        
        Args:
            text: Text to speak
            play: Play audio immediately
            
        Returns:
            Success status
        """
        if not self.tts or not self.tts.is_available:
            logger.error("Text-to-Speech not available")
            return False
        
        try:
            await self.tts.speak(text, play=play)
            return True
        except Exception as e:
            logger.error(f"Speak failed: {e}")
            return False
    
    async def voice_interaction(self, 
                               process_callback: Callable[[str], str],
                               duration: int = 5) -> bool:
        """
        Complete voice interaction: Listen → Process → Respond
        
        Args:
            process_callback: Function to process user input and return response
            duration: Recording duration
            
        Returns:
            Success status
        """
        if not self.is_ready:
            logger.error("Voice Controller not ready")
            return False
        
        try:
            # Listen
            logger.info("🎤 Listening...")
            user_text = await self.listen(duration)
            
            if not user_text:
                logger.warning("No speech detected")
                return False
            
            logger.info(f"Heard: {user_text}")
            
            # Process
            response = await process_callback(user_text)
            
            # Speak response
            logger.info(f"Responding: {response}")
            await self.speak(response)
            
            return True
            
        except Exception as e:
            logger.error(f"Voice interaction failed: {e}")
            return False
