from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, Dict, Any
from pathlib import Path
import json, os, time
from urllib.parse import urlparse, urlunparse

from ...deps import get_current_user_required, require_role

router = APIRouter(prefix="/api/sys", tags=["sys"])  # system controls

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()

@router.post("/shutdown")
def emergency_shutdown(reason: Optional[str] = None, user = Depends(get_current_user_required)):
    """Activate emergency stop by writing KI_ROOT/emergency_stop JSON file.
    Roles: admin or papa only.
    """
    require_role(user, {"admin", "papa"})
    path = KI_ROOT / "emergency_stop"
    rec = {"ts": int(time.time()), "by": user.get("username") or user.get("email") or str(user.get("id")), "reason": reason or ""}
    try:
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "path": str(path)}
    except Exception as e:
        raise HTTPException(500, f"shutdown failed: {e}")

@router.post("/recover")
def emergency_recover(user = Depends(get_current_user_required)):
    """Disable emergency stop by removing KI_ROOT/emergency_stop. Roles: admin or papa only."""
    require_role(user, {"admin", "papa"})
    path = KI_ROOT / "emergency_stop"
    try:
        path.unlink(missing_ok=True)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"recover failed: {e}")

@router.post("/invalidate_last")
def invalidate_last(n: int = 10, tag: str = "tool_usage", user = Depends(get_current_user_required)):
    """Mark the last N blocks with a tag as invalid via audit entries.
    Roles: admin or papa only.
    """
    require_role(user, {"admin", "papa"})
    try:
        from ...memory_store import search_blocks, get_block, add_block  # type: ignore
        hits = search_blocks(tag, top_k=max(1, n), min_score=0.0) or []
        ids = [bid for (bid, _s) in hits][:max(1, n)]
        audit = {"ts": int(time.time()), "by": user.get("username") or user.get("email") or str(user.get("id")), "action": "invalidate", "tag": tag, "ids": ids}
        add_block(title=f"Invalidate last {len(ids)} blocks", content=json.dumps(audit, ensure_ascii=False), tags=["audit","invalidate", tag], url=None, meta=audit)
        return {"ok": True, "invalidated": len(ids)}
    except Exception as e:
        raise HTTPException(500, f"invalidate failed: {e}")


@router.get("/db_info")
def db_info(user = Depends(get_current_user_required)):
    """Return masked database configuration and engine info.
    Roles: admin or papa only.
    """
    require_role(user, {"admin", "papa"})
    try:
        from ...db import engine  # type: ignore
    except Exception as e:
        raise HTTPException(500, f"db engine unavailable: {e}")

    raw = os.getenv("DATABASE_URL", "")
    masked = raw
    try:
        if raw:
            u = urlparse(raw)
            netloc = u.hostname or ""
            if u.port:
                netloc += f":{u.port}"
            # keep username presence, mask password if present
            if u.username:
                netloc = (u.username or "user") + ":***@" + (u.hostname or "localhost")
                if u.port:
                    netloc += f":{u.port}"
            masked = urlunparse((u.scheme, netloc, u.path, u.params, u.query, u.fragment))
    except Exception:
        masked = "(unparseable)"

    # sqlite fallback path
    if not raw:
        try:
            ki_root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
        except Exception:
            ki_root = Path.home() / "ki_ana"
        masked = f"sqlite:///{ki_root / 'netapi' / 'users.db'}"

    try:
        url_rendered = str(engine.url)
        dialect = engine.url.get_backend_name() if hasattr(engine.url, 'get_backend_name') else engine.dialect.name
    except Exception:
        url_rendered = "(n/a)"; dialect = "(n/a)"

    return {
        "ok": True,
        "database": {
            "dialect": dialect,
            "configured_url_masked": masked,
            "engine_url_truncated": url_rendered.split('@')[-1] if '@' in url_rendered else url_rendered,
            "is_sqlite": dialect.startswith('sqlite') if isinstance(dialect, str) else False,
        }
    }
