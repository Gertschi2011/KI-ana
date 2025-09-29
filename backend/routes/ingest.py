from __future__ import annotations
from flask import Blueprint, request, jsonify

bp = Blueprint("ingest", __name__)

@bp.post("/upload")
def upload():
    # Scaffold endpoint: accepts metadata and simulates enqueue
    data = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": True, "job_id": "demo-upload-1", "meta": data})

@bp.post("/crawl")
def crawl():
    data = request.get_json(force=True, silent=True) or {}
    url = data.get("url")
    if not url:
        return jsonify({"ok": False, "error": "missing_url"}), 400
    return jsonify({"ok": True, "job_id": "demo-crawl-1", "url": url})
