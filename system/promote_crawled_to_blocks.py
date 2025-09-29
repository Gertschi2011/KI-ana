#!/usr/bin/env python3
import json, sys, hashlib, argparse, time
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, List

BASE_DIR = Path.home() / "ki_ana"
MEM_LONG = BASE_DIR / "memory" / "long_term"
BLOCKS_DIR = MEM_LONG / "blocks"
SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"


def _canonical(obj: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(obj)
    for k in ("hash", "hash_stored", "hash_calc"):
        data.pop(k, None)
    return data


def _calc_sha256(obj: Dict[str, Any]) -> str:
    raw = json.dumps(_canonical(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _infer_title(payload: Dict[str, Any]) -> str:
    title = payload.get("title") or payload.get("topic") or ""
    if title:
        return str(title)
    # Fallback: first line of content
    content = str(payload.get("content") or "").strip()
    if content:
        first = content.splitlines()[0][:120].strip()
        return first
    return "Web-Crawl"


def _block_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = str(payload.get("source") or "")
    ts = payload.get("timestamp") or payload.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    content = str(payload.get("content") or "").strip()
    title = _infer_title(payload)
    # Stable id: prefer given id else hash of source or content
    if payload.get("id"):
        bid = str(payload.get("id"))
    elif source:
        bid = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    else:
        bid = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    tags: List[str] = []
    # add source domain and crawler tag
    if source:
        try:
            dom = urlparse(source).netloc
            if dom:
                tags.append(f"domain:{dom}")
        except Exception:
            pass
    tags.append("crawler:true")

    # canonical content hash preference: provided by crawler or fallback to content hash
    canonical_hash = str(payload.get("content_sha256") or hashlib.sha256(content.encode("utf-8")).hexdigest())

    block = {
        "id": bid,
        "title": title,
        "topic": payload.get("topic") or title,
        "content": content,
        "source": source,
        "timestamp": ts,
        "meta": {
            "author": payload.get("author") or "",
            # simplified provenance marker for downstream consumers
            "provenance": "crawler",
            # allow verifying the content identity independent of block file hashing
            "canonical_hash": canonical_hash,
            # keep original type/source as auxiliary fields
            "provenance_aux": {
                "type": payload.get("type") or "web_crawl",
                "source": source,
            },
            "tags": payload.get("tags") or [],
            # reflection field for self-assessment (e.g., "veraltet", "widersprüchlich", "nicht belegt")
            "reflection": (payload.get("reflection") or "").strip(),
            # versioning fields may be added later in promote(): predecessor_id, version
        },
        "tags": tags,
    }
    block["hash"] = _calc_sha256(block)
    return block


def promote(dry_run: bool = False, limit: int = 100) -> Dict[str, Any]:
    count_in, count_out, skipped = 0, 0, 0
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(MEM_LONG.glob("*.json"))
    for p in files[:limit]:
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            count_in += 1
            block = _block_from_payload(payload)

            # Versioning: find previous block by same topic (exact match)
            try:
                prev = None
                prev_path = None
                topic = str(block.get("topic") or "").strip()
                if topic:
                    # scan existing blocks for same topic, prefer most recent timestamp
                    candidates = []
                    for q in BLOCKS_DIR.glob("*.json"):
                        try:
                            obj = json.loads(q.read_text(encoding="utf-8"))
                            if str(obj.get("topic") or "").strip() == topic and obj.get("id") != block.get("id"):
                                candidates.append((int(obj.get("timestamp", 0)) if isinstance(obj.get("timestamp"), int) else 0, q, obj))
                        except Exception:
                            continue
                    if candidates:
                        candidates.sort(key=lambda x: x[0], reverse=True)
                        _ts, prev_path, prev = candidates[0]
                if prev and prev_path:
                    # set predecessor/version in new block
                    meta = block.setdefault("meta", {})
                    meta["predecessor_id"] = prev.get("id")
                    prev_ver = 0
                    try:
                        prev_ver = int(prev.get("meta", {}).get("version", 0))
                    except Exception:
                        prev_ver = 0
                    meta["version"] = max(1, prev_ver + 1)

                    # archive previous block and point to successor
                    pmeta = prev.setdefault("meta", {})
                    pmeta["archived"] = True
                    pmeta["archived_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    pmeta["archived_reason"] = "superseded"
                    pmeta["successor_id"] = block.get("id")
                    # recalc hash, resign previous and validate+store
                    prev["hash"] = _calc_sha256(prev)
                    try:
                        from importlib.machinery import SourceFileLoader as _Loader
                        if SIGNER_PATH.exists():
                            _mod_prev = _Loader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
                            sig_p, pub_p, ts_p = _mod_prev.sign_block(prev)  # type: ignore
                            prev["signature"], prev["pubkey"], prev["signed_at"] = sig_p, pub_p, ts_p
                        # validate and store archived previous
                        _utils = _Loader("block_utils", str(BASE_DIR / "system" / "block_utils.py")).load_module()  # type: ignore
                        _ = _utils.validate_and_store_block(prev, overwrite=True)  # type: ignore
                    except Exception:
                        # fallback to direct write
                        if not dry_run:
                            prev_path.write_text(json.dumps(prev, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            except Exception:
                pass

            # Ethics check & annotate before signing
            try:
                from importlib.machinery import SourceFileLoader as _Loader
                _eguard_path = BASE_DIR / "system" / "ethical_guard.py"
                if _eguard_path.exists():
                    _eguard = _Loader("ethical_guard", str(_eguard_path)).load_module()  # type: ignore
                    assess = _eguard.check_block(block)  # type: ignore
                    meta = block.setdefault("meta", {})
                    meta["ethics"] = assess
                    # Set reflection label if suggested and not already present
                    if assess.get("reflection") and not (meta.get("reflection") or "").strip():
                        meta["reflection"] = assess.get("reflection")
            except Exception:
                pass

            # Sign block (optional, graceful fallback) AFTER versioning & ethics
            try:
                from importlib.machinery import SourceFileLoader as _Loader
                if SIGNER_PATH.exists():
                    _mod = _Loader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
                    sig, pub, ts_iso = _mod.sign_block(block)  # type: ignore
                    block["signature"], block["pubkey"], block["signed_at"] = sig, pub, ts_iso
            except Exception:
                pass
            # Validate and store new block
            try:
                from importlib.machinery import SourceFileLoader as _Loader
                _utils = _Loader("block_utils", str(BASE_DIR / "system" / "block_utils.py")).load_module()  # type: ignore
                res_store = _utils.validate_and_store_block(block)  # type: ignore
                if res_store.get("dedup"):
                    skipped += 1
                    continue
            except Exception:
                # fallback to legacy write
                out = BLOCKS_DIR / f"{block['id']}.json"
                if not dry_run:
                    out.write_text(json.dumps(block, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            count_out += 1
        except Exception:
            skipped += 1
            continue
    return {"ok": True, "in": count_in, "out": count_out, "skipped": skipped, "blocks_dir": str(BLOCKS_DIR)}


def main():
    ap = argparse.ArgumentParser(description="Promote crawled notes to canonical blocks")
    ap.add_argument("--dry-run", action="store_true", help="Don't write files, just report")
    ap.add_argument("--limit", type=int, default=100, help="Max files to process")
    args = ap.parse_args()
    res = promote(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
