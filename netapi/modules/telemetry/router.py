from __future__ import annotations
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from typing import Any, Dict
import time

from ...db import SessionLocal
from ...models import BrowserError
from ...deps import get_current_user_opt, get_current_user_required, require_role

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


def _client_ip(request: Request) -> str:
    try:
        h = request.headers
        ip = h.get("x-forwarded-for") or h.get("X-Forwarded-For") or (request.client.host if request.client else "")
        if ip and "," in ip:
            ip = ip.split(",", 1)[0].strip()
        return ip or ""
    except Exception:
        return ""


def _scrub_url(url: str) -> str:
    try:
        from urllib.parse import urlsplit, urlunsplit
        u = urlsplit(url or "")
        # drop query and fragment
        return urlunsplit((u.scheme, u.netloc, u.path, "", "")) or (u.path or "")
    except Exception:
        return (url or "").split("?")[0].split("#")[0]


@router.post("/error")
async def telemetry_error(request: Request, body: Dict[str, Any] | None = None, user = Depends(get_current_user_opt)):
    js = body or {}
    # Basic sanitize/limits
    msg = str(js.get("message") or "")[:500]
    url = _scrub_url(str(js.get("url") or ""))[:400]
    stack = str(js.get("stack") or "")[:4000]
    level = str(js.get("level") or "error")[:12]
    ts = int(time.time())
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")[:400]
    uid = int((user or {}).get("id") or 0)

    # Simple upsert-ish: collapse identical message+url within a small time window
    try:
        with SessionLocal() as db:
            # window: last 10 minutes
            win = ts - 600
            rec = (
                db.query(BrowserError)
                .filter(BrowserError.message == msg, BrowserError.url == url, BrowserError.ts >= win)
                .order_by(BrowserError.id.desc())
                .first()
            )
            if rec:
                rec.count = int(rec.count or 1) + 1
                rec.ts = ts
                rec.user_id = uid or rec.user_id
                db.add(rec); db.commit()
                return JSONResponse({"ok": True, "id": rec.id, "count": rec.count})
            be = BrowserError(ts=ts, level=level, message=msg, url=url, stack=stack, user_id=uid, user_agent=ua, ip=ip, count=1)
            db.add(be); db.commit(); db.refresh(be)
            return JSONResponse({"ok": True, "id": be.id, "count": be.count})
    except Exception:
        # never break UI
        return JSONResponse({"ok": True})


@router.get("/summary")
def telemetry_summary(since: int = 86400, top: int = 5, user = Depends(get_current_user_required)):
    # Creator/Admin only
    require_role(user, {"creator", "admin"})
    now = int(time.time())
    t0 = max(0, now - int(since or 86400))
    try:
        with SessionLocal() as db:
            from sqlalchemy import func
            q = (
                db.query(BrowserError.message, BrowserError.url, func.sum(BrowserError.count).label('total'))
                .filter(BrowserError.ts >= t0)
                .group_by(BrowserError.message, BrowserError.url)
                .order_by(func.sum(BrowserError.count).desc())
            )
            rows = q.limit(max(1, min(500, int(top or 5)))).all()
            items = [{"message": m or "", "url": u or "", "count": int(c or 0)} for (m,u,c) in rows]

            # Telemetry sanity (best-effort): show whether chat traffic is happening.
            interactions_1h = None
            try:
                from netapi.modules.observability import metrics as _m
                c = _m.window_route_status_counts(route="/api/v2/chat", method="POST", window_seconds=3600, exclude_statuses={401})
                interactions_1h = int(c.get("ok2xx") or 0)
            except Exception:
                interactions_1h = None

            return {"ok": True, "since": t0, "items": items, "sanity": {"interactions_1h": interactions_1h}}
    except Exception:
        return {"ok": True, "since": t0, "items": []}


@router.get("/recent")
def telemetry_recent(limit: int = 50, since: int = 0, user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    try:
        with SessionLocal() as db:
            q = db.query(BrowserError)
            if since:
                q = q.filter(BrowserError.ts >= int(since))
            rows = q.order_by(BrowserError.ts.desc()).limit(max(1, min(500, int(limit or 50)))).all()
            items = [{
                "ts": int(r.ts or 0),
                "level": r.level or "error",
                "message": r.message or "",
                "url": r.url or "",
                "stack": r.stack or "",
                "user_id": int(r.user_id or 0),
                "ip": r.ip or "",
                "count": int(r.count or 1),
            } for r in rows]
            return {"ok": True, "items": items}
    except Exception:
        return {"ok": True, "items": []}


@router.get("/series")
def telemetry_series(hours: int = 24, user = Depends(get_current_user_required)):
    """Return per-hour aggregated counts for the last `hours`. Creator/Admin only."""
    require_role(user, {"creator", "admin"})
    try:
        hours = max(1, min(240, int(hours or 24)))
        now = int(time.time())
        start = now - hours * 3600
        with SessionLocal() as db:
            rows = (
                db.query(BrowserError.ts, BrowserError.count)
                .filter(BrowserError.ts >= start)
                .order_by(BrowserError.ts.asc())
                .all()
            )
        # Bucketize into hours
        buckets = {}
        for ts, cnt in rows:
            try:
                h = int(ts) // 3600
                buckets[h] = buckets.get(h, 0) + int(cnt or 1)
            except Exception:
                continue
        # Build full series including empty buckets
        series = []
        for i in range(hours):
            hb = (start // 3600) + i + 1  # end-aligned buckets up to now
            t0 = hb * 3600
            series.append({"t": t0, "count": int(buckets.get(hb, 0))})
        return {"ok": True, "start": start, "end": now, "points": series}
    except Exception:
        return {"ok": True, "start": 0, "end": 0, "points": []}


def prune_old(days: int = 30) -> int:
    """Delete browser_errors older than `days`. Returns rows deleted."""
    try:
        cutoff = int(time.time()) - max(1, int(days)) * 86400
        with SessionLocal() as db:
            from sqlalchemy import delete
            res = db.execute(delete(BrowserError).where(BrowserError.ts < cutoff))
            db.commit()
            return int(getattr(res, 'rowcount', 0) or 0)
    except Exception:
        return 0


@router.post("/prune")
def telemetry_prune(days: int = 30, user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    n = prune_old(days)
    # Audit (best effort)
    try:
        from ..admin.router import write_audit  # type: ignore
        write_audit("telemetry_prune", actor_id=int((user or {}).get("id") or 0), target_type="telemetry", target_id=0, meta={"deleted": int(n), "days": int(days)})
    except Exception:
        pass
    return {"ok": True, "deleted": n, "days": int(days)}
