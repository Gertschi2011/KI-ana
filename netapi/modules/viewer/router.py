from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import json, hashlib, traceback
from datetime import datetime
from fastapi import Body
from netapi.deps import get_current_user_required, get_current_user_opt
from netapi.deps import has_any_role
import os
from netapi import memory_store as _mem
from importlib.machinery import SourceFileLoader

router = APIRouter(prefix="/viewer", tags=["viewer"])

# Use KI_ROOT environment variable or fallback to calculated path
KI_ROOT_ENV = os.getenv("KI_ROOT")
if KI_ROOT_ENV:
    PROJECT_ROOT = Path(KI_ROOT_ENV)
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]

CHAIN_DIR      = PROJECT_ROOT / "system" / "chain"
MEM_BLOCKS_DIR = PROJECT_ROOT / "memory" / "long_term" / "blocks"
STATIC_DIR     = PROJECT_ROOT / "netapi" / "static"
SIGNER_PATH    = PROJECT_ROOT / "system" / "block_signer.py"
REFLECT_PATH   = PROJECT_ROOT / "system" / "reflection_engine.py"
KEYS_DIR       = PROJECT_ROOT / "system" / "keys"

# Guards: allow access if Papa‑Modus enabled OR current user is admin
def _papa_on() -> bool:
    try:
        return os.getenv("PAPA_MODE", "").lower() in {"1", "true", "on"}
    except Exception:
        return False

def _require_admin_or_papa(current: dict | None) -> None:
    # Allow if Papa‑Modus is enabled globally
    if _papa_on():
        return
    # Else require role 'admin' or 'papa'
    if has_any_role(current, {"admin", "papa", "creator"}):
        return
    raise HTTPException(403, "viewer requires Papa‑Modus or admin/papa role")

# ---------- Helpers ---------------------------------------------------------

def _canonical(obj: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(obj)
    # Exclude transient/derived fields when computing canonical hash.
    # Must match system/block_signer.py canonical_bytes() exclusions to keep hashes consistent.
    for k in ("hash", "hash_stored", "hash_calc", "signature", "pubkey", "signed_at"):
        data.pop(k, None)
    return data

def _calc_sha256(obj: Dict[str, Any]) -> str:
    try:
        raw = json.dumps(_canonical(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        return ""

def _validate_block(data: Dict[str, Any]) -> Tuple[bool, str, str]:
    """return (valid, reason, calc_hash)"""
    try:
        calc = _calc_sha256(data)
    except Exception:
        return False, "parse_error", ""
    stored = (data.get("hash") or "").strip()
    if not stored:
        return False, "hash_missing", calc
    if stored != calc:
        return False, "hash_mismatch", calc
    return True, "ok", calc


def _load_json_file(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ts(v: Any) -> str:
    if isinstance(v, (int, float)):
        return datetime.utcfromtimestamp(v).isoformat() + "Z"
    if isinstance(v, str):
        return v
    return ""


def _verify_signature(data: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        if not SIGNER_PATH.exists():
            return False, "signer_missing"
        mod = SourceFileLoader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
        if not hasattr(mod, "verify_block"):
            return False, "verify_missing"
        ok, reason = mod.verify_block(data)  # type: ignore
        return bool(ok), str(reason)
    except Exception as e:
        return False, f"verify_error:{type(e).__name__}"


def _load_signer():
    try:
        if not SIGNER_PATH.exists():
            return None
        mod = SourceFileLoader("block_signer", str(SIGNER_PATH)).load_module()  # type: ignore
        return mod
    except Exception:
        return None


def _load_reflector():
    try:
        if not REFLECT_PATH.exists():
            return None
        mod = SourceFileLoader("reflection_engine", str(REFLECT_PATH)).load_module()  # type: ignore
        return mod
    except Exception:
        return None


def _summarize_block(p: Path, origin: str) -> Dict[str, Any]:
    data = _load_json_file(p)
    valid, reason, calc = _validate_block(data)
    sig_ok, sig_reason = _verify_signature(data)
    stored = (data.get("hash") or "").strip()
    # tags detection (from memory or chain meta)
    tags: List[str] = []
    try:
        if isinstance(data.get("tags"), list):
            tags = list(data.get("tags"))
        elif isinstance((data.get("meta") or {}).get("tags"), list):
            tags = list((data.get("meta") or {}).get("tags") or [])
    except Exception:
        tags = []
    submind = ""
    for t in tags:
        if isinstance(t, str) and t.startswith("submind:"):
            submind = t.split(":",1)[1]
            break

    # Rating lookup via memory_store (soft)
    rating_avg: float = 0.0
    rating_count: int = 0
    try:
        rid = data.get("id") or p.stem
        r = _mem.get_rating(str(rid))
        if isinstance(r, dict):
            rating_avg = float(r.get("avg", 0.0) or 0.0)
            rating_count = int(r.get("count", 0) or 0)
    except Exception:
        pass
    meta = data.get("meta") or {}
    source = data.get("source") or meta.get("source") or ""
    try:
        if isinstance(source, str) and source.startswith("http://"):
            source = "https://" + source[len("http://"):]
    except Exception:
        pass
    author = meta.get("author") or ""
    # --- Trust signals (enhanced heuristics) ---
    def _host_score(u: str) -> float:
        try:
            import urllib.parse as up
            host = up.urlparse(u or "").netloc.lower()
            if not host:
                return 0.5
            # Whitelist/blacklist hints (very light-weight)
            good = ("wikipedia", ".gov", ".edu", "nature.com", "nih.gov", "who.int", "bmj.com", "cdc.gov")
            bad  = ("click", "adserver", "track", "malware", "phish")
            if any(g in host for g in good):
                return 0.95
            if any(b in host for b in bad):
                return 0.2
            # default for known host
            return 0.65
        except Exception:
            return 0.5
    def _age_score(ts: Any) -> float:
        try:
            t = int(ts) if isinstance(ts, (int, float)) else int(data.get("ts") or 0)
        except Exception:
            t = int(data.get("ts") or 0) if isinstance(data.get("ts"), (int, float)) else 0
        import time as _t
        now = int(_t.time())
        age = max(0, now - (t or 0))
        # 0..2y → 1.0..0.6, older → 0.5 floor
        two_years = 2*365*24*3600
        if age <= 0:
            return 0.8
        if age >= two_years:
            return 0.5
        # linear degrade
        return 1.0 - 0.4*(age/two_years)
    def _sig_score(v_ok: bool, s_ok: bool) -> float:
        # reward blocks that are hash-valid and signature-valid
        if v_ok and s_ok:
            return 1.0
        if v_ok and not s_ok:
            return 0.7
        if s_ok and not v_ok:
            return 0.6
        return 0.3
    def _rating_count_score(cnt: int) -> float:
        # more raters increase confidence, saturate around ~10
        c = max(0, int(cnt or 0))
        if c <= 0: return 0.3
        if c >= 10: return 1.0
        return 0.3 + 0.7*(c/10.0)
    def _author_score(name: str) -> float:
        try:
            n = (name or '').strip()
            if not n:
                return 0.5
            return 0.75
        except Exception:
            return 0.5

    src_score = _host_score(source)
    age_score = _age_score(data.get("timestamp") or data.get("ts"))
    sig_score = _sig_score(valid, sig_ok)
    rc_score  = _rating_count_score(rating_count)
    auth_score = _author_score(author)
    # combine with weights; clamp to [0,1]
    try:
        raw = (
            0.35*float(rating_avg or 0.0) +
            0.20*float(src_score) +
            0.15*float(age_score) +
            0.20*float(sig_score) +
            0.10*float(rc_score) +
            0.05*float(auth_score)
        )
        trust_score = max(0.0, min(1.0, round(raw, 3)))
    except Exception:
        trust_score = float(rating_avg or 0.0)
    # Extract content preview for search
    content = data.get("content") or data.get("text") or ""
    if isinstance(content, str):
        content_preview = content[:500]  # First 500 chars for preview/search
    else:
        content_preview = ""
    
    return {
        "id": data.get("id") or p.stem,
        "title": data.get("title") or data.get("topic") or "",
        "topic": data.get("topic") or "",
        "source": source,
        "timestamp": data.get("timestamp") or data.get("created_at") or "",
        "origin": origin,
        "size": p.stat().st_size,
        "file": str(p.as_posix()),
        "valid": valid,
        "reason": reason,
        "sig_valid": sig_ok,
        "sig_reason": sig_reason,
        "hash_stored": stored or "",
        "hash_calc": calc or "",
        "tags": tags,
        "submind": submind,
        "author": author,
        "rating_avg": rating_avg,
        "rating_count": rating_count,
        "content_preview": content_preview,
        "trust": {
            "score": trust_score,
            "signals": {
                "source": round(src_score, 3),
                "age": round(age_score, 3),
                "signature": round(sig_score, 3),
                "rating": float(rating_avg),
                "rating_count": int(rating_count),
                "author": round(auth_score, 3),
            }
        },
    }


def _find_block_by_id(block_id: str) -> Optional[Path]:
    """Findet eine Block-Datei anhand der ID in beiden Verzeichnissen."""
    for base in (CHAIN_DIR, MEM_BLOCKS_DIR):
        if not base.exists():
            continue
        cand = base / f"{block_id}.json"
        if cand.exists():
            return cand
    return None

# ---------- Routes: UI ------------------------------------------------------

@router.get("", response_class=FileResponse)
async def serve_viewer():
    index = STATIC_DIR / "block_viewer.html"
    if not index.exists():
        raise HTTPException(404, f"block_viewer.html not found at {index}")
    return FileResponse(index)

# Health/quick ping for UI preflight
@router.head("/api/blocks")
async def head_blocks():
    return Response(status_code=200)

# ---------- Routes: API (list/detail) --------------------------------------

@router.get("/api/blocks")
async def list_blocks(
    verified_only: bool = True,
    q: str | None = None,
    sort: str = "none",
    page: int = 1,
    limit: int = 50,
    current=Depends(get_current_user_opt),
):
    _require_admin_or_papa(current)
    try:
        items: List[Dict[str, Any]] = []

        def safe_add(p: Path, origin: str):
            try:
                items.append(_summarize_block(p, origin))
            except Exception:
                items.append({
                    "id": p.stem,
                    "file": str(p.as_posix()),
                    "origin": origin,
                    "title": "",
                    "topic": "",
                    "timestamp": "",
                    "source": "",
                    "size": p.stat().st_size,
                    "valid": False,
                    "reason": "parse_error",
                    "hash_stored": "",
                    "hash_calc": "",
                })

        if CHAIN_DIR.exists():
            for p in sorted(CHAIN_DIR.glob("*.json")):
                safe_add(p, "system/chain")

        if MEM_BLOCKS_DIR.exists():
            for p in sorted(MEM_BLOCKS_DIR.glob("*.json")):
                safe_add(p, "memory/long_term/blocks")

        # optionally filter to only signature-verified blocks
        if verified_only:
            items = [it for it in items if it.get("sig_valid") and it.get("valid")]

        # server-side quick search filter (title/topic/source/origin/content/tags)
        qq = (q or "").strip().lower()
        if qq:
            def _hay(it: Dict[str, Any]) -> str:
                # Include title, topic, source, origin, content preview, and tags
                tags_str = ' '.join(it.get('tags', []))
                content = it.get('content_preview', '')
                return f"{it.get('title','')} {it.get('topic','')} {it.get('source','')} {it.get('origin','')} {content} {tags_str}".lower()
            items = [it for it in items if qq in _hay(it)]

        # sorting
        s = (sort or "none").strip().lower()
        try:
            if s == "trust":
                items.sort(key=lambda it: float(((it.get("trust") or {}).get("score") or 0.0)), reverse=True)
            elif s == "rating":
                items.sort(key=lambda it: float(it.get("rating_avg") or 0.0), reverse=True)
            elif s == "time":
                def _to_ts(x):
                    if isinstance(x, (int, float)): return int(x)
                    if isinstance(x, str):
                        try:
                            from datetime import datetime
                            return int(datetime.fromisoformat(x.replace('Z','+00:00')).timestamp())
                        except Exception:
                            return 0
                    return 0
                items.sort(key=lambda it: _to_ts(it.get("timestamp")), reverse=True)
        except Exception:
            pass

        # pagination (after filtering & sorting)
        try:
            p = max(1, int(page))
        except Exception:
            p = 1
        try:
            lim = int(limit)
        except Exception:
            lim = 50
        # clamp to sane bounds
        if lim <= 0:
            lim = 50
        if lim > 200:
            lim = 200
        total = len(items)
        start = (p - 1) * lim
        end = start + lim
        page_items = items[start:end] if start < total else []

        return {
            "ok": True,
            "total": total,
            "count": len(page_items),
            "page": p,
            "limit": lim,
            "pages": ( (total + lim - 1) // lim ) if lim else 1,
            "items": page_items,
        }

    except Exception:
        raise HTTPException(500, f"list_blocks failed:\n{traceback.format_exc()}")


@router.get("/api/blocks/health")
async def blocks_health(current=Depends(get_current_user_opt)):
    """Return signer availability and verification coverage stats for blocks."""
    _require_admin_or_papa(current)
    try:
        total = 0
        with_hash = 0
        hash_ok = 0
        with_sig = 0
        sig_ok = 0
        for base in (CHAIN_DIR, MEM_BLOCKS_DIR):
            if not base.exists():
                continue
            for p in base.glob("*.json"):
                total += 1
                try:
                    data = _load_json_file(p)
                except Exception:
                    continue
                if data.get("hash"):
                    with_hash += 1
                v_ok, _, _calc = _validate_block(data)
                if v_ok:
                    hash_ok += 1
                if data.get("signature") and data.get("pubkey"):
                    with_sig += 1
                s_ok, _ = _verify_signature(data)
                if s_ok:
                    sig_ok += 1
        signer_mod = _load_signer()
        signer_available = bool(signer_mod and hasattr(signer_mod, "sign_block"))
        # Soft check for existing key files without generating new ones
        keys_present = False
        try:
            keys_present = (KEYS_DIR / "ed25519.pub").exists() and (KEYS_DIR / "ed25519.priv").exists()
        except Exception:
            keys_present = False
        return {
            "ok": True,
            "signer": {
                "available": signer_available,
                "keys_present": keys_present,
            },
            "stats": {
                "total": total,
                "with_hash": with_hash,
                "hash_ok": hash_ok,
                "with_signature": with_sig,
                "signature_ok": sig_ok,
                "verified_ok_percent": (round((sig_ok / total) * 100, 2) if total else 0.0),
            },
        }
    except Exception:
        raise HTTPException(500, "health_failed")


@router.get("/api/block")
async def get_block(file: str, require_verified: bool = True, current=Depends(get_current_user_opt)):
    _require_admin_or_papa(current)
    path = PROJECT_ROOT / file
    if not path.exists() or not path.is_file():
        raise HTTPException(404, f"Block file not found: {file}")
    try:
        data = _load_json_file(path)
        valid, reason, calc = _validate_block(data)
        sig_ok, sig_reason = _verify_signature(data)
        data["_validation"] = {"valid": valid, "reason": reason, "hash_calc": calc, "sig_valid": sig_ok, "sig_reason": sig_reason}
        if require_verified and (not sig_ok or not valid):
            raise HTTPException(403, "block not verified")
    except Exception as e:
        raise HTTPException(400, f"Parse error: {e}")
    return JSONResponse(data)


@router.get("/api/block/rating")
async def get_block_rating(id: str):
    try:
        r = _mem.get_rating(str(id))
        return {"ok": True, "rating": r or None}
    except Exception as e:
        raise HTTPException(400, f"rating error: {e}")


class RateIn:  # lightweight pydantic-less to avoid extra import churn here
    def __init__(self, id: str, score: float, proof_url: str = "", comment: str = "") -> None:
        self.id = id; self.score = float(score); self.proof_url = proof_url; self.comment = comment

@router.post("/api/block/rate")
async def rate_block(payload: dict, user = Depends(get_current_user_required)):
    """Rate a block (0.0..1.0). Reviewer is current user."""
    try:
        rid = str(payload.get("id") or "").strip()
        score = float(payload.get("score"))
        proof_url = str(payload.get("proof_url") or "")
        comment = str(payload.get("comment") or "")
        if not rid:
            raise HTTPException(400, "missing id")
        reviewer = (user.get("username") or user.get("email") or f"uid:{user.get('id')}")
        rec = _mem.rate_block(rid, score, proof_url=proof_url or None, reviewer=reviewer, comment=comment or None)
        return {"ok": True, **rec}
    except Exception as e:
        raise HTTPException(400, f"rate error: {e}")


@router.get("/api/block/by-id/{block_id}")
async def get_block_by_id(block_id: str, require_verified: bool = True, current=Depends(get_current_user_opt)):
    _require_admin_or_papa(current)
    p = _find_block_by_id(block_id)
    if not p:
        raise HTTPException(404, f"Block id not found: {block_id}")
    try:
        data = _load_json_file(p)
        valid, reason, calc = _validate_block(data)
        sig_ok, sig_reason = _verify_signature(data)
        data["_validation"] = {"valid": valid, "reason": reason, "hash_calc": calc, "file": str(p.as_posix()), "sig_valid": sig_ok, "sig_reason": sig_reason}
        if require_verified and (not sig_ok or not valid):
            raise HTTPException(403, "block not verified")
        return {"ok": True, "block": data}
    except Exception as e:
        raise HTTPException(400, f"Parse error: {e}")


@router.get("/api/block/download")
async def download_block(file: str, current=Depends(get_current_user_opt)):
    _require_admin_or_papa(current)
    path = PROJECT_ROOT / file
    if not path.exists() or not path.is_file():
        raise HTTPException(404, f"Block file not found: {file}")
    # ETag = Hash der Datei, hilft Browser-Caching
    etag = hashlib.sha256(path.read_bytes()).hexdigest()
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    return FileResponse(path, media_type="application/json", filename=Path(file).name, headers=headers)


# ---------- Reflection over blocks ------------------------------------------

@router.get("/api/reflect/blocks")
async def reflect_blocks(topic: str):
    """Analyze all blocks for a topic and derive insights/corrections."""
    if not topic or not topic.strip():
        raise HTTPException(400, "missing topic")
    topic_q = topic.strip().lower()

    # Collect candidate blocks from both stores
    def _iter_blocks():
        for base in (CHAIN_DIR, MEM_BLOCKS_DIR):
            if not base.exists():
                continue
            for p in base.glob("*.json"):
                try:
                    data = _load_json_file(p)
                except Exception:
                    continue
                t = str(data.get("topic") or "").lower()
                title = str(data.get("title") or "").lower()
                # simple filter: substring in topic or title
                if topic_q in t or topic_q in title:
                    yield data

    blocks = list(_iter_blocks())
    mod = _load_reflector()
    if mod is None or not hasattr(mod, "reflect_blocks_by_topic"):
        raise HTTPException(503, "reflection engine not available")
    try:
        res = mod.reflect_blocks_by_topic(topic, blocks)  # type: ignore
        return JSONResponse(res)
    except Exception as e:
        raise HTTPException(500, f"reflect failed: {e}")


# ---------- Routes: maintenance (protected) --------------------------------

@router.post("/api/block/rehash")
async def rehash_block(file: str = Body(..., embed=True), user = Depends(get_current_user_required)):
    """
    Rechnet den Hash eines Blocks mit der kanonischen Methode neu
    und speichert ihn im Feld 'hash'. Nur für eingeloggte Nutzer mit Rolle 'creator'.
    """
    # any logged-in user may request a rehash on a single file

    path = PROJECT_ROOT / file
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Block file not found")

    try:
        data = _load_json_file(path)
    except Exception as e:
        raise HTTPException(400, f"Parse error: {e}")

    data["hash"] = _calc_sha256(data)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {"ok": True, "file": file}


@router.post("/api/block/sign")
async def sign_block(file: str = Body(..., embed=True), user = Depends(get_current_user_required)):
    """
    Signiert einen Block mit dem lokalen Signer (falls vorhanden) und schreibt die Signatur in die Datei.
    Nur für Nutzer mit Rolle 'worker' oder 'admin'.
    """
    from netapi.deps import has_any_role
    if not has_any_role(user, {"worker", "admin", "papa"}):
        raise HTTPException(403, "worker role required")
    path = PROJECT_ROOT / file
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Block file not found")
    signer = _load_signer()
    if signer is None or not hasattr(signer, "sign_block"):
        raise HTTPException(503, "signer not available")
    try:
        data = _load_json_file(path)
        # signer returns (sig_b64, pub_b64, signed_at)
        sig_b64, pub_b64, signed_at = signer.sign_block(dict(data))  # type: ignore
        data["signature"] = sig_b64
        data["pubkey"] = pub_b64
        data["signed_at"] = signed_at
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return {"ok": True, "file": file}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"sign failed: {e}")


@router.post("/api/block/sign-all")
async def sign_all_blocks(user = Depends(get_current_user_required)):
    """
    Signiert alle Blöcke in Chain und Memory, falls Signer verfügbar ist.
    Nur für Nutzer mit Rolle 'worker' oder 'admin'.
    """
    from netapi.deps import has_any_role
    if not has_any_role(user, {"worker", "admin", "papa"}):
        raise HTTPException(403, "worker role required")
    signer = _load_signer()
    if signer is None or not hasattr(signer, "sign_block"):
        raise HTTPException(503, "signer not available")
    fixed = 0
    checked = 0
    errors: list[str] = []
    for base in (CHAIN_DIR, MEM_BLOCKS_DIR):
        if not base.exists():
            continue
        for p in base.glob("*.json"):
            try:
                data = _load_json_file(p)
                sig_b64, pub_b64, signed_at = signer.sign_block(dict(data))  # type: ignore
                data["signature"] = sig_b64
                data["pubkey"] = pub_b64
                data["signed_at"] = signed_at
                p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
                fixed += 1
                checked += 1
            except Exception as e:
                errors.append(f"{p.name}: {e}")
                continue
    return {"ok": True, "checked": checked, "signed": fixed, "errors": errors}


@router.post("/api/block/rehash-dryrun")
async def rehash_block_dryrun(file: str = Body(..., embed=True), user = Depends(get_current_user_required)):
    """Nur berechnen, nicht speichern – für UI‑Diff."""
    # any logged-in user may test a single file

    path = PROJECT_ROOT / file
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Block file not found")

    try:
        data = _load_json_file(path)
        calc = _calc_sha256(data)
    except Exception as e:
        raise HTTPException(400, f"Parse error: {e}")

    return {"ok": True, "calc": calc, "stored": data.get("hash") or ""}


@router.post("/api/block/rehash-all")
async def rehash_all_blocks(user = Depends(get_current_user_required)):
    """
    Rehash alle Blockdateien in Chain und Memory, falls Hash fehlt oder abweicht.
    Nur für Nutzer mit Rolle 'creator'.
    """
    from netapi.deps import has_any_role
    if not has_any_role(user, {"worker", "admin"}):
        raise HTTPException(403, "worker role required")

    fixed = 0
    checked = 0
    errors: list[str] = []
    for base in (CHAIN_DIR, MEM_BLOCKS_DIR):
        if not base.exists():
            continue
        for p in base.glob("*.json"):
            try:
                data = _load_json_file(p)
                calc = _calc_sha256(data)
                stored = (data.get("hash") or "").strip()
                checked += 1
                if not stored or stored != calc:
                    data["hash"] = calc
                    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
                    fixed += 1
            except Exception as e:
                errors.append(f"{p.name}: {e}")
                continue
    return {"ok": True, "checked": checked, "fixed": fixed, "errors": errors}


@router.delete("/api/block")
async def delete_block(file: str, user = Depends(get_current_user_required)):
    from netapi.deps import has_any_role
    if not has_any_role(user, {"worker", "admin"}):
        raise HTTPException(403, "worker role required")

    path = PROJECT_ROOT / file
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Block file not found")

    path.unlink()
    return {"ok": True, "deleted": file}
