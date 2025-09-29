from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from pathlib import Path
from importlib.machinery import SourceFileLoader
from netapi.deps import get_current_user_required, has_any_role

router = APIRouter(prefix="/ingest", tags=["ingest"])

PROMOTE_PATH = Path.home() / "ki_ana" / "system" / "promote_crawled_to_blocks.py"
CONSENSUS_PATH = Path.home() / "ki_ana" / "system" / "consensus_merge.py"


def _load_promoter():
    if not PROMOTE_PATH.exists():
        raise RuntimeError(f"promoter script not found at {PROMOTE_PATH}")
    loader = SourceFileLoader("promote_crawled_to_blocks", str(PROMOTE_PATH))
    mod = loader.load_module()  # type: ignore
    if not hasattr(mod, "promote"):
        raise RuntimeError("promoter script lacks promote()")
    return mod


def _load_consensus():
    if not CONSENSUS_PATH.exists():
        raise RuntimeError(f"consensus script not found at {CONSENSUS_PATH}")
    loader = SourceFileLoader("consensus_merge", str(CONSENSUS_PATH))
    mod = loader.load_module()  # type: ignore
    if not hasattr(mod, "consensus_merge"):
        raise RuntimeError("consensus script lacks consensus_merge()")
    return mod


def _log_audit(component: str, action: str, outcome: str, reasons, meta):
    try:
        from importlib.machinery import SourceFileLoader as _Loader
        tl_path = Path.home() / "ki_ana" / "system" / "thought_logger.py"
        if not tl_path.exists():
            return
        _mod = _Loader("thought_logger", str(tl_path)).load_module()  # type: ignore
        if hasattr(_mod, "log_decision"):
            _mod.log_decision(component=component, action=action, outcome=outcome, reasons=reasons, meta=meta)  # type: ignore
    except Exception:
        pass


def _conscience_review(action: str, user_meta: dict):
    try:
        from importlib.machinery import SourceFileLoader as _Loader
        c_path = Path.home() / "ki_ana" / "system" / "conscience.py"
        if not c_path.exists():
            return {"decision": "allow", "risk": 0.0, "reasons": []}
        _c = _Loader("conscience", str(c_path)).load_module()  # type: ignore
        ctx = {"user": user_meta, "external_network": False}
        return _c.review_action(component="ingest", action=action, context=ctx)  # type: ignore
    except Exception:
        return {"decision": "allow", "risk": 0.0, "reasons": ["conscience_error"]}


@router.post("/promote-crawled")
async def promote_crawled(dry_run: Optional[bool] = False, limit: Optional[int] = 100, user = Depends(get_current_user_required)):
    if not has_any_role(user, {"admin", "worker"}):
        raise HTTPException(403, "admin or worker role required")
    try:
        conscience = _conscience_review("promote_crawled", {"username": user.get("username"), "role": user.get("role")})
        if conscience.get("decision") == "block":
            _log_audit("ingest", "promote_crawled", "blocked", conscience.get("reasons", []), {"user": user.get("username"), "role": user.get("role"), "risk": conscience.get("risk")})
            raise HTTPException(423, "conscience_block: action not permitted")
        mod = _load_promoter()
        res = mod.promote(dry_run=bool(dry_run), limit=int(limit or 100))  # type: ignore
        _log_audit(
            component="ingest", action="promote_crawled", outcome="ok",
            reasons=["promote executed"], meta={"user": user.get("username"), "role": user.get("role"), "conscience": conscience, **res}
        )
        # attach conscience info
        return JSONResponse({**res, "conscience": conscience})
    except Exception as e:
        _log_audit(
            component="ingest", action="promote_crawled", outcome="error",
            reasons=[str(e)], meta={"user": user.get("username"), "role": user.get("role")}
        )
        raise HTTPException(500, f"promote failed: {e}")


@router.post("/subki/merge")
async def subki_merge(
    proposals: Optional[List[Dict[str, Any]]] = Body(None),
    min_confidence: Optional[float] = 0.7,
    dry_run: Optional[bool] = False,
    user = Depends(get_current_user_required)
):
    if not has_any_role(user, {"admin", "worker"}):
        raise HTTPException(403, "admin or worker role required")
    try:
        conscience = _conscience_review("subki_merge", {"username": user.get("username"), "role": user.get("role"), "min_confidence": min_confidence})
        if conscience.get("decision") == "block":
            _log_audit("ingest", "subki_merge", "blocked", conscience.get("reasons", []), {"user": user.get("username"), "role": user.get("role"), "risk": conscience.get("risk")})
            raise HTTPException(423, "conscience_block: action not permitted")
        mod = _load_consensus()
        res = mod.consensus_merge(proposals=proposals, min_confidence=float(min_confidence or 0.7), dry_run=bool(dry_run))  # type: ignore
        _log_audit(
            component="ingest", action="subki_merge", outcome="ok",
            reasons=["merge executed"], meta={"user": user.get("username"), "role": user.get("role"), "conscience": conscience, **res}
        )
        return JSONResponse({**res, "conscience": conscience})
    except Exception as e:
        _log_audit(
            component="ingest", action="subki_merge", outcome="error",
            reasons=[str(e)], meta={"user": user.get("username"), "role": user.get("role")}
        )
        raise HTTPException(500, f"merge failed: {e}")
