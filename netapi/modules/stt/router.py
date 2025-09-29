from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional
import os, time, tempfile, shutil

router = APIRouter(prefix="/api/stt", tags=["stt"])  # Speech-To-Text

_WHISPER_MODEL = None
_WHISPER_NAME = None
_RATE: dict[str, list[float]] = {}


def _rate_allow(ip: str, key: str, *, limit: int = 5, per_seconds: int = 60) -> bool:
    import time
    now = time.time()
    bucket = _RATE.setdefault(f"{ip}:{key}", [])
    # purge old
    while bucket and now - bucket[0] > per_seconds:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def _load_whisper():
    global _WHISPER_MODEL, _WHISPER_NAME
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    try:
        import whisper  # type: ignore
        name = os.getenv("KI_WHISPER_MODEL", "base")
        _WHISPER_MODEL = whisper.load_model(name)
        _WHISPER_NAME = name
        return _WHISPER_MODEL
    except Exception:
        return None


@router.post("/recognize")
async def stt_recognize(request: Request, audio: UploadFile = File(...), lang: Optional[str] = Form(None)):
    """
    Server‑seitige Transkription.
    Erfordert Whisper (openai‑whisper) oder liefert 501, wenn kein Backend vorhanden.
    """
    if not audio:
        raise HTTPException(400, "audio file required")

    # Basic rate limit per IP
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "stt", limit=5, per_seconds=60):
        raise HTTPException(429, "rate limit: 5/min per IP")

    # Save to temp file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix="_stt") as tmp:
            shutil.copyfileobj(audio.file, tmp)
            tmp_path = Path(tmp.name)
    finally:
        try:
            await audio.close()
        except Exception:
            pass

    # Prefer Whisper
    model = _load_whisper()
    if model is None:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(501, "stt backend not available (install 'openai-whisper' or provide Vosk)")

    try:
        kwargs = {}
        if lang:
            kwargs["language"] = lang
        # Transcribe
        result = model.transcribe(str(tmp_path), **kwargs)
        text = (result.get("text") or "").strip()
        return JSONResponse({"ok": True, "text": text, "backend": f"whisper:{_WHISPER_NAME}"})
    except Exception as e:
        raise HTTPException(500, f"stt failed: {e}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
