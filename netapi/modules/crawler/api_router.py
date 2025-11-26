from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from ...deps import get_current_user_required, has_any_role
from .targets import ensure_targets_file, generate_target_id, load_targets, save_targets

try:  # Reuse existing crawler logic (with fallback already handled there)
    from .router import run_crawler_once  # type: ignore
except Exception as exc:  # pragma: no cover - import fallback should already exist
    run_crawler_once = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

router = APIRouter(tags=["crawler-api"])

_CRAWLER_LOCK_PATH = Path("/tmp/kiana_crawler.lock")
_KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
_STATUS_PATH = _KI_ROOT / "system" / "crawler_state.json"
_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)

_state: Dict[str, Any] = {
    "running": False,
    "last_run_ts": 0,
    "last_error": None,
}
_state_lock = asyncio.Lock()
_run_lock = asyncio.Lock()

ensure_targets_file()


_DOMAIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "ki-ana.at": {
        "label": "KI_ana",
        "tags": ["internal", "docs"],
        "interval_sec": 86400,
        "trust": 0.95,
    },
    "static.ki-ana.at": {
        "label": "KI_ana",
        "tags": ["internal", "docs"],
        "interval_sec": 86400,
        "trust": 0.95,
    },
    "bmi.gv.at": {
        "label": "BMI Cybercrime",
        "tags": ["cybercrime", "security", "austria"],
        "interval_sec": 21600,
        "trust": 0.85,
    },
    "bka.de": {
        "label": "BKA Cybercrime",
        "tags": ["cybercrime", "security", "de"],
        "interval_sec": 28800,
        "trust": 0.85,
    },
    "europol.europa.eu": {
        "label": "Europol Cybercrime",
        "tags": ["cybercrime", "security", "eu"],
        "interval_sec": 21600,
        "trust": 0.9,
    },
    "enisa.europa.eu": {
        "label": "ENISA Cybersecurity",
        "tags": ["cybercrime", "security", "eu"],
        "interval_sec": 28800,
        "trust": 0.9,
    },
    "nomoreransom.org": {
        "label": "NoMoreRansom",
        "tags": ["cybercrime", "security"],
        "interval_sec": 28800,
        "trust": 0.85,
    },
    "bbc.com": {
        "label": "BBC World",
        "tags": ["news", "world", "english"],
        "interval_sec": 7200,
        "trust": 0.7,
    },
    "aljazeera.com": {
        "label": "Al Jazeera",
        "tags": ["news", "world", "english"],
        "interval_sec": 7200,
        "trust": 0.7,
    },
    "dw.com": {
        "label": "DW World",
        "tags": ["news", "europe", "english"],
        "interval_sec": 10800,
        "trust": 0.7,
    },
    "thehindu.com": {
        "label": "The Hindu International",
        "tags": ["news", "asia", "english"],
        "interval_sec": 10800,
        "trust": 0.65,
    },
}


def _load_state_from_disk() -> None:
    try:
        if not _STATUS_PATH.exists():
            return
        data = json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        last_ts = int(data.get("last_run_ts") or 0)
        last_error = data.get("last_error")
        _state["last_run_ts"] = max(0, last_ts)
        _state["last_error"] = str(last_error) if last_error not in (None, "") else None
    except Exception:
        # Keep defaults on parse errors
        pass


def _require_admin(user: dict = Depends(get_current_user_required)) -> dict:
    """Allow only Papa/Admin or explicit admin-flagged accounts."""
    if has_any_role(user, {"admin", "papa"}) or bool(user.get("is_papa")) or bool(user.get("is_admin")):
        return user
    raise HTTPException(status_code=403, detail="forbidden")


async def _persist_state() -> None:
    async with _state_lock:
        try:
            payload = {
                "running": bool(_state.get("running", False)),
                "last_run_ts": int(_state.get("last_run_ts") or 0),
                "last_error": _state.get("last_error"),
            }
            _STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def _cleanup_stale_lock() -> None:
    if not _CRAWLER_LOCK_PATH.exists():
        return
    try:
        pid_raw = _CRAWLER_LOCK_PATH.read_text(encoding="utf-8").strip()
        pid = int(pid_raw or "0")
        if pid <= 0:
            raise ValueError("invalid pid")
        os.kill(pid, 0)  # Raises ProcessLookupError if PID no longer exists
    except ProcessLookupError:
        try:
            _CRAWLER_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
    except Exception:
        # For any other parsing/permission issue, do not remove the lock blindly
        pass


def _snapshot() -> Dict[str, Any]:
    running = _run_lock.locked() or bool(_state.get("running", False))
    last_ts = int(_state.get("last_run_ts") or 0)
    err = _state.get("last_error")
    try:
        targets = load_targets()
        target_count = len(targets)
        enabled_count = sum(1 for t in targets if t.get("enabled"))
    except Exception:
        target_count = None
        enabled_count = None
    return {
        "ok": True,
        "running": running,
        "last_run_ts": last_ts,
        "last_error": err if err not in ("", None) else None,
        "target_count": target_count,
        "enabled_targets": enabled_count,
    }


def _clean_tags(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw_list = [x.strip() for x in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        raw_list = [str(x).strip() for x in raw]
    else:
        return []
    cleaned: List[str] = []
    for item in raw_list:
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def _parse_interval_seconds(value: Any) -> int:
    if value is None:
        return 1800
    try:
        interval = int(float(value))
    except Exception as exc:  # pragma: no cover - conversion errors handled
        raise HTTPException(status_code=400, detail={"ok": False, "error": "invalid_interval", "message": str(exc)})
    interval = max(60, interval)
    if interval > 24 * 3600:
        interval = 24 * 3600
    return interval


def _normalize_url(value: str) -> str:
    url = str(value or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "missing_url", "message": "URL is required"})
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail={"ok": False, "error": "invalid_url", "message": "URL must start with http:// or https://"})
    return url


def _normalize_label(value: Any) -> str:
    label = str(value or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "missing_label", "message": "Label is required"})
    return label


def _domain_preset(url: str) -> Optional[Dict[str, Any]]:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return None
    host = host.lower()
    if not host:
        return None
    for suffix, preset in _DOMAIN_PRESETS.items():
        if host == suffix or host.endswith("." + suffix):
            return dict(preset)
    return None


def create_target_from_url(
    url: str,
    *,
    label: Optional[str] = None,
    tags: Iterable[str] | None = None,
    interval_sec: int | float | None = None,
    trust: float | None = None,
    enabled: Optional[bool] = None,
    existing_targets: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    normalized_url = _normalize_url(url)
    preset = _domain_preset(normalized_url) or {}
    base_label_raw = label or preset.get("label") or urlparse(normalized_url).netloc
    base_label = _normalize_label(base_label_raw)
    merged_tags = list(preset.get("tags") or [])
    if tags:
        merged_tags.extend(tags)
    cleaned_tags = _clean_tags(merged_tags)
    base_interval = interval_sec or preset.get("interval_sec") or 1800
    parsed_interval = _parse_interval_seconds(base_interval)
    trust_val = trust if trust is not None else preset.get("trust")
    if trust_val is not None:
        try:
            trust_val = float(trust_val)
        except Exception as exc:
            raise HTTPException(status_code=400, detail={"ok": False, "error": "invalid_trust", "message": str(exc)})
        trust_val = max(0.0, min(1.0, trust_val))
    enabled_flag = bool(enabled if enabled is not None else preset.get("enabled", True))
    existing = list(existing_targets or [])
    target_id = generate_target_id(base_label, (t.get("id") for t in existing))
    new_target: Dict[str, Any] = {
        "id": target_id,
        "label": base_label,
        "url": normalized_url,
        "enabled": enabled_flag,
        "interval_sec": parsed_interval,
        "last_run_ts": 0,
        "last_status": None,
        "tags": cleaned_tags,
    }
    if trust_val is not None:
        new_target["trust"] = trust_val
    return new_target


@router.get("/status")
async def get_crawler_status(user: dict = Depends(_require_admin)) -> Dict[str, Any]:
    _ = user  # dependency enforcement only
    return _snapshot()


@router.get("/targets")
async def list_crawler_targets(user: dict = Depends(_require_admin)) -> Dict[str, Any]:
    _ = user
    items = load_targets()
    return {"ok": True, "items": items, "count": len(items)}


@router.post("/targets", status_code=201)
async def create_crawler_target(
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(_require_admin),
) -> Dict[str, Any]:
    _ = user
    data = dict(payload or {})
    label = _normalize_label(data.get("label"))
    url = _normalize_url(data.get("url"))
    enabled = bool(data.get("enabled", True))
    interval_sec = _parse_interval_seconds(data.get("interval_sec"))
    tags = _clean_tags(data.get("tags"))

    targets = load_targets()
    new_id = generate_target_id(label, (t.get("id") for t in targets))
    new_target = {
        "id": new_id,
        "label": label,
        "url": url,
        "enabled": enabled,
        "interval_sec": interval_sec,
        "last_run_ts": 0,
        "last_status": None,
        "tags": tags,
    }
    trust = data.get("trust")
    if trust is not None:
        try:
            new_target["trust"] = float(trust)
        except Exception:
            raise HTTPException(status_code=400, detail={"ok": False, "error": "invalid_trust", "message": "trust must be numeric"})

    targets.append(new_target)
    save_targets(targets)
    return {"ok": True, "item": new_target}


@router.post("/targets/from-url", status_code=201)
async def create_crawler_target_from_url(
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(_require_admin),
) -> Dict[str, Any]:
    _ = user
    data = dict(payload or {})
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "missing_url", "message": "URL is required"})

    targets = load_targets()
    normalized_url = _normalize_url(url)
    if any(str(t.get("url") or "").strip().lower() == normalized_url.lower() for t in targets):
        raise HTTPException(status_code=409, detail={"ok": False, "error": "target_exists", "message": normalized_url})

    cleaned_tags = _clean_tags(data.get("tags"))
    new_target = create_target_from_url(
        normalized_url,
        label=data.get("label"),
        tags=cleaned_tags,
        interval_sec=data.get("interval_sec"),
        trust=data.get("trust"),
        enabled=data.get("enabled"),
        existing_targets=targets,
    )

    persist = bool(data.get("persist", True))
    if persist:
        targets.append(new_target)
        save_targets(targets)

    return {"ok": True, "item": new_target, "persisted": persist}


@router.put("/targets/{target_id}")
async def update_crawler_target(
    target_id: str,
    payload: Dict[str, Any] = Body(...),
    user: dict = Depends(_require_admin),
) -> Dict[str, Any]:
    _ = user
    targets = load_targets()
    for target in targets:
        if str(target.get("id")) != str(target_id):
            continue
        data = dict(payload or {})
        if "label" in data:
            target["label"] = _normalize_label(data.get("label"))
        if "url" in data:
            target["url"] = _normalize_url(data.get("url"))
        if "enabled" in data:
            target["enabled"] = bool(data.get("enabled"))
        if "interval_sec" in data:
            target["interval_sec"] = _parse_interval_seconds(data.get("interval_sec"))
        if "tags" in data:
            target["tags"] = _clean_tags(data.get("tags"))
        if "trust" in data:
            try:
                target["trust"] = float(data.get("trust"))
            except Exception:
                raise HTTPException(status_code=400, detail={"ok": False, "error": "invalid_trust", "message": "trust must be numeric"})
        save_targets(targets)
        return {"ok": True, "item": target}
    raise HTTPException(status_code=404, detail={"ok": False, "error": "target_not_found", "message": target_id})


@router.delete("/targets/{target_id}", status_code=204)
async def delete_crawler_target(
    target_id: str,
    user: dict = Depends(_require_admin),
) -> Response:
    _ = user
    targets = load_targets()
    remaining = [t for t in targets if str(t.get("id")) != str(target_id)]
    if len(remaining) == len(targets):
        raise HTTPException(status_code=404, detail={"ok": False, "error": "target_not_found", "message": target_id})
    save_targets(remaining)
    return Response(status_code=204)


@router.post("/run")
async def trigger_crawler_run(user: dict = Depends(_require_admin)) -> Dict[str, Any]:
    if _IMPORT_ERROR is not None or run_crawler_once is None:
        raise HTTPException(status_code=503, detail=f"crawler_unavailable: {_IMPORT_ERROR}")

    if _run_lock.locked():
        raise HTTPException(status_code=409, detail={"ok": False, "error": "crawler_already_running"})

    _cleanup_stale_lock()

    async with _run_lock:
        _state["running"] = True
        _state["last_error"] = None
        await _persist_state()

        started_monotonic = time.perf_counter()

        try:
            loop = asyncio.get_running_loop()
            # Manueller Trigger erzwingt sofortigen Lauf unabhängig vom letzten Timestamp
            try:
                run_result = await loop.run_in_executor(
                    None,
                    lambda: run_crawler_once(force=True),  # type: ignore[call-arg]
                )
            except TypeError:
                # Rückwärtskompatibilität für ältere Signaturen ohne force-Argument
                run_result = await loop.run_in_executor(None, run_crawler_once)
        except HTTPException:
            _state["last_run_ts"] = int(time.time())
            _state["last_error"] = "permission_denied"
            raise
        except Exception as exc:
            finished_ts = int(time.time())
            message = (str(exc) or "crawler run failed").strip()
            if len(message) > 400:
                message = f"{message[:397]}..."
            _state["last_run_ts"] = finished_ts
            _state["last_error"] = message
            duration_ms = max(0, int((time.perf_counter() - started_monotonic) * 1000))
            error_payload = {
                "ok": False,
                "running": False,
                "last_run_ts": finished_ts,
                "last_error": message,
                "error": "crawler_run_failed",
                "message": message,
                "duration_ms": duration_ms,
            }
            return JSONResponse(status_code=500, content=error_payload)
        else:
            finished_ts = int(time.time())
            duration_ms = max(0, int((time.perf_counter() - started_monotonic) * 1000))
            if isinstance(run_result, dict):
                run_summary: Dict[str, Any] = dict(run_result)
            else:
                run_summary = {"result": run_result}
            ok_flag = bool(run_summary.get("ok", True))
            error_val = run_summary.get("error") if isinstance(run_summary.get("error"), str) else None
            if not ok_flag and not error_val:
                error_val = str(run_summary.get("message") or "crawler_run_failed")
            _state["last_run_ts"] = finished_ts
            _state["last_error"] = None if ok_flag else error_val

            response: Dict[str, Any] = {
                "ok": ok_flag,
                "running": False,
                "last_run_ts": finished_ts,
                "last_error": _state["last_error"],
                "duration_ms": duration_ms,
                "result": run_summary,
            }
            for key, value in run_summary.items():
                if key == "ok":
                    continue
                response[key] = value
            return response
        finally:
            _state["running"] = False
            await _persist_state()


def note_crawler_result(ok: bool, *, error: str | None = None) -> None:
    """Allow background tasks to update the cached status."""
    _state["running"] = False
    _state["last_run_ts"] = int(time.time())
    _state["last_error"] = None if ok else (error or "unknown_error")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_persist_state())
            return
    except RuntimeError:
        pass
    # No running loop – persist synchronously as fallback
    try:
        payload = {
            "running": False,
            "last_run_ts": int(_state.get("last_run_ts") or int(time.time())),
            "last_error": _state.get("last_error"),
        }
        _STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# Load state once the module is imported
_load_state_from_disk()
