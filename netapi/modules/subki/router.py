from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

router = APIRouter(prefix="/api/subki", tags=["subki"])

BASE_DIR = Path(__file__).resolve().parents[3]
SUBKI_ROOT = BASE_DIR / "memory" / "subki"
REG_DIR = SUBKI_ROOT / "registrations"
PROP_DIR = SUBKI_ROOT / "proposals"
INBOX_DIR = SUBKI_ROOT  # each subki_id has /inbox under its own dir
TRUST_PATH = SUBKI_ROOT / "trust.json"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
for p in [REG_DIR, PROP_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# Runtime settings for active_subkis
RUNTIME_SETTINGS = BASE_DIR / "runtime" / "settings.json"

def _load_active_subkis() -> Optional[set[str]]:
    try:
        if not RUNTIME_SETTINGS.exists():
            return None
        obj = json.loads(RUNTIME_SETTINGS.read_text(encoding="utf-8")) or {}
        arr = obj.get("active_subkis")
        if isinstance(arr, list) and len(arr) > 0:
            return {str(x) for x in arr}
    except Exception:
        return None
    return None

def _audit_subki(event: Dict[str, Any]) -> None:
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        logdir = root / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "subki_audit.jsonl").open("a", encoding="utf-8").write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

def verify_ed25519_block(block: Dict[str, Any]) -> bool:
    try:
        sig_hex = block["signature"]
        pub_hex = block["pubkey"]
        sig = bytes.fromhex(sig_hex)
        pub = bytes.fromhex(pub_hex)
        verify_key = VerifyKey(pub)
        # canonical json without signature/pubkey
        b2 = dict(block)
        b2.pop("signature", None)
        b2.pop("pubkey", None)
        canonical = json.dumps(b2, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        verify_key.verify(canonical, sig)
        return True
    except (BadSignatureError, KeyError, ValueError):
        return False

@router.post("/register")
async def register(meta: Dict[str, Any]):
    subki_id = (meta.get("subki_id") or "").strip()
    owner = (meta.get("owner") or "").strip()
    if not subki_id or not owner:
        raise HTTPException(400, "missing subki_id or owner")
    f = REG_DIR / f"{subki_id}.json"
    reg = {
        "subki_id": subki_id,
        "owner": owner,
        "persona_name": meta.get("persona_name") or "",
        "public_key": meta.get("public_key") or "",
        "capabilities": meta.get("capabilities") or [],
    }
    f.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}

@router.get("/status")
async def status():
    regs = [p.stem for p in REG_DIR.glob("*.json")]
    return {"ok": True, "registered": regs}

@router.post("/sync")
async def sync(payload: Dict[str, Any]):
    meta = payload.get("meta") or {}
    blocks = payload.get("blocks") or []
    if not isinstance(blocks, list):
        raise HTTPException(400, "blocks must be a list")
    # Persist raw proposals for audit
    node_id = (meta.get("subki_id") or "unknown").strip() or "unknown"
    node_dir = SUBKI_ROOT / node_id / "proposals"
    node_dir.mkdir(parents=True, exist_ok=True)
    accepted: List[Dict[str, Any]] = []
    dropped_inactive = 0
    active = _load_active_subkis()
    for b in blocks:
        try:
            if not verify_ed25519_block(b):
                raise HTTPException(status_code=403, detail="Invalid signature")
            else:
                # attach minimal meta for consensus
                prop = {
                    "title": b.get("title"),
                    "content": b.get("content"),
                    "topic": b.get("tags", ["misc"])[0] if b.get("tags") else (b.get("title") or "misc"),
                    "tags": b.get("tags") or [],
                    "timestamp": b.get("ts") or b.get("timestamp"),
                    "source": b.get("source") or f"subki:{node_id}",
                    "node_id": node_id,
                    "meta": {
                        "confidence": float(b.get("confidence", 0.75)),
                        "role_prompt": meta.get("role_prompt") or "",
                        "reflection": b.get("reflection") or "",
                    },
                }
                # write proposal copy
                (node_dir / f"{b.get('hash','nohash')}.json").write_text(
                    json.dumps(prop, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                # Filter by active_subkis if configured
                if active is not None and node_id not in active:
                    dropped_inactive += 1
                    _audit_subki({"ts": int(__import__('time').time()), "type": "dropped_inactive", "node_id": node_id, "title": prop.get("title")})
                else:
                    accepted.append(prop)
        except Exception:
            continue
    # Run consensus merge
    try:
        from ....system import consensus_merge as cm
        res = cm.consensus_merge(accepted, dry_run=False)
    except Exception as e:
        raise HTTPException(500, f"consensus error: {e}")
    return {"ok": True, "accepted": len(accepted), "dropped_inactive": dropped_inactive, "consensus": res}


@router.post("/feedback")
async def feedback(payload: Dict[str, Any]):
    """Feedback endpoint for Sub‑KIs.

    Supports two shapes:
      1) Trust update (existing): {"subki_id":"node-1", "trust":0.9} or {"subki_id":"node-1", "delta":+0.05}
      2) Block feedback (new): {"block_id":"...", "status":"accepted|rejected|error|ok", "cid":"..."}

    Returns trust map for (1), or {ok:true} for (2) and appends an audit log line.
    """
    # Shape 2: block feedback audit
    if payload.get("block_id") and payload.get("status") is not None:
        try:
            bid = str(payload.get("block_id") or "").strip()
            status = str(payload.get("status") or "").strip().lower()
            cid = str(payload.get("cid") or "").strip()
            # Write audit record
            root = Path(__file__).resolve().parents[3]
            logdir = root / "logs"
            logdir.mkdir(parents=True, exist_ok=True)
            rec = {
                "ts": int(__import__("time").time()),
                "type": "subki_block_feedback",
                "block_id": bid,
                "status": status,
                "cid": cid,
            }
            (logdir / "subki_feedback.jsonl").open("a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, f"audit_error: {e}")

    # Shape 1: trust update
    sid = (payload.get("subki_id") or "").strip()
    if not sid:
        raise HTTPException(400, "missing subki_id")
    trust_map: Dict[str, float] = {}
    try:
        if TRUST_PATH.exists():
            trust_map = json.loads(TRUST_PATH.read_text(encoding="utf-8"))
            if not isinstance(trust_map, dict):
                trust_map = {}
    except Exception:
        trust_map = {}
    val = payload.get("trust")
    delta = payload.get("delta")
    if val is not None:
        try:
            v = float(val)
        except Exception:
            raise HTTPException(400, "invalid trust value")
    else:
        v = float(trust_map.get(sid, 0.8))
        if delta is None:
            raise HTTPException(400, "provide trust or delta")
        try:
            v = v + float(delta)
        except Exception:
            raise HTTPException(400, "invalid delta value")
    # clamp and persist
    if v < 0.0:
        v = 0.0
    if v > 1.0:
        v = 1.0
    trust_map[sid] = v
    try:
        TRUST_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRUST_PATH.write_text(json.dumps(trust_map, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"persist_error: {e}")
    return {"ok": True, "trust": trust_map}


@router.get("/trust")
async def get_trust():
    """Return current trust map for Sub-KIs."""
    try:
        if TRUST_PATH.exists():
            trust_map = json.loads(TRUST_PATH.read_text(encoding="utf-8"))
            if not isinstance(trust_map, dict):
                trust_map = {}
        else:
            trust_map = {}
        return {"ok": True, "trust": trust_map}
    except Exception as e:
        raise HTTPException(500, f"read_error: {e}")


@router.get("/summary")
async def subki_summary():
    """Summarize trust and acceptance metrics per Sub‑KI.
    accepted_blocks is counted from stored blocks with provenance_aux.node_id.
    rejected_blocks is approximated by proposals_total - accepted.
    """
    try:
        # load trust map
        trust: Dict[str, float] = {}
        if TRUST_PATH.exists():
            trust = json.loads(TRUST_PATH.read_text(encoding="utf-8")) or {}
            if not isinstance(trust, dict):
                trust = {}
        # discover nodes
        node_ids = set(trust.keys())
        for p in SUBKI_ROOT.iterdir():
            if p.is_dir():
                node_ids.add(p.name)
        # pre-scan accepted by node from blocks
        accepted_by_node: Dict[str, int] = {}
        if BLOCKS_DIR.exists():
            for bp in BLOCKS_DIR.glob("*.json"):
                try:
                    b = json.loads(bp.read_text(encoding="utf-8"))
                    aux = (b.get("meta") or {}).get("provenance_aux") or {}
                    nid = str(aux.get("node_id") or "")
                    if nid:
                        accepted_by_node[nid] = accepted_by_node.get(nid, 0) + 1
                except Exception:
                    continue
        # proposals count per node
        proposals_total: Dict[str, int] = {}
        for nid in node_ids:
            pdir = SUBKI_ROOT / nid / "proposals"
            if pdir.exists():
                proposals_total[nid] = len(list(pdir.glob("*.json")))
            else:
                proposals_total[nid] = 0
        # active set from settings (optional)
        active_set = _load_active_subkis() or set()
        # build result list
        items: List[Dict[str, Any]] = []
        for nid in sorted(node_ids):
            acc = int(accepted_by_node.get(nid, 0))
            tot = int(proposals_total.get(nid, 0))
            rej = max(0, tot - acc)
            items.append({
                "subki_id": nid,
                "trust": float(trust.get(nid, 0.8)),
                "accepted_blocks": acc,
                "rejected_blocks": rej,
                "active": (nid in active_set) if active_set else True,
            })
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(500, f"summary_error: {e}")


@router.get("/ui/trust_dashboard", response_class=HTMLResponse)
async def trust_dashboard():
    """Simple HTML dashboard summarizing trust and acceptance metrics."""
    try:
        data = await subki_summary()  # type: ignore
        items = data.get("items") or []
        rows = []
        for it in items:
            mark = "<span class='pill' style='background:#e6ffe6;color:#1a4'>aktiv</span>" if it.get('active') else "<span class='pill muted'>inaktiv</span>"
            rows.append(
                f"<tr><td>{it['subki_id']} {mark}</td><td>{it['trust']:.2f}</td><td>{it['accepted_blocks']}</td><td>{it['rejected_blocks']}</td></tr>"
            )
        html = """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<link rel='stylesheet' href='/static/styles.css'><title>Trust Dashboard</title>
</head><body class='page'>
<div id='nav' data-src='/static/nav.html'></div>
<main class='container'>
  <section class='card'>
    <h2>Trust‑Dashboard</h2>
    <p class='small'>Übersicht je Sub‑KI: Trust, angenommene und abgelehnte Blöcke.</p>
    <div class='table-wrap'>
      <table class='table'>
        <thead><tr><th>Sub‑KI</th><th>Trust</th><th>Angenommen</th><th>Abgelehnt</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p><a class='btn' href='/static/papa.html'>Zurück</a></p>
  </section>
</main>
<script defer src='/static/nav.js'></script>
</body></html>
""".replace("{rows}", "".join(rows))
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(500, f"dashboard_error: {e}")


@router.post("/broadcast")
async def broadcast(payload: Dict[str, Any]):
    """Receive a broadcast block from a Sub‑KI and store in its inbox.
    Body: { "subki_id": "node-1", "block": {..} }
    Writes to memory/subki/<id>/inbox/<ts>_<id>.json
    """
    sid = (payload.get("subki_id") or "").strip()
    block = payload.get("block") or {}
    if not sid or not isinstance(block, dict):
        raise HTTPException(400, "missing subki_id or block")
    try:
        import time, json
        node_dir = SUBKI_ROOT / sid
        inbox = node_dir / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        bid = str(block.get("id") or f"noid_{int(time.time())}")
        path = inbox / f"{int(time.time())}_{bid}.json"
        path.write_text(json.dumps(block, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "saved": str(path)}
    except Exception as e:
        raise HTTPException(500, f"broadcast_error: {e}")


@router.get("/ui/broadcasts", response_class=HTMLResponse)
async def ui_broadcasts():
    """List all inbox items grouped by Sub‑KI id."""
    try:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        if SUBKI_ROOT.exists():
            for node in SUBKI_ROOT.iterdir():
                if not node.is_dir():
                    continue
                inbox = node / "inbox"
                items: List[Dict[str, Any]] = []
                for p in sorted(inbox.glob("*.json")) if inbox.exists() else []:
                    try:
                        b = json.loads(p.read_text(encoding="utf-8"))
                        items.append({"file": p.name, "id": b.get("id"), "title": b.get("title"), "topic": b.get("topic")})
                    except Exception:
                        continue
                if items:
                    groups[node.name] = items
        # render HTML
        sections = []
        for nid, items in groups.items():
            lis = "".join([f"<li><code>{i['file']}</code> — <strong>{(i.get('title') or i.get('id') or '')}</strong> <em>{i.get('topic') or ''}</em></li>" for i in items])
            sections.append(f"<section class='card'><h3>Sub‑KI: {nid}</h3><ul>{lis}</ul></section>")
        inner = "".join(sections) or "<section class='card'><p class='small'>Keine Broadcasts verfügbar.</p></section>"
        html = f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<link rel='stylesheet' href='/static/styles.css'><title>Sub‑KI Broadcasts</title>
</head><body class='page'>
<div id='nav' data-src='/static/nav.html'></div>
<main class='container'>
  <h2>🔄 Sub‑KI Broadcasts</h2>
  {inner}
  <p><a class='btn' href='/static/papa.html'>Zurück</a></p>
</main>
<script defer src='/static/nav.js'></script>
</body></html>
"""
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(500, f"ui_broadcasts_error: {e}")
