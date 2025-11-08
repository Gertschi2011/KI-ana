"""
Local Text-to-Speech (TTS) Service

Uses Piper TTS for local speech synthesis.
No cloud APIs needed!

Voices are downloaded on-demand from:
https://huggingface.co/rhasspy/piper-voices
"""
from __future__ import annotations
import time
import os
import wave
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import tempfile

try:
    from piper import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    print("⚠️  Piper TTS not available. Install with: pip install piper-tts")


@dataclass
class SynthesisResult:
    """Result of a TTS synthesis operation."""
    audio_path: str
    text: str
    voice: str
    duration: float
    processing_time: float
    sample_rate: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "audio_path": self.audio_path,
            "text": self.text,
            "voice": self.voice,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "sample_rate": self.sample_rate,
            "real_time_factor": self.processing_time / self.duration if self.duration > 0 else 0
        }


class LocalTTSService:
    """
    Local Text-to-Speech service using Piper.
    
    Singleton pattern to avoid loading voices multiple times.
    """
    
    _instance: Optional['LocalTTSService'] = None
    
    # Popular voices (will be downloaded on first use)
    VOICES = {
        "de_DE-thorsten-low": {
            "language": "German",
            "quality": "low",
            "speed": "fast",
            "size_mb": 30
        },
        "de_DE-thorsten-medium": {
            "language": "German",
            "quality": "medium",
            "speed": "medium",
            "size_mb": 60
        },
        "en_US-lessac-medium": {
            "language": "English (US)",
            "quality": "medium",
            "speed": "medium",
            "size_mb": 60
        },
        "en_GB-alan-medium": {
            "language": "English (UK)",
            "quality": "medium",
            "speed": "medium",
            "size_mb": 60
        }
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        if not PIPER_AVAILABLE:
            print("❌ Piper TTS not available")
            self._initialized = True
            return
        
        self._initialized = True
        self.voices: Dict[str, PiperVoice] = {}
        self.voices_dir = Path.home() / "ki_ana" / "models" / "piper"
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        
        # Default voice
        self.default_voice = os.getenv("PIPER_VOICE", "de_DE-thorsten-low")
        
        print(f"✅ Local TTS Service initialized (default voice: {self.default_voice})")
    
    def _download_voice(self, voice_key: str) -> Path:
        """Download a voice model if not already present."""
        voice_path = self.voices_dir / f"{voice_key}.onnx"
        config_path = self.voices_dir / f"{voice_key}.onnx.json"
        
        if voice_path.exists() and config_path.exists():
            return voice_path
        
        print(f"📥 Downloading voice: {voice_key}...")
        print(f"⚠️  Voice download not yet implemented.")
        print(f"💡 Please download manually from:")
        print(f"   https://huggingface.co/rhasspy/piper-voices/tree/main")
        print(f"   Save to: {self.voices_dir}")
        
        raise FileNotFoundError(f"Voice not found: {voice_key}. Please download manually.")
    
    def _load_voice(self, voice_key: str) -> PiperVoice:
        """Load a voice if not already loaded."""
        if not PIPER_AVAILABLE:
            raise RuntimeError("Piper TTS not available")
        
        if voice_key in self.voices:
            return self.voices[voice_key]
        
        if voice_key not in self.VOICES:
            raise ValueError(f"Unknown voice: {voice_key}. Available: {list(self.VOICES.keys())}")
        
        # Check if voice exists, download if needed
        voice_path = self._download_voice(voice_key)
        
        print(f"🔊 Loading voice: {voice_key}...")
        start = time.time()
        
        voice = PiperVoice.load(str(voice_path))
        
        load_time = time.time() - start
        self.voices[voice_key] = voice
        
        print(f"✅ Voice loaded in {load_time:.2f}s")
        return voice
    
    def synthesize(
        self,
        text: str,
        voice: str = None,
        output_path: str = None
    ) -> SynthesisResult:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice to use (default: configured default)
            output_path: Path to save audio file (default: temp file)
        
        Returns:
            SynthesisResult with audio path and metadata
        """
        if not PIPER_AVAILABLE:
            raise RuntimeError("Piper TTS not available")
        
        voice_key = voice or self.default_voice
        voice_obj = self._load_voice(voice_key)
        
        # Create output path if not provided
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        
        print(f"🔊 Synthesizing: '{text[:50]}...'")
        start = time.time()
        
        # Synthesize
        with wave.open(output_path, 'wb') as wav_file:
            voice_obj.synthesize(text, wav_file)
        
        processing_time = time.time() - start
        
        # Get audio duration
        with wave.open(output_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
        
        return SynthesisResult(
            audio_path=output_path,
            text=text,
            voice=voice_key,
            duration=duration,
            processing_time=processing_time,
            sample_rate=rate
        )
    
    def synthesize_to_bytes(
        self,
        text: str,
        voice: str = None
    ) -> bytes:
        """
        Synthesize speech and return as bytes.
        
        Args:
            text: Text to synthesize
            voice: Voice to use
        
        Returns:
            Audio data as bytes (WAV format)
        """
        result = self.synthesize(text, voice=voice)
        
        try:
            with open(result.audio_path, 'rb') as f:
                audio_data = f.read()
            return audio_data
        finally:
            # Cleanup temp file
            try:
                os.unlink(result.audio_path)
            except:
                pass
    
    def get_voice_info(self, voice: str = None) -> Dict[str, Any]:
        """Get information about a voice."""
        voice_key = voice or self.default_voice
        if voice_key not in self.VOICES:
            raise ValueError(f"Unknown voice: {voice_key}")
        
        info = self.VOICES[voice_key].copy()
        info["loaded"] = voice_key in self.voices
        info["key"] = voice_key
        
        return info
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List all available voices."""
        return [
            {
                "key": key,
                "loaded": key in self.voices,
                **info
            }
            for key, info in self.VOICES.items()
        ]


# Singleton instance
_service: Optional[LocalTTSService] = None


def get_tts_service() -> LocalTTSService:
    """Get the singleton TTS service instance."""
    global _service
    if _service is None:
        _service = LocalTTSService()
    return _service


# Convenience function
def synthesize(text: str, voice: str = None, output_path: str = None) -> str:
    """Synthesize speech (convenience function)."""
    service = get_tts_service()
    result = service.synthesize(text, voice=voice, output_path=output_path)
    return result.audio_path


if __name__ == "__main__":
    # Quick test
    print("🔊 Local TTS Service Test\n")
    
    if not PIPER_AVAILABLE:
        print("❌ Piper TTS not installed. Install with:")
        print("   pip install piper-tts")
        exit(1)
    
    service = get_tts_service()
    
    # List voices
    print("Available voices:")
    for voice in service.list_voices():
        print(f"  - {voice['key']}: {voice['language']} ({voice['quality']} quality)")
    
    print("\n💡 To test synthesis, provide text:")
    print("   python system/local_tts.py 'Hallo, ich bin KI_ana!'")
    
    # Test if text provided
    import sys
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        print(f"\n🔊 Testing with: {text}")
        
        try:
            result = service.synthesize(text)
            
            print(f"\n✅ Synthesis complete!")
            print(f"📝 Text: {result.text}")
            print(f"🔊 Voice: {result.voice}")
            print(f"⏱️  Duration: {result.duration:.2f}s")
            print(f"⚡ Processing: {result.processing_time:.2f}s")
            print(f"📊 Real-time factor: {result.processing_time/result.duration:.2f}x")
            print(f"💾 Saved to: {result.audio_path}")
        except FileNotFoundError as e:
            print(f"\n❌ {e}")
