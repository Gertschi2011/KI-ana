"""
Audio Processor - Voice & Audio Understanding for KI_ana

Enables the AI to:
- Transcribe speech to text (STT)
- Generate speech from text (TTS)
- Analyze audio content
- Voice conversation capability
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any
from pathlib import Path
import io


class AudioProcessor:
    """
    Audio processing system for voice interaction.
    
    Supports:
    - Speech-to-Text (Whisper)
    - Text-to-Speech (ElevenLabs, Piper, etc.)
    - Audio analysis
    
    Usage:
        audio = AudioProcessor()
        
        # Transcribe audio
        text = await audio.transcribe(audio_path)
        
        # Generate speech
        audio_data = await audio.synthesize("Hello World")
    """
    
    def __init__(self):
        self.stt_available = False
        self.tts_available = False
        self._check_availability()
    
    def _check_availability(self):
        """Check available audio capabilities"""
        # Check Whisper (OpenAI or local)
        try:
            import whisper
            self.stt_available = True
            self.stt_engine = "whisper"
        except ImportError:
            self.stt_available = False
        
        # Check TTS options
        try:
            import pyttsx3
            self.tts_available = True
            self.tts_engine = "pyttsx3"
        except ImportError:
            # Check ElevenLabs
            import os
            if os.getenv("ELEVEN_API_KEY"):
                self.tts_available = True
                self.tts_engine = "elevenlabs"
            else:
                self.tts_available = False
    
    async def transcribe(
        self,
        audio_path: str,
        language: str = "de",
        model_size: str = "base"
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text using Whisper.
        
        Args:
            audio_path: Path to audio file
            language: Language code (de, en, etc.)
            model_size: Whisper model size (tiny, base, small, medium, large)
            
        Returns:
            Dict with transcription and metadata
        """
        if not self.stt_available:
            return {
                "success": False,
                "error": "STT not available. Install whisper: pip install openai-whisper"
            }
        
        try:
            import whisper
            
            # Load model
            model = whisper.load_model(model_size)
            
            # Transcribe
            result = model.transcribe(audio_path, language=language)
            
            return {
                "success": True,
                "text": result["text"],
                "language": result.get("language", language),
                "model": model_size,
                "segments": result.get("segments", [])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def transcribe_realtime(
        self,
        audio_stream,
        callback
    ):
        """
        Transcribe audio in real-time.
        
        Args:
            audio_stream: Audio input stream
            callback: Function to call with transcription results
        """
        # TODO: Implement real-time transcription
        # Could use faster-whisper or whisper.cpp
        pass
    
    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0
    ) -> Dict[str, Any]:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice ID/name
            speed: Speech speed (0.5-2.0)
            
        Returns:
            Dict with audio data and metadata
        """
        if not self.tts_available:
            return {
                "success": False,
                "error": "TTS not available"
            }
        
        try:
            if self.tts_engine == "elevenlabs":
                return await self._synthesize_elevenlabs(text, voice)
            elif self.tts_engine == "pyttsx3":
                return await self._synthesize_pyttsx3(text, speed)
            else:
                return {
                    "success": False,
                    "error": "No TTS engine available"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _synthesize_elevenlabs(self, text: str, voice: str) -> Dict[str, Any]:
        """Synthesize using ElevenLabs API"""
        try:
            import os
            import requests
            
            api_key = os.getenv("ELEVEN_API_KEY")
            voice_id = os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            
            if voice != "default":
                voice_id = voice
            
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "Accept": "audio/mpeg",
                    "xi-api-key": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75
                    }
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"ElevenLabs API error: {response.status_code}")
            
            return {
                "success": True,
                "audio_data": response.content,
                "format": "mp3",
                "engine": "elevenlabs"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _synthesize_pyttsx3(self, text: str, speed: float) -> Dict[str, Any]:
        """Synthesize using pyttsx3 (offline)"""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            engine.setProperty('rate', int(150 * speed))
            
            # Save to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
            
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            
            # Read audio data
            with open(temp_path, "rb") as f:
                audio_data = f.read()
            
            # Cleanup
            Path(temp_path).unlink()
            
            return {
                "success": True,
                "audio_data": audio_data,
                "format": "wav",
                "engine": "pyttsx3"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Analyze audio characteristics.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Dict with audio metadata
        """
        try:
            import librosa
            
            # Load audio
            y, sr = librosa.load(audio_path)
            
            # Extract features
            duration = librosa.get_duration(y=y, sr=sr)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            
            return {
                "success": True,
                "duration_seconds": float(duration),
                "sample_rate": int(sr),
                "tempo_bpm": float(tempo),
                "spectral_centroid_mean": float(spectral_centroids.mean())
            }
            
        except ImportError:
            # Fallback: basic file info
            try:
                import wave
                with wave.open(audio_path, 'rb') as wav:
                    frames = wav.getnframes()
                    rate = wav.getframerate()
                    duration = frames / float(rate)
                    
                    return {
                        "success": True,
                        "duration_seconds": duration,
                        "sample_rate": rate
                    }
            except Exception:
                pass
            
            return {
                "success": False,
                "error": "Audio analysis libraries not available"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audio processor statistics"""
        return {
            "stt_available": self.stt_available,
            "stt_engine": getattr(self, "stt_engine", None),
            "tts_available": self.tts_available,
            "tts_engine": getattr(self, "tts_engine", None)
        }


# Global instance
_audio_processor_instance: Optional[AudioProcessor] = None


def get_audio_processor() -> AudioProcessor:
    """Get or create global AudioProcessor instance"""
    global _audio_processor_instance
    if _audio_processor_instance is None:
        _audio_processor_instance = AudioProcessor()
    return _audio_processor_instance


if __name__ == "__main__":
    # Self-test
    import asyncio
    
    print("=== Audio Processor Self-Test ===\n")
    
    async def test():
        audio = AudioProcessor()
        stats = audio.get_statistics()
        
        print(f"STT available: {stats['stt_available']}")
        if stats['stt_available']:
            print(f"  Engine: {stats['stt_engine']}")
        
        print(f"TTS available: {stats['tts_available']}")
        if stats['tts_available']:
            print(f"  Engine: {stats['tts_engine']}")
        
        if not stats['stt_available']:
            print("\n⚠️  Install Whisper: pip install openai-whisper")
        if not stats['tts_available']:
            print("⚠️  Install TTS: pip install pyttsx3")
        
        print("\n✅ Audio Processor initialized!")
    
    asyncio.run(test())
