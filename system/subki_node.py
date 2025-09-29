#!/usr/bin/env python3
from __future__ import annotations
import os, json, socket, hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

BASE_DIR = Path.home() / "ki_ana"
NODE_DIR = BASE_DIR / "memory" / "subki"

SUBKI_ID = os.getenv("SUBKI_ID") or socket.gethostname()
ROLE_PROMPT = (
    "Du bist eine Sub-KI von KI_ana. Lerne von deinem Nutzer, aber gib Wissen nur weiter, wenn du sicher bist. "
    "Bewerte jeden Vorschlag mit einem 'confidence' Wert zwischen 0 und 1."
)

app = FastAPI(title=f"KI_ana Sub-KI Node ({SUBKI_ID})")


def _ensure_dirs():
    (NODE_DIR / SUBKI_ID / "proposals").mkdir(parents=True, exist_ok=True)


def _save_proposal(p: Dict[str, Any]) -> str:
    _ensure_dirs()
    content = (p.get("content") or "").strip()
    title = (p.get("title") or "").strip() or (content.splitlines()[0][:80] if content else "Untitled")
    pid = hashlib.sha256((title + "\n" + content).encode("utf-8")).hexdigest()[:16]
    rec = {
        "id": pid,
        "node_id": SUBKI_ID,
        "title": title,
        "topic": p.get("topic") or title,
        "content": content,
        "tags": p.get("tags") or [],
        "source": p.get("source") or "local:user",
        "timestamp": int(os.environ.get("EPOCH_TS", "0")) or __import__("time").time(),
        "meta": {
            "role_prompt": ROLE_PROMPT,
            "confidence": float(p.get("confidence") or 0.5),
            "reflection": (p.get("reflection") or "").strip(),
            "provenance": "subki",
        }
    }
    out = NODE_DIR / SUBKI_ID / "proposals" / f"{pid}.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return pid


@app.post("/subki/learn")
async def learn(proposal: Dict[str, Any]):
    if not isinstance(proposal, dict):
        raise HTTPException(400, "invalid body")
    if not (proposal.get("content") or "").strip():
        raise HTTPException(400, "missing content")
    pid = _save_proposal(proposal)
    return JSONResponse({"ok": True, "proposal_id": pid, "node_id": SUBKI_ID})


@app.get("/subki/export")
async def export_proposals():
    _ensure_dirs()
    items: List[dict] = []
    for p in (NODE_DIR / SUBKI_ID / "proposals").glob("*.json"):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return JSONResponse({"ok": True, "node_id": SUBKI_ID, "count": len(items), "proposals": items})


@app.post("/subki/clear_export")
async def clear_export():
    _ensure_dirs()
    n = 0
    for p in (NODE_DIR / SUBKI_ID / "proposals").glob("*.json"):
        try:
            p.unlink()
            n += 1
        except Exception:
            continue
    return JSONResponse({"ok": True, "deleted": n})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8123)))
