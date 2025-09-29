#!/usr/bin/env python3
from __future__ import annotations
"""
Media worker: processes jobs
  - media.thumbnail {path:'/uploads/file', w:256, h:256}
  - media.ocr       {path:'/uploads/file', store:true}
  - media.whisper   {path:'/uploads/file', lang:'de', store:true}

Writes thumbnails into /uploads as PNG (thumb_<stem>_<w>x<h>.png).
OCR/Whisper results are stored as memory blocks (tags: ocr|stt,media).
"""
import os, time, json, mimetypes
from pathlib import Path
from typing import Any, Dict

from ..netapi.db import SessionLocal
from ..netapi.models import Job
from ..netapi import memory_store as _mem
import urllib.request as _ur
import urllib.error as _ue
try:
    # optional audit logger
    from ..netapi.modules.admin.router import write_audit  # type: ignore
except Exception:  # pragma: no cover
    def write_audit(*args, **kwargs):  # type: ignore
        return None, ""

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
UPLOADS = KI_ROOT / "uploads"


def _now() -> int: return int(time.time())


def _lease_one(db) -> Job | None:
    now = _now()
    j = (
        db.query(Job)
        .filter(Job.type.in_(["media.thumbnail","media.ocr","media.whisper"]), ((Job.status == "queued") | (Job.lease_until < now)))
        .order_by(Job.priority.desc(), Job.id.asc())
        .first()
    )
    if not j:
        return None
    j.status = "leased"; j.lease_until = now + 60; j.updated_at = now
    db.add(j); db.commit(); db.refresh(j)
    return j


def _done(db, j: Job):
    j.status = "done"; j.lease_until = 0; j.updated_at = _now(); j.error = ""
    db.add(j); db.commit()


def _fail(db, j: Job, msg: str):
    j.attempts = int(j.attempts or 0) + 1
    j.error = (msg or "")[:2000]
    now = _now()
    if j.attempts >= 5:
        j.status = "failed"; j.lease_until = 0
    else:
        j.status = "queued"; j.lease_until = now + min(3600, 5 * (2 ** min(7, j.attempts)))
    j.updated_at = now
    db.add(j); db.commit()


def _load_payload(j: Job) -> Dict[str, Any]:
    try:
        return json.loads(j.payload or "{}")
    except Exception:
        return {}


def _abs_from_rel(rel: str) -> Path:
    p = rel or ""
    if p.startswith("/uploads/"):
        return (KI_ROOT / p.lstrip("/")).resolve()
    return (KI_ROOT / p.lstrip("/")).resolve()


def _thumbnail(path: Path, w: int = 256, h: int = 256) -> Path:
    out = UPLOADS / f"thumb_{path.stem}_{w}x{h}.png"
    # Idempotency: skip if thumbnail exists and is newer than source
    try:
        if out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
            return out
    except Exception:
        pass
    buf = None
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("video/"):
            cap = cv2.VideoCapture(str(path))
            ok, frame = cap.read(); cap.release()
            img = frame if ok and frame is not None else None
        else:
            img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            ih, iw = img.shape[:2]
            scale = min(w / max(1, iw), h / max(1, ih))
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
            resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
            ok, enc = cv2.imencode('.png', resized)
            if ok:
                buf = enc.tobytes()
    except Exception:
        buf = None
    if buf is None:
        from PIL import Image  # type: ignore
        with Image.open(path) as im:
            im.thumbnail((w, h))
            import io
            bio = io.BytesIO(); im.save(bio, format='PNG'); buf = bio.getvalue()
    out.write_bytes(buf)
    return out


def _emit_knowledge(kind: str, path: Path, *, text: str | None, job_id: int | None) -> None:
    """Best-effort POST to /api/knowledge. Requires ADMIN_API_TOKEN (or creator session)."""
    try:
        payload = {
            "source": f"media:{path.name}",
            "type": kind,
            "tags": ["media"] + ([f"job:{job_id}"] if job_id else []),
            "content": (text or f"generated {kind} for /uploads/{path.name}")[:200000],
            "ts": int(_now()),
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = _ur.Request("http://127.0.0.1:8000/api/knowledge", data=data, headers={"Content-Type":"application/json"})
        tok = os.getenv("ADMIN_API_TOKEN")
        if tok:
            req.add_header("Authorization", f"Bearer {tok}")
        _ur.urlopen(req, timeout=2)
    except Exception:
        pass


def _ocr_to_memory(path: Path) -> tuple[str | None, str]:
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    text = ""
    # Idempotency: skip if an OCR block for this URL already exists
    try:
        from ..netapi.memory_store import META_PATH as _MS_META  # type: ignore
        import json as _json
        if _MS_META.exists():
            meta = _json.loads(_MS_META.read_text(encoding='utf-8'))
            url = f"/uploads/{path.name}"
            for _bid, info in meta.items():
                if str(info.get('url') or '') == url:
                    tags = info.get('tags') or []
                    if 'ocr' in tags:
                        return None
    except Exception:
        pass
    try:
        if ctype.startswith("image/"):
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore
            text = pytesseract.image_to_string(Image.open(path))
        elif ctype == "application/pdf":
            from pdfminer.high_level import extract_text  # type: ignore
            text = extract_text(str(path)) or ""
    except Exception:
        text = ""
    text = (text or "").strip()
    if not text:
        return None, ""
    try:
        bid = _mem.add_block(title=f"OCR: {path.name}", content=text, tags=["ocr","media"], url=f"/uploads/{path.name}")
        return bid, text
    except Exception:
        return None, text


def _whisper_to_memory(path: Path, lang: str | None = None) -> tuple[str | None, str]:
    try:
        import whisper  # type: ignore
    except Exception:
        return None
    # Idempotency: skip if a STT block for this URL already exists
    try:
        from ..netapi.memory_store import META_PATH as _MS_META  # type: ignore
        import json as _json
        if _MS_META.exists():
            meta = _json.loads(_MS_META.read_text(encoding='utf-8'))
            url = f"/uploads/{path.name}"
            for _bid, info in meta.items():
                if str(info.get('url') or '') == url:
                    tags = info.get('tags') or []
                    if 'stt' in tags:
                        return None
    except Exception:
        pass
    try:
        name = os.getenv("KI_WHISPER_MODEL", "base")
        model = whisper.load_model(name)
        res = model.transcribe(str(path), language=lang)
        text = (res.get("text") or "").strip()
        if not text:
            return None
        bid = _mem.add_block(title=f"STT: {path.name}", content=text, tags=["stt","media"], url=f"/uploads/{path.name}")
        return bid, text
    except Exception:
        return None, text


def _exec(j: Job) -> None:
    p = _load_payload(j)
    rel = str(p.get("path") or "")
    if not rel:
        raise RuntimeError("missing path")
    src = _abs_from_rel(rel)
    if not src.exists():
        raise RuntimeError("file not found")
    if j.type == "media.thumbnail":
        w = int(p.get("w") or 256); h = int(p.get("h") or 256)
        out = _thumbnail(src, w=w, h=h)
        try:
            write_audit("media_thumbnail", actor_id=0, target_type="media", target_id=int(j.id or 0), meta={"file": str(src), "thumb": str(out), "w": w, "h": h})
        except Exception:
            pass
        # Emit knowledge block (no heavy content)
        try:
            _emit_knowledge("thumb", src, text=f"Thumbnail generated: /uploads/{out.name}", job_id=int(j.id or 0))
        except Exception:
            pass
    elif j.type == "media.ocr":
        bid, text = _ocr_to_memory(src)
        try:
            _emit_knowledge("ocr", src, text=text, job_id=int(j.id or 0))
        except Exception:
            pass
        try:
            write_audit("media_ocr", actor_id=0, target_type="media", target_id=int(j.id or 0), meta={"file": str(src), "block_id": bid})
        except Exception:
            pass
    elif j.type == "media.whisper":
        bid, text = _whisper_to_memory(src, p.get("lang"))
        try:
            _emit_knowledge("whisper", src, text=text, job_id=int(j.id or 0))
        except Exception:
            pass
        try:
            write_audit("media_whisper", actor_id=0, target_type="media", target_id=int(j.id or 0), meta={"file": str(src), "block_id": bid, "lang": p.get("lang")})
        except Exception:
            pass
    else:
        raise RuntimeError(f"unknown job type {j.type}")


def _write_heartbeat(last: dict | None = None) -> None:
    try:
        logdir = KI_ROOT / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        hb = {
            "name": "media",
            "ts": _now(),
            "pid": os.getpid(),
            "host": os.uname().nodename if hasattr(os, 'uname') else None,
            "job_types": ["media.thumbnail","media.ocr","media.whisper"],
        }
        if last:
            hb.update(last)
        (logdir / "worker_heartbeat_media.json").write_text(json.dumps(hb, ensure_ascii=False), encoding='utf-8')
        # Also POST to local API (non-fatal if offline)
        try:
            import urllib.request as _ur
            data = json.dumps({
                "name": hb.get("name"),
                "type": "media",
                "status": hb.get("last_status") or "ok",
                "pid": hb.get("pid"),
                "job_types": hb.get("job_types"),
                "ts": hb.get("ts"),
            }).encode("utf-8")
            req = _ur.Request("http://127.0.0.1:8000/api/jobs/heartbeat", data=data, headers={"Content-Type":"application/json"})
            _ur.urlopen(req, timeout=2)
        except Exception:
            pass
    except Exception:
        pass


def main():
    print("[media_worker] starting …")
    idle = float(os.getenv("KI_WORKER_IDLE_SLEEP", "2"))
    last_hb = 0
    while True:
        try:
            with SessionLocal() as db:
                now = _now()
                if now - last_hb >= 10:
                    _write_heartbeat(None); last_hb = now
                j = _lease_one(db)
                if not j:
                    time.sleep(idle)
                    # periodic heartbeat even if idle
                    now = _now()
                    if now - last_hb >= 10:
                        _write_heartbeat(None); last_hb = now
                    continue
                try:
                    _exec(j)
                    _done(db, j)
                    print(f"[media_worker] done #{j.id} {j.type}")
                    _write_heartbeat({"last_job_id": j.id, "last_type": j.type, "last_status": "done"}); last_hb = _now()
                except Exception as e:
                    _fail(db, j, f"{type(e).__name__}: {e}")
                    print(f"[media_worker] failed #{j.id}: {e}")
                    try:
                        write_audit("media_job_failed", actor_id=0, target_type="job", target_id=int(j.id or 0), meta={"type": j.type, "error": f"{type(e).__name__}: {e}"})
                    except Exception:
                        pass
                    _write_heartbeat({"last_job_id": j.id, "last_type": j.type, "last_status": "failed"}); last_hb = _now()
        except KeyboardInterrupt:
            print("[media_worker] exiting")
            break
        except Exception as e:
            print("[media_worker] outer error:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
