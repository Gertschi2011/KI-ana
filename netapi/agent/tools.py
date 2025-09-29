from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os, re

# Memory store (lazy)
try:
    from netapi.memory_store import search_blocks, get_block
except Exception:  # pragma: no cover
    def search_blocks(query: str, top_k: int = 5, min_score: float = 0.12):  # type: ignore
        return []
    def get_block(bid: str):  # type: ignore
        return None

# Web QA aggregator
try:
    from netapi.web_qa import web_search_and_summarize
except Exception:  # pragma: no cover
    def web_search_and_summarize(query: str, user_context: Optional[Dict[str, Any]] = None, max_results: int = 3):  # type: ignore
        return {"query": query, "allowed": False, "results": []}

try:
    from netapi.core import llm_local  # type: ignore
except Exception:  # pragma: no cover
    llm_local = None  # type: ignore

_SAFE_EXPR = re.compile(r"^[0-9\s+\-*/().,]+$")
_UNIT_RX   = re.compile(r"(?P<val>\d+(?:[\.,]\d+)?)\s*(?P<u1>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\s*(?:in|zu|nach)\s*(?P<u2>km/h|m/s|km|m|cm|mm|mi|mph|kg|g|lb|c|f)\b", re.I)

def _short(text: str, n: int = 220) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    t = t[:n]
    cut = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
    return (t[:cut+1] if cut > 80 else t).rstrip() + " …"

def _to_float(s: str) -> float:
    return float(str(s).replace(',', '.'))

def tool_calc_or_convert(text: str) -> Optional[str]:
    t = (text or '').strip()
    if not t:
        return None
    m = _UNIT_RX.search(t)
    if m:
        val = _to_float(m.group('val'))
        u1, u2 = m.group('u1').lower(), m.group('u2').lower()
        to_m = {'mm': 1e-3, 'cm': 1e-2, 'm': 1.0, 'km': 1e3, 'mi': 1609.344}
        to_ms = {'m/s': 1.0, 'km/h': 1000.0/3600.0, 'mph': 1609.344/3600.0}
        to_kg = {'g': 1e-3, 'kg': 1.0, 'lb': 0.45359237}
        def c_to_f(x): return x*9/5 + 32
        def f_to_c(x): return (x-32)*5/9
        if u1 in to_ms and u2 in to_ms:
            v = (val * to_ms[u1]) / to_ms[u2]; return f"Umrechnung: {val:g} {m.group('u1')} = {v:.4g} {m.group('u2')}"
        if u1 in to_m and u2 in to_m:
            v = (val * to_m[u1]) / to_m[u2]; return f"Umrechnung: {val:g} {m.group('u1')} = {v:.4g} {m.group('u2')}"
        if u1 in to_kg and u2 in to_kg:
            v = (val * to_kg[u1]) / to_kg[u2]; return f"Umrechnung: {val:g} {m.group('u1')} = {v:.4g} {m.group('u2')}"
        if u1 == 'c' and u2 == 'f': return f"Umrechnung: {val:g} C = {c_to_f(val):.4g} F"
        if u1 == 'f' and u2 == 'c': return f"Umrechnung: {val:g} F = {f_to_c(val):.4g} C"
    expr = t.replace(',', '.')
    if _SAFE_EXPR.match(expr):
        try:
            import ast, operator as op
            allowed = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod, ast.FloorDiv, ast.Load, ast.Constant}
            def _eval(node):
                if type(node) not in allowed: raise ValueError('unsichere Operation')
                if isinstance(node, ast.Expression): return _eval(node.body)
                if isinstance(node, ast.Num): return node.n
                if isinstance(node, ast.Constant) and isinstance(node.value, (int,float)): return node.value
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                    v=_eval(node.operand); return +v if isinstance(node.op, ast.UAdd) else -v
                if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv)):
                    a=_eval(node.left); b=_eval(node.right)
                    ops={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.Pow:op.pow,ast.Mod:op.mod,ast.FloorDiv:op.floordiv}
                    return ops[type(node.op)](a,b)
                raise ValueError('unsupported expression')
            import ast
            return f"Rechnung: {expr} = { _eval(ast.parse(expr, mode='eval')) }"
        except Exception:
            return None
    return None

def tool_memory_search(query: str, *, top_k: int = 3, min_score: float = 0.12) -> Tuple[List[dict], List[str]]:
    hits = search_blocks(query, top_k=top_k, min_score=min_score) or []
    out: List[dict] = []; ids: List[str] = []
    for bid, score in hits:
        b = get_block(bid);
        if not b: continue
        ids.append(bid)
        out.append({"id": bid, "score": float(score), "title": b.get("title") or "Speicher", "content": b.get("content") or "", "tags": list(b.get("tags") or [])})
    return out, ids

def tool_web_peek(query: str, *, lang: str = "de") -> Tuple[str, List[dict]]:
    if os.getenv("ALLOW_NET", "1") != "1":
        return "", []
    res = web_search_and_summarize(query, user_context={"lang": lang}) or {}
    items = list(res.get("results") or [])
    if not items: return "", []
    pts: List[str] = []; srcs: List[dict] = []
    for it in items[:3]:
        title = it.get("title") or "Web"
        summ  = it.get("summary") or ""
        url   = it.get("url") or ""
        pts.append(f"• {title}: {_short(summ, 280)}")
        srcs.append({"title": title, "url": url})
    return "Gefundene Punkte:\n" + "\n".join(pts), srcs

# Light web utilities (open/extract) are left in agent for streaming path.

