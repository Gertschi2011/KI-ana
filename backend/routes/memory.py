from __future__ import annotations
from flask import Blueprint, request, jsonify
from typing import Dict, Any, List
import hashlib, json, time

bp = Blueprint("memory", __name__)

_CHAIN: List[Dict[str, Any]] = []


def _hash_block(b: Dict[str, Any]) -> str:
    data = json.dumps(b, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _last_hash() -> str:
    return _CHAIN[-1]["hash"] if _CHAIN else "0" * 64


def _verify_chain() -> bool:
    prev = "0" * 64
    for b in _CHAIN:
        if b.get("prev_hash") != prev:
            return False
        h = _hash_block({k: v for k, v in b.items() if k != "hash"})
        if h != b.get("hash"):
            return False
        prev = b["hash"]
    return True


@bp.get("/blocks")
def list_blocks():
    return jsonify({"ok": True, "items": _CHAIN, "valid": _verify_chain()})


@bp.post("/append")
def append_block():
    payload = request.get_json(force=True, silent=True) or {}
    content = payload.get("content") or {}
    b = {
        "ts": int(time.time()),
        "type": payload.get("type") or "KNOWLEDGE",
        "source": payload.get("source") or "api",
        "tags": payload.get("tags") or [],
        "prev_hash": _last_hash(),
        "content": content,
    }
    b["hash"] = _hash_block(b)
    _CHAIN.append(b)
    return jsonify({"ok": True, "block": b, "valid": _verify_chain()})


@bp.post("/verify")
def verify_chain_endpoint():
    return jsonify({"ok": True, "valid": _verify_chain(), "height": len(_CHAIN)})
