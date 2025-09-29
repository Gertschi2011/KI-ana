#!/usr/bin/env python3
from __future__ import annotations
import json, time, sys
from pathlib import Path
from typing import Any, Dict, Optional
from importlib.machinery import SourceFileLoader

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"


def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, obj: Dict[str, Any]) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _sign(block: Dict[str, Any]) -> Dict[str, Any]:
    mod = SourceFileLoader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
    sig, pub, ts = mod.sign_block(block)  # type: ignore
    block["signature"], block["pubkey"], block["signed_at"] = sig, pub, ts
    return block


essential_status = {"active", "archived", "updated", "deprecated"}


def edit_block(block_id: str, new_content: Optional[str] = None, status: Optional[str] = None, reason: Optional[str] = None) -> Dict[str, Any]:
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    src = BLOCKS_DIR / f"{block_id}.json"
    if not src.exists():
        raise FileNotFoundError(f"Block not found: {src}")
    old = _load_json(src)

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_block = dict(old)
    new_block["id"] = f"{block_id}_v{int(time.time())}"
    if new_content is not None:
        new_block["content"] = new_content
    meta = new_block.setdefault("meta", {})
    meta["prev_id"] = block_id
    if status:
        if status not in essential_status:
            raise ValueError(f"invalid status: {status}")
        meta["status"] = status
    if reason:
        meta["change_reason"] = reason
    meta.setdefault("provenance", "edit")
    new_block["timestamp"] = ts

    new_block = _sign(new_block)
    dst = BLOCKS_DIR / f"{new_block['id']}.json"
    _write_json(dst, new_block)
    return {"ok": True, "new_id": new_block["id"], "prev_id": block_id, "path": str(dst)}


def archive_block(block_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    return edit_block(block_id, status="archived", reason=reason or "archived")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: edit_block.py <block_id> <status|update> [value_or_reason]")
        sys.exit(2)
    bid = sys.argv[1]
    mode = sys.argv[2]
    if mode == "update":
        content = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(edit_block(bid, new_content=content, status="updated"), ensure_ascii=False))
    elif mode in essential_status:
        reason = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(edit_block(bid, status=mode, reason=reason), ensure_ascii=False))
    else:
        print("invalid mode")
        sys.exit(2)
