from __future__ import annotations
import os
import json
import hashlib
import time
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any, Tuple
from importlib.machinery import SourceFileLoader
from pathlib import Path

from netapi.deps import get_current_user_required, require_role

BASE_DIR = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
UTILS_PATH = BASE_DIR / "system" / "block_utils.py"

_utils = SourceFileLoader("block_utils", str(UTILS_PATH)).load_module()  # type: ignore

router = APIRouter(tags=["blocks"])


CHAIN_DIR = BASE_DIR / "system" / "chain"
MEM_BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"


def _canonical(obj: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(obj)
    for k in ("hash", "hash_stored", "hash_calc", "signature", "pubkey", "signed_at"):
        data.pop(k, None)
    return data


def _calc_sha256(obj: Dict[str, Any]) -> str:
    raw = json.dumps(_canonical(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _verify_signature(data: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        if not SIGNER_PATH.exists():
            return False, "signer_missing"
        mod = SourceFileLoader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
        if not hasattr(mod, "verify_block"):
            return False, "verify_missing"
        ok, reason = mod.verify_block(data)  # type: ignore
        return bool(ok), str(reason)
    except Exception as e:
        return False, f"verify_error:{type(e).__name__}"


def _summarize_block(p: Path, origin: str) -> Dict[str, Any]:
    data = json.loads(p.read_text(encoding="utf-8"))
    stored = str(data.get("hash") or "").strip()
    calc = ""
    valid = False
    reason = "ok"
    try:
        calc = _calc_sha256(data)
        if not stored:
            valid = False
            reason = "hash_missing"
        elif stored != calc:
            valid = False
            reason = "hash_mismatch"
        else:
            valid = True
            reason = "ok"
    except Exception:
        valid = False
        reason = "parse_error"
    sig_ok, sig_reason = _verify_signature(data)
    meta = data.get("meta") or {}
    source = data.get("source") or meta.get("source") or ""
    return {
        "id": data.get("id") or p.stem,
        "title": data.get("title") or data.get("topic") or "",
        "topic": data.get("topic") or "",
        "source": source,
        "timestamp": data.get("timestamp") or data.get("created_at") or "",
        "origin": origin,
        "size": p.stat().st_size,
        "file": str(p.as_posix()),
        "valid": valid,
        "reason": reason,
        "sig_valid": sig_ok,
        "sig_reason": sig_reason,
        "hash_stored": stored,
        "hash_calc": calc,
    }


@router.get("/blocks")
def list_blocks(topic: Optional[str] = None,
               tags: Optional[str] = Query(None, description="Comma-separated tags"),
               hash: Optional[str] = Query(None, alias="hash"),
               limit: int = 200):
    tag_list: List[str] = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    blocks = _utils.query_blocks(topic=topic, tags=tag_list, content_hash=hash, limit=limit)  # type: ignore
    # verify signatures before returning
    out = []
    for b in blocks:
        ok, _ = _utils.verify_signature(b)  # type: ignore
        if ok:
            out.append(b)
    return {"ok": True, "count": len(out), "items": out}


@router.get("/blocks/{block_id}")
def get_block(block_id: str):
    obj, reason = _utils.load_block_by_id(block_id, verify=True)  # type: ignore
    if not obj:
        raise HTTPException(status_code=404, detail=reason)
    return obj


# -------- New API contract (creator-only) ---------------------------------


@router.get("/api/blocks")
def api_list_blocks(
    page: int = 1,
    limit: int = 50,
    include_unverified: bool = False,
    user=Depends(get_current_user_required),
):
    require_role(user, {"creator"})

    try:
        p = max(1, int(page or 1))
    except Exception:
        p = 1
    try:
        lim = int(limit)
    except Exception:
        lim = 50
    if lim <= 0:
        lim = 50
    if lim > 200:
        lim = 200

    items: List[Dict[str, Any]] = []

    def safe_add(path: Path, origin: str) -> None:
        try:
            items.append(_summarize_block(path, origin))
        except Exception:
            items.append({
                "id": path.stem,
                "file": str(path.as_posix()),
                "origin": origin,
                "title": "",
                "topic": "",
                "timestamp": "",
                "source": "",
                "size": path.stat().st_size,
                "valid": False,
                "reason": "parse_error",
                "sig_valid": False,
                "sig_reason": "parse_error",
                "hash_stored": "",
                "hash_calc": "",
            })

    if CHAIN_DIR.exists():
        for path in sorted(CHAIN_DIR.glob("*.json")):
            safe_add(path, "system/chain")
    if MEM_BLOCKS_DIR.exists():
        for path in sorted(MEM_BLOCKS_DIR.glob("*.json")):
            safe_add(path, "memory/long_term/blocks")

    if not include_unverified:
        items = [it for it in items if it.get("valid") and it.get("sig_valid")]

    total = len(items)
    start = (p - 1) * lim
    end = start + lim
    page_items = items[start:end] if start < total else []

    return {
        "ok": True,
        "total": total,
        "count": len(page_items),
        "page": p,
        "limit": lim,
        "pages": ((total + lim - 1) // lim) if lim else 1,
        "items": page_items,
    }


@router.post("/api/blocks/rehash")
def api_rehash_blocks(user=Depends(get_current_user_required)):
    require_role(user, {"creator"})

    changed = 0
    errors: list[str] = []

    for base, origin in ((CHAIN_DIR, "system/chain"), (MEM_BLOCKS_DIR, "memory/long_term/blocks")):
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                calc = _calc_sha256(data)
                stored = str(data.get("hash") or "").strip()
                if stored != calc:
                    # update hash and clear signature-related fields (signature is no longer valid)
                    data["hash"] = calc
                    for k in ("signature", "pubkey", "signed_at"):
                        data.pop(k, None)
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
                    changed += 1
            except Exception as e:
                errors.append(f"{origin}/{path.name}: {type(e).__name__}: {e}")

    return {"ok": True, "count": changed, "errors": errors}
