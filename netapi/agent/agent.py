from __future__ import annotations
# -----------------------------
# Tool registry preference
# -----------------------------
def _tools_registry_path() -> Path:
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
    except Exception:
        root = Path.home() / "ki_ana"
    return (root / "runtime" / "tools.json").resolve()

def _load_tools_index() -> Dict[str, Dict[str, Any]]:
    p = _tools_registry_path()
    try:
        if p.exists():
            arr = json.loads(p.read_text(encoding="utf-8")) or []
            if isinstance(arr, list):
                return {str(x.get("name") or "").lower(): x for x in arr}
    except Exception:
        pass
    return {}

def _tool_good(name: str, idx: Optional[Dict[str, Dict[str, Any]]] = None, threshold: float = 0.6) -> bool:
    try:
        i = (idx or _load_tools_index()).get(str(name or "").lower()) or {}
        sr = float(i.get("success_rate") or 0.0)
        return sr >= float(threshold)
    except Exception:
        return False

def _recent_success_map(days: int = 7) -> Dict[str, float]:
    """Compute recent success rate per tool over the last N days from tool_usage blocks.
    Returns a mapping tool_name -> success_rate_recent (0..1).
    """
    try:
        lookback = max(1, int(days)) * 24 * 3600
        now = int(time.time())
        # Lazy import
        try:
            from netapi import memory_store as _mem  # type: ignore
        except Exception:
            return {}
        hits = _mem.search_blocks("tool_usage", top_k=2000, min_score=0.0) or []  # type: ignore
        okc: Dict[str, int] = {}
        tot: Dict[str, int] = {}
        for bid, _sc in hits:
            b = _mem.get_block(bid)
            if not b:
                continue
            meta = b.get("meta") or {}
            ts = int(meta.get("ts") or b.get("ts") or 0)
            if ts and (now - ts) > lookback:
                continue
            text = str(b.get("content") or "")
            for line in text.splitlines():
                s = line.strip().lstrip("• ")
                if ":" not in s:
                    continue
                tname, status = s.split(":", 1)
                tname = tname.strip().lower()
                status = status.strip().lower()
                tot[tname] = tot.get(tname, 0) + 1
                if status.startswith("ok"):
                    okc[tname] = okc.get(tname, 0) + 1
        out: Dict[str, float] = {}
        for k, v in tot.items():
            out[k] = float(okc.get(k, 0)) / max(1, int(v))
        return out
    except Exception:
        return {}

"""
Simple reasoning agent with a minimal toolset (memory search, web peek,
safe calc/convert) and a short reflective loop. Designed to be robust even
when optional deps are missing. Prefers local LLM (Ollama) if available;
otherwise, falls back to deterministic heuristics.

Public entrypoint: run_agent(message: str, *, persona: str, lang: str, conv_id: str)
Returns dict: { ok, reply, trace, sources, used_memory_ids, quick_replies, conv_id }
"""

import os
import re
import time
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
import random

# Optional local LLM
try:
    from netapi.core import llm_local  # type: ignore
except Exception:  # pragma: no cover
    llm_local = None  # type: ignore

# Memory store (lazy-safe)
try:
    from netapi.memory_store import search_blocks, get_block, add_block  # type: ignore
except Exception:  # pragma: no cover
    def search_blocks(query: str, top_k: int = 5, min_score: float = 0.12):  # type: ignore
        return []
    def get_block(bid: str):  # type: ignore
        return None
    def add_block(**kw):  # type: ignore
        return None

# Web QA (lazy-safe)
try:
    from netapi.web_qa import web_search_and_summarize  # type: ignore
except Exception:  # pragma: no cover
    def web_search_and_summarize(query: str, user_context: Optional[Dict[str, Any]] = None, max_results: int = 3):  # type: ignore
        return {"query": query, "allowed": False, "results": []}

# Memory bridge (importance heuristic)
try:
    from netapi.core.memory_bridge import process_and_store_memory  # type: ignore
except Exception:  # pragma: no cover
    def process_and_store_memory(input_text: str, lang: str = "de", auto_refine: bool = True):  # type: ignore
        return {"saved_block": None, "refined_block": None, "skipped": True}


# -----------------------------
# Utilities
# -----------------------------
def _short(text: str, n: int = 220) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    t = t[:n]
    cut = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
    return (t[:cut+1] if cut > 80 else t).rstrip() + " …"


def _style_for_persona(text: str, persona: str) -> str:
    """Very light post-processing for persona. For 'kids', keep it short and friendly."""
    try:
        p = (persona or '').lower()
        if p.startswith('kids') or p == 'kids':
            return _short(text or '', 400)
        return text
    except Exception:
        return text


_SAFE_EXPR = re.compile(r"^[0-9\s+\-*/().,]+$")
_UNIT_RX   = re.compile(r"(?P<val>\d+(?:[\.,]\d+)?)\s*(?P<u1>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\s*(?:in|zu|nach)\s*(?P<u2>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\b", re.I)

# Basic knowledge blocks for common queries
BASIC_KNOWLEDGE = {
    "erde": "Die Erde ist ein Gesteinsplanet mit Kruste, Mantel und Kern. Sie besteht vor allem aus Sauerstoff, Silizium, Magnesium und Eisen.",
    "sonne": "Die Sonne ist ein Stern im Zentrum unseres Sonnensystems. Sie besteht hauptsächlich aus Wasserstoff und Helium.",
    "mensch": "Der Mensch ist ein Säugetier aus der Familie der Hominiden. Er zeichnet sich durch Sprache, Kultur und Bewusstsein aus.",
    "mond": "Der Mond ist der einzige natürliche Satellit der Erde. Er ist ein felsiger, airloser Himmelskörper.",
    "erde-mond": "Die Erde und der Mond sind ein Doppelplanetensystem. Sie sind durch die Schwerkraft miteinander verbunden.",
    "erde-sonne": "Die Erde und die Sonne sind durch die Schwerkraft miteinander verbunden. Die Erde umkreist die Sonne in einem elliptischen Orbit.",
    "erde-mensch": "Die Erde ist der Heimatplanet des Menschen. Der Mensch lebt auf der Erde und nutzt ihre Ressourcen."
}

# Smalltalk detection and fallback phrase
SMALLTALK_FALLBACK = "Danke, dass du fragst 😊 Mir geht es gut – ich bin bereit, dir zu helfen. Und dir?"
CLARIFY_FALLBACK = (
    "Meinst du die Entstehungsgeschichte, die heutige Zusammensetzung oder die Struktur? "
    "Sag mir kurz, was dich am meisten interessiert."
)
KIDS_CLARIFY_FALLBACK = (
    "Worum geht's dir am meisten? Grundlagen, Beispiele oder etwas Spannendes dazu? 🙂"
)
WEBMISS_CLARIFIER = (
    "Ich konnte im Web gerade nichts Verlässliches dazu finden. "
    "Hilft es, wenn ich gezielter suche? Zum Beispiel nach (a) Grundlagen, (b) konkreten Beispielen "
    "oder (c) aktuellen Nachrichten zu deinem Thema?"
)

# Quick replies for clarification
CLARIFY_QUICK_REPLIES = ["Entstehung", "Zusammensetzung", "Struktur"]

# sehr leichte Entschärfung gegen Spam/Loops (pro Konversation)
_clarify_cooldown: dict = {}
_WEBMISS_COOLDOWN_SECS = 20
# Guard against repetitive clarify fallback loops per conversation
_fallback_loop_guard: dict = {}
_FALLBACK_LOOP_COOLDOWN_SECS = 25

def _allow_webmiss_clarifier(conv_id: str, now_ts: float) -> bool:
    key = str(conv_id or "global")
    last = float(_clarify_cooldown.get(key, 0.0) or 0.0)
    ok = (now_ts - last) > _WEBMISS_COOLDOWN_SECS
    if ok:
        _clarify_cooldown[key] = float(now_ts)
    return ok
SMALLTALK_RX = re.compile(
    r"\b(wie\s+geht('?|\s*e?s)?\s*(dir|euch)|alles\s+klar|hallo|hi|hey|servus|moin|guten\s+(morgen|tag|abend)|na\b)\b",
    re.I,
)


def _to_float(s: str) -> float:
    return float(str(s).replace(',', '.'))


def _convert_units(val: float, u1: str, u2: str) -> Optional[Tuple[float, str]]:
    u1 = u1.lower(); u2 = u2.lower()
    to_m = {'mm': 1e-3, 'cm': 1e-2, 'm': 1.0, 'km': 1e3, 'mi': 1609.344}
    to_ms_speed = {'m/s': 1.0, 'km/h': 1000.0/3600.0, 'mph': 1609.344/3600.0}
    to_kg = {'g': 1e-3, 'kg': 1.0, 'lb': 0.45359237}
    def c_to_f(x): return x*9/5 + 32
    def f_to_c(x): return (x-32)*5/9
    if u1 in to_ms_speed and u2 in to_ms_speed:
        ms = val * to_ms_speed[u1]; out = ms / to_ms_speed[u2]; return out, u2
    if u1 in to_m and u2 in to_m:
        m = val * to_m[u1]; out = m / to_m[u2]; return out, u2
    if u1 in to_kg and u2 in to_kg:
        kg = val * to_kg[u1]; out = kg / to_kg[u2]; return out, u2
    if u1 == 'c' and u2 == 'f':
        return c_to_f(val), 'F'
    if u1 == 'f' and u2 == 'c':
        return f_to_c(val), 'C'
    return None


def tool_calc_or_convert(text: str) -> Optional[str]:
    t = (text or '').strip()
    if not t:
        return None
    m = _UNIT_RX.search(t)
    if m:
        val = _to_float(m.group('val'))
        res = _convert_units(val, m.group('u1'), m.group('u2'))
        if res:
            v, u = res
            return f"Umrechnung: {val:g} {m.group('u1')} = {v:.4g} {u}"
    expr = t.replace(',', '.')
    if _SAFE_EXPR.match(expr):
        try:
            import ast, operator as op
            allowed = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod, ast.FloorDiv, ast.Load, ast.Constant}
            def _eval(node):
                if type(node) not in allowed:
                    raise ValueError("unsichere Operation")
                if isinstance(node, ast.Expression):
                    return _eval(node.body)
                if isinstance(node, ast.Num):
                    return node.n
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                    v = _eval(node.operand)
                    return +v if isinstance(node.op, ast.UAdd) else -v
                if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv)):
                    a = _eval(node.left); b = _eval(node.right)
                    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv}
                    return ops[type(node.op)](a, b)
                raise ValueError("unsupported expression")
            tree = ast.parse(expr, mode='eval')
            return f"Rechnung: {expr} = { _eval(tree) }"
        except Exception:
            return None
    return None


def tool_memory_search(query: str, *, top_k: int = 3, min_score: float = 0.12) -> Tuple[List[dict], List[str]]:
    hits = search_blocks(query, top_k=top_k, min_score=min_score) or []
    out: List[dict] = []
    ids: List[str] = []
    for bid, score in hits:
        b = get_block(bid)
        if not b:
            continue
        ids.append(bid)
        out.append({
            "id": bid,
            "score": float(score),
            "title": str(b.get("title") or "Speicher"),
            "content": str(b.get("content") or ""),
            "tags": list(b.get("tags") or []),
        })
    return out, ids


def tool_web_peek(query: str, *, lang: str = "de") -> Tuple[str, List[dict]]:
    if os.getenv("ALLOW_NET", "1") != "1":
        return "", []
    res = web_search_and_summarize(query, user_context={"lang": lang}) or {}
    items = list(res.get("results") or [])
    if not items:
        return "", []
    # Build compact stitched brief
    pts: List[str] = []
    srcs: List[dict] = []
    for it in items[:3]:
        title = it.get("title") or "Web"
        summ  = it.get("summary") or ""
        url   = it.get("url") or ""
        pts.append(f"• {title}: {_short(summ, 280)}")
        srcs.append({"title": title, "url": url})
    body = "Gefundene Punkte:\n" + "\n".join(pts)
    return body, srcs


# ---------------- Internet agent utilities ---------------------------------
import requests
from bs4 import BeautifulSoup  # type: ignore

NET_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 KianaAgent/1.0"
    )
}


def net_search(query: str, *, lang: str = "de", max_results: int = 5) -> List[Dict[str, Any]]:
    """Unified search via web_qa aggregator (CSE/YouTube/DDG/Wiki)."""
    try:
        res = web_search_and_summarize(query, user_context={"lang": lang}, max_results=max_results) or {}
        items = res.get("results") or []
        return list(items)
    except Exception:
        return []


def net_open(url: str) -> Dict[str, Any]:
    """Fetch a URL and extract clean text + links."""
    try:
        r = requests.get(url, headers=NET_HEADERS, timeout=10)
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        for bad in soup(["script","style","noscript","header","footer","nav","form","aside"]):
            bad.extract()
        paras: List[str] = []
        for el in soup.find_all(["p","li","article","section"]):
            t = el.get_text(" ", strip=True)
            if len(t) >= 60:
                paras.append(t)
        # links
        links: List[Dict[str, str]] = []
        seen = set()
        for a in soup.find_all("a"):
            href = (a.get("href") or "").strip()
            title = a.get_text(" ", strip=True) or href
            if not href or href.startswith("#"):
                continue
            if href in seen:
                continue
            seen.add(href)
            if href.startswith("/") and r.url:
                from urllib.parse import urljoin
                href = urljoin(r.url, href)
            if href.startswith("http"):
                links.append({"url": href, "title": title})
            if len(links) >= 20:
                break
        text = "\n".join(paras)
        return {"url": r.url, "text": text, "links": links}
    except Exception:
        return {"url": url, "text": "", "links": []}


def net_extract_answer(context_text: str, question: str, *, lang: str = "de") -> str:
    """Use local LLM to extract a concise answer from given context; else fallback."""
    if llm_local is not None and getattr(llm_local, "available", lambda: False)():
        sys = (
            "Lies den Kontext und beantworte die Frage in 2–4 Sätzen. "
            "Antworte nur, wenn die Antwort im Kontext plausibel abgedeckt ist; sonst formuliere kurz, was fehlt."
        )
        instr = f"[Kontext]\n{_short(context_text, 4000)}\n\n[Frage]\n{question}\n\n[Antwort]"
        out = llm_local.chat_once(instr, system=sys)
        if out:
            return out.strip()
    # Fallback: naiver Auszug
    text = context_text.strip()
    if not text:
        return "Keine belastbaren Inhalte gefunden."
    return _short(text, 600)


def _llm_plan(user: str, persona: str, lang: str) -> Optional[List[Dict[str, Any]]]:
    if llm_local is None or not getattr(llm_local, "available", lambda: False)():
        return None
    sys = (
        "Du bist ein Agent mit Werkzeugen: calc, mem, web, device, net.search, net.open, net.extract, net.follow. "
        "Plane bis zu 5 Schritte und antworte NUR mit einer JSON‑Liste. "
        "Schema je Schritt: {tool: '<name>', input: '<string oder JSON>'}. "
        "calc: Rechnungen/Units. mem: Wissensblöcke suchen. web: Kurzrecherche (Aggregator). device: 'deviceId action {json}'. "
        "net.search: Websuche (liefert Ergebnisliste im Agentenspeicher). net.open: URL öffnen. net.follow: Index oder Link öffnen. "
        "net.extract: aus der zuletzt geöffneten Seite eine knappe Antwort extrahieren. "
        "Schließe immer mit {tool:'final', input:'knappe, klare Antwort auf Deutsch'}."
    )
    prompt = f"Nutzer: {user}\nSprache: {lang}\nPersona: {persona}\nGib nur JSON zurück."
    out = llm_local.chat_once(prompt, system=sys, json_response=True)
    try:
        import json
        if out:
            return json.loads(out)
    except Exception:
        return None
    return None


def _check_basic_knowledge(query: str) -> Optional[str]:
    """Check if the query matches any basic knowledge topic."""
    query = query.lower()
    for topic, answer in BASIC_KNOWLEDGE.items():
        if topic in query:
            return answer
    return None

def run_agent(message: str, *, persona: str = "friendly", lang: str = "de-DE", conv_id: str = "") -> Dict[str, Any]:
    user = (message or "").strip()
    if not user:
        return {
            "ok": True, 
            "reply": "Wie kann ich dir helfen? Wenn du magst, sag kurz, worum es geht (z. B. Grundlagen, Beispiele oder Umsetzung).", 
            "trace": [], 
            "sources": [], 
            "used_memory_ids": [],
            "quick_replies": []
        }
    
    # Check for basic knowledge match first
    basic_answer = _check_basic_knowledge(user)
    if basic_answer:
        return {
            "ok": True, 
            "reply": basic_answer, 
            "trace": [{"type": "basic_knowledge"}], 
            "sources": [], 
            "used_memory_ids": [],
            "quick_replies": [],
            "conv_id": conv_id or ""
        }
    
    # Smalltalk early-return
    if SMALLTALK_RX.search(user):
        return {
            "ok": True, 
            "reply": SMALLTALK_FALLBACK, 
            "trace": [], 
            "sources": [], 
            "used_memory_ids": [],
            "quick_replies": [],
            "conv_id": conv_id or ""
        }

    trace: List[Dict[str, Any]] = []
    sources: List[dict] = []
    used_mem_ids: List[str] = []
    tools_used: List[Dict[str, Any]] = []
    reply = ""

    # Check for follow-up responses to previous fallback question (only specific patterns)
    user_lower = user.lower()
    if any(pattern in user_lower for pattern in [
        "bitte erklär", "erkläre es", "erklär es", "kurz erklär", "einfach erklär",
        "ja, kurz", "ja kurz", "kurz bitte", "knapp bitte",
        "erklärung", "erklaer", "erklaerung", "explain", "explanation"
    ]):
        # User wants a brief explanation - try to provide one
        hits, mem_ids = tool_memory_search(user, top_k=2)
        used_mem_ids.extend(mem_ids)
        if hits:
            best_hit = hits[0]
            reply = f"Kurz erklärt: {_short(best_hit['content'], 300)}"
            trace.append({"tool": "mem", "input": user, "hits": [best_hit.get("id")]})
            tools_used.append({"tool": "mem", "ok": True, "meta": {"hits": 1}})
        else:
            reply = "Ich habe dazu leider keine gespeicherten Informationen. Möchtest du, dass ich im Web recherchiere?"
        return {"ok": True, "reply": reply, "trace": trace, "sources": sources, "used_memory_ids": used_mem_ids, "tools_used": tools_used}
    
    elif any(pattern in user_lower for pattern in [
        "ja, recherchier", "recherchiere bitte", "bitte recherchier", "ja recherchier",
        "such bitte", "bitte such", "web bitte", "im web",
        # Treat simple affirmatives as consent to research (default to research to avoid loops)
        "ja", "ok", "okay", "gern", "mach", "bitte"
    ]):
        # User wants web research - force web search
        if os.getenv("ALLOW_NET", "1") == "1":
            results = net_search(user, lang=(lang or "de"), max_results=3)
            trace.append({"tool": "net.search", "input": user, "count": len(results)})
            tools_used.append({"tool": "net.search", "ok": len(results) > 0, "meta": {"count": len(results)}})
            if results:
                pick = results[0]
                page = net_open(pick["url"])
                trace.append({"tool": "net.open", "url": page.get("url"), "chars": len(page.get("text",""))})
                tools_used.append({"tool": "net.open", "ok": bool(page.get("text")), "meta": {"url": page.get("url"), "reason": "Quelle öffnen"}})
                ans = net_extract_answer(page.get("text",""), user, lang=(lang or "de"))
                reply = f"Nach kurzer Recherche: {ans}"
                sources.append({"title": pick.get("title"), "url": pick.get("url")})
            else:
                # Keine Treffer → optionale Nachfrage mit Debounce
                if _allow_webmiss_clarifier(conv_id, time.time()):
                    reply = WEBMISS_CLARIFIER
                else:
                    reply = CLARIFY_FALLBACK
        else:
            reply = "Web-Recherche ist derzeit nicht verfügbar."
        return {"ok": True, "reply": reply, "trace": trace, "sources": sources, "used_memory_ids": used_mem_ids, "tools_used": tools_used}

    # Try an LLM-generated plan first
    plan = _llm_plan(user, persona, lang) or []
    if not isinstance(plan, list):
        plan = []

    def _finalize(ans: str) -> str:
        # Persist significant insights softly
        try:
            if ans and len(ans) > 160:
                process_and_store_memory(ans, lang=(lang or "de-DE"))
        except Exception:
            pass
        return ans

    if plan:
        for step in plan[:4]:
            tool = str(step.get("tool") or "").lower()
            arg  = str(step.get("input") or user)
            # shared scratchpad
            if 'scratch' not in locals():
                scratch: Dict[str, Any] = {"results": [], "page": {}}
            if tool == "calc":
                out = tool_calc_or_convert(arg) or ""
                trace.append({"tool": "calc", "input": arg, "output": out})
                if out:
                    reply = out
                tools_used.append({"tool": "calc", "ok": bool(out), "meta": {"reason": "Berechnung notwendig"}})
            elif tool == "mem":
                hits, ids = tool_memory_search(arg, top_k=3)
                used_mem_ids.extend(ids)
                note = "\n\n(Relevante Notizen)\n" + "\n".join(f"• {h['title']}: {_short(h['content'], 180)}" for h in hits) if hits else ""
                trace.append({"tool": "mem", "input": arg, "hits": [h.get("id") for h in hits]})
                reply = (reply + ("\n\n" if reply else "") + note).strip() if note else reply
                tools_used.append({"tool": "mem", "ok": bool(hits), "meta": {"hits": len(hits), "reason": ("Treffer im Gedächtnis gefunden" if hits else "Kein Treffer im Gedächtnis")}})
            elif tool == "web":
                brief, srcs = tool_web_peek(arg, lang=(lang or "de"))
                if brief:
                    trace.append({"tool": "web", "input": arg, "points": _short(brief, 200)})
                    reply = (reply + ("\n\n" if reply else "") + brief).strip()
                if srcs:
                    sources.extend(srcs)
                tools_used.append({"tool": "web", "ok": bool(brief), "meta": {"sources": len(srcs or [])}})
            elif tool in ("net.search", "netsearch", "search"):
                # Prefer tool if registry indicates good success; otherwise still allow (plan guided)
                results = net_search(arg, lang=(lang or "de"), max_results=5)
                scratch["results"] = results
                trace.append({"tool": "net.search", "input": arg, "results": [{"title": r.get("title"), "url": r.get("url"), "source": r.get("source")} for r in results[:5]]})
                tools_used.append({"tool": "net.search", "ok": len(results) > 0, "meta": {"count": len(results)}})
            elif tool in ("net.open", "open"):
                page = net_open(arg)
                scratch["page"] = page
                trace.append({"tool": "net.open", "url": page.get("url"), "chars": len(page.get("text",""))})
                tools_used.append({"tool": "net.open", "ok": bool(page.get("text")), "meta": {"url": page.get("url")}})
            elif tool in ("net.follow", "follow"):
                target = None
                try:
                    import json as _json
                    obj = _json.loads(arg) if arg.strip().startswith("{") else {"index": int(arg)}
                    idx = int(obj.get("index", 0))
                    # prefer last search results
                    results = (scratch.get("results") or [])
                    if results and 0 <= idx < len(results):
                        target = results[idx].get("url")
                    if not target:
                        links = (scratch.get("page") or {}).get("links") or []
                        if links and 0 <= idx < len(links):
                            target = links[idx].get("url")
                except Exception:
                    pass
                if target:
                    page = net_open(target)
                    scratch["page"] = page
                    trace.append({"tool": "net.follow", "url": page.get("url"), "chars": len(page.get("text",""))})
                else:
                    trace.append({"tool": "net.follow", "error": "no_target"})
                tools_used.append({"tool": "net.follow", "ok": bool(target), "meta": {"target": bool(target)}})
            elif tool in ("net.extract", "extract"):
                ctx = (scratch.get("page") or {}).get("text") or ""
                ans = net_extract_answer(ctx, arg or user, lang=(lang or "de"))
                reply = (reply + ("\n\n" if reply else "") + ans).strip()
                trace.append({"tool": "net.extract", "chars_ctx": len(ctx), "ok": bool(ans)})
                tools_used.append({"tool": "net.extract", "ok": bool(ans), "meta": {"reason": "Zusammenfassung/Antwort aus Seite extrahiert"}})
            elif tool == "device":
                # Lazy import; agent uses a tiny wrapper to avoid router deps
                try:
                    from netapi.devices.api import exec_device as _dev_exec, list_devices as _dev_list  # type: ignore
                except Exception:
                    _dev_exec = None; _dev_list = None  # type: ignore
                # Parse format: "device_id action {json}"
                did, act, aobj = None, None, {}
                try:
                    parts = (arg or "").strip().split(" ", 2)
                    if len(parts) >= 2:
                        did, act = parts[0], parts[1]
                    if len(parts) == 3:
                        import json as _json
                        aobj = _json.loads(parts[2])
                except Exception:
                    pass
                if _dev_exec and did and act:
                    ok, res = _dev_exec(did, act, aobj)
                    trace.append({"tool": "device", "input": {"id": did, "action": act, "args": aobj}, "ok": ok})
                    if ok:
                        reply = (reply + ("\n\n" if reply else "") + f"Geräteaktion {did}:{act} ausgeführt.").strip()
                    else:
                        reply = (reply + ("\n\n" if reply else "") + f"Geräteaktion fehlgeschlagen ({res.get('error','?')}).").strip()
                    tools_used.append({"tool": "device", "ok": bool(ok), "meta": {"id": did, "action": act}})
                else:
                    # If no exec, list available devices to guide user
                    if _dev_list:
                        devs = _dev_list() or []
                        if devs:
                            names = ", ".join(d.get('id') for d in devs[:5] if d.get('id'))
                            reply = (reply + ("\n\n" if reply else "") + f"Verfügbare Geräte: {names}").strip()
                    trace.append({"tool": "device", "error": "not_available_or_parse_error"})
            elif tool == "final":
                reply = str(arg).strip() or reply
                break
            else:
                # unknown → best-effort heuristics
                pass
        # If plan executed but produced no concrete reply, avoid looping the same clarify fallback.
        reply = (reply or "").strip()
        if not reply:
            now_ts = time.time()
            key = str(conv_id or "global")
            last_fallback = float(_fallback_loop_guard.get(key, 0.0) or 0.0)
            fallback_cooldown_hit = (now_ts - last_fallback) <= _FALLBACK_LOOP_COOLDOWN_SECS
            # Try quick memory or web extract before falling back
            hits2, mem_ids2 = tool_memory_search(user, top_k=1)
            if hits2:
                used_memory_ids.extend(mem_ids2)
                reply = f"Kurz erklärt: {_short(hits2[0]['content'], 300)}"
                trace.append({"tool": "mem", "input": user, "hits": [hits2[0].get("id")]})
            elif os.getenv("ALLOW_NET", "1") == "1":
                results = net_search(user, lang=(lang or "de"), max_results=3)
                trace.append({"tool": "net.search", "input": user, "count": len(results)})
                if results:
                    pick = results[0]
                    page = net_open(pick.get("url") or "")
                    trace.append({"tool": "net.open", "url": page.get("url"), "chars": len(page.get("text",""))})
                    ans = net_extract_answer(page.get("text",""), user, lang=(lang or "de"))
                    reply = f"Nach kurzer Recherche: {ans}"
                    sources.append({"title": pick.get("title"), "url": pick.get("url")})
            if not reply:
                if not fallback_cooldown_hit:
                    reply = (KIDS_CLARIFY_FALLBACK if (persona or '').lower().startswith('kids') else CLARIFY_FALLBACK)
                    _fallback_loop_guard[key] = now_ts
                else:
                    reply = "Ich formuliere es kurz und pragmatisch: " + _short(user, 60)
        # Apply persona style
        reply = _style_for_persona(reply, persona)
        # Persist a compact tool-usage memory block
        try:
            if tools_used:
                title = "Tool-Nutzung"
                lines = [f"• {t.get('tool')}: {'ok' if t.get('ok') else 'fail'}" for t in tools_used]
                content = ("Tool-Verwendung in dieser Antwort:\n" + "\n".join(lines)).strip()
                tags = ["tool_usage"] + [f"tool:{t.get('tool')}" for t in tools_used if t.get('tool')]
                add_block(title=title, content=content, tags=tags, url=None, meta={"conv_id": conv_id or "", "ts": int(time.time())})
        except Exception:
            pass
        reply = _style_for_persona(reply, persona)
        return {"ok": True, "reply": _finalize(reply), "trace": trace, "sources": sources, "used_memory_ids": used_mem_ids, "tools_used": tools_used}

    # No LLM plan available → heuristic execution (Agenten-Modus light)
    # 1) Quick calc/convert
    calc = tool_calc_or_convert(user)
    if calc:
        trace.append({"tool": "calc", "input": user, "output": calc})
        reply = calc
        tools_used.append({"tool": "calc", "ok": True})

    # 2) Memory
    hits, ids = tool_memory_search(user, top_k=3)
    used_mem_ids.extend(ids)
    if hits:
        mem_note = "\n\n(Relevante Notizen)\n" + "\n".join(f"• {h['title']}: {_short(h['content'], 180)}" for h in hits)
        trace.append({"tool": "mem", "input": user, "hits": [h.get("id") for h in hits]})
        reply = (reply + ("\n\n" if reply else "") + mem_note).strip()
        tools_used.append({"tool": "mem", "ok": True, "meta": {"hits": len(hits)}})

    # 3) Web (optional) — decide where/how to search
    brief, srcs = ("", [])
    web_nothing = False
    # 3) Web (optional) — prefer tools with good success rate; else fallback if nothing found
    if os.getenv("ALLOW_NET", "1") == "1":
        idx = _load_tools_index()
        recent = _recent_success_map(days=7)
        ql = user.lower()
        # heuristic provider preference
        prefer_yt = any(k in ql for k in ["video", "vortrag", "tutorial", "youtube"])
        prefer_wiki = any(k in ql for k in ["wiki", "was ist", "definition"])
        # Combined score for net.search: 0.7 * success_rate + 0.3 * recent_success
        try:
            base_sr = float((idx.get("net.search") or {}).get("success_rate") or 0.0)
        except Exception:
            base_sr = 0.0
        try:
            fb_sr = float((idx.get("net.search") or {}).get("feedback_score") or 0.0)
        except Exception:
            fb_sr = 0.0
        recent_sr = float(recent.get("net.search") or 0.0)
        combined = 0.6*base_sr + 0.2*recent_sr + 0.2*fb_sr
        # Persona/role bias
        pl = (persona or "").lower()
        if "forscher" in pl:
            combined += 0.1  # nudge towards web
        elif "erklaer" in pl or "erklär" in pl:
            combined -= 0.1  # nudge towards memory
        elif "kritik" in pl:
            combined -= 0.05
        # Exploration chance (10%)
        explore = (random.random() < 0.10)
        # If mem already yielded content and net.search is NOT good, downrank web branch (unless exploring or role bias high)
        allow_web = True
        if reply and (combined < 0.6) and not explore:
            allow_web = False
        # Run unified search and open best match (only if allowed)
        results = net_search(user, lang=(lang or "de"), max_results=5) if allow_web else []
        trace.append({"tool": "net.search", "input": user, "count": len(results)})
        tools_used.append({"tool": "net.search", "ok": len(results) > 0, "meta": {"count": len(results), "reason": ("Kein Memory‑Treffer → Websuche aktiviert" if (not reply) else ("Exploration/Web‑Bias" if allow_web else "Web übersprungen"))}})
        pick = None
        if prefer_yt:
            for r in results:
                if (r.get("source") or "").startswith("yt") or "youtube" in (r.get("url") or ""):
                    pick = r; break
        if prefer_wiki and not pick:
            for r in results:
                if (r.get("source") == "wiki") or "wikipedia.org" in (r.get("url") or ""):
                    pick = r; break
        pick = pick or (results[0] if results else None)
        if pick and pick.get("url"):
            page = net_open(pick["url"])
            trace.append({"tool": "net.open", "url": page.get("url"), "chars": len(page.get("text",""))})
            tools_used.append({"tool": "net.open", "ok": bool(page.get("text")), "meta": {"url": page.get("url")}})
            ans = net_extract_answer(page.get("text",""), user, lang=(lang or "de"))
            reply = (reply + ("\n\n" if reply else "") + ans).strip()
            sources.append({"title": pick.get("title"), "url": pick.get("url")})
        else:
            web_nothing = True

    if not reply:
        # Wenn die heuristische Websuche nichts fand und Cooldown ok → gezielte Nachfrage
        now_ts = time.time()
        key = str(conv_id or "global")
        last_fallback = float(_fallback_loop_guard.get(key, 0.0) or 0.0)
        fallback_cooldown_hit = (now_ts - last_fallback) <= _FALLBACK_LOOP_COOLDOWN_SECS
        if web_nothing and _allow_webmiss_clarifier(conv_id, now_ts):
            reply = WEBMISS_CLARIFIER
            _fallback_loop_guard[key] = now_ts
        elif not fallback_cooldown_hit:
            reply = (KIDS_CLARIFY_FALLBACK if (persona or '').lower().startswith('kids') else CLARIFY_FALLBACK)
            _fallback_loop_guard[key] = now_ts
        else:
            # Cooldown aktiv → nicht erneut die gleiche Rückfrage senden.
            # Stattdessen eine kurze, pragmatische Antwort erzeugen.
            hits2, mem_ids2 = tool_memory_search(user, top_k=1)
            if hits2:
                used_mem_ids.extend(mem_ids2)
                reply = f"Kurz erklärt: {_short(hits2[0]['content'], 300)}"
                trace.append({"tool": "mem", "input": user, "hits": [hits2[0].get("id")]})
            elif os.getenv("ALLOW_NET", "1") == "1":
                results = net_search(user, lang=(lang or "de"), max_results=3)
                trace.append({"tool": "net.search", "input": user, "count": len(results)})
                if results:
                    pick = results[0]
                    page = net_open(pick.get("url") or "")
                    trace.append({"tool": "net.open", "url": page.get("url"), "chars": len(page.get("text",""))})
                    ans = net_extract_answer(page.get("text",""), user, lang=(lang or "de"))
                    reply = f"Nach kurzer Recherche: {ans}"
                    sources.append({"title": pick.get("title"), "url": pick.get("url")})
                else:
                    reply = "Ich formuliere es kurz und pragmatisch: " + _short(user, 60)
            else:
                reply = "Ich formuliere es kurz und pragmatisch: " + _short(user, 60)

    return {"ok": True, "reply": _finalize(reply), "trace": trace, "sources": sources, "used_memory_ids": used_mem_ids}


__all__ = ["run_agent"]


# -----------------------------
# Streaming Agent
# -----------------------------
async def run_agent_stream(message: str, *, persona: str = "friendly", lang: str = "de-DE", conv_id: str = ""):
    """Async generator yielding {'delta': str} chunks and finally {'done': True}.
    Streams step-wise progress and, if available, LLM extraction in chunks.
    """
    user = (message or "").strip()
    tools_used: List[Dict[str, Any]] = []
    if not user:
        yield {"delta": "Wie kann ich dir helfen? Wenn du magst, sag kurz, worum es geht (z. B. Grundlagen, Beispiele oder Umsetzung)."}
        yield {"done": True, "tools_used": tools_used}
        return
    
    # Check for basic knowledge match first
    basic_answer = _check_basic_knowledge(user)
    if basic_answer:
        yield {"delta": basic_answer}
        yield {"done": True, "quick_replies": [], "conv_id": conv_id or "", "tools_used": tools_used}
        return
    
    # Smalltalk early-return
    if SMALLTALK_RX.search(user):
        yield {"delta": SMALLTALK_FALLBACK}
        yield {"done": True, "quick_replies": [], "conv_id": conv_id or "", "tools_used": []}
        return

    try:
        plan = _llm_plan(user, persona, lang) or []
        if not isinstance(plan, list):
            plan = []
    except Exception:
        plan = []

    scratch: Dict[str, Any] = {"results": [], "page": {}}

    if plan:
        for step in plan[:5]:
            tool = str(step.get("tool") or "").lower()
            arg  = str(step.get("input") or user)
            try:
                if tool == "calc":
                    out = tool_calc_or_convert(arg) or ""
                    if out: yield {"delta": out + "\n"}
                    tools_used.append({"tool": "calc", "ok": bool(out)})
                elif tool == "mem":
                    hits, _ids = tool_memory_search(arg, top_k=3)
                    if hits:
                        note = "\n".join(f"• {h['title']}: {_short(h['content'], 180)}" for h in hits)
                        yield {"delta": "(Relevante Notizen)\n" + note + "\n"}
                    tools_used.append({"tool": "mem", "ok": bool(hits), "meta": {"hits": len(hits or [])}})
                elif tool in ("web", "net.search", "netsearch", "search"):
                    yield {"delta": f"🔎 Suche: {arg}\n"}
                    results = net_search(arg, lang=(lang or "de"), max_results=5)
                    scratch["results"] = results
                    for i, r in enumerate(results[:5]):
                        yield {"delta": f"{i}: {r.get('title','Web')}\n"}
                    tools_used.append({"tool": "net.search", "ok": len(results) > 0, "meta": {"count": len(results)}})
                elif tool in ("net.open", "open"):
                    yield {"delta": f"🔗 Öffne: {arg}\n"}
                    page = net_open(arg)
                    scratch["page"] = page
                    tools_used.append({"tool": "net.open", "ok": bool((page or {}).get('text')), "meta": {"url": (page or {}).get('url')}})
                elif tool in ("net.follow", "follow"):
                    import json as _json
                    yield {"delta": f"➡️ Folge: {arg}\n"}
                    target = None
                    try:
                        obj = _json.loads(arg) if arg.strip().startswith("{") else {"index": int(arg)}
                        idx = int(obj.get("index", 0))
                        results = (scratch.get("results") or [])
                        if results and 0 <= idx < len(results):
                            target = results[idx].get("url")
                        if not target:
                            links = (scratch.get("page") or {}).get("links") or []
                            if links and 0 <= idx < len(links):
                                target = links[idx].get("url")
                    except Exception:
                        target = None
                    if target:
                        page = net_open(target)
                        scratch["page"] = page
                    tools_used.append({"tool": "net.follow", "ok": bool(target), "meta": {"target": bool(target)}})
                elif tool in ("net.extract", "extract"):
                    ctx = (scratch.get("page") or {}).get("text") or ""
                    if llm_local is not None and getattr(llm_local, "available", lambda: False)():
                        sys = (
                            "Lies den Kontext und beantworte die Frage in 2–4 Sätzen. "
                            "Antworte nur, wenn die Antwort im Kontext plausibel abgedeckt ist; sonst formuliere kurz, was fehlt."
                        )
                        instr = f"[Kontext]\n{_short(ctx, 4000)}\n\n[Frage]\n{user}\n\n[Antwort]"
                        for chunk in llm_local.chat_stream(instr, system=sys):
                            if chunk:
                                yield {"delta": chunk}
                    else:
                        # Fallback extraction
                        from_text = (scratch.get("page") or {}).get("text") or ""
                        if from_text:
                            yield {"delta": _short(from_text, 600) + "\n"}
                    tools_used.append({"tool": "net.extract", "ok": True})
                elif tool == "device":
                    yield {"delta": f"⚙️ Gerät: {arg}\n"}
                    try:
                        from netapi.devices.api import exec_device as _dev_exec  # type: ignore
                        parts = (arg or "").strip().split(" ", 2)
                        if len(parts) >= 2:
                            did, act = parts[0], parts[1]
                            import json as _json
                            aobj = _json.loads(parts[2]) if len(parts) == 3 else {}
                            ok, _res = _dev_exec(did, act, aobj)
                            yield {"delta": ("ok\n" if ok else "fehler\n")}
                    except Exception:
                        yield {"delta": "fehler\n"}
                elif tool == "final":
                    text = arg.strip()
                    if text:
                        yield {"delta": ("\n" + text)}
                    break
            except Exception:
                continue
        # Persist a compact tool-usage memory block
        try:
            if tools_used:
                title = "Tool-Nutzung"
                lines = [f"• {t.get('tool')}: {'ok' if t.get('ok') else 'fail'}" for t in tools_used]
                content = ("Tool-Verwendung in dieser Antwort:\n" + "\n".join(lines)).strip()
                tags = ["tool_usage"] + [f"tool:{t.get('tool')}" for t in tools_used if t.get('tool')]
                add_block(title=title, content=content, tags=tags, url=None, meta={"conv_id": conv_id or "", "ts": int(time.time())})
        except Exception:
            pass
        yield {"done": True, "tools_used": tools_used}
        return

    # Fallback: heuristic streaming
    # 1) calc quick
    try:
        calc = tool_calc_or_convert(user)
        if calc:
            yield {"delta": calc}
            yield {"done": True}
            return
    except Exception:
        pass

    # 2) unified search and quick extract
    if os.getenv("ALLOW_NET", "1") == "1":
        yield {"delta": f"🔎 Suche: {user}\n"}
        results = net_search(user, lang=(lang or "de"), max_results=5)
        target = results[0].get("url") if results else None
        if target:
            yield {"delta": f"🔗 Öffne: {target}\n"}
            page = net_open(target)
            ctx = page.get("text", "")
            if llm_local is not None and getattr(llm_local, "available", lambda: False)():
                sys = "Lies den Kontext und gib eine kurze Antwort (2–4 Sätze)."
                instr = f"[Kontext]\n{_short(ctx, 4000)}\n\n[Frage]\n{user}\n\n[Antwort]"
                for chunk in llm_local.chat_stream(instr, system=sys):
                    if chunk:
                        yield {"delta": chunk}
                yield {"done": True}
                return
            else:
                ans = net_extract_answer(ctx, user, lang=(lang or "de"))
                yield {"delta": ans}
                yield {"done": True}
                return
    # 3 Check for follow-up responses before ultimate fallback (only specific patterns)
    user_lower = user.lower()
    if any(pattern in user_lower for pattern in [
        "bitte erklär", "erkläre es", "erklär es", "kurz erklär", "einfach erklär",
        "ja, kurz", "ja kurz", "kurz bitte", "knapp bitte",
        "erklärung", "erklaer", "erklaerung", "explain", "explanation"
    ]):
        # User wants brief explanation
        hits, _ids = tool_memory_search(user, top_k=2)
        if hits:
            best_hit = hits[0]
            yield {"delta": f"Kurz erklärt: {_short(best_hit['content'], 300)}"}
        else:
            yield {"delta": "Ich habe dazu leider keine gespeicherten Informationen. Möchtest du, dass ich im Web recherchiere?"}
        yield {"done": True}
        return
    elif any(pattern in user_lower for pattern in [
        "ja, recherchier", "recherchiere bitte", "bitte recherchier", "ja recherchier",
        "such bitte", "bitte such", "web bitte", "im web",
        # Treat simple affirmatives as consent to research
        "ja", "ok", "okay", "gern", "mach", "bitte"
    ]):
        # User wants web research
        if os.getenv("ALLOW_NET", "1") == "1":
            yield {"delta": f"🔎 Recherchiere: {user}\n"}
            results = net_search(user, lang=(lang or "de"), max_results=3)
            if results:
                pick = results[0]
                yield {"delta": f"🔗 Öffne: {pick.get('url')}\n"}
                page = net_open(pick["url"])
                ans = net_extract_answer(page.get("text",""), user, lang=(lang or "de"))
                yield {"delta": f"Nach kurzer Recherche: {ans}"}
            else:
                # Keine Treffer → optionale Nachfrage mit Debounce
                if _allow_webmiss_clarifier(conv_id, time.time()):
                    yield {"delta": WEBMISS_CLARIFIER}
                else:
                    yield {"delta": CLARIFY_FALLBACK}
        else:
            yield {"delta": "Ich bin dir gerne bei anderen Fragen behilflich. Was genau möchtest du wissen?"}
        yield {"done": True}
        return
    
    # ultimate fallback with loop guard and pragmatic alternative
    now_ts = time.time()
    key = str(conv_id or "global")
    last_fallback = float(_fallback_loop_guard.get(key, 0.0) or 0.0)
    fallback_cooldown_hit = (now_ts - last_fallback) <= _FALLBACK_LOOP_COOLDOWN_SECS
    if not fallback_cooldown_hit:
        _fallback_loop_guard[key] = now_ts
        yield {"delta": (KIDS_CLARIFY_FALLBACK if (persona or '').lower().startswith('kids') else CLARIFY_FALLBACK)}
        yield {
            "done": True,
            "quick_replies": CLARIFY_QUICK_REPLIES,
            "conv_id": conv_id or "",
        }
    else:
        # Do not ask again; provide a brief pragmatic response instead
        alt = "Ich formuliere es kurz und pragmatisch: " + _short(user, 60)
        yield {"delta": alt}
        yield {"done": True, "conv_id": conv_id or ""}
