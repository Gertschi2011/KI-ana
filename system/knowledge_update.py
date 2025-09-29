#!/usr/bin/env python3
from __future__ import annotations
import json, time
from typing import List, Dict, Any, Optional
from pathlib import Path
from importlib.machinery import SourceFileLoader

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"


def _load_blocks_by_topic(topic: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in (BLOCKS_DIR.glob("*.json")):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(b.get("topic") or "").lower().startswith(topic.lower()):
            out.append(b)
    return sorted(out, key=lambda x: x.get("timestamp", ""), reverse=True)


def _sign(block: Dict[str, Any]) -> Dict[str, Any]:
    mod = SourceFileLoader("block_signer", str(BASE_DIR / "system" / "block_signer.py")).load_module()  # type: ignore
    sig, pub, ts = mod.sign_block(block)  # type: ignore
    block["signature"], block["pubkey"], block["signed_at"] = sig, pub, ts
    return block


def propose_updates(topic: str, max_sources: int = 3) -> Dict[str, Any]:
    # identify latest block timestamp for topic
    existing = _load_blocks_by_topic(topic)
    since = None
    if existing:
        since = existing[0].get("timestamp")
    # fetch trusted sources via web_crawler
    crawler = SourceFileLoader("web_crawler", str(BASE_DIR / "system" / "web_crawler.py")).load_module()  # type: ignore
    trusted = [
        "https://en.wikipedia.org/wiki/{}".format(topic.replace(" ", "_")),
        "https://www.nature.com/search?q={}".format(topic),
        "https://www.bbc.co.uk/search?q={}".format(topic),
        "https://www.who.int/search?query={}".format(topic),
    ]
    results: List[Dict[str, Any]] = []
    for url in trusted[:max_sources]:
        try:
            r = crawler.fetch_url(url, allow_cache=True)  # type: ignore
            if not r or not r.get("ok"):
                continue
            text = r.get("text") or r.get("content") or ""
            results.append({"url": url, "len": len(text)})
        except Exception:
            continue
    # propose block
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    content = f"Update-Vorschlag für Thema '{topic}' basierend auf {len(results)} Quellen seit {since or 'unbekannt'}"
    upd = {
        "id": f"update_proposal_{int(time.time())}",
        "title": f"Update-Vorschlag: {topic}",
        "topic": topic,
        "content": content,
        "source": "knowledge_update",
        "timestamp": now,
        "tags": ["update", "proposal"],
        "meta": {
            "provenance": "auto_update",
            "sources": results,
            "since": since,
        },
    }
    upd = _sign(upd)
    (BLOCKS_DIR / f"{upd['id']}.json").write_text(json.dumps(upd, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"ok": True, "proposal_id": upd["id"], "sources": results}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: knowledge_update.py <topic> [max_sources]")
        sys.exit(2)
    topic = sys.argv[1]
    mx = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    print(json.dumps(propose_updates(topic, mx), ensure_ascii=False))
