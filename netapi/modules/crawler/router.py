from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Any, Dict, List

# Prefer normal package import; fall back to file-based import when running
# in environments where top-level package 'ki_ana' isn't on sys.path.
try:
    from ki_ana.system.crawler_loop import run_crawler_once, promote_crawled_to_blocks  # type: ignore
except Exception:
    from importlib.machinery import SourceFileLoader as _Loader  # type: ignore
    from pathlib import Path as _Path  # type: ignore
    try:
        _p = _Path.home() / "ki_ana" / "system" / "crawler_loop.py"
        _mod = _Loader("crawler_loop", str(_p)).load_module()  # type: ignore
        run_crawler_once = getattr(_mod, "run_crawler_once")  # type: ignore
        promote_crawled_to_blocks = getattr(_mod, "promote_crawled_to_blocks")  # type: ignore
    except Exception as _e:
        # Delay the import error until the endpoint is actually called, so the app can boot
        def _fail(*args, **kwargs):  # type: ignore
            raise RuntimeError(f"crawler_loop import failed: {_e}")
        run_crawler_once = _fail  # type: ignore
        promote_crawled_to_blocks = _fail  # type: ignore

router = APIRouter(prefix="/crawler", tags=["crawler"])
# Separate UI router without /api prefix
ui_router = APIRouter(tags=["crawler-ui"])

from ...deps import get_current_user_required, require_role
from ...deps import get_db
from ...models import Job
from sqlalchemy.orm import Session
import time, json

def _require_admin_or_worker(user: dict) -> None:
    # Backward-compatible shim using centralized deps helper
    require_role(user, {"admin", "worker"})

@router.post("/run")
async def run_once(user = Depends(get_current_user_required)) -> Dict[str, Any]:
    """Fetch from configured sources and store under memory/crawled/."""
    _require_admin_or_worker(user)
    res = run_crawler_once()
    return res

@router.post("/promote")
async def promote(user = Depends(get_current_user_required)) -> Dict[str, Any]:
    """Promote eligible crawled docs into long-term blocks."""
    _require_admin_or_worker(user)
    try:
        n = promote_crawled_to_blocks()
        return {"ok": True, "promoted": int(n)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------- Job queue integration -------------------------

@router.post("/enqueue/run")
async def enqueue_run(
    payload: Dict[str, Any] = Body(default_factory=dict),
    user = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Enqueue a crawler run as background job.

    Body accepts optional fields like {"priority": 0, "idempotency_key": "...", ...}
    Additional fields are stored in the job payload for workers.
    """
    # Basic role check
    _require_admin_or_worker(user)
    body = dict(payload or {})
    idem = body.get("idempotency_key")
    if idem:
        existing = db.query(Job).filter(Job.idempotency_key == str(idem)).first()
        if existing:
            return {"ok": True, "id": existing.id, "status": existing.status}
    now = int(time.time())
    j = Job(
        type="crawler.run",
        payload=json.dumps({k: v for k, v in body.items() if k not in {"priority", "idempotency_key"}}, ensure_ascii=False),
        status="queued",
        attempts=0,
        lease_until=0,
        idempotency_key=str(idem) if idem else None,
        priority=int(body.get("priority") or 0),
        created_at=now,
        updated_at=now,
    )
    db.add(j); db.commit(); db.refresh(j)
    return {"ok": True, "id": j.id}


@router.post("/enqueue/promote")
async def enqueue_promote(
    payload: Dict[str, Any] = Body(default_factory=dict),
    user = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Enqueue promotion of crawled docs into blocks as background job.

    Body accepts {"limit": 100, "dry_run": false, "priority": 0, "idempotency_key": "..."}
    """
    _require_admin_or_worker(user)
    body = dict(payload or {})
    idem = body.get("idempotency_key")
    if idem:
        existing = db.query(Job).filter(Job.idempotency_key == str(idem)).first()
        if existing:
            return {"ok": True, "id": existing.id, "status": existing.status}
    now = int(time.time())
    j = Job(
        type="crawler.promote",
        payload=json.dumps({k: v for k, v in body.items() if k not in {"priority", "idempotency_key"}}, ensure_ascii=False),
        status="queued",
        attempts=0,
        lease_until=0,
        idempotency_key=str(idem) if idem else None,
        priority=int(body.get("priority") or 0),
        created_at=now,
        updated_at=now,
    )
    db.add(j); db.commit(); db.refresh(j)
    return {"ok": True, "id": j.id}


@ui_router.get("/ui/crawl", response_class=HTMLResponse)
async def crawl_ui() -> str:
    """Runs one crawl cycle and promotion, renders a compact HTML report."""
    res = run_crawler_once()
    try:
        promoted = promote_crawled_to_blocks()
    except Exception as e:
        promoted = f"error: {e}"
    urls: List[str] = []
    for item in (res.get("fetched") or []):
        u = item.get("url")
        if u:
            urls.append(str(u))
    html = [
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<link rel='stylesheet' href='/static/styles.css'><title>Crawler Ergebnis</title></head><body class='page'>",
        "<div id='nav' data-src='/static/nav.html'></div>",
        "<main class='container'>",
        "<section class='card'>",
        "<h2>Crawler jetzt ausgeführt</h2>",
        f"<p class='small'>Gefetchte Quellen: {len(urls)} · Promoted: {promoted}</p>",
        "<ul>",
    ]
    for u in urls:
        html.append(f"<li><a href='{u}' target='_blank' rel='noopener'>{u}</a></li>")
    html += [
        "</ul>",
        "<p><a class='btn' href='/static/papa.html'>Zurück zum Papa‑Menü</a></p>",
        "</section>",
        "</main>",
        "<script defer src='/static/nav.js'></script>",
        "</body></html>",
    ]
    return "".join(html)

# Convenience redirects for users expecting a generic /webui entrypoint
@ui_router.get("/webui", include_in_schema=False)
@ui_router.get("/webui/", include_in_schema=False)
async def webui_redirect():
    return RedirectResponse(url="/static/papa.html", status_code=307)
