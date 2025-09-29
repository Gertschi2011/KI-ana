from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, AsyncGenerator, List
from pathlib import Path
import json, os, time

try:
    from sse_starlette.sse import EventSourceResponse  # type: ignore
except Exception:
    EventSourceResponse = None  # type: ignore

from ...agent.agent import run_agent, run_agent_stream
try:
    from ...agent.planner import deliberate_pipeline as _PLANNER
except Exception:
    _PLANNER = None  # type: ignore

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentChatIn(BaseModel):
    message: str
    persona: Optional[str] = "friendly"
    lang: Optional[str] = "de-DE"
    mode: Optional[str] = "auto"   # auto | research
    conv_id: Optional[str] = ""


from ...deps import get_current_user_required, require_role
from ...deps import is_kid as _is_kid

@router.post("/chat")
async def agent_chat(body: AgentChatIn, user = Depends(get_current_user_required)) -> Dict[str, Any]:
    # Papa+/Creator only
    require_role(user, {"papa", "creator"})
    # Kids rail: no agent access
    if _is_kid(user):
        raise HTTPException(403, "kids_restricted")
    # Prefer unified planner pipeline if available (deterministic, evidenzbasiert)
    if _PLANNER is not None:
        try:
            ans, srcs, plan_b, critic_b = _PLANNER(
                body.message,
                persona=(body.persona or "friendly"),
                lang=(body.lang or "de-DE"),
                style="balanced",
                bullets=5,
                logic="balanced",
                fmt="structured",
            )
            reply = ans.strip()
            # attach compact sources block
            if srcs:
                lines = [f"- {s.get('title') or 'Web'} ({s.get('url') or ''})" for s in srcs[:3]]
                reply = (reply + "\n\nQuellen:\n" + "\n".join(lines)).strip()
            extras = {}
            if plan_b: extras["plan"] = plan_b
            if critic_b: extras["critic"] = critic_b
            return {"ok": True, "reply": reply, "sources": srcs, **extras}
        except Exception:
            pass
    # Fallback: legacy agent
    res = run_agent(body.message, persona=(body.persona or "friendly"), lang=(body.lang or "de-DE"), conv_id=(body.conv_id or ""))
    out = {"ok": True, **res}
    try:
        txt = (out.get("reply") or "").strip()
        # Detect WEBMISS clarifier by substring to avoid tight coupling
        if "Hilft es, wenn ich gezielter suche?" in txt:
            out["quick_replies"] = [
                {"title": "Grundlagen", "text": "Grundlagen"},
                {"title": "Beispiele", "text": "Beispiele"},
                {"title": "Aktuelle Nachrichten", "text": "Aktuelle Nachrichten"},
            ]
    except Exception:
        pass
    return out


@router.get("/stream")
async def agent_stream(message: str, persona: str = "friendly", lang: str = "de-DE", conv_id: str = "", user = Depends(get_current_user_required)):
    # Papa+/Creator only
    require_role(user, {"papa", "creator"})
    # Kids rail: no agent access
    if _is_kid(user):
        raise HTTPException(403, "kids_restricted")
    if not message.strip():
        raise HTTPException(400, "empty message")
    async def gen() -> AsyncGenerator[dict, None]:
        async for ev in run_agent_stream(message, persona=persona, lang=lang, conv_id=conv_id):
            try:
                # If a WEBMISS clarifier line is emitted, follow with quick_replies hint event
                if isinstance(ev, dict) and isinstance(ev.get("delta"), str) and "Hilft es, wenn ich gezielter suche?" in ev.get("delta"):
                    yield {"data": __import__('json').dumps(ev)}
                    yield {"data": __import__('json').dumps({
                        "quick_replies": [
                            {"title": "Grundlagen", "text": "Grundlagen"},
                            {"title": "Beispiele", "text": "Beispiele"},
                            {"title": "Aktuelle Nachrichten", "text": "Aktuelle Nachrichten"},
                        ]
                    })}
                    continue
            except Exception:
                pass
            yield {"data": __import__('json').dumps(ev)}
    if EventSourceResponse is None:
        # fallback to non-stream
        res = run_agent(message, persona=persona, lang=lang, conv_id=conv_id)
        return {"delta": res.get("reply") or "", "done": True}
    return EventSourceResponse(gen(), ping=15)

# -----------------------------
# Tool Registry & Proposals
# -----------------------------
KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
TOOLS_PATH = KI_ROOT / "runtime" / "tools.json"
TOOLS_PATH.parent.mkdir(parents=True, exist_ok=True)

def _read_tools() -> List[Dict[str, Any]]:
    try:
        if TOOLS_PATH.exists():
            data = json.loads(TOOLS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def _write_tools(items: List[Dict[str, Any]]) -> None:
    try:
        TOOLS_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"persist tools failed: {e}")

class ToolIn(BaseModel):
    name: str
    description: Optional[str] = None
    endpoint: Optional[str] = None
    kind: Optional[str] = "http"  # http | python | device
    auth: Optional[Dict[str, Any]] = None  # e.g., {"type":"bearer","env":"API_KEY"}
    meta: Optional[Dict[str, Any]] = None

@router.get("/tools")
def list_tools():
    items = _read_tools()
    if not items:
        # Bootstrap defaults on first call
        defaults: List[Dict[str, Any]] = [
            {"name":"mem.search","description":"Volltextsuche in Blöcken","kind":"python"},
            {"name":"mem.add","description":"Text als Block speichern","kind":"python"},
            {"name":"mem.rate","description":"Block bewerten","kind":"python"},
            {"name":"net.search","description":"Websuche (Aggregator)","kind":"http"},
            {"name":"net.open","description":"Webseite abrufen","kind":"http"},
            {"name":"net.extract","description":"Kontext zusammenfassen","kind":"python"},
            {"name":"net.image.analyze","description":"Bildanalyse (Labels/OCR, stub)","kind":"http","endpoint":"/api/media/image/analyze"},
            {"name":"calc","description":"Rechnen/Einheiten","kind":"python"},
            {"name":"chart","description":"Daten zu Diagramm rendern","kind":"python"},
            {"name":"stt.recognize","description":"Sprache→Text","kind":"http","endpoint":"/api/stt/recognize"},
            {"name":"tts.speak","description":"Text→Sprache","kind":"http","endpoint":"/api/elevenlabs/speak"},
            {"name":"sys.audit","description":"Audit-Block schreiben","kind":"python"},
            {"name":"sys.shutdown","description":"Not-Aus","kind":"python"},
        ]
        now = int(time.time())
        for d in defaults:
            d.update({"created_at": now, "success_rate": 0.0, "uses": 0, "auth": {}, "meta": {}})
        _write_tools(defaults)
        items = defaults
    return {"ok": True, "items": items}

from ...deps import get_current_user_required, require_role  # after FastAPI router init
from ... import memory_store as _mem

@router.post("/tools/add")
def add_tool(tool: ToolIn, user = Depends(get_current_user_required)):
    # Admin/worker required
    require_role(user, {"admin", "worker", "creator"})
    items = _read_tools()
    if any((str(x.get("name")).lower()==tool.name.lower()) for x in items):
        raise HTTPException(409, "tool already exists")
    rec = {
        "name": tool.name.strip(),
        "description": (tool.description or "").strip(),
        "endpoint": (tool.endpoint or "").strip(),
        "kind": (tool.kind or "http").strip(),
        "auth": tool.auth or {},
        "meta": tool.meta or {},
        "created_at": int(time.time()),
        "success_rate": 0.0,
        "uses": 0,
    }
    items.append(rec)
    _write_tools(items)
    try:
        _mem.add_block(title=f"Tool registriert: {rec['name']}", content=json.dumps(rec, ensure_ascii=False), tags=["tool","registry"], url=None, meta={"event":"tool_add"})
    except Exception:
        pass
    return {"ok": True, "tool": rec}

class ToolProposalIn(BaseModel):
    name: str
    problem: str
    idea: Optional[str] = None
    expected_benefit: Optional[str] = None

@router.post("/tools/propose")
def propose_tool(p: ToolProposalIn, request: Request, user = Depends(get_current_user_required)):
    # Anyone logged in may propose; store as memory block for admin review
    meta = {
        "proposer": (user or {}).get("username") or (user or {}).get("email") or "user",
        "ip": request.client.host if request.client else None,
        "ts": int(time.time()),
    }
    content = f"Problem: {p.problem}\n\nIdee: {p.idea or ''}\n\nErwarteter Nutzen: {p.expected_benefit or ''}"
    bid = None
    try:
        bid = _mem.add_block(title=f"Tool‑Vorschlag: {p.name}", content=content, tags=["tool","proposal"], url=None, meta=meta)
    except Exception:
        bid = None
    return {"ok": True, "stored": bool(bid), "id": bid}

# -------- Proposals listing & approval --------
@router.get("/tools/proposals")
def list_tool_proposals(q: Optional[str] = None, limit: int = 100):
    try:
        from ...memory_store import search_blocks, get_block  # type: ignore
    except Exception:
        raise HTTPException(500, "memory unavailable")
    query = (q or "tool proposal").strip()
    hits = search_blocks(query, top_k=max(10, min(1000, limit)), min_score=0.0) or []
    items: List[Dict[str, Any]] = []
    for bid, _score in hits:
        b = get_block(bid)
        if not b: continue
        tags = [str(t).lower() for t in (b.get("tags") or [])]
        if not ("tool" in tags and "proposal" in tags):
            continue
        items.append({"id": bid, "title": b.get("title"), "tags": b.get("tags"), "ts": b.get("ts") or b.get("timestamp")})
    return {"ok": True, "items": items}

@router.post("/tools/approve")
def approve_tool(id: str, description: Optional[str] = None, endpoint: Optional[str] = None, kind: Optional[str] = None, user = Depends(get_current_user_required)):
    # Admin/worker required
    require_role(user, {"admin", "worker", "creator"})
    try:
        from ...memory_store import get_block  # type: ignore
    except Exception:
        raise HTTPException(500, "memory unavailable")
    b = get_block(id)
    if not b:
        raise HTTPException(404, "proposal not found")
    title = str(b.get("title") or "").strip()
    name = title.replace("Tool‑Vorschlag:", "").replace("Tool-Vorschlag:", "").strip()
    if not name:
        raise HTTPException(400, "cannot parse tool name from title")
    tool = ToolIn(name=name, description=description or b.get("content",""), endpoint=endpoint, kind=(kind or "http"))
    return add_tool(tool, user)

# -------- Bootstrap micro-tool from template --------
class BootstrapIn(BaseModel):
    name: str
    kind: Optional[str] = "python"  # python | http
    description: Optional[str] = None
    from_proposal_id: Optional[str] = None

@router.post("/tools/bootstrap")
def bootstrap_tool(body: BootstrapIn, user = Depends(get_current_user_required)):
    require_role(user, {"admin", "papa", "creator"})
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    # Write source files under KI_ROOT/runtime/tools_src/<name>/
    try:
        from pathlib import Path
        import json as _json
        KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
        base = (KI_ROOT / "runtime" / "tools_src" / name).resolve()
        base.mkdir(parents=True, exist_ok=True)
        readme = base / "README.md"
        readme.write_text(f"# {name}\n\nBootstrap micro-tool ({body.kind}).\n", encoding="utf-8")
        if (body.kind or "python").lower() == "python":
            mod = base / f"tool_{name}.py"
            mod.write_text(
                """
def handle(args: dict) -> dict:
    # Example python micro-tool handler. Args in, dict out.
    x = args.get('x'); y = args.get('y')
    try:
        s = float(x) + float(y)
    except Exception:
        return {"ok": False, "error": "bad args"}
    return {"ok": True, "sum": s}
""".lstrip(), encoding="utf-8")
            entry = {"name": name, "description": body.description or "Python micro-tool", "endpoint": None, "kind": "python", "auth": {}, "meta": {"src": str(base)}}
        else:
            app = base / "app.py"
            app.write_text(
                """
from fastapi import FastAPI
app = FastAPI()

@app.post("/run")
def run(body: dict):
    # Echo example
    return {"ok": True, "echo": body}
""".lstrip(), encoding="utf-8")
            entry = {"name": name, "description": body.description or "HTTP micro-tool", "endpoint": f"/ext/{name}", "kind": "http", "auth": {}, "meta": {"src": str(base)}}
        # Register into tools.json
        items = _read_tools()
        if any((str(x.get("name")).lower()==name.lower()) for x in items):
            raise HTTPException(409, "tool already exists")
        items.append({"created_at": int(time.time()), "success_rate": 0.0, "uses": 0, **entry})
        _write_tools(items)
        # Audit
        try:
            meta = {"by": user.get("username") or user.get("email") or str(user.get("id")), "ts": int(time.time()), "kind": body.kind}
            _mem.add_block(title=f"Tool‑Bootstrap: {name}", content=_json.dumps(entry, ensure_ascii=False), tags=["tool","bootstrapped"], url=None, meta=meta)
        except Exception:
            pass
        return {"ok": True, "tool": entry}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"bootstrap failed: {e}")

# -------- Aggregation from tool_usage blocks --------
@router.post("/tools/aggregate")
def aggregate_tools(user = Depends(get_current_user_required)):
    require_role(user, {"admin", "worker", "creator"})
    items = _read_tools()
    idx = {str(x.get("name")).lower(): x for x in items}
    # scan memory for tool_usage blocks
    try:
        from ...memory_store import search_blocks, get_block  # type: ignore
        hits = search_blocks("tool_usage", top_k=1000, min_score=0.0) or []
        counts: Dict[str, Dict[str, int]] = {}
        for bid, _ in hits:
            b = get_block(bid)
            if not b: continue
            tags = [str(t).lower() for t in (b.get("tags") or [])]
            if "tool_usage" not in tags: continue
            text = str(b.get("content") or "")
            for line in text.splitlines():
                line = line.strip().lstrip("• ")
                if not line or ":" not in line: continue
                tool, status = line.split(":", 1)
                tool = tool.strip().lower(); status = status.strip().lower()
                rec = counts.setdefault(tool, {"ok":0, "fail":0})
                if status.startswith("ok"): rec["ok"] += 1
                else: rec["fail"] += 1
        # update registry with usage success
        for tname, c in counts.items():
            rec = idx.get(tname)
            if not rec:
                rec = {"name": tname, "description": "", "endpoint": "", "kind": "python", "auth": {}, "meta": {}, "created_at": int(time.time())}
                items.append(rec); idx[tname] = rec
            uses = int(c.get("ok",0) + c.get("fail",0))
            succ = (float(c.get("ok",0)) / max(1, uses))
            rec["uses"] = uses
            rec["success_rate"] = round(succ, 4)
        # include tool_feedback blocks (user ratings) into registry
        fb_hits = search_blocks("tool_feedback", top_k=2000, min_score=0.0) or []
        fb_pos: Dict[str, int] = {}
        fb_tot: Dict[str, int] = {}
        for bid, _ in fb_hits:
            b = get_block(bid)
            if not b: continue
            try:
                meta = b.get("meta") or {}
                tool = str(meta.get("tool") or "").lower().strip()
                delta = int(meta.get("delta") or 0)
                if not tool: continue
                fb_tot[tool] = fb_tot.get(tool, 0) + 1
                if delta > 0:
                    fb_pos[tool] = fb_pos.get(tool, 0) + 1
            except Exception:
                continue
        for tname, total in fb_tot.items():
            rec = idx.get(tname)
            if not rec:
                rec = {"name": tname, "description": "", "endpoint": "", "kind": "python", "auth": {}, "meta": {}, "created_at": int(time.time())}
                items.append(rec); idx[tname] = rec
            pos = float(fb_pos.get(tname, 0))
            rec["feedback_score"] = round(pos / max(1.0, float(total)), 4)
        _write_tools(items)
        return {"ok": True, "updated": len(counts)}
    except Exception as e:
        raise HTTPException(500, f"aggregate failed: {e}")

# -------- Reject proposal (mark) --------
@router.post("/tools/reject")
def reject_tool(id: str, reason: Optional[str] = None, user = Depends(get_current_user_required)):
    require_role(user, {"admin", "papa", "creator"})
    try:
        from ...memory_store import get_block, add_block  # type: ignore
        b = get_block(id)
        if not b:
            raise HTTPException(404, "proposal not found")
        meta = {"ts": int(time.time()), "action": "reject", "by": (user.get("username") or user.get("email") or str(user.get("id"))), "reason": reason or ""}
        add_block(title=f"Tool‑Vorschlag abgelehnt: {b.get('title','')} ", content=json.dumps({"proposal_id": id, "reason": reason or ""}, ensure_ascii=False), tags=["tool","proposal","rejected"], url=None, meta=meta)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"reject failed: {e}")

# -------- List recent tool usage blocks --------
@router.get("/tools/usage")
def list_tool_usage(limit: int = 100, user = Depends(get_current_user_required)):
    require_role(user, {"admin", "papa", "creator"})
    try:
        from ...memory_store import search_blocks, get_block  # type: ignore
        hits = search_blocks("tool_usage", top_k=max(10, min(2000, limit)), min_score=0.0) or []
        items: List[Dict[str, Any]] = []
        for bid, _ in hits:
            b = get_block(bid)
            if not b: continue
            tags = [str(t).lower() for t in (b.get("tags") or [])]
            if "tool_usage" not in tags: continue
            items.append({
                "id": bid,
                "title": b.get("title"),
                "content": b.get("content"),
                "tags": b.get("tags"),
                "ts": b.get("ts") or b.get("timestamp")
            })
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(500, f"list usage failed: {e}")

# -------- List risky prompt audits --------
@router.get("/tools/risky")
def list_risky_prompts(limit: int = 100, user = Depends(get_current_user_required)):
    require_role(user, {"admin", "papa", "creator"})
    try:
        from ...memory_store import search_blocks, get_block  # type: ignore
        hits = search_blocks("risky_prompt", top_k=max(10, min(2000, limit)), min_score=0.0) or []
        items: List[Dict[str, Any]] = []
        for bid, _ in hits:
            b = get_block(bid)
            if not b: continue
            tags = [str(t).lower() for t in (b.get("tags") or [])]
            if "risky_prompt" not in tags: continue
            items.append({
                "id": bid,
                "title": b.get("title"),
                "content": b.get("content"),
                "tags": b.get("tags"),
                "meta": b.get("meta"),
                "ts": b.get("ts") or b.get("timestamp")
            })
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(500, f"list risky failed: {e}")
