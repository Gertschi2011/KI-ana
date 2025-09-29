from __future__ import annotations
from flask import Blueprint, request, jsonify
from backend.core.security import hash_password, verify_password, create_tokens, verify_token

bp = Blueprint("auth", __name__)

# In-memory users for scaffold; replace with SQLAlchemy model later
_USERS = {
    "admin@example.com": {
        "password": hash_password("admin123"),
        "roles": ["admin"],
    }
}

@bp.post("/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = _USERS.get(email)
    if not user or not verify_password(password, user["password"]):
        return jsonify({"ok": False, "error": "invalid_credentials"}), 401
    toks = create_tokens(email)
    return jsonify({"ok": True, "access": toks.access, "refresh": toks.refresh, "roles": user["roles"]})

@bp.post("/refresh")
def refresh():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get("refresh") or ""
    payload = verify_token(token, refresh=True)
    if not payload:
        return jsonify({"ok": False, "error": "invalid_refresh"}), 401
    email = payload.get("sub")
    toks = create_tokens(email)
    return jsonify({"ok": True, "access": toks.access, "refresh": toks.refresh})
