"""
Local Speech-to-Text (STT) Service

Uses OpenAI Whisper for local speech recognition.
No cloud APIs needed!

Models:
- tiny: 39M params, ~1GB RAM, fastest
- base: 74M params, ~1GB RAM, good balance
- small: 244M params, ~2GB RAM, better quality
- medium: 769M params, ~5GB RAM, high quality
- large: 1550M params, ~10GB RAM, best quality
"""
from __future__ import annotations
import time
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import whisper
import numpy as np


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    text: str
    language: str
    segments: List[Dict[str, Any]]
    model: str
    duration: float
    processing_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "segments": self.segments,
            "model": self.model,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "real_time_factor": self.processing_time / self.duration if self.duration > 0 else 0
        }


class LocalSTTService:
    """
    Local Speech-to-Text service using Whisper.
    
    Singleton pattern to avoid loading models multiple times.
    """
    
    _instance: Optional['LocalSTTService'] = None
    
    # Available models with their characteristics
    MODELS = {
        "tiny": {
            "params": "39M",
            "ram_gb": 1,
            "speed": "fastest",
            "quality": "basic"
        },
        "base": {
            "params": "74M",
            "ram_gb": 1,
            "speed": "fast",
            "quality": "good"
        },
        "small": {
            "params": "244M",
            "ram_gb": 2,
            "speed": "medium",
            "quality": "better"
        },
        "medium": {
            "params": "769M",
            "ram_gb": 5,
            "speed": "slow",
            "quality": "high"
        },
        "large": {
            "params": "1550M",
            "ram_gb": 10,
            "speed": "slowest",
            "quality": "best"
        }
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.models: Dict[str, whisper.Whisper] = {}
        self.cache_dir = Path.home() / "ki_ana" / "models" / "whisper"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Default model (base is good balance)
        self.default_model = os.getenv("WHISPER_MODEL", "base")
        
        print(f"✅ Local STT Service initialized (default model: {self.default_model})")
    
    def _load_model(self, model_key: str) -> whisper.Whisper:
        """Load a model if not already loaded."""
        if model_key in self.models:
            return self.models[model_key]
        
        if model_key not in self.MODELS:
            raise ValueError(f"Unknown model: {model_key}. Available: {list(self.MODELS.keys())}")
        
        print(f"📥 Loading Whisper model: {model_key} ({self.MODELS[model_key]['params']})...")
        
        start = time.time()
        model = whisper.load_model(model_key, download_root=str(self.cache_dir))
        load_time = time.time() - start
        
        self.models[model_key] = model
        print(f"✅ Model loaded in {load_time:.2f}s")
        
        return model
    
    def transcribe_file(
        self,
        audio_path: str,
        model: str = None,
        language: str = None,
        task: str = "transcribe"
    ) -> TranscriptionResult:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file (mp3, wav, m4a, etc.)
            model: Model to use (tiny/base/small/medium/large)
            language: Language code (e.g., 'de', 'en') or None for auto-detect
            task: 'transcribe' or 'translate' (to English)
        
        Returns:
            TranscriptionResult with text and metadata
        """
        model_key = model or self.default_model
        model_obj = self._load_model(model_key)
        
        print(f"🎤 Transcribing: {audio_path}")
        start = time.time()
        
        # Transcribe
        result = model_obj.transcribe(
            audio_path,
            language=language,
            task=task,
            fp16=False  # Use FP32 for better compatibility
        )
        
        processing_time = time.time() - start
        
        # Get audio duration
        try:
            import librosa
            duration = librosa.get_duration(path=audio_path)
        except:
            # Fallback: estimate from result
            duration = result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0
        
        return TranscriptionResult(
            text=result["text"].strip(),
            language=result.get("language", language or "unknown"),
            segments=result.get("segments", []),
            model=model_key,
            duration=duration,
            processing_time=processing_time
        )
    
    def transcribe_audio_data(
        self,
        audio_data: bytes,
        model: str = None,
        language: str = None,
        task: str = "transcribe"
    ) -> TranscriptionResult:
        """
        Transcribe audio from bytes (e.g., uploaded file).
        
        Args:
            audio_data: Audio data as bytes
            model: Model to use
            language: Language code or None
            task: 'transcribe' or 'translate'
        
        Returns:
            TranscriptionResult
        """
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        
        try:
            result = self.transcribe_file(
                audio_path=tmp_path,
                model=model,
                language=language,
                task=task
            )
            return result
        finally:
            # Cleanup
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def get_model_info(self, model: str = None) -> Dict[str, Any]:
        """Get information about a model."""
        model_key = model or self.default_model
        if model_key not in self.MODELS:
            raise ValueError(f"Unknown model: {model_key}")
        
        info = self.MODELS[model_key].copy()
        info["loaded"] = model_key in self.models
        info["key"] = model_key
        
        return info
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models."""
        return [
            {
                "key": key,
                "loaded": key in self.models,
                **info
            }
            for key, info in self.MODELS.items()
        ]
    
    def benchmark(self, audio_path: str = None) -> Dict[str, Any]:
        """
        Benchmark transcription performance.
        
        Args:
            audio_path: Path to test audio file
        
        Returns:
            Benchmark results with timing statistics
        """
        if audio_path is None:
            print("⚠️  No audio file provided for benchmark")
            return {}
        
        results = {}
        
        # Test with different models
        for model_key in ["tiny", "base", "small"]:  # Skip large models for quick benchmark
            try:
                print(f"\n🧪 Benchmarking {model_key}...")
                result = self.transcribe_file(audio_path, model=model_key)
                
                results[model_key] = {
                    "model": model_key,
                    "processing_time": result.processing_time,
                    "duration": result.duration,
                    "real_time_factor": result.processing_time / result.duration if result.duration > 0 else 0,
                    "text_length": len(result.text),
                    "language": result.language
                }
            except Exception as e:
                results[model_key] = {"error": str(e)}
        
        return results


# Singleton instance
_service: Optional[LocalSTTService] = None


def get_stt_service() -> LocalSTTService:
    """Get the singleton STT service instance."""
    global _service
    if _service is None:
        _service = LocalSTTService()
    return _service


# Convenience functions
def transcribe(audio_path: str, model: str = None, language: str = None) -> str:
    """Transcribe audio file (convenience function)."""
    service = get_stt_service()
    result = service.transcribe_file(audio_path, model=model, language=language)
    return result.text


if __name__ == "__main__":
    # Quick test
    print("🎤 Local STT Service Test\n")
    
    service = get_stt_service()
    
    # List models
    print("Available models:")
    for model in service.list_models():
        print(f"  - {model['key']}: {model['params']} params, {model['ram_gb']}GB RAM ({model['quality']} quality)")
    
    print("\n💡 To test transcription, provide an audio file:")
    print("   python system/local_stt.py <audio_file.mp3>")
    
    # Test if audio file provided
    import sys
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        print(f"\n🎤 Testing with: {audio_file}")
        
        result = service.transcribe_file(audio_file, model="base")
        
        print(f"\n✅ Transcription complete!")
        print(f"📝 Text: {result.text}")
        print(f"🌍 Language: {result.language}")
        print(f"⏱️  Duration: {result.duration:.2f}s")
        print(f"⚡ Processing: {result.processing_time:.2f}s")
        print(f"📊 Real-time factor: {result.processing_time/result.duration:.2f}x")
