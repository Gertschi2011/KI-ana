from __future__ import annotations
from flask import Blueprint, request, jsonify

bp = Blueprint("search", __name__)

@bp.get("/")
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": True, "items": []})
    # Scaffold: return echo result
    return jsonify({"ok": True, "items": [{"id": "echo", "text": q, "score": 0.5}]})
