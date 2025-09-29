#!/usr/bin/env python3
from __future__ import annotations
import json, hashlib, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
SUBKI_DIR = BASE_DIR / "memory" / "subki"
SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"
UTILS_PATH = BASE_DIR / "system" / "block_utils.py"
TRUST_PATH = SUBKI_DIR / "trust.json"


def _calc_sha256(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _canonical_block_from_proposal(p: Dict[str, Any]) -> Dict[str, Any]:
    title = (p.get("title") or "").strip() or (str(p.get("topic") or "").strip() or "SubKI Vorschlag")
    content = (p.get("content") or "").strip()
    topic = (p.get("topic") or title).strip()
    ts = int(p.get("timestamp") or int(time.time()))
    source = p.get("source") or f"subki:{p.get('node_id','unknown')}"

    canonical_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    block = {
        "id": hashlib.sha256((topic + "\n" + title + "\n" + content).encode("utf-8")).hexdigest()[:16],
        "title": title,
        "topic": topic,
        "content": content,
        "source": source,
        "timestamp": ts,
        "meta": {
            "provenance": "subki",
            "canonical_hash": canonical_hash,
            "provenance_aux": {
                "node_id": p.get("node_id"),
                "confidence": float(p.get("meta", {}).get("confidence", p.get("confidence", 0.0))),
                "role_prompt": p.get("meta", {}).get("role_prompt") or p.get("role_prompt") or "",
            },
            "reflection": (p.get("meta", {}).get("reflection") or p.get("reflection") or "").strip(),
            "tags": list(set((p.get("tags") or []) + ["subki:true"]))
        },
        "tags": list(set((p.get("tags") or []) + ["subki:true"]))
    }
    # lightweight internal hash for quick compare
    block["hash"] = _calc_sha256({k: v for k, v in block.items() if k not in ("hash", "signature", "pubkey", "signed_at")})
    return block


def _sign_block(block: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from importlib.machinery import SourceFileLoader as _Loader
        if SIGNER_PATH.exists():
            _mod = _Loader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
            sig, pub, ts_iso = _mod.sign_block(block)  # type: ignore
            block["signature"], block["pubkey"], block["signed_at"] = sig, pub, ts_iso
    except Exception:
        pass
    return block


def _load_disk_proposals(limit_per_node: int = 200) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not SUBKI_DIR.exists():
        return out
    for node_dir in SUBKI_DIR.iterdir():
        if not node_dir.is_dir():
            continue
        prop_dir = node_dir / "proposals"
        if not prop_dir.exists():
            continue
        for p in list(sorted(prop_dir.glob("*.json"), reverse=True))[:limit_per_node]:
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
    return out


def consensus_merge(proposals: Optional[List[Dict[str, Any]]] = None,
                    min_confidence: float = 0.7,
                    dry_run: bool = False) -> Dict[str, Any]:
    """Selects confident, non-duplicate proposals and writes them as signed blocks.
    Strategy:
      - Filter by meta.confidence >= threshold
      - Group by topic; within group, prefer highest confidence and longest content
      - Deduplicate by canonical content hash
    Returns: { ok, selected: [ids], skipped: n, written: n }
    """
    props = proposals if isinstance(proposals, list) else _load_disk_proposals()
    if not props:
        return {"ok": True, "selected": [], "skipped": 0, "written": 0}

    # Load trust map
    trust: Dict[str, float] = {}
    try:
        if TRUST_PATH.exists():
            trust = json.loads(TRUST_PATH.read_text(encoding="utf-8"))
            if not isinstance(trust, dict):
                trust = {}
    except Exception:
        trust = {}

    def _trust_for(node_id: str) -> float:
        try:
            v = float(trust.get(node_id, 0.8))
            if v < 0.0:
                return 0.0
            if v > 1.0:
                return 1.0
            return v
        except Exception:
            return 0.8

    # Filter by effective confidence (confidence * trust)
    def _base_conf(p):
        m = p.get("meta") or {}
        return float(m.get("confidence", p.get("confidence", 0.0)))

    def _eff_conf(p):
        nid = str(p.get("node_id") or "unknown")
        return _base_conf(p) * _trust_for(nid)

    eligible = [p for p in props if _eff_conf(p) >= float(min_confidence)]
    if not eligible:
        return {"ok": True, "selected": [], "skipped": len(props), "written": 0}

    # Group by topic
    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for p in eligible:
        t = (p.get("topic") or p.get("title") or "").strip() or "misc"
        by_topic.setdefault(t, []).append(p)

    # Select best per topic
    selected: List[Dict[str, Any]] = []
    for t, lst in by_topic.items():
        lst.sort(key=lambda p: (_eff_conf(p), len((p.get("content") or ""))), reverse=True)
        best = lst[0]
        selected.append(best)

    # Dedup by content hash
    seen_content: set[str] = set()
    blocks: List[Dict[str, Any]] = []
    for p in selected:
        b = _canonical_block_from_proposal(p)
        ch = b.get("meta", {}).get("canonical_hash", "")
        if ch in seen_content:
            continue
        seen_content.add(ch)
        blocks.append(b)

    # Write and sign (with ethics annotation)
    written = 0
    ids: List[str] = []
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    for b in blocks:
        # ethics assessment
        try:
            from importlib.machinery import SourceFileLoader as _Loader
            _eguard_path = BASE_DIR / "system" / "ethical_guard.py"
            if _eguard_path.exists():
                _eguard = _Loader("ethical_guard", str(_eguard_path)).load_module()  # type: ignore
                assess = _eguard.check_block(b)  # type: ignore
                meta = b.setdefault("meta", {})
                meta["ethics"] = assess
                if assess.get("reflection") and not (meta.get("reflection") or "").strip():
                    meta["reflection"] = assess.get("reflection")
        except Exception:
            pass
        out = BLOCKS_DIR / f"{b['id']}.json"
        b = _sign_block(b)
        try:
            from importlib.machinery import SourceFileLoader as _Loader
            _utils = _Loader("block_utils", str(UTILS_PATH)).load_module()  # type: ignore
            res = _utils.validate_and_store_block(b)  # type: ignore
            if not res.get("ok"):
                continue
            written += 1
            ids.append(b["id"])
        except Exception:
            if not dry_run:
                out.write_text(json.dumps(b, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            written += 1
            ids.append(b["id"])

    return {"ok": True, "selected": ids, "skipped": len(props) - len(blocks), "written": written}
