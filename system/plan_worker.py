#!/usr/bin/env python3
from __future__ import annotations
"""
Planner Worker: sequentially processes PlanSteps via Planner API.
- Leases next step via POST /api/plan/lease-step
- Executes (placeholder) and reports result via POST /api/plan/complete-step
- Auth: ADMIN_API_TOKEN if set
"""
import os, time, json, traceback, threading
from urllib import request as _ur
import urllib.parse as _up

API_BASE = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000")
SLEEP_SEC = float(os.getenv("PLANNER_POLL_INTERVAL", "2"))
KI_ROOT = os.getenv("KI_ROOT", os.path.expanduser("~/ki_ana"))
HB_PATH = os.path.join(KI_ROOT, "runtime", "plan_worker_heartbeat")


def _req(path: str, data: dict | None = None, timeout: float = 5.0):
    url = API_BASE.rstrip("/") + path
    headers = {"Content-Type": "application/json"}
    tok = os.getenv("ADMIN_API_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    r = _ur.Request(url, data=body, headers=headers)
    with _ur.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}


def _do_step(step: dict) -> tuple[bool, str]:
    """Execute a step. For now, placeholder behaviors by type.
    Return (ok, result_text).
    """
    typ = (step.get("type") or "task").lower()
    payload = step.get("payload") or {}
    try:
        # Minimal behaviors; extend as needed
        if typ in {"task", "note"}:
            return True, f"ack: {payload!r}"
        elif typ == "sleep":
            dur = float(payload.get("seconds") or 1)
            time.sleep(max(0.0, min(dur, 30.0)))
            return True, f"slept {dur} sec"
        elif typ == "knowledge_add":
            # Payload: { content: str, tags: [..]|"a,b", source: str, type: str }
            content = (payload.get("content") or "").strip()
            if not content:
                return False, "knowledge_add: missing content"
            tags = payload.get("tags")
            if isinstance(tags, list):
                tags = ",".join([str(t).strip() for t in tags if str(t).strip()])
            elif isinstance(tags, str):
                tags = ",".join([t.strip() for t in tags.split(",") if t.strip()])
            else:
                tags = ""
            src = str(payload.get("source") or "plan").strip()[:120]
            kb_type = str(payload.get("type") or "text").strip()[:60]
            body = {
                "source": src,
                "type": kb_type,
                "tags": tags,
                "content": content,
                "ts": int(time.time()),
            }
            try:
                r = _req("/api/knowledge", body, timeout=5.0)
                if r and r.get("ok"):
                    return True, f"knowledge_add: ok"
                return False, f"knowledge_add failed: {r}"
            except Exception as e:
                return False, f"knowledge_add exception: {e}"
        elif typ == "device_event":
            # Payload: { device_id: int, event: { type: str, payload: {...} } }
            dev_id = int(payload.get("device_id") or 0)
            ev = payload.get("event") or {}
            ev_type = (ev.get("type") or "message").strip()
            ev_payload = ev.get("payload") or {}
            if dev_id <= 0:
                return False, "device_event: missing device_id"
            try:
                r = _req(f"/os/devices/{dev_id}/events", {"type": ev_type, "payload": ev_payload}, timeout=6.0)
                if r and r.get("ok"):
                    return True, f"device_event: pushed id={r.get('id')}"
                return False, f"device_event failed: {r}"
            except Exception as e:
                return False, f"device_event exception: {e}"
        elif typ == "knowledge_search":
            # Payload: { q: str, limit?: int }
            q = str(payload.get("q") or "").strip()
            lim = int(payload.get("limit") or 5)
            try:
                params = {"q": q, "limit": max(1, min(lim, 50))}
                # Direct GET not implemented in _req helper; use POST to a small proxy or reuse search via GET-like body
                # We'll call /api/knowledge/search with params appended manually
                base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
                url = base + "/api/knowledge/search?" + _up.urlencode(params)
                req = _ur.Request(url, method="GET")
                tok = os.getenv("ADMIN_API_TOKEN", "").strip()
                if tok:
                    req.add_header("Authorization", f"Bearer {tok}")
                with _ur.urlopen(req, timeout=6.0) as r:
                    data = json.loads(r.read().decode("utf-8") or "{}")
                items = data.get("items") or []
                n = len(items)
                if not n:
                    return True, "knowledge_search: 0 hits"
                # Summarize first few items (titles/sources)
                parts = []
                for it in items[:3]:
                    ts = it.get("ts")
                    src = (it.get("source") or "")[:60]
                    typ2 = (it.get("type") or "")[:40]
                    parts.append(f"- [{typ2}] {src} @ {ts}")
                return True, f"knowledge_search: {n} hits\n" + "\n".join(parts)
            except Exception as e:
                return False, f"knowledge_search exception: {e}"
        elif typ == "web_fetch":
            # Payload: { url: str, method?: 'GET'|'POST', headers?: dict, body?: str|dict, timeout?: int, save_knowledge?: bool, knowledge_tags?: str }
            try:
                url = str(payload.get("url") or "").strip()
                if not url:
                    return False, "web_fetch: missing url"
                method = (payload.get("method") or "GET").upper().strip()
                headers = payload.get("headers") or {}
                if not isinstance(headers, dict):
                    headers = {}
                timeout = float(payload.get("timeout") or 10)
                data_bytes = None
                if method != "GET":
                    body = payload.get("body")
                    if isinstance(body, (dict, list)):
                        data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
                        headers.setdefault("Content-Type", "application/json")
                    elif isinstance(body, str):
                        data_bytes = body.encode("utf-8")
                req = _ur.Request(url, data=data_bytes, method=method)
                # auth header from ADMIN_API_TOKEN only for same-origin internal calls; otherwise honor provided headers only
                for k, v in headers.items():
                    try: req.add_header(str(k), str(v))
                    except Exception: pass
                with _ur.urlopen(req, timeout=timeout) as resp:
                    ctype = resp.headers.get("Content-Type", "")
                    raw = resp.read()
                text = None; js = None
                try:
                    if "json" in ctype.lower():
                        js = json.loads(raw.decode("utf-8"))
                    else:
                        text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    text = raw[:200].decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)[:200]
                # Optionally persist to knowledge
                if bool(payload.get("save_knowledge")):
                    try:
                        content = json.dumps(js, ensure_ascii=False) if js is not None else (text or "")
                        _ = _req("/api/knowledge", {
                            "source": "plan:web_fetch",
                            "type": "note",
                            "tags": str(payload.get("knowledge_tags") or "web,fetch"),
                            "content": content[:4000]
                        }, timeout=5.0)
                    except Exception:
                        pass
                if js is not None:
                    return True, f"web_fetch: json ok keys={list(js)[:5]}"
                else:
                    preview = (text or "")
                    if len(preview) > 200:
                        preview = preview[:200] + "…"
                    return True, f"web_fetch: text ok len={len(text or '')} preview={preview!r}"
            except Exception as e:
                return False, f"web_fetch exception: {e}"
        elif typ == "analyze_knowledge":
            # Payload: { q: str, limit?: int, save_knowledge?: bool, title?: str }
            try:
                q = str(payload.get("q") or "").strip()
                lim = int(payload.get("limit") or 10)
                params = {"q": q, "limit": max(1, min(lim, 100))}
                base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
                url = base + "/api/knowledge/search?" + _up.urlencode(params)
                req = _ur.Request(url, method="GET")
                tok = os.getenv("ADMIN_API_TOKEN", "").strip()
                if tok:
                    req.add_header("Authorization", f"Bearer {tok}")
                with _ur.urlopen(req, timeout=8.0) as r:
                    data = json.loads(r.read().decode("utf-8") or "{}")
                items = data.get("items") or []
                n = len(items)
                # Build a compact analysis summary
                by_type = {}
                sources = {}
                for it in items:
                    t = (it.get("type") or "").strip() or "note"
                    s = (it.get("source") or "").strip() or "?"
                    by_type[t] = by_type.get(t, 0) + 1
                    sources[s] = sources.get(s, 0) + 1
                types_str = ", ".join([f"{k}:{v}" for k,v in sorted(by_type.items(), key=lambda x:-x[1])[:5]]) or "—"
                srcs_str = ", ".join([f"{k}:{v}" for k,v in sorted(sources.items(), key=lambda x:-x[1])[:5]]) or "—"
                summary = f"analyze_knowledge: {n} Treffer · Typen {types_str} · Quellen {srcs_str}"
                # Optional: persist reflection
                if bool(payload.get("save_knowledge")):
                    try:
                        title = str(payload.get("title") or "Knowledge-Analyse")
                        _ = _req("/api/knowledge", {
                            "source": "plan:analyze",
                            "type": "reflection",
                            "tags": "reflection,knowledge",
                            "content": f"{title}: {summary}"
                        }, timeout=5.0)
                    except Exception:
                        pass
                return True, summary
            except Exception as e:
                return False, f"analyze_knowledge exception: {e}"
        elif typ in {"os_notify", "notify"}:
            # Payload: { text: str, title?: str }
            try:
                body = {"name": "notify.send", "args": {"text": str(payload.get("text") or ""), "title": str(payload.get("title") or "Planner")}}
                r = _req("/os/syscall", body, timeout=5.0)
                if r and r.get("ok"):
                    return True, "os_notify: ok"
                return False, f"os_notify failed: {r}"
            except Exception as e:
                return False, f"os_notify exception: {e}"
        elif typ == "media_thumbnail":
            # Payload: { path: str, max_w?: int, max_h?: int }
            mpath = str(payload.get("path") or "").strip()
            mw = int(payload.get("max_w") or 512)
            mh = int(payload.get("max_h") or 512)
            if not mpath:
                return False, "media_thumbnail: missing path"
            try:
                r = _req("/api/media/thumbnail", {"path": mpath, "max_w": mw, "max_h": mh}, timeout=15.0)
                if r and r.get("ok"):
                    out = r.get("output") or {}
                    return True, f"media_thumbnail: ok -> {out.get('path','')}"
            except Exception:
                pass
            # Fallback: record request as knowledge note
            try:
                _ = _req("/api/knowledge", {"source": "plan:media", "type": "note", "tags": "media,thumbnail", "content": f"Thumbnail requested for {mpath} ({mw}x{mh})"}, timeout=5.0)
            except Exception:
                pass
            return True, "media_thumbnail: recorded request"
        elif typ == "media_whisper":
            # Payload: { path: str, lang?: str }
            mpath = str(payload.get("path") or "").strip()
            lang = (payload.get("lang") or "").strip() or None
            if not mpath:
                return False, "media_whisper: missing path"
            try:
                body = {"path": mpath}
                if lang: body["lang"] = lang
                r = _req("/api/media/whisper", body, timeout=60.0)
                if r and r.get("ok"):
                    txt = (r.get("text") or "")[:200]
                    return True, f"media_whisper: ok len={len(r.get('text') or '')}"
            except Exception:
                pass
            # Fallback: record request as knowledge note
            try:
                note = f"Transcribe requested for {mpath}" + (f" lang={lang}" if lang else "")
                _ = _req("/api/knowledge", {"source": "plan:media", "type": "note", "tags": "media,whisper", "content": note}, timeout=5.0)
            except Exception:
                pass
            return True, "media_whisper: recorded request"
        else:
            return True, f"noop:{typ} {payload!r}"
    except Exception as e:
        return False, f"exception: {e}"


def _within_low_priority_window() -> bool:
    # Allowed window for low priority, format HH-HH, default 22-06
    try:
        rng = os.getenv("LOW_PRIORITY_ALLOWED_HOURS", "22-06")
        parts = str(rng).split("-")
        if len(parts) != 2:
            return True
        start = int(parts[0]) % 24
        end = int(parts[1]) % 24
        hour = time.localtime().tm_hour
        if start <= end:
            return start <= hour < end
        else:
            # wraps midnight
            return hour >= start or hour < end
    except Exception:
        return True


def _worker_loop(slot: int):
    while True:
        try:
            # Heartbeat from slot 0 only (best-effort)
            if slot == 0:
                try:
                    os.makedirs(os.path.dirname(HB_PATH), exist_ok=True)
                    with open(HB_PATH, "w") as f:
                        f.write(str(int(time.time())))
                except Exception:
                    pass
            leased = _req("/api/plan/lease-step", {})
            if not leased or leased.get("ok") is not True:
                time.sleep(SLEEP_SEC)
                continue
            step = leased.get("step")
            plan_id = leased.get("plan_id")
            if not step:
                time.sleep(SLEEP_SEC)
                continue

            # Deadline / priority handling (soft)
            payload = step.get("payload") or {}
            deadline = int(payload.get("deadline_ts") or step.get("deadline_ts") or 0)
            prio = (payload.get("priority") or step.get("priority") or "normal").lower()
            if deadline and int(time.time()) > deadline:
                ok, res = False, f"missed deadline: {deadline}"
            else:
                # Retry policy
                max_retries = int(payload.get("max_retries") or step.get("max_retries") or 0)
                backoff = int(payload.get("retry_backoff_sec") or step.get("retry_backoff_sec") or 2)
                attempts = 0
                ok = False
                res = ""
                while True:
                    attempts += 1
                    ok, res = _do_step(step)
                    if ok:
                        if prio == "low" and not _within_low_priority_window():
                            # annotate result to show it was executed outside preferred window
                            res = (res or "") + " | note: low-priority executed outside preferred window"
                        break
                    if attempts > max_retries:
                        break
                    # exponential backoff
                    wait = min(60, backoff * (2 ** (attempts - 1)))
                    time.sleep(wait)
            _req("/api/plan/complete-step", {
                "step_id": int(step.get("id") or 0),
                "plan_id": int(plan_id or 0),
                "ok": bool(ok),
                "result": res if ok else None,
                "error": None if ok else (res or f"failed after retries"),
            })
        except Exception:
            # Log locally and backoff
            print(f"[plan_worker:{slot}] error:\n" + traceback.format_exc())
            time.sleep(max(SLEEP_SEC, 3.0))


def main() -> int:
    try:
        conc = max(1, int(os.getenv("WORKER_CONCURRENCY", "1")))
    except Exception:
        conc = 1
    threads = []
    for i in range(conc):
        t = threading.Thread(target=_worker_loop, args=(i,), daemon=True)
        t.start()
        threads.append(t)
    # Join forever
    for t in threads:
        t.join()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
