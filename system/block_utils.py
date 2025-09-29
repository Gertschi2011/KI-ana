#!/usr/bin/env python3
from __future__ import annotations
import json, hashlib
from pathlib import Path
from typing import Dict, Any, Tuple, List
from importlib.machinery import SourceFileLoader

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"


def _canonical(obj: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(obj)
    for k in ("hash", "hash_stored", "hash_calc", "signature", "pubkey", "signed_at"):
        data.pop(k, None)
    return data


def calc_block_hash(block: Dict[str, Any]) -> str:
    raw = json.dumps(_canonical(block), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_signer():
    if not SIGNER_PATH.exists():
        raise RuntimeError("block_signer.py not found")
    return SourceFileLoader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore


def verify_signature(block: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        signer = _load_signer()
        ok, reason = signer.verify_block(block)  # type: ignore
        return bool(ok), str(reason)
    except Exception as e:
        return False, f"verify_error:{type(e).__name__}"


def _existing_hashes() -> Tuple[set, set]:
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    seen_block_hash: set = set()
    seen_canonical_hash: set = set()
    for p in BLOCKS_DIR.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            if obj.get("hash"):
                seen_block_hash.add(obj["hash"])
            ch = obj.get("meta", {}).get("canonical_hash")
            if ch:
                seen_canonical_hash.add(ch)
        except Exception:
            continue
    return seen_block_hash, seen_canonical_hash


def validate_and_store_block(block: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    """Validate essential invariants and persist to blocks/ as JSON.
    Checks:
      - meta.provenance present
      - signature present and valid
      - no duplicate by block hash or canonical_hash
    Returns: { ok, reason?, path?, dedup? }
    """
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    meta = block.setdefault("meta", {})
    prov = (meta.get("provenance") or "").strip()
    if not prov:
        return {"ok": False, "reason": "provenance_missing"}

    # ensure hash
    block_hash = calc_block_hash(block)
    block["hash"] = block_hash

    # signature required and must be valid
    ok, reason = verify_signature(block)
    if not ok:
        return {"ok": False, "reason": f"signature_invalid:{reason}"}

    # duplicate check
    seen_block_hash, seen_canonical_hash = _existing_hashes()
    if block_hash in seen_block_hash:
        return {"ok": True, "dedup": True, "reason": "block_hash_exists"}
    ch = meta.get("canonical_hash")
    if ch and ch in seen_canonical_hash:
        return {"ok": True, "dedup": True, "reason": "canonical_hash_exists"}

    # path uniqueness by id
    bid = str(block.get("id") or block_hash[:16])
    out = BLOCKS_DIR / f"{bid}.json"
    if out.exists() and not overwrite:
        # if existing content identical, mark as dedup
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
            if existing.get("hash") == block_hash:
                return {"ok": True, "dedup": True, "reason": "same_file"}
        except Exception:
            pass
    out.write_text(json.dumps(block, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    # publish event (best-effort)
    try:
        bus = SourceFileLoader("events_bus", str(BASE_DIR / "system" / "events_bus.py")).load_module()  # type: ignore
        evt = {
            "type": "block:new",
            "id": block.get("id") or (block_hash[:16]),
            "hash": block_hash,
            "topic": block.get("topic") or "",
            "path": str(out),
        }
        getattr(bus, "publish", lambda *_a, **_k: None)(evt)  # type: ignore
    except Exception:
        pass
    return {"ok": True, "path": str(out)}


def load_block_by_id(block_id: str, verify: bool = True) -> Tuple[Dict[str, Any] | None, str]:
    p = BLOCKS_DIR / f"{block_id}.json"
    if not p.exists():
        return None, "not_found"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None, "read_error"
    if verify:
        ok, reason = verify_signature(obj)
        if not ok:
            return None, f"invalid_signature:{reason}"
    return obj, "ok"


def query_blocks(topic: str | None = None, tags: List[str] | None = None, content_hash: str | None = None, limit: int = 200) -> List[Dict[str, Any]]:
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    topic = (topic or "").strip()
    tags = tags or []
    content_hash = (content_hash or "").strip()
    out: List[Dict[str, Any]] = []
    for p in sorted(BLOCKS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:2000]:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            if topic and (obj.get("topic") or "").strip() != topic:
                continue
            if content_hash and (obj.get("meta", {}).get("canonical_hash") or "") != content_hash:
                continue
            if tags:
                ot = set(obj.get("tags") or []) | set(obj.get("meta", {}).get("tags") or [])
                if not set(tags).issubset(ot):
                    continue
            out.append(obj)
            if len(out) >= limit:
                break
        except Exception:
            continue
    return out
