from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json, os, signal, subprocess, sys, secrets, hashlib, time
from datetime import datetime

from netapi.deps import get_current_user_required

router = APIRouter(prefix="/api/subminds", tags=["subminds"])

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))).resolve()
SUBM_DIR = KI_ROOT / "subminds"
RUNTIME_DIR = KI_ROOT / "system" / "submind_runtime"
SUBM_DIR.mkdir(parents=True, exist_ok=True)
CALLBACKS_DIRNAME = "callbacks"
LEASES_DIRNAME = "leases"


def _require_admin(user: Dict[str, Any]) -> str:
    role = (user.get("role") or "user").lower()
    if role not in ("admin", "creator"):
        raise HTTPException(403, "admin/creator required")
    return role


def _list_dirs(base: Path) -> List[Path]:
    return [p for p in base.iterdir() if p.is_dir()]


def _proc_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


class RegisterIn(BaseModel):
    submind_id: str = Field(min_length=3, max_length=40)
    role: str = Field(default="child")
    description: Optional[str] = None


@router.get("")
def list_subminds(user = Depends(get_current_user_required)):
    # Sichtbar für eingeloggte Nutzer; Admin/Creator sehen PIDs
    role = (user.get("role") or "user").lower()
    items: List[Dict[str, Any]] = []
    for d in _list_dirs(SUBM_DIR):
        cfg = d / "config.json"
        meta = {"id": d.name, "path": str(d)}
        if cfg.exists():
            try:
                j = json.loads(cfg.read_text(encoding="utf-8"))
                meta.update({
                    "role": j.get("role") or j.get("submind_role"),
                    "description": j.get("description"),
                })
            except Exception:
                pass
        pidf = d / "run.pid"
        if role in ("admin","creator") and pidf.exists():
            try:
                pid = int(pidf.read_text().strip())
                meta["pid"] = pid
                meta["alive"] = _proc_alive(pid)
            except Exception:
                meta["alive"] = False
        # last heartbeat
        try:
            hb = d / "heartbeat.json"
            if hb.exists():
                import json as _json
                jhb = _json.loads(hb.read_text(encoding='utf-8'))
                if isinstance(jhb, dict) and jhb.get('ts'):
                    meta['last_heartbeat'] = int(jhb.get('ts'))
        except Exception:
            pass
        # Reputation (Durchschnitt über Blöcke mit Tag submind:<id>)
        try:
            from netapi import memory_store as _mem
            # META enthält Zuordnung id->tags
            meta_idx_path = Path(_mem.META_PATH)
            j = json.loads(meta_idx_path.read_text(encoding='utf-8')) if meta_idx_path.exists() else {}
            total = 0.0; cnt = 0
            for bid, m in j.items():
                tags = (m.get('tags') or [])
                if any((isinstance(t,str) and t.lower()==f"submind:{d.name}".lower()) for t in tags):
                    r = _mem.get_rating(bid)
                    if r and r.get('count',0)>0:
                        total += float(r.get('avg',0.0)) * int(r.get('count',0))
                        cnt += int(r.get('count',0))
            if cnt>0:
                meta['reputation_avg'] = round(total/max(cnt,1)/1.0, 4)
                meta['reputation_count'] = cnt
        except Exception:
            pass
        items.append(meta)
    return {"count": len(items), "items": items}


@router.post("")
def register_submind(body: RegisterIn, user = Depends(get_current_user_required)):
    _require_admin(user)
    sid = body.submind_id.strip()
    target = SUBM_DIR / sid
    if target.exists():
        raise HTTPException(409, "submind already exists")
    target.mkdir(parents=True)
    # Provisioniere Runtime-Skelet
    api_key = secrets.token_urlsafe(32)
    api_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    cfg = {
        "submind_id": sid,
        "role": body.role,
        "description": body.description or "",
        "parent_endpoint": "/api",
        "api_key_hash": api_hash,
        "created_at": int(time.time()),
    }
    (target / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    # Kopiere Runtime Listener, falls vorhanden
    try:
        for fname in ("runtime_listener.py",):
            src = RUNTIME_DIR / fname
            if src.exists():
                (target / fname).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass
    return {"ok": True, "id": sid, "api_key": api_key}


@router.post("/{submind_id}/start")
def start_submind(submind_id: str, user = Depends(get_current_user_required)):
    _require_admin(user)
    d = SUBM_DIR / submind_id
    if not d.exists():
        raise HTTPException(404, "submind not found")
    pidf = d / "run.pid"
    if pidf.exists():
        try:
            pid = int(pidf.read_text().strip())
            if _proc_alive(pid):
                return {"ok": True, "pid": pid, "alive": True}
        except Exception:
            pass
    # starte Python Listener im Hintergrund
    listener = d / "runtime_listener.py"
    if not listener.exists():
        raise HTTPException(400, "runtime listener missing")
    proc = subprocess.Popen([sys.executable, str(listener)], cwd=str(d), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pidf.write_text(str(proc.pid), encoding="utf-8")
    return {"ok": True, "pid": proc.pid}


@router.post("/{submind_id}/stop")
def stop_submind(submind_id: str, user = Depends(get_current_user_required)):
    _require_admin(user)
    d = SUBM_DIR / submind_id
    pidf = d / "run.pid"
    if not pidf.exists():
        return {"ok": True, "stopped": False}
    try:
        pid = int(pidf.read_text().strip())
    except Exception:
        pidf.unlink(missing_ok=True)
        return {"ok": True, "stopped": False}
    try:
        os.kill(pid, signal.SIGTERM)
        pidf.unlink(missing_ok=True)
        return {"ok": True, "stopped": True}
    except Exception:
        return {"ok": False, "stopped": False}


# -------------- API Key Management -----------------------------------------

def _read_cfg(sid: str) -> Tuple[Path, Dict[str, Any]]:
    d = SUBM_DIR / sid
    if not d.exists():
        raise HTTPException(404, "submind not found")
    cfgp = d / "config.json"
    if not cfgp.exists():
        raise HTTPException(500, "submind config missing")
    try:
        return d, json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"invalid config: {e}")


@router.post("/{submind_id}/key/rotate")
def rotate_key(submind_id: str, user = Depends(get_current_user_required)):
    _require_admin(user)
    d, cfg = _read_cfg(submind_id)
    api_key = secrets.token_urlsafe(32)
    api_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    cfg["api_key_hash"] = api_hash
    cfg["rotated_at"] = int(time.time())
    (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "api_key": api_key}


def _auth_submind(sid: str, key: Optional[str]) -> Dict[str, Any]:
    if not key:
        raise HTTPException(401, "missing submind key")
    _, cfg = _read_cfg(sid)
    want = (cfg.get("api_key_hash") or "").strip()
    if not want:
        raise HTTPException(403, "submind not provisioned for API key")
    got = hashlib.sha256(key.encode("utf-8")).hexdigest()
    if got != want:
        raise HTTPException(401, "invalid submind key")
    return cfg

# ---------------------
# Callback & Task Status
# ---------------------

class CallbackIn(BaseModel):
    task_id: str = Field(min_length=3, max_length=120)
    status: str = Field(min_length=2)  # e.g., 'progress' | 'done' | 'failed'
    result: Optional[Any] = None
    progress: Optional[float] = None  # 0..1
    lease: Optional[str] = None
    error: Optional[str] = None

def _dir_callbacks(sid: str) -> Path:
    d = SUBM_DIR / sid / CALLBACKS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def _dir_leases(sid: str) -> Path:
    d = SUBM_DIR / sid / LEASES_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d

def _now_iso() -> str:
    try:
        return datetime.utcnow().isoformat() + "Z"
    except Exception:
        return str(int(time.time()))

def _short_preview(obj: Any, max_len: int = 160) -> str:
    try:
        if isinstance(obj, str):
            s = obj.strip()
        else:
            s = json.dumps(obj, ensure_ascii=False)[:max_len]
        if len(s) > max_len:
            return s[:max_len-1] + "…"
        return s
    except Exception:
        return ""

def _publish_event(evt: Dict[str, Any]) -> None:
    # Best-effort publish via system.events_bus
    try:
        from importlib.machinery import SourceFileLoader as _Loader
        bus = _Loader("events_bus", str(KI_ROOT / "system" / "events_bus.py")).load_module()  # type: ignore
        if hasattr(bus, "publish"):
            bus.publish(evt)  # type: ignore
    except Exception:
        pass

def _verify_lease(sid: str, task_id: str, lease: Optional[str]) -> bool:
    # If a lease exists, require match; else accept
    try:
        lp = _dir_leases(sid) / f"{task_id}.json"
        if not lp.exists():
            return True
        j = json.loads(lp.read_text(encoding="utf-8"))
        want = str(j.get("lease") or "").strip()
        got = str(lease or "").strip()
        return (not want) or (want == got)
    except Exception:
        return False

@router.post("/{submind_id}/callback")
def submind_callback(
    submind_id: str,
    payload: CallbackIn,
    x_submind_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    # Authenticate
    key = x_submind_key
    if not key and authorization and authorization.lower().startswith("bearer "):
        key = authorization.split(" ", 1)[1].strip()
    _auth_submind(submind_id, key)

    # Verify lease if managed
    if not _verify_lease(submind_id, payload.task_id, payload.lease):
        raise HTTPException(409, "lease_mismatch")

    cb_dir = _dir_callbacks(submind_id)
    path = cb_dir / f"{payload.task_id}.json"
    record: Dict[str, Any] = {
        "task_id": payload.task_id,
        "status": payload.status,
        "progress": payload.progress,
        "result": payload.result,
        "error": payload.error,
        "ts": int(time.time()),
        "updated_at": _now_iso(),
    }
    # Idempotency: if same status/result already recorded, keep first write
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if old.get("status") == payload.status and json.dumps(old.get("result"), sort_keys=True, ensure_ascii=False) == json.dumps(payload.result, sort_keys=True, ensure_ascii=False):
                return {"ok": True, "stored": False, "path": str(path)}
        except Exception:
            pass
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # Publish event for UI
    _publish_event({
        "type": "submind_result",
        "submind": submind_id,
        "task_id": payload.task_id,
        "status": payload.status,
        "ts": int(time.time()),
        "preview": _short_preview(payload.result),
    })
    return {"ok": True, "stored": True, "path": str(path)}

class StatusIn(BaseModel):
    task_id: str = Field(min_length=3, max_length=120)
    status: str = Field(min_length=2)
    progress: Optional[float] = None
    lease: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

@router.post("/{submind_id}/status")
def submind_status(
    submind_id: str,
    payload: StatusIn,
    x_submind_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    key = x_submind_key
    if not key and authorization and authorization.lower().startswith("bearer "):
        key = authorization.split(" ", 1)[1].strip()
    _auth_submind(submind_id, key)
    if not _verify_lease(submind_id, payload.task_id, payload.lease):
        raise HTTPException(409, "lease_mismatch")
    cb_dir = _dir_callbacks(submind_id)
    path = cb_dir / f"{payload.task_id}.json"
    rec = {
        "task_id": payload.task_id,
        "status": payload.status,
        "progress": payload.progress,
        "meta": payload.meta or {},
        "updated_at": _now_iso(),
    }
    try:
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            old.update(rec)
            rec = old
    except Exception:
        pass
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _publish_event({"type": "submind_status", "submind": submind_id, "task_id": payload.task_id, "status": payload.status, "progress": payload.progress, "ts": int(time.time())})
    return {"ok": True}

@router.get("/{submind_id}/task/{task_id}")
def get_task_record(submind_id: str, task_id: str, user = Depends(get_current_user_required)):
    # Admin or creator required to read raw records
    _require_admin(user)
    p = _dir_callbacks(submind_id) / f"{task_id}.json"
    if not p.exists():
        raise HTTPException(404, "not found")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"parse error: {e}")


class LeaseIn(BaseModel):
    task_id: str = Field(min_length=3, max_length=120)
    ttl_seconds: int = Field(default=900, ge=60, le=24*3600)

@router.post("/{submind_id}/lease")
def issue_lease(submind_id: str, payload: LeaseIn, user = Depends(get_current_user_required)):
    """Issue a lease token for a task to a submind (admin/creator only)."""
    _require_admin(user)
    lid = secrets.token_urlsafe(24)
    lp = _dir_leases(submind_id) / f"{payload.task_id}.json"
    now = int(time.time())
    rec = {
        "task_id": payload.task_id,
        "lease": lid,
        "issued_at": now,
        "expires_at": now + int(payload.ttl_seconds),
        "submind": submind_id,
        "status": "issued",
    }
    lp.write_text(json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"ok": True, "task_id": payload.task_id, "lease": lid, "expires_at": rec["expires_at"]}


class IngestItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    url: Optional[str] = None
    tags: Optional[List[str]] = None

class IngestIn(BaseModel):
    items: List[IngestItem] = Field(default_factory=list)


def _audit_submind(event: Dict[str, Any]) -> None:
    try:
        logdir = KI_ROOT / "logs"; logdir.mkdir(parents=True, exist_ok=True)
        (logdir / "audit_submind.jsonl").open("a", encoding="utf-8").write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


@router.post("/{submind_id}/ingest")
def ingest(submind_id: str, payload: IngestIn, x_submind_key: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    # Key aus Header ziehen: bevorzugt X-Submind-Key, sonst Bearer
    key = x_submind_key
    if not key and authorization and authorization.lower().startswith("bearer "):
        key = authorization.split(" ", 1)[1].strip()
    cfg = _auth_submind(submind_id, key)

    if not payload.items:
        raise HTTPException(400, "no items")
    try:
        from netapi import memory_store as _mem
    except Exception:
        raise HTTPException(500, "memory unavailable")

    ids: List[str] = []
    for it in payload.items:
        tags = list(it.tags or [])
        # mark as submind contribution
        tags.append(f"submind:{submind_id}")
        # einfache Signatur: sha256(content + api_hash)
        api_hash = cfg.get('api_key_hash') or ''
        sig = hashlib.sha256((it.content.strip() + api_hash).encode('utf-8')).hexdigest()
        meta = {"source":"submind","author": submind_id, "signature": sig}
        bid = _mem.add_block(title=it.title.strip(), content=it.content.strip(), tags=tags, url=it.url, meta=meta)
        if isinstance(bid, str):
            ids.append(bid)
            # optional: automatische Verfeinerung/Abgleich
            try:
                _mem.auto_update_block(bid)
            except Exception:
                pass

    _audit_submind({
        "ts": int(time.time()),
        "submind": submind_id,
        "count": len(ids),
        "ids": ids[:10],
    })
    return {"ok": True, "imported": len(ids), "ids": ids}


@router.get("/reputation")
def submind_reputation(submind_id: Optional[str] = None, user = Depends(get_current_user_required)):
    """Aggregiert Bewertungen pro Submind (über Tags 'submind:<id>')."""
    try:
        from netapi import memory_store as _mem
        meta_idx_path = Path(_mem.META_PATH)
        meta = json.loads(meta_idx_path.read_text(encoding='utf-8')) if meta_idx_path.exists() else {}
        acc: Dict[str, Dict[str, float]] = {}
        cnts: Dict[str, int] = {}
        # Sammle gewichtete Summen (avg*count) pro Submind
        for bid, m in meta.items():
            tags = (m.get('tags') or [])
            sid = None
            for t in tags:
                if isinstance(t, str) and t.lower().startswith('submind:'):
                    sid = t.split(':',1)[1].lower(); break
            if not sid:
                continue
            if submind_id and sid.lower() != submind_id.lower():
                continue
            r = _mem.get_rating(bid)
            if r and r.get('count',0)>0:
                w = float(r.get('avg',0.0)) * int(r.get('count',0))
                acc[sid] = {"sum": acc.get(sid, {}).get("sum", 0.0) + w}
                cnts[sid] = cnts.get(sid, 0) + int(r.get('count',0))
        items = []
        for sid, s in acc.items():
            c = max(1, cnts.get(sid,0))
            items.append({"submind": sid, "avg": round(s.get('sum',0.0)/c, 4), "count": cnts.get(sid,0)})
        # include subminds without ratings as zero-count
        if not submind_id:
            for d in _list_dirs(SUBM_DIR):
                sid = d.name.lower()
                if not any(x['submind']==sid for x in items):
                    items.append({"submind": sid, "avg": 0.0, "count": 0})
        items.sort(key=lambda x: x['avg'], reverse=True)
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(500, f"reputation error: {e}")


@router.post("/{submind_id}/heartbeat")
def heartbeat(submind_id: str, x_submind_key: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    """Submind heartbeat – authenticated via submind key.
    Stores a small heartbeat.json with ts and optional meta.
    """
    cfg = _auth_submind(submind_id, x_submind_key or (authorization.split(" ",1)[1] if (authorization or '').lower().startswith('bearer ') else None))
    d, _ = _read_cfg(submind_id)
    try:
        import json as _json, time as _time
        payload = {"ts": int(_time.time())}
        (d / "heartbeat.json").write_text(_json.dumps(payload), encoding='utf-8')
        return {"ok": True, **payload}
    except Exception as e:
        raise HTTPException(500, f"heartbeat failed: {e}")
