from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel
from typing import Any, Dict, Optional, Literal, Iterator
from netapi.deps import get_current_user_required, require_role
from netapi.db import SessionLocal
from netapi.models import Device, DeviceEvent
from netapi.models import KnowledgeBlock  # 4B integration
try:
    from netapi.modules.admin.router import write_audit  # type: ignore
except Exception:
    def write_audit(*args, **kwargs):  # type: ignore
        return None
import time
import os, hashlib, secrets
import json
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import text as _t

from .capabilities import allowed_caps
from . import syscalls as sc

router = APIRouter(prefix="/os", tags=["os"])

class SysIn(BaseModel):
    name: Literal["fs.read","web.get","proc.run","mem.store","mem.recall","notify.send"]
    args: Dict[str, Any] = {}


@router.get("/me")
def whoami(user = Depends(get_current_user_required)):
    # Return a minimal identity snapshot for UI
    return {
        "ok": True,
        "id": int(user.get("id") or 0),
        "username": str(user.get("username") or ""),
        "role": str(user.get("role") or "user"),
        "tier": str(user.get("tier") or user.get("role") or "user"),
    }

@router.get("/caps")
def get_caps(user = Depends(get_current_user_required)):
    role = (user.get("role") or "user").lower()
    return {"role": role, "caps": allowed_caps(role)}

@router.post("/syscall")
def syscall(body: SysIn, user = Depends(get_current_user_required)):
    role = (user.get("role") or "user").lower()
    try:
        if body.name == "fs.read":
            return sc.sc_fs_read(role, **body.args)
        if body.name == "web.get":
            return sc.sc_web_get(role, **body.args)
        if body.name == "proc.run":
            return sc.sc_proc_run(role, **body.args)
        if body.name == "mem.store":
            return sc.sc_mem_store(role, **body.args)
        if body.name == "mem.recall":
            return sc.sc_mem_recall(role, **body.args)
        if body.name == "notify.send":
            return sc.sc_notify_send(role, **body.args)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except TypeError as e:
        raise HTTPException(400, f"bad args: {e}")
    raise HTTPException(400, f"unknown syscall: {body.name}")


# --- Devices (Papa OS) ------------------------------------------------------

class DeviceIn(BaseModel):
    name: str
    os: str = ""
    owner_id: Optional[int] = None


@router.get("/devices")
def devices_list(user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    with SessionLocal() as db:
        rows = db.query(Device).order_by(Device.id.desc()).limit(200).all()
        items = [{
            "id": d.id,
            "name": d.name or "",
            "os": d.os or "",
            "owner_id": int(d.owner_id or 0),
            "status": d.status or "unknown",
            "last_seen": int(d.last_seen or 0),
            "token_hint": d.token_hint or "",
            "issued_at": int(d.issued_at or 0),
            "last_auth_at": int(d.last_auth_at or 0),
            "revoked_at": int(d.revoked_at or 0),
            "last_event_delivered": int((db.query(DeviceEvent.delivered_at).filter(DeviceEvent.device_id==d.id, DeviceEvent.delivered_at>0).order_by(DeviceEvent.delivered_at.desc()).limit(1).scalar() or 0)),
            "last_event_queued": int((db.query(DeviceEvent.ts).filter(DeviceEvent.device_id==d.id).order_by(DeviceEvent.ts.desc()).limit(1).scalar() or 0)),
            "events_queued": int((db.query(DeviceEvent).filter(DeviceEvent.device_id==d.id, DeviceEvent.delivered_at==0).count() or 0)),
            "events_pruned": int(getattr(d, 'events_pruned_total', 0) or 0),
            "last_ack_ts": int(getattr(d, 'last_ack_ts', 0) or 0),
            "last_ack_type": str(getattr(d, 'last_ack_type', '') or ''),
            "last_ack_status": str(getattr(d, 'last_ack_status', '') or ''),
        } for d in rows]
        return {"ok": True, "items": items}


@router.post("/devices")
def devices_add(body: DeviceIn, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    now = int(time.time())
    with SessionLocal() as db:
        # issue token (one-time plaintext)
        token = secrets.token_urlsafe(24)  # ~32 chars
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        hint = token[:8]
        d = Device(
            name=(body.name or "").strip()[:120],
            os=(body.os or "").strip()[:60],
            owner_id=int(body.owner_id or user.get("id") or 0),
            status="unknown",
            last_seen=0,
            created_at=now,
            updated_at=now,
            token_hash=token_hash,
            token_hint=hint,
            issued_at=now,
            last_auth_at=0,
            revoked_at=0,
        )
        db.add(d); db.commit(); db.refresh(d)
        # Audit
        try:
            write_audit("device_add", actor_id=int(user.get("id") or 0), target_type="device", target_id=int(d.id or 0), meta={"name": d.name, "os": d.os})
        except Exception:
            pass
        return {"ok": True, "id": d.id, "token": token, "token_hint": hint}


@router.delete("/devices/{dev_id}")
def devices_remove(dev_id: int, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    with SessionLocal() as db:
        d = db.query(Device).filter(Device.id == int(dev_id)).first()
        if not d:
            raise HTTPException(404, "device not found")
        db.delete(d); db.commit()
        # Audit
        try:
            write_audit("device_remove", actor_id=int(user.get("id") or 0), target_type="device", target_id=int(dev_id or 0), meta={"name": d.name, "os": d.os})
        except Exception:
            pass
        return {"ok": True}


@router.get("/devices/stats")
def devices_stats(hours: int = 24, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    hours = max(1, min(int(hours or 24), 720))  # up to 30 days
    since = int(time.time()) - hours * 3600
    with SessionLocal() as db:
        try:
            rows = db.bind.execute(_t(
                "SELECT ts_hour, queued_total, pruned_total FROM device_events_stats WHERE ts_hour >= :s ORDER BY ts_hour ASC"
            ), {"s": since - (since % 3600)}).fetchall()
        except Exception:
            rows = []
        items = [
            {
                "ts_hour": int(r[0]),
                "queued_total": int(r[1]),
                "pruned_total": int(r[2]),
            } for r in rows
        ]
        # compute delta vs ~24h ago if data exists
        dq = 0; dp = 0
        if items:
            now_q = items[-1]["queued_total"]
            now_p = items[-1]["pruned_total"]
            # find the first point >= now-24h (or the earliest available)
            target = int(time.time()) - 24*3600
            base = items[0]
            for it in items:
                if it["ts_hour"] >= target:
                    base = it
                    break
            dq = now_q - int(base.get("queued_total", 0))
            dp = now_p - int(base.get("pruned_total", 0))
        return {"ok": True, "items": items, "delta_24h": {"queued": int(dq), "pruned": int(dp)}}


# --- Device Events / SSE ----------------------------------------------------

class PushEventIn(BaseModel):
    type: str = "message"
    payload: Dict[str, Any] = {}


@router.post("/devices/{dev_id}/events")
def devices_push_event(dev_id: int, body: PushEventIn, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    now = int(time.time())
    with SessionLocal() as db:
        d = db.query(Device).filter(Device.id==int(dev_id)).first()
        if not d:
            raise HTTPException(404, "device not found")
        payload_json = json.dumps(body.payload or {})
        ev = DeviceEvent(device_id=int(dev_id), ts=now, type=(body.type or "message")[:40], payload=payload_json, delivered_at=0)
        db.add(ev); db.commit(); db.refresh(ev)
        # 4B: write knowledge block for relevant device events
        try:
            kind_map = {"log_upload":"log", "config_update":"config", "message":"note"}
            ktype = kind_map.get((ev.type or "").lower())
            # Extract simple text if provided in payload
            try:
                payload_obj = json.loads(payload_json or "{}")
            except Exception:
                payload_obj = {}
            text = ""
            for key in ("text","content","message","log"):
                v = payload_obj.get(key)
                if isinstance(v, str) and v.strip():
                    text = v.strip()
                    break
            if ktype or text:
                now2 = int(time.time())
                source = f"device:{int(dev_id)}"
                ktype2 = (ktype or (ev.type or "note")).lower()[:60]
                tags = ["device", f"device:{int(dev_id)}", f"os:{(d.os or '').lower()}"]
                content = text or f"Device event {ev.type} at {now2}"
                # dedupe by hash
                import hashlib as _hl
                tags_csv = ",".join(sorted(set(t for t in tags if t)))
                h = _hl.sha256((source+"\n"+ktype2+"\n"+tags_csv+"\n"+content).encode("utf-8")).hexdigest()
                row = db.query(KnowledgeBlock).filter(KnowledgeBlock.hash == h).first()
                if row:
                    row.ts = now2; row.updated_at = now2
                else:
                    kb = KnowledgeBlock(ts=now2, source=source[:120], type=ktype2, tags=tags_csv[:400], content=content, hash=h, created_at=now2, updated_at=now2)
                    db.add(kb)
                db.commit()
        except Exception:
            pass
        try:
            write_audit("device_event_push", actor_id=int(user.get("id") or 0), target_type="device", target_id=int(dev_id or 0), meta={"type": ev.type, "payload_size": len(payload_json)})
        except Exception:
            pass
        return {"ok": True, "id": int(ev.id)}


@router.get("/devices/{dev_id}/events")
def devices_events_stream(dev_id: int, request: Request, authorization: Optional[str] = Header(default=None)):
    # Bearer token required unless localhost bypass is active and request is local
    try:
        host = (request.client.host if request.client else "") or ""
    except Exception:
        host = ""
    require_local = (os.getenv("OS_DEVICES_LOCALHOST_REQUIRES_TOKEN", "0") == "1")
    is_local = host in {"127.0.0.1", "::1", "localhost"}
    with SessionLocal() as db:
        d = db.query(Device).filter(Device.id == int(dev_id)).first()
        if not d:
            raise HTTPException(404, "device not found")
        if (not is_local) or require_local:
            if not authorization or not authorization.lower().startswith("bearer "):
                raise HTTPException(401, "missing bearer token")
            token = authorization.split(" ", 1)[1].strip()
            th = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if int(d.revoked_at or 0) > 0 or not d.token_hash or th != (d.token_hash or ""):
                raise HTTPException(401, "unauthorized")

    def event_gen() -> Iterator[bytes]:
        last_keepalive = time.time()
        while True:
            # client disconnect?
            if await_disconnect(request):
                break
            try:
                with SessionLocal() as dbi:
                    ev = (
                        dbi.query(DeviceEvent)
                        .filter(DeviceEvent.device_id == int(dev_id), DeviceEvent.delivered_at == 0)
                        .order_by(DeviceEvent.id.asc())
                        .first()
                    )
                    if ev:
                        payload = {
                            "id": int(ev.id),
                            "ts": int(ev.ts or 0),
                            "type": ev.type or "message",
                            "payload": json.loads(ev.payload or "{}")
                        }
                        # mark delivered
                        ev.delivered_at = int(time.time())
                        dbi.add(ev); dbi.commit()
                        data = ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")
                        yield data
                        last_keepalive = time.time()
                        continue
            except Exception:
                pass
            # keepalive comment every 20s
            nowt = time.time()
            if nowt - last_keepalive >= 20:
                yield b": keepalive\n\n"
                last_keepalive = nowt
            time.sleep(0.5)

    def await_disconnect(req: Request) -> bool:
        try:
            return bool(req.client is None or req.is_disconnected())  # type: ignore
        except Exception:
            return False

    return StreamingResponse(event_gen(), media_type="text/event-stream")


class AckIn(BaseModel):
    type: str
    status: str = "ok"  # ok|error|received|processing
    meta: Dict[str, Any] = {}


@router.post("/devices/{dev_id}/ack")
def devices_ack(dev_id: int, body: AckIn, request: Request, authorization: Optional[str] = Header(default=None)):
    # Device acknowledges receipt/processing of a command/event
    try:
        host = (request.client.host if request.client else "") or ""
    except Exception:
        host = ""
    require_local = (os.getenv("OS_DEVICES_LOCALHOST_REQUIRES_TOKEN", "0") == "1")
    is_local = host in {"127.0.0.1", "::1", "localhost"}
    with SessionLocal() as db:
        d = db.query(Device).filter(Device.id == int(dev_id)).first()
        if not d:
            raise HTTPException(404, "device not found")
        if (not is_local) or require_local:
            if not authorization or not authorization.lower().startswith("bearer "):
                raise HTTPException(401, "missing bearer token")
            token = authorization.split(" ", 1)[1].strip()
            th = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if int(d.revoked_at or 0) > 0 or not d.token_hash or th != (d.token_hash or ""):
                raise HTTPException(401, "unauthorized")
        # update device ack fields
        now = int(time.time())
        d.last_ack_ts = now
        d.last_ack_type = (body.type or "")[:40]
        d.last_ack_status = (body.status or "")[:20]
        d.updated_at = now
        db.add(d); db.commit()
        try:
            write_audit("device_ack", actor_id=0, target_type="device", target_id=int(dev_id or 0), meta={"type": d.last_ack_type, "status": d.last_ack_status})
        except Exception:
            pass
        return {"ok": True}


class HeartbeatIn(BaseModel):
    id: int
    status: Optional[str] = None  # ok|warn|offline


@router.post("/devices/heartbeat")
def devices_heartbeat(body: HeartbeatIn, request: Request, authorization: Optional[str] = Header(default=None), user = Depends(get_current_user_required)):
    # Accept localhost heartbeats without token by default; can be disabled via OS_DEVICES_LOCALHOST_REQUIRES_TOKEN=1
    try:
        host = (request.client.host if request.client else "") or ""
    except Exception:
        host = ""
    require_local = (os.getenv("OS_DEVICES_LOCALHOST_REQUIRES_TOKEN", "0") == "1")
    is_local = host in {"127.0.0.1", "::1", "localhost"}
    with SessionLocal() as db:
        d = db.query(Device).filter(Device.id == int(body.id or 0)).first()
        if not d:
            raise HTTPException(404, "device not found")
        # Validate Authorization: Bearer <token> when not localhost or when localhost enforcement is enabled
        if (not is_local) or require_local:
            if not authorization or not authorization.lower().startswith("bearer "):
                raise HTTPException(401, "missing bearer token")
            token = authorization.split(" ", 1)[1].strip()
            if not token:
                raise HTTPException(401, "invalid token")
            th = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if int(d.revoked_at or 0) > 0 or not d.token_hash or th != (d.token_hash or ""):
                raise HTTPException(401, "unauthorized")
            d.last_auth_at = int(time.time())
        d.last_seen = int(time.time())
        if body.status:
            d.status = (body.status or "").strip()[:20]
        d.updated_at = int(time.time())
        db.add(d); db.commit()
        try:
            write_audit("device_heartbeat", actor_id=int(user.get("id") or 0), target_type="device", target_id=int(d.id or 0), meta={"status": d.status})
        except Exception:
            pass
        return {"ok": True}


class RotateIn(BaseModel):
    id: int


@router.post("/devices/rotate")
def devices_rotate(body: RotateIn, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    now = int(time.time())
    token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    hint = token[:8]
    with SessionLocal() as db:
        d = db.query(Device).filter(Device.id == int(body.id or 0)).first()
        if not d:
            raise HTTPException(404, "device not found")
        d.token_hash = token_hash
        d.token_hint = hint
        d.issued_at = now
        d.last_auth_at = 0
        d.revoked_at = 0
        d.updated_at = now
        db.add(d); db.commit()
        try:
            write_audit("device_rotate", actor_id=int(user.get("id") or 0), target_type="device", target_id=int(d.id or 0), meta={"token_hint": hint})
        except Exception:
            pass
        # return plaintext token once
        return {"ok": True, "id": d.id, "token": token, "token_hint": hint}


class RevokeIn(BaseModel):
    id: int


@router.post("/devices/revoke")
def devices_revoke(body: RevokeIn, user = Depends(get_current_user_required)):
    require_role(user, {"creator"})
    now = int(time.time())
    with SessionLocal() as db:
        d = db.query(Device).filter(Device.id == int(body.id or 0)).first()
        if not d:
            raise HTTPException(404, "device not found")
        d.token_hash = ""
        d.token_hint = ""
        d.revoked_at = now
        d.updated_at = now
        db.add(d); db.commit()
        try:
            write_audit("device_revoke", actor_id=int(user.get("id") or 0), target_type="device", target_id=int(d.id or 0))
        except Exception:
            pass
        return {"ok": True}