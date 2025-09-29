from __future__ import annotations
from flask import Blueprint, request, jsonify
import time

bp = Blueprint("orchestrator", __name__)

# Minimal tool registry stub
_TOOLS = {
    "echo": lambda args: {"text": str(args.get("text", ""))},
    "sleep": lambda args: (time.sleep(int(args.get("seconds", 1))), {"slept": True})[1],
}

@bp.post("/invoke")
def invoke():
    data = request.get_json(force=True, silent=True) or {}
    tool = (data.get("tool") or "").strip()
    args = data.get("args") or {}
    if tool not in _TOOLS:
        return jsonify({"ok": False, "error": "unknown_tool", "available": list(_TOOLS.keys())}), 400
    try:
        start = time.time()
        out = _TOOLS[tool](args)
        dur = time.time() - start
        trace = {"tool": tool, "args": args, "output": out, "duration_ms": int(dur*1000), "status": "ok"}
        return jsonify({"ok": True, "trace": trace})
    except Exception as e:
        return jsonify({"ok": False, "error": "tool_failed", "detail": str(e)[:200]}), 500
