def _ensure_eleven_alias():
    """If ELEVEN_API_KEY is missing but LEVEN_API_KEY exists (typo), alias it."""
    try:
        if not os.getenv("ELEVEN_API_KEY") and os.getenv("LEVEN_API_KEY"):
            os.environ["ELEVEN_API_KEY"] = os.getenv("LEVEN_API_KEY") or ""
    except Exception:
        pass
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import os, time, json

router = APIRouter(tags=["voice"])  # mounted under /api in app


@router.get("/voice")
def voice_profile(request: Request):
    """Return detected voice/language preferences for greeting/tts.
    Uses client IP geo lookup as a hint.
    """
    try:
        from ...geo_voice import detect_voice
    except Exception:
        detect_voice = lambda _ip: {"lang": "en-US", "greeting": "Hi, I’m KI_ana. I’m happy you’re here!"}  # type: ignore
    ip = request.client.host if request.client else None
    cfg = detect_voice(ip)
    return JSONResponse(cfg)


_TTS_RATE = {}


def _rate_limited(key: str, per_seconds: int = 3) -> bool:
    now = time.time()
    last = float(_TTS_RATE.get(key) or 0)
    if now - last < per_seconds:
        return True
    _TTS_RATE[key] = now
    return False


@router.get("/voice/health")
def voice_health():
    """Return health status for TTS backend (does not make an external call)."""
    _ensure_eleven_alias()
    ok = True
    reason = ""
    # Check env presence expected by core.speech
    if not os.getenv("ELEVEN_API_KEY"):
        ok = False
        reason = "missing ELEVEN_API_KEY"
    return {"ok": ok, "backend": "elevenlabs", "reason": reason}


@router.get("/elevenlabs/speak")
def tts_speak(request: Request, text: str, lang: str = "de-DE"):
    """Generate speech via ElevenLabs API and return MP3.
    Requires env ELEVEN_API_KEY. Rate‑limited per IP.
    """
    ip = request.client.host if request.client else "?"
    if _rate_limited(ip):
        raise HTTPException(429, "rate limited")
    _ensure_eleven_alias()
    try:
        from ...core import speech
    except Exception:
        raise HTTPException(501, "tts backend not available")
    # Explicit API key check for clearer error upfront
    if not os.getenv("ELEVEN_API_KEY"):
        raise HTTPException(501, "ELEVEN_API_KEY not configured")
    if not text or not text.strip():
        raise HTTPException(400, "text required")
    try:
        path = Path(speech.synthesize(text.strip()))
        if not path.exists():
            raise HTTPException(500, "tts file missing")
        return FileResponse(path, media_type="audio/mpeg", filename=path.name)
    except ValueError as ve:
        # Allow core to bubble up configuration errors
        raise HTTPException(501, str(ve))
    except Exception as e:
        raise HTTPException(500, f"tts failed: {e}")

