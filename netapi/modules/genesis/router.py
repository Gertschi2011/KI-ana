from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path
from importlib.machinery import SourceFileLoader

router = APIRouter(prefix="/genesis", tags=["genesis"])
BASE_DIR = Path.home() / "ki_ana"


def _load_loader():
    p = BASE_DIR / "system" / "genesis_loader.py"
    mod = SourceFileLoader("genesis_loader", str(p)).load_module()  # type: ignore
    if not hasattr(mod, "load_genesis"):
        raise RuntimeError("genesis_loader.load_genesis missing")
    return mod


@router.get("")
async def get_genesis(tags: str | None = None, provenance: str | None = None, linked_to: str | None = None):
    """Return emergency and cognitive genesis blocks.
    Optional filters:
      - tags: comma-separated list; block must contain all provided tags
      - provenance: exact match against block.meta.provenance
      - linked_to: exact match against block.meta.linked_to
    """
    mod = _load_loader()
    data = mod.load_genesis()  # type: ignore

    def _match(b):
        if not isinstance(b, dict):
            return False
        meta = b.get("meta", {}) or {}
        # provenance
        if provenance is not None and str(meta.get("provenance", "")) != provenance:
            return False
        # linked_to
        if linked_to is not None and str(meta.get("linked_to", "")) != linked_to:
            return False
        # tags (must contain all requested)
        if tags:
            req = [t.strip().lower() for t in tags.split(",") if t.strip()]
            have = [t.strip().lower() for t in (b.get("tags") or [])]
            for t in req:
                if t and t not in have:
                    return False
        return True

    em = data.get("emergency")
    cog = data.get("cognitive")
    if any([tags, provenance, linked_to]):
        em = em if _match(em) else None
        cog = cog if _match(cog) else None
    payload = {
        "ok": True,
        "emergency": em,
        "emergency_hash_ok": data.get("emergency_hash_ok"),
        "cognitive": cog,
    }
    return JSONResponse(payload)
