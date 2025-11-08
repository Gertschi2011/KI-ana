from __future__ import annotations
from flask import Blueprint, request, jsonify, make_response
from backend.core.security import hash_password, verify_password, create_tokens, verify_token

bp = Blueprint("auth", __name__)

# In-memory users for scaffold; replace with SQLAlchemy model later
_USERS = {
    "admin@example.com": {
        "password": hash_password("admin123"),
        "roles": ["admin"],
    }
}

# Seed Papa user (Gerald). For production, replace with DB-backed users.
_USERS["gerald@ki-ana.at"] = {
    "password": hash_password("Jawohund2011!"),
    "roles": ["papa", "admin"],
}

# QA test user with full rights
_USERS["test@ki-ana.at"] = {
    "password": hash_password("Test12345!"),
    "roles": ["admin", "papa"],
}

@bp.post("/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    # Accept username or email from payload, but our in-memory store is keyed by email
    raw = (data.get("email") or data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    # Resolve bare usernames to corporate email domain
    candidate_keys = [raw]
    if raw and ("@" not in raw):
        candidate_keys.append(f"{raw}@ki-ana.at")
    user = None
    for key in candidate_keys:
        user = _USERS.get(key)
        if user:
            raw = key
            break
    if not user or not verify_password(password, user["password"]):
        return jsonify({"ok": False, "error": "invalid_credentials"}), 401
    toks = create_tokens(raw)
    roles = list(user.get("roles", ["user"]))
    is_admin = "admin" in [r.lower() for r in roles]
    is_papa = "papa" in [r.lower() for r in roles]
    username_disp = (raw.split("@", 1)[0] if "@" in raw else raw)
    caps = {
        "can_manage_users": is_admin or is_papa,
        "can_view_block_viewer": is_admin or is_papa,
        "can_sign_blocks": is_admin or is_papa,
        "can_rehash_blocks": is_admin or is_papa,
        "can_view_admin": is_admin,
    }
    resp = make_response(jsonify({
        "ok": True,
        "access": toks.access,
        "refresh": toks.refresh,
        "roles": roles,
        "user": {
            "email": raw,
            "username": username_disp,
            "roles": roles,
            "is_admin": is_admin,
            "is_papa": is_papa,
            "caps": caps,
        }
    }))
    # Also set a short-lived HttpOnly cookie so browsers can auto-carry the session
    try:
        # 1 hour cookie; adjust as needed
        resp.set_cookie("access_token", toks.access, httponly=True, samesite="Lax", max_age=3600, path="/")
    except Exception:
        pass
    return resp


@bp.post("/register")
def register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "missing_fields"}), 400
    if email in _USERS:
        return jsonify({"ok": False, "error": "user_exists"}), 409
    _USERS[email] = {"password": hash_password(password), "roles": ["user"]}
    return jsonify({"ok": True, "user": {"email": email, "username": email, "roles": ["user"]}})

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


def _read_access_token() -> str | None:
    # Prefer Authorization: Bearer <token>, fallback to cookie
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None
    cookie_tok = request.cookies.get("access_token")
    return cookie_tok or None


@bp.get("/me")
def me():
    token = _read_access_token()
    if not token:
        return jsonify({"auth": False, "user": None})
    payload = verify_token(token, refresh=False)
    if not payload:
        return jsonify({"auth": False, "user": None}), 401
    email = payload.get("sub")
    user = _USERS.get(email, {"roles": ["user"]})
    roles = list(user.get("roles", ["user"]))
    is_admin = "admin" in [r.lower() for r in roles]
    is_papa = "papa" in [r.lower() for r in roles]
    username_disp = (email.split("@", 1)[0] if email and "@" in email else (email or ""))
    caps = {
        "can_manage_users": is_admin or is_papa,
        "can_view_block_viewer": is_admin or is_papa,
        "can_sign_blocks": is_admin or is_papa,
        "can_rehash_blocks": is_admin or is_papa,
        "can_view_admin": is_admin,
    }
    return jsonify({
        "auth": True,
        "user": {
            "email": email,
            "username": username_disp,
            "roles": roles,
            "is_admin": is_admin,
            "is_papa": is_papa,
            "caps": caps,
        }
    })


@bp.post("/logout")
def logout():
    resp = make_response(jsonify({"ok": True}))
    try:
        resp.delete_cookie("access_token", path="/")
    except Exception:
        pass
    return resp
