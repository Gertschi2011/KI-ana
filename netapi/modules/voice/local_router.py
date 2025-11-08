"""
Local Voice API Router

Provides REST API for local STT (Whisper) and TTS (Piper).
Fully offline voice processing!
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path
import tempfile
import os

# Add system path for imports
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

try:
    from local_stt import get_stt_service
    STT_AVAILABLE = True
except Exception as e:
    print(f"Warning: Local STT not available: {e}")
    STT_AVAILABLE = False

try:
    from local_tts import get_tts_service
    TTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Local TTS not available: {e}")
    TTS_AVAILABLE = False

router = APIRouter(prefix="/api/voice/local", tags=["voice-local"])


# Request/Response Models
class TranscribeRequest(BaseModel):
    """Request to transcribe audio."""
    model: Optional[str] = Field(None, description="Whisper model (tiny/base/small/medium/large)")
    language: Optional[str] = Field(None, description="Language code (e.g., 'de', 'en') or None for auto-detect")
    task: str = Field("transcribe", description="'transcribe' or 'translate' (to English)")


class SynthesizeRequest(BaseModel):
    """Request to synthesize speech."""
    text: str = Field(..., description="Text to synthesize")
    voice: Optional[str] = Field(None, description="Voice to use")


# STT Endpoints
@router.post("/stt/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    model: Optional[str] = None,
    language: Optional[str] = None,
    task: str = "transcribe"
):
    """
    Transcribe uploaded audio file using local Whisper.
    
    Supports: mp3, wav, m4a, ogg, flac, etc.
    """
    if not STT_AVAILABLE:
        raise HTTPException(503, "Local STT not available")
    
    try:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "audio.wav").suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Transcribe
            service = get_stt_service()
            result = service.transcribe_file(
                audio_path=tmp_path,
                model=model,
                language=language,
                task=task
            )
            
            return {
                "ok": True,
                "result": result.to_dict()
            }
        finally:
            # Cleanup
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    except Exception as e:
        raise HTTPException(500, f"Transcription error: {e}")


@router.get("/stt/models")
async def list_stt_models():
    """List available Whisper models."""
    if not STT_AVAILABLE:
        raise HTTPException(503, "Local STT not available")
    
    try:
        service = get_stt_service()
        models = service.list_models()
        
        return {
            "ok": True,
            "models": models
        }
    except Exception as e:
        raise HTTPException(500, f"List models error: {e}")


@router.get("/stt/stats")
async def get_stt_stats():
    """Get STT service statistics."""
    if not STT_AVAILABLE:
        raise HTTPException(503, "Local STT not available")
    
    try:
        service = get_stt_service()
        
        return {
            "ok": True,
            "available": True,
            "default_model": service.default_model,
            "loaded_models": list(service.models.keys()),
            "cache_dir": str(service.cache_dir),
            "models": service.list_models()
        }
    except Exception as e:
        raise HTTPException(500, f"Stats error: {e}")


# TTS Endpoints
@router.post("/tts/synthesize")
async def synthesize_speech(request: SynthesizeRequest):
    """
    Synthesize speech from text using local Piper TTS.
    
    Returns audio file (WAV format).
    """
    if not TTS_AVAILABLE:
        raise HTTPException(503, "Local TTS not available")
    
    try:
        service = get_tts_service()
        result = service.synthesize(
            text=request.text,
            voice=request.voice
        )
        
        # Return audio file
        return FileResponse(
            result.audio_path,
            media_type="audio/wav",
            filename="speech.wav",
            headers={
                "X-Duration": str(result.duration),
                "X-Processing-Time": str(result.processing_time),
                "X-Voice": result.voice
            }
        )
    
    except Exception as e:
        raise HTTPException(500, f"Synthesis error: {e}")


@router.post("/tts/synthesize/json")
async def synthesize_speech_json(request: SynthesizeRequest):
    """
    Synthesize speech and return metadata (without audio file).
    """
    if not TTS_AVAILABLE:
        raise HTTPException(503, "Local TTS not available")
    
    try:
        service = get_tts_service()
        result = service.synthesize(
            text=request.text,
            voice=request.voice
        )
        
        # Return metadata only
        return {
            "ok": True,
            "result": result.to_dict()
        }
    
    except Exception as e:
        raise HTTPException(500, f"Synthesis error: {e}")


@router.get("/tts/voices")
async def list_tts_voices():
    """List available TTS voices."""
    if not TTS_AVAILABLE:
        raise HTTPException(503, "Local TTS not available")
    
    try:
        service = get_tts_service()
        voices = service.list_voices()
        
        return {
            "ok": True,
            "voices": voices
        }
    except Exception as e:
        raise HTTPException(500, f"List voices error: {e}")


@router.get("/tts/stats")
async def get_tts_stats():
    """Get TTS service statistics."""
    if not TTS_AVAILABLE:
        raise HTTPException(503, "Local TTS not available")
    
    try:
        service = get_tts_service()
        
        return {
            "ok": True,
            "available": True,
            "default_voice": service.default_voice,
            "loaded_voices": list(service.voices.keys()),
            "voices_dir": str(service.voices_dir),
            "voices": service.list_voices()
        }
    except Exception as e:
        raise HTTPException(500, f"Stats error: {e}")


# Combined Endpoints
@router.get("/health")
async def health_check():
    """Check if local voice services are healthy."""
    return {
        "ok": True,
        "stt": {
            "available": STT_AVAILABLE,
            "service": "Whisper"
        },
        "tts": {
            "available": TTS_AVAILABLE,
            "service": "Piper"
        }
    }


@router.get("/stats")
async def get_voice_stats():
    """Get combined voice service statistics."""
    stats = {
        "ok": True,
        "stt": {"available": STT_AVAILABLE},
        "tts": {"available": TTS_AVAILABLE}
    }
    
    if STT_AVAILABLE:
        try:
            service = get_stt_service()
            stats["stt"]["default_model"] = service.default_model
            stats["stt"]["loaded_models"] = list(service.models.keys())
        except:
            pass
    
    if TTS_AVAILABLE:
        try:
            service = get_tts_service()
            stats["tts"]["default_voice"] = service.default_voice
            stats["tts"]["loaded_voices"] = list(service.voices.keys())
        except:
            pass
    
    return stats
