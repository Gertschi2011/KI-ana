from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path
from typing import List, Dict, Any
import os, time, shutil, mimetypes, secrets, json

from ...deps import get_current_user_opt, get_current_user_required, require_role
from ...db import SessionLocal
from ...models import Job

router = APIRouter(prefix="/api/media", tags=["media"])

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
UPLOAD_DIR = KI_ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ACCEPTED_PREFIXES = ("image/", "audio/", "video/", "application/pdf")


def _safe_name(orig: str) -> str:
    base = Path(orig).name.replace("\x00", "")
    if not base:
        base = "file"
    ts = int(time.time())
    rand = secrets.token_hex(4)
    return f"{ts}_{rand}_{base}"


@router.get("/allowed")
def allowed():
    return {"ok": True, "accept": ["image/*", "audio/*", "video/*", "application/pdf"]}


def _default_lang() -> str:
    return os.getenv("KI_LANG_DEFAULT", "de-DE")


@router.post("/upload")
async def upload(files: List[UploadFile] = File(...), user = Depends(get_current_user_opt), request: Request = None):
    if not files:
        raise HTTPException(400, "no files")
    # Language hint for downstream (e.g., Whisper). Prefer X-Lang header.
    try:
        lang_hint = (request.headers.get('X-Lang') if request else None) or (request.headers.get('x-lang') if request else None) or _default_lang()
    except Exception:
        lang_hint = _default_lang()
    items: List[Dict[str, Any]] = []
    for f in files:
        ctype = (f.content_type or mimetypes.guess_type(f.filename or "")[0] or "application/octet-stream").lower()
        if not (ctype.startswith("image/") or ctype.startswith("audio/") or ctype.startswith("video/") or ctype == "application/pdf"):
            raise HTTPException(415, f"unsupported content-type: {ctype}")
        name = _safe_name(f.filename or "upload.bin")
        out = UPLOAD_DIR / name
        with out.open("wb") as w:
            shutil.copyfileobj(f.file, w)
        url = f"/uploads/{name}"
        # Persist as memory block for traceability
        try:
            from ... import memory_store as _mem  # lazy import
            tag_type = "image" if ctype.startswith("image/") else ("audio" if ctype.startswith("audio/") else ("video" if ctype.startswith("video/") else "pdf"))
            uploader = (user or {}).get("username") or (user or {}).get("email") or "guest"
            meta = {"source": "upload", "uploader": uploader, "mime": ctype, "url": url}
            bid = _mem.add_block(title=f"Upload: {name}", content=f"{ctype} → {url}", tags=["media", tag_type], url=url, meta=meta)
        except Exception:
            bid = ""
        rec: Dict[str, Any] = {
            "name": f.filename or name,
            "stored_as": name,
            "content_type": ctype,
            "url": url,
            "block_id": bid or None,
        }
        # Auto‑enqueue media processing jobs (best effort)
        try:
            rel = url  # '/uploads/...'
            jobs: Dict[str, Any] = {}
            if ctype.startswith("image/"):
                jid = _enqueue_job("media.thumbnail", {"path": rel, "w": 256, "h": 256}, priority=1, idempotency_key=f"thumb:{name}:256x256");
                if jid: jobs["thumbnail"] = jid
                jid = _enqueue_job("media.ocr", {"path": rel, "store": True}, priority=0, idempotency_key=f"ocr:{name}")
                if jid: jobs["ocr"] = jid
            elif ctype == "application/pdf":
                jid = _enqueue_job("media.ocr", {"path": rel, "store": True}, priority=0, idempotency_key=f"ocr:{name}")
                if jid: jobs["ocr"] = jid
            elif ctype.startswith("audio/"):
                jid = _enqueue_job("media.whisper", {"path": rel, "lang": lang_hint, "store": True}, priority=0, idempotency_key=f"whisper:{name}")
                if jid: jobs["whisper"] = jid
            elif ctype.startswith("video/"):
                jid = _enqueue_job("media.thumbnail", {"path": rel, "w": 256, "h": 256}, priority=1, idempotency_key=f"thumb:{name}:256x256")
                if jid: jobs["thumbnail"] = jid
            if jobs:
                rec["jobs"] = jobs
        except Exception:
            pass
        items.append(rec)
    return JSONResponse({"ok": True, "items": items})


def _enqueue_job(jtype: str, payload: Dict[str, Any], *, priority: int = 0, idempotency_key: str | None = None) -> int | None:
    try:
        with SessionLocal() as db:
            if idempotency_key:
                existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
                if existing:
                    return int(existing.id)
            now = int(time.time())
            j = Job(
                type=jtype,
                payload=json.dumps(payload, ensure_ascii=False),
                status="queued",
                attempts=0,
                lease_until=0,
                idempotency_key=idempotency_key,
                priority=int(priority or 0),
                created_at=now,
                updated_at=now,
            )
            db.add(j); db.commit(); db.refresh(j)
            return int(j.id)
    except Exception:
        return None


def _ocr_image(path: Path) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        img = Image.open(path)
        txt = pytesseract.image_to_string(img)
        return (txt or "").strip()
    except Exception:
        return ""


def _ocr_pdf(path: Path) -> str:
    # lightweight pdfminer usage if available
    try:
        from pdfminer.high_level import extract_text  # type: ignore
        txt = extract_text(str(path)) or ""
        return txt.strip()
    except Exception:
        return ""


@router.post("/ocr")
def ocr_extract(body: Dict[str, Any], request: Request, user = Depends(get_current_user_required)):
    """
    Extract text from an uploaded image/PDF and optionally store as memory block.
    Body: {"path": "/uploads/<file>", "store": true}
    """
    # Guard: only admin/worker may OCR via backend service
    require_role(user, {"admin", "worker"})
    rel = str(body.get("path") or body.get("url") or "").strip()
    do_store = bool(body.get("store", True))
    if not rel or not rel.startswith("/uploads/"):
        raise HTTPException(400, "path must be under /uploads/")
    p = (KI_ROOT / rel.lstrip("/"))
    if not p.exists():
        raise HTTPException(404, "file not found")
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    text = ""
    if ctype.startswith("image/"):
        text = _ocr_image(p)
    elif ctype == "application/pdf":
        text = _ocr_pdf(p)
    else:
        raise HTTPException(415, f"unsupported content-type: {ctype}")
    if not text:
        return {"ok": False, "text": "", "stored": False, "note": "backend missing or no text found"}
    stored_id = None
    if do_store:
        try:
            from ... import memory_store as _mem
            stored_id = _mem.add_block(title=f"OCR: {p.name}", content=text, tags=["ocr"], url=rel)
        except Exception:
            stored_id = None
    return {"ok": True, "text": text, "stored": bool(stored_id), "id": stored_id}
_OCR_RATE: dict[str, list[float]] = {}

def _rate_allow_ocr(ip: str, key: str, *, limit: int = 10, per_seconds: int = 300) -> bool:
    import time
    now = time.time()
    bucket = _OCR_RATE.setdefault(f"{ip}:{key}", [])
    while bucket and now - bucket[0] > per_seconds:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


@router.get("/thumbnail")
def thumbnail(path: str, w: int = 256, h: int = 256, user = Depends(get_current_user_required)):
    """Create a small thumbnail for an uploaded image/video first frame.

    Input path must be under `/uploads/`. Uses OpenCV if available, else Pillow.
    Returns PNG bytes.
    """
    # Guard: only admin/worker may render thumbnails via backend
    require_role(user, {"admin", "worker"})
    rel = (path or "").strip()
    if not rel.startswith("/uploads/"):
        raise HTTPException(400, "path must be under /uploads/")
    p = (KI_ROOT / rel.lstrip("/")).resolve()
    if not p.exists():
        raise HTTPException(404, "file not found")
    ctype = (mimetypes.guess_type(p.name)[0] or "application/octet-stream").lower()
    # Try OpenCV for both image/video; fallback to Pillow for images
    buf = None
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        if ctype.startswith("video/"):
            cap = cv2.VideoCapture(str(p))
            ok, frame = cap.read()
            cap.release()
            img = frame if ok and frame is not None else None
        else:
            img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            ih, iw = img.shape[:2]
            scale = min(w / max(1, iw), h / max(1, ih))
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
            resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
            ok2, enc = cv2.imencode('.png', resized)
            if ok2:
                buf = enc.tobytes()
    except Exception:
        buf = None
    if buf is None:
        try:
            from PIL import Image  # type: ignore
            import io
            with Image.open(p) as im:
                im.thumbnail((w, h))
                bio = io.BytesIO()
                im.save(bio, format='PNG')
                buf = bio.getvalue()
        except Exception:
            raise HTTPException(415, f"unsupported file for thumbnail: {ctype}")
    return Response(content=buf, media_type='image/png')


@router.post("/thumbnail")
def thumbnail_json(body: Dict[str, Any], user = Depends(get_current_user_required)):
    """
    JSON-friendly thumbnail stub for planner worker.
    Body: { path: '/uploads/..', max_w?: int, max_h?: int }
    Returns: { ok: true, output: { path: '/uploads/..(thumb?)' } }
    """
    require_role(user, {"admin", "worker", "creator"})
    rel = str(body.get("path") or "").strip()
    if not rel.startswith("/uploads/"):
        raise HTTPException(400, "path must be under /uploads/")
    # Best-effort: point to original or a hypothetical thumb path
    mw = int(body.get("max_w") or body.get("w") or 256)
    mh = int(body.get("max_h") or body.get("h") or 256)
    # If real GET endpoint is desired, frontends can fetch /api/media/thumbnail?path=..&w=&h=
    return {"ok": True, "output": {"path": rel, "w": mw, "h": mh}}


@router.post("/whisper")
def whisper_json(body: Dict[str, Any], user = Depends(get_current_user_required)):
    """
    JSON-friendly whisper stub for planner worker.
    Body: { path: '/uploads/..', lang?: 'de'|'en'|... }
    Returns: { ok: true, text: '...' }
    """
    require_role(user, {"admin", "worker", "creator"})
    rel = str(body.get("path") or "").strip()
    if not rel.startswith("/uploads/"):
        raise HTTPException(400, "path must be under /uploads/")
    lang = str(body.get("lang") or "").strip() or _default_lang()
    # Stub transcript; real implementation can integrate Whisper server
    return {"ok": True, "text": f"[stub transcript {lang}] {rel}"}


@router.post("/chart")
def render_chart(body: Dict[str, Any], request: Request, user = Depends(get_current_user_required)):
    """
    Render a simple chart from JSON input.
    Input: { labels: [str], values: [number], title?: str }
    Output: image/png (Matplotlib) or HTML fallback (Chart.js inline).
    DoS guards: max 200 points, label length <= 60, rate limit per IP.
    """
    # Role check: allow logged-in users; admins/creators can render larger payloads later if needed
    ip = request.client.host if request.client else "?"
    if not _rate_allow(ip, "chart", limit=10, per_seconds=60):
        raise HTTPException(429, "rate limit: 10/min per IP")
    chart_type = str(body.get("type") or "line").strip().lower()  # 'line' | 'bar'
    labels = list(body.get("labels") or [])
    values = list(body.get("values") or [])
    if not labels or not values or len(labels) != len(values):
        raise HTTPException(400, "labels and values required and must be same length")
    if len(labels) > 200:
        raise HTTPException(413, "too many points; max 200")
    try:
        labels = [str(x)[:60] for x in labels]
        vals = []
        for i, x in enumerate(values):
            try:
                vals.append(float(x))
            except Exception:
                raise HTTPException(400, f"values must be numeric (bad at index {i})")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "invalid payload")
    title = str(body.get("title") or "").strip()[:120]
    # Try Matplotlib
    try:
        import matplotlib
        matplotlib.use('Agg')  # no GUI
        import matplotlib.pyplot as plt  # type: ignore
        import io as _io
        fig, ax = plt.subplots(figsize=(min(10, max(4, len(labels)*0.2)), 4))
        if chart_type == 'bar':
            ax.bar(range(len(vals)), vals, color="#4a90e2")
        else:
            ax.plot(range(len(vals)), vals, marker='o')
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.grid(True, linestyle='--', alpha=0.4)
        if title:
            ax.set_title(title)
        bio = _io.BytesIO()
        plt.tight_layout()
        fig.savefig(bio, format='png')
        plt.close(fig)
        return Response(content=bio.getvalue(), media_type='image/png')
    except Exception:
        pass
    # Fallback HTML (render basic SVG chart without external libs)
    html = """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Chart</title>
<script>
// Minimal inline renderer: create a simple SVG chart
function render(){
  const labels = {labels_json};
  const values = {values_json};
  const w=800,h=260,pad=30; const max=Math.max.apply(null, values.concat([1]));
  let svg = `<svg width="${w}" height="${h}" xmlns="https://www.w3.org/2000/svg">`;
  // axes
  svg += `<line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" stroke="#999"/>`;
  svg += `<line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h-pad}" stroke="#999"/>`;
  // plot
  const n=values.length; const xs=[]; const ys=[];
  for(let i=0;i<n;i++){ const x = pad + i*(w-2*pad)/Math.max(1,n-1); const y = h-pad - (values[i]/max)*(h-2*pad); xs.push(x); ys.push(y); }
  const type = {chart_type_json};
  if (type === 'bar'){
    const barW = Math.max(2, (w-2*pad)/Math.max(1,n));
    for(let i=0;i<n;i++){
      const bh = (values[i]/max)*(h-2*pad);
      const x = pad + i*barW;
      const y = h-pad-bh;
      svg += `<rect x="${x}" y="${y}" width="${Math.max(1,barW-1)}" height="${Math.max(1,bh)}" fill="#4a90e2"/>`;
    }
  } else {
    for(let i=1;i<n;i++){
      svg += `<line x1="${xs[i-1]}" y1="${ys[i-1]}" x2="${xs[i]}" y2="${ys[i]}" stroke="#4a90e2"/>`;
    }
    for(let i=0;i<n;i++){
      svg += `<circle cx="${xs[i]}" cy="${ys[i]}" r="3" fill="#4a90e2"/>`;
    }
  }
  svg += `</svg>`;
  document.getElementById('chart').innerHTML = svg;
}
</script>
</head><body onload="render()" style="margin:0;padding:10px;font-family:sans-serif">
  {title_html}
  <div id="chart"></div>
</body></html>
""".replace("{labels_json}", json.dumps(labels))\
      .replace("{values_json}", json.dumps(vals))\
      .replace("{chart_type_json}", json.dumps(chart_type))\
      .replace("{title_html}", (f"<h3>{title}</h3>" if title else ""))
    return HTMLResponse(html)


def _rate_allow(ip: str, key: str, limit: int = 10, per_seconds: int = 60) -> bool:
    """Very small in-memory rate limiter (best-effort)."""
    try:
        import time as _t
        global _RATE_BUCKET
        try:
            _RATE_BUCKET
        except NameError:
            _RATE_BUCKET = {}
        bucket = _RATE_BUCKET.setdefault(key, {})
        now = int(_t.time())
        win = now // per_seconds
        rec = bucket.get(ip)
        if not rec or rec[0] != win:
            bucket[ip] = (win, 1)
            return True
        _, n = rec
        if n >= limit:
            return False
        bucket[ip] = (win, n+1)
        return True
    except Exception:
        return True


@router.post("/image/analyze")
async def analyze_image(request: Request, file: UploadFile = File(...), user = Depends(get_current_user_required)):
    """
    Analyze an image (stub): returns format, size and average color. Login required.
    DoS guard: 10/min/IP and max 10MB file size accepted.
    """
    ip = request.client.host if request.client else "?"
    if not _rate_allow_ocr(ip, "img_analyze", limit=10, per_seconds=60):
        raise HTTPException(429, "rate limit: 10/min per IP")
    try:
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, "image too large")
        try:
            from PIL import Image  # type: ignore
            import io
            im = Image.open(io.BytesIO(data))
            w, h = im.size
            fmt = im.format or ""
            # compute average color (downscale to small)
            im_small = im.convert('RGB')
            im_small.thumbnail((16,16))
            pixels = list(im_small.getdata())
            r = sum(p[0] for p in pixels) // max(1, len(pixels))
            g = sum(p[1] for p in pixels) // max(1, len(pixels))
            b = sum(p[2] for p in pixels) // max(1, len(pixels))
            return {"ok": True, "format": fmt, "width": w, "height": h, "avg_color": [int(r), int(g), int(b)]}
        except ImportError:
            return {"ok": True, "note": "Pillow not installed; returning stub", "size_bytes": len(data)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"invalid image: {e}")
