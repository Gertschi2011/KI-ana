from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pathlib import Path
import os, time, json, threading


router = APIRouter(prefix="/api/autonomy", tags=["autonomy"])

KI_ROOT = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
RUNTIME_DIR = KI_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
LEVEL_FILE = RUNTIME_DIR / "autonomy.json"
RULES_FILE = RUNTIME_DIR / "auto_rules.json"
STATE_FILE = RUNTIME_DIR / "auto_state.json"

# Default rules: hourly knowledge search for "error"
DEFAULT_RULES: Dict[str, Any] = {
    "rules": [
        {"id": "hourly_error_search", "type": "cron", "spec": "@hourly", "action": {"type": "knowledge_search", "q": "error", "limit": 3}},
        {"id": "worker_offline_alert", "type": "watch", "metric": "worker_heartbeat_age", "gt": 300, "action": {"type": "os_notify", "text": "Planner-Worker offline >5min"}},
        {"id": "hourly_summary", "type": "cron", "spec": "@hourly", "action": {"type": "hourly_summary"}},
        {"id": "offline_devices_watch", "type": "watch", "metric": "devices_offline", "gt": 0, "action": {"type": "os_notify", "text": "Geräte offline erkannt"}},
        {"id": "dev1_offline_reboot", "type": "device_offline", "device_id": "1", "offline_sec": 600, "action": {"type": "plan_create", "title": "Reboot notification – device 1"}},
        {"id": "daily_report", "type": "cron", "spec": "@daily", "action": {"type": "daily_report"}},
        {"id": "weekly_report", "type": "cron", "spec": "@weekly", "action": {"type": "weekly_report"}},
        {"id": "combo_warn_worker_devices", "type": "combo", "all": [{"metric": "worker_heartbeat_age", "gt": 60}, {"metric": "devices_offline", "gt": 0}], "action": {"type": "os_notify", "text": "Combo: Worker alt + Geräte offline"}},
        {"id": "cfg_hash_watch", "type": "cron", "spec": "@hourly", "files": [], "action": {"type": "config_hash_watch"}},
        {"id": "rule_suggestions", "type": "cron", "spec": "@daily", "action": {"type": "rule_suggestions"}},
        # Catch-all knowledge question: if a recent topic/question is detected (from chat conv_state),
        # create a small plan that runs analyze_knowledge so the user gets a factual answer instead of a stub.
        # Debounced in _tick_once via state (catch_all_last_ts/topic).
        {"id": "catch_all_question", "type": "catch_all_question", "window_sec": 20, "cooldown_sec": 30,
         "action": {"type": "plan_create", "title": "Default Knowledge Answer"}}
    ]
}

# ---- Level management -------------------------------------------------------

def _read_level() -> int:
    try:
        if LEVEL_FILE.exists():
            data = json.loads(LEVEL_FILE.read_text(encoding="utf-8") or "{}")
            return int(data.get("level", 0))
    except Exception:
        pass
    return 0

def _write_level(level: int) -> None:
    try:
        LEVEL_FILE.write_text(json.dumps({"level": int(level)}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

@router.get("/level")
def get_level(user = Depends(get_current_user_required)):
    # creator/admin can view
    require_role(user, {"creator", "admin"})
    return {"ok": True, "level": _read_level()}

@router.post("/level")
def set_level(body: Dict[str, Any], user = Depends(get_current_user_required)):
    # creator/admin can set
    require_role(user, {"creator", "admin"})
    lvl = int(body.get("level") or 0)
    if lvl not in (0,1,2):
        raise HTTPException(400, "level must be 0,1,2")
    _write_level(lvl)
    return {"ok": True, "level": lvl}

# ---- Rules management -------------------------------------------------------

def _read_rules() -> Dict[str, Any]:
    try:
        if RULES_FILE.exists():
            data = json.loads(RULES_FILE.read_text(encoding="utf-8") or "{}") or {"rules": []}
            # Auto-migrate: ensure catch_all_question rule exists once
            try:
                rules = list(data.get("rules") or [])
                has_catch = any(str(r.get("id") or "").strip() == "catch_all_question" for r in rules)
                if not has_catch:
                    rules.append({
                        "id": "catch_all_question",
                        "type": "catch_all_question",
                        "window_sec": 20,
                        "cooldown_sec": 30,
                        "action": {"type": "plan_create", "title": "Default Knowledge Answer"}
                    })
                    data["rules"] = rules
                    _write_rules(data)
            except Exception:
                pass
            return data
    except Exception:
        pass
    return DEFAULT_RULES

def _write_rules(data: Dict[str, Any]) -> None:
    try:
        RULES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

@router.get("/rules")
def get_rules(user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    return {"ok": True, **_read_rules()}

@router.post("/rules")
def set_rules(body: Dict[str, Any], user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    if not isinstance(body, dict) or not isinstance(body.get("rules"), list):
        raise HTTPException(400, "rules: [] required")
    _write_rules({"rules": body.get("rules")})
    return {"ok": True}

# ---- Background auto-planner -----------------------------------------------

_stop = False
_thread: threading.Thread | None = None

def _api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import urllib.request, json as _j
    base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = base + path
    tok = os.getenv("ADMIN_API_TOKEN", "").strip()
    req = urllib.request.Request(url, data=_j.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json", **({"Authorization": f"Bearer {tok}"} if tok else {})})
    with urllib.request.urlopen(req, timeout=5.0) as r:
        return _j.loads(r.read().decode("utf-8") or "{}")

# ---- Test endpoint: log condition -------------------------------------------
@router.post("/test_log_condition")
def test_log_condition(body: Dict[str, Any], user = Depends(get_current_user_required)):
    """
    Test a log condition against recent logs. Accepts either a single log_recent leaf
    or a small combo node focused on logs (e.g., { any: [ log_recent, ... ] } or { not: {...} }).
    Returns { ok: true, matches: N, samples: [ {ts, type, device, msg} ... ] }.
    """
    # creator/admin only
    require_role(user, {"creator", "admin"})
    try:
        # Fetch recent logs (up to 1000)
        data = _api_get("/api/logs?limit=1000")
        items: List[Dict[str, Any]] = []
        if isinstance(data, dict) and data.get("items"):
            items = list(data.get("items") or [])
        elif isinstance(data, list):
            items = data
        nowi = int(time.time())
        # Fetch metrics once (for metric conditions)
        try:
            import urllib.request, json as _j
            base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
            with urllib.request.urlopen(base+"/api/system/status", timeout=3.0) as r:
                sys = _j.loads(r.read().decode("utf-8") or "{}")
            metrics = (sys.get("metrics") or {})
        except Exception:
            metrics = {}
        device_cache: Dict[str, Dict[str, Any]] = {}

        def flatten_log_nodes(node: Any) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            if not node:
                return out
            if isinstance(node, dict):
                t = str(node.get("type") or "")
                if t == "log_recent":
                    out.append(node)
                    return out
                if "not" in node:
                    out.extend(flatten_log_nodes(node.get("not")))
                if isinstance(node.get("any"), list):
                    for n in node.get("any"):
                        out.extend(flatten_log_nodes(n))
                if isinstance(node.get("all"), list):
                    for n in node.get("all"):
                        out.extend(flatten_log_nodes(n))
                return out
            if isinstance(node, list):
                for n in node:
                    out.extend(flatten_log_nodes(n))
            return out

        nodes: List[Dict[str, Any]] = []
        if isinstance(body, dict) and ("node" in body or "condition" in body):
            cond = dict(body.get("node") or body.get("condition") or {})
            auto_suggest_flag = bool(body.get("auto_suggest") or False)
        else:
            cond = dict(body or {})
            auto_suggest_flag = False
        try:
            env_auto = str(os.getenv("GUARDIAN_AUTO_SUGGEST", "0")).strip() in {"1","true","True"}
        except Exception:
            env_auto = False
        auto_suggest = bool(auto_suggest_flag or env_auto)
        if isinstance(cond, dict):
            if str(cond.get("type") or "") == "log_recent":
                nodes = [cond]
            else:
                nodes = flatten_log_nodes(cond.get("any") or cond.get("all") or cond)

        def match_one(lg: Dict[str, Any], c: Dict[str, Any]) -> bool:
            try:
                ts = int(lg.get("ts") or lg.get("created_at") or 0)
                within = int(c.get("within_sec") or 0)
                if within <= 0 or (nowi - ts) > within:
                    return False
                devf = str(c.get("device_id") or "").strip()
                if devf and str(lg.get("device_id") or lg.get("dev") or "") != devf:
                    return False
                ltype = str(c.get("log_type") or "").strip()
                typ2 = str(lg.get("type") or lg.get("level") or lg.get("category") or "").strip()
                if ltype and typ2.lower() != ltype.lower():
                    return False
                hostf = str(c.get("host") or c.get("hostname") or "").strip()
                srcf = str(c.get("source") or c.get("logger") or "").strip()
                levelf = str(c.get("level") or c.get("severity") or "").strip()
                host2 = str(lg.get("host") or lg.get("hostname") or "").strip()
                src2 = str(lg.get("source") or lg.get("logger") or "").strip()
                level2 = str(lg.get("level") or lg.get("severity") or "").strip()
                if hostf and host2.lower() != hostf.lower():
                    return False
                if srcf and src2.lower() != srcf.lower():
                    return False
                if levelf and level2.lower() != levelf.lower():
                    return False
                rx = c.get("message_regex")
                if isinstance(rx, str) and rx.strip():
                    try:
                        import re as _re
                        if not _re.search(rx, str(lg.get("message") or lg.get("msg") or lg.get("text") or "")):
                            return False
                    except Exception:
                        return False
                return True
            except Exception:
                return False

        hits: List[Dict[str, Any]] = []
        if nodes:
            for lg in items:
                for n in nodes:
                    if match_one(lg, n):
                        hits.append(lg)
                        break
        samples: List[Dict[str, Any]] = []
        for h in sorted(hits, key=lambda z: int(z.get("ts") or z.get("created_at") or 0), reverse=True)[:5]:
            samples.append({
                "ts": int(h.get("ts") or h.get("created_at") or 0),
                "type": str(h.get("type") or h.get("level") or h.get("category") or ""),
                "device": str(h.get("device_id") or h.get("dev") or ""),
                "msg": str(h.get("message") or h.get("msg") or h.get("text") or "")[:160],
            })

        # Full-evaluator for provided condition (combo support)
        def eval_cond(c: Dict[str, Any]) -> bool:
            # metric
            if "metric" in c:
                try:
                    m = str(c.get("metric") or ""); val = float(metrics.get(m) or 0)
                    if "gt" in c: return val > float(c.get("gt") or 0)
                    if "gte" in c: return val >= float(c.get("gte") or 0)
                    if "lt" in c: return val < float(c.get("lt") or 0)
                    if "lte" in c: return val <= float(c.get("lte") or 0)
                    return False
                except Exception:
                    return False
            # device_offline
            if (c.get("type") or "") == "device_offline":
                try:
                    dev_id = str(c.get("device_id") or "").strip(); thr = int(c.get("offline_sec") or 600)
                    if not dev_id:
                        return False
                    if dev_id not in device_cache:
                        device_cache[dev_id] = _api_get(f"/api/devices/{dev_id}") or {}
                    d = device_cache.get(dev_id) or {}
                    last_seen = int(d.get("last_seen") or d.get("updated_at") or 0)
                    status = str(d.get("status") or "").lower()
                    return (status == "offline") or (last_seen and (nowi - last_seen) > thr)
                except Exception:
                    return False
            # log_recent
            if (c.get("type") or "") == "log_recent":
                # true if any log in pulled set matches
                for lg in items:
                    if match_one(lg, c):
                        return True
                return False
            return False

        def eval_node(node: Any) -> bool:
            if not node:
                return True
            if isinstance(node, list):
                return all(eval_node(n) for n in node)
            if isinstance(node, dict):
                if "not" in node:
                    return not eval_node(node.get("not"))
                sub_all = node.get("all")
                sub_any = node.get("any")
                if sub_all is not None or sub_any is not None:
                    ok_all = True if sub_all is None else eval_node(list(sub_all))
                    ok_any = True if sub_any is None else any(eval_node(n) for n in list(sub_any))
                    return ok_all and ok_any
                return eval_cond(node)
            return False

        overall = eval_node(cond)

        # Optional Guardian auto-suggest for critical logs
        if auto_suggest and samples:
            try:
                CRIT_TYPES = {"kernel.error", "system.critical"}
                crit = False
                for s in samples:
                    lvl = str((s.get("type") or "")).lower()
                    typ = str((s.get("type") or "")).lower()
                    # If client provided level filter in condition, honor that too
                    cond_level = str(cond.get("level") or cond.get("severity") or "").lower()
                    log_type = str(cond.get("log_type") or "").lower()
                    if cond_level == "error" or lvl == "error" or typ in CRIT_TYPES or log_type in CRIT_TYPES:
                        crit = True; break
                if crit:
                    msg = samples[0].get("msg") or ""
                    content = f"Kritisches Log erkannt → Vorschlag: Autonomes Notify. Beispiel: [{samples[0].get('type','')}] dev {samples[0].get('device','')}: {msg[:240]}"
                    _api_post("/api/knowledge", {
                        "source": "autonomy", "type": "note", "tags": "autonomy,suggested_rule,guardian",
                        "content": content
                    })
            except Exception:
                pass

        return {"ok": True, "result": bool(overall), "matches": len(hits), "samples": samples}
    except HTTPException:
        raise
    except Exception:
        return {"ok": False, "matches": 0, "samples": []}

def _api_get(path: str) -> Any:
    import urllib.request, json as _j
    base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = base + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        ct = (resp.headers.get("Content-Type") or "")
        data = resp.read().decode("utf-8", errors="ignore")
        return _j.loads(data) if "json" in ct or data.strip().startswith("{") else data

def _api_post(path: str, payload: Dict[str, Any]) -> Any:
    import urllib.request, json as _j
    base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    url = base + path
    data = _j.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    # If ADMIN_API_TOKEN is present, include for privileged writes
    tok = os.getenv("ADMIN_API_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=3.5) as resp:
        ct = (resp.headers.get("Content-Type") or "")
        out = resp.read().decode("utf-8", errors="ignore")
        return _j.loads(out) if "json" in ct or out.strip().startswith("{") else out

def _tick_once() -> None:
    lvl = _read_level()
    # Level 0: do nothing
    if lvl <= 0:
        return
    # Load rules and last-run state
    rules = _read_rules().get("rules", [])
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8") or "{}") if STATE_FILE.exists() else {}
    except Exception:
        state = {}
    now = int(time.time())
    # Pull quick metrics for watches
    try:
        import urllib.request, json as _j
        base = os.getenv("PLANNER_API_BASE", "http://127.0.0.1:8000").rstrip("/")
        with urllib.request.urlopen(base+"/api/system/status", timeout=3.0) as r:
            sys = _j.loads(r.read().decode("utf-8") or "{}")
        metrics = (sys.get("metrics") or {})
    except Exception:
        metrics = {}
    for rule in rules:
        rid = str(rule.get("id") or "")
        typ = str(rule.get("type") or "")
        action = rule.get("action") or {}
        if not rid or not typ:
            continue
        last_run = int((state.get(rid) or 0))
        should = False
        if typ == "cron":
            spec = str(rule.get("spec") or "")
            if spec.startswith("@hourly") and (now - last_run >= 3600):
                should = True
            elif spec.startswith("@daily") and (now - last_run >= 86400):
                should = True
            elif spec.startswith("@weekly") and (now - last_run >= 7*86400):
                should = True
        elif typ == "watch":
            # e.g., worker_heartbeat_age > 300
            try:
                metric = str(rule.get("metric") or "")
                gt = float(rule.get("gt") or 0)
                val = float(metrics.get(metric) or 0)
                if val > gt and now - last_run >= 300:
                    should = True
            except Exception:
                should = False
        elif typ == "combo":
            # Evaluate combined conditions: supports nested {all:[]}, {any:[]}, {not:{...}}
            try:
                def eval_cond(c: dict) -> bool:
                    # Metric condition
                    if "metric" in c:
                        try:
                            m = str(c.get("metric") or ""); val = float(metrics.get(m) or 0)
                            if "gt" in c: return val > float(c.get("gt") or 0)
                            if "gte" in c: return val >= float(c.get("gte") or 0)
                            if "lt" in c: return val < float(c.get("lt") or 0)
                            if "lte" in c: return val <= float(c.get("lte") or 0)
                            return False
                        except Exception:
                            return False
                    # Device offline style condition
                    if (c.get("type") or "") == "device_offline":
                        try:
                            dev_id = str(c.get("device_id") or "").strip(); thr = int(c.get("offline_sec") or 600)
                            if not dev_id:
                                return False
                            d = _api_get(f"/api/devices/{dev_id}")
                            last_seen = int(d.get("last_seen") or d.get("updated_at") or 0)
                            status = str(d.get("status") or "").lower()
                            return (status == "offline") or (last_seen and (now - last_seen) > thr)
                        except Exception:
                            return False
                    # Log recent condition: presence of log_type within timeframe (optionally per device), optional message_regex, host/source/level filters
                    if (c.get("type") or "") == "log_recent":
                        try:
                            ltype = str(c.get("log_type") or "").strip()
                            within = int(c.get("within_sec") or 600)
                            devf = str(c.get("device_id") or "").strip()
                            hostf = str(c.get("host") or c.get("hostname") or "").strip()
                            srcf = str(c.get("source") or c.get("logger") or "").strip()
                            levelf = str(c.get("level") or c.get("severity") or "").strip()
                            msg_re_pat = c.get("message_regex")
                            msg_re = None
                            if isinstance(msg_re_pat, str) and msg_re_pat.strip():
                                try:
                                    import re as _re
                                    msg_re = _re.compile(msg_re_pat)
                                except Exception:
                                    msg_re = None
                            if within <= 0 or not ltype:
                                return False
                            qs = _up.urlencode({"limit": 400})
                            lj = _api_get(f"/api/logs?{qs}")
                            items = []
                            if isinstance(lj, dict) and lj.get("items"):
                                items = list(lj.get("items") or [])
                            elif isinstance(lj, list):
                                items = lj
                            since = now - within
                            for lg in items:
                                try:
                                    ts = int(lg.get("ts") or lg.get("created_at") or 0)
                                    typ2 = str(lg.get("type") or lg.get("level") or lg.get("category") or "").strip()
                                    dev2 = str(lg.get("device_id") or lg.get("dev") or "").strip()
                                    host2 = str(lg.get("host") or lg.get("hostname") or "").strip()
                                    src2 = str(lg.get("source") or lg.get("logger") or "").strip()
                                    level2 = str(lg.get("level") or lg.get("severity") or "").strip()
                                    if ts >= since and typ2.lower() == ltype.lower() and (not devf or dev2 == devf):
                                        if hostf and host2.lower() != hostf.lower():
                                            continue
                                        if srcf and src2.lower() != srcf.lower():
                                            continue
                                        if levelf and level2.lower() != levelf.lower():
                                            continue
                                        if msg_re is not None:
                                            msg = str(lg.get("message") or lg.get("msg") or lg.get("text") or "")
                                            if not msg_re.search(msg):
                                                continue
                                        return True
                                except Exception:
                                    continue
                            return False
                        except Exception:
                            return False
                    return False
                def eval_node(node: dict | list | None) -> bool:
                    try:
                        if not node:
                            return True
                        # If node is a list, treat as all[]
                        if isinstance(node, list):
                            return all(eval_node(n) for n in node)
                        if isinstance(node, dict):
                            if "not" in node:
                                return not eval_node(node.get("not"))
                            sub_all = node.get("all")
                            sub_any = node.get("any")
                            has_group = (sub_all is not None) or (sub_any is not None)
                            if has_group:
                                ok_all = True if sub_all is None else eval_node(list(sub_all))
                                ok_any = True if sub_any is None else any(eval_node(n) for n in list(sub_any))
                                return ok_all and ok_any
                            # Leaf condition dict
                            return eval_cond(node)
                        return False
                    except Exception:
                        return False
                # Root group: combine all/any per rule if provided, otherwise accept rule itself as a group/leaf
                root = {}
                if isinstance(rule.get("all"), list):
                    root["all"] = rule.get("all")
                if isinstance(rule.get("any"), list):
                    root["any"] = rule.get("any")
                if "not" in rule:
                    root = {"not": rule.get("not")}
                ok = eval_node(root or rule)
                if ok and (now - last_run >= 120):
                    should = True
            except Exception:
                should = False
        elif typ == "device_offline":
            try:
                dev_id = str(rule.get("device_id") or "").strip()
                thr = int(rule.get("offline_sec") or 600)
                if dev_id:
                    # Query device
                    d = _api_get(f"/api/devices/{dev_id}")
                    # Accept both registry and DB styles
                    last_seen = int(d.get("last_seen") or d.get("updated_at") or 0)
                    status = str(d.get("status") or "").lower()
                    if (status == "offline") or (last_seen and (now - last_seen) > thr):
                        # Cooldown 10 min per rule
                        if now - last_run >= max(300, thr//2):
                            should = True
                            # If action is notify, bake a specific message
                            if isinstance(action, dict) and not action.get("text"):
                                action["text"] = f"Device {dev_id} offline >{thr//60}min"
                            # Track incident in state for reports
                            try:
                                off = state.get("dev_offline_hist") or {}
                                arr = off.get(str(dev_id)) or []
                                # keep only last 7 days
                                cutoff = now - 7*86400
                                arr = [int(t) for t in arr if int(t) >= cutoff]
                                arr.append(now)
                                off[str(dev_id)] = arr
                                state["dev_offline_hist"] = off
                            except Exception:
                                pass
            except Exception:
                should = False
        elif typ == "catch_all_question":
            try:
                # Use latest conversation topic from runtime/conv_state.json (populated by chat module)
                conv_path = KI_ROOT / "runtime" / "conv_state.json"
                topic = ""; ts_topic = 0
                if conv_path.exists():
                    try:
                        cv = json.loads(conv_path.read_text(encoding="utf-8") or "{}")
                        # pick the most recent record
                        for k, v in (cv.items() if isinstance(cv, dict) else []):
                            tsv = int((v or {}).get("ts") or 0)
                            if tsv > ts_topic:
                                ts_topic = tsv
                                topic = str((v or {}).get("last_topic") or "").strip()
                    except Exception:
                        topic = ""; ts_topic = 0
                win = int(rule.get("window_sec") or 20)
                cool = int(rule.get("cooldown_sec") or 30)
                last_ts = int(state.get("catch_all_last_ts") or 0)
                last_top = str(state.get("catch_all_last_topic") or "")
                # Fire if we have a recent topic, it's different from last handled or past cooldown
                if topic and (now - ts_topic <= max(5, win)) and (topic != last_top or now - last_ts >= cool):
                    should = True
                    # Dynamically set steps for this action
                    try:
                        # Determine web_ok policy (runtime/settings.json or env AUTONOMY_WEB_OK_DEFAULT)
                        web_ok = False
                        try:
                            settings_path = KI_ROOT / "runtime" / "settings.json"
                            if settings_path.exists():
                                cfg = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
                                web_ok = bool(cfg.get("web_ok"))
                        except Exception:
                            web_ok = False
                        try:
                            if not web_ok:
                                web_ok = str(os.getenv("AUTONOMY_WEB_OK_DEFAULT", "0")).strip() in {"1","true","True"}
                        except Exception:
                            pass

                        steps: List[Dict[str, Any]]
                        if web_ok:
                            # Lightweight web fetch followed by knowledge synthesis
                            steps = [
                                {"type": "web_fetch", "payload": {"q": topic, "limit": 3}},
                                {"type": "analyze_knowledge", "payload": {"q": topic, "limit": 20, "save_knowledge": True, "title": f"User Question: {topic}"}},
                            ]
                        else:
                            steps = [
                                {"type": "analyze_knowledge", "payload": {"q": topic, "limit": 20, "save_knowledge": True, "title": f"User Question: {topic}"}}
                            ]
                        action["steps"] = steps
                        # If no explicit title was given, derive one
                        if not action.get("title"):
                            action["title"] = f"Default Knowledge Answer – {topic}"
                    except Exception:
                        pass
                    # Update debounce state immediately to prevent duplicate enqueues within this tick
                    state["catch_all_last_ts"] = now
                    state["catch_all_last_topic"] = topic
            except Exception:
                should = False

        if not should:
            continue
        # Execute: depending on autonomy level
        if lvl == 1:
            # Suggest: create a plan in queued state for review
            title = f"[Suggest] {rid}"
        else:
            title = f"[Auto] {rid}"
        steps: List[Dict[str, Any]] = []
        atype = str(action.get("type") or "")
        if atype == "knowledge_search":
            steps.append({"type": "knowledge_search", "payload": {"q": action.get("q") or "error", "limit": int(action.get("limit") or 3)}})
        elif atype in {"os_notify", "notify"}:
            steps.append({"type": "os_notify", "payload": {"text": action.get("text") or rid, "title": "Autonomy"}})
        elif atype == "plan_create":
            # Build a structured plan (default: reboot notification for a device)
            dev_id = str(rule.get("device_id") or action.get("device_id") or "").strip()
            thr = int(rule.get("offline_sec") or action.get("offline_sec") or 0)
            # Allow custom steps via action.steps
            custom_steps = action.get("steps") if isinstance(action.get("steps"), list) else None
            if custom_steps:
                steps = custom_steps
            else:
                # Default reboot notification plan
                msg = action.get("text") or (f"Device {dev_id} offline >{thr//60}min – Reboot notification" if dev_id and thr else "Reboot notification")
                steps = [
                    {"type": "os_notify", "payload": {"title": "Autonomy", "text": msg}},
                    {"type": "knowledge_add", "payload": {"source": "autonomy", "type": "note", "tags": "autonomy,device,intervention", "content": f"{msg} – protokolliert durch Autonomy"}},
                ]
                try:
                    if dev_id:
                        steps.append({
                            "type": "device_event",
                            "payload": {
                                "device_id": int(dev_id),
                                "event": {"type": "reboot_notification", "payload": {"reason": "autonomy_device_offline", "offline_sec": thr}}
                            }
                        })
                except Exception:
                    pass
            # Refine title, if provided
            try:
                t_override = action.get("title")
                if t_override:
                    title = t_override
                else:
                    # Keep prefix but add device context
                    if dev_id:
                        title = f"{title} – Reboot notification (dev {dev_id})"
                    else:
                        title = f"{title} – Reboot notification"
            except Exception:
                pass
        if atype == "hourly_summary":
            # Build last-hour plan summary and write knowledge reflection (hourly)
            try:
                now = int(time.time()); since = now - 3600
                items = []
                try:
                    # Pull recent plans (limit 200) and filter client-side by created_at
                    j = _api_get("/api/plan?limit=200")
                    items = list(j.get("items") or [])
                except Exception:
                    items = []
                last_hour = [p for p in items if int(p.get("created_at") or 0) >= since]
                total = len(last_hour)
                by = {"queued":0, "running":0, "done":0, "failed":0, "canceled":0}
                for p in last_hour:
                    st = str(p.get("status") or "").lower()
                    if st in by: by[st] += 1
                text = f"Letzte Stunde: {total} Pläne · done {by['done']} · failed {by['failed']} · queued {by['queued']} · running {by['running']} · canceled {by['canceled']}"
                # Append devices overview
                try:
                    sys = _api_get('/api/system/status')
                    m = (sys.get('metrics') or {})
                    doff = int(m.get('devices_offline') or 0)
                    dtot = m.get('devices_total')
                    if dtot is None:
                        text += f" · Geräte-Übersicht: {doff} offline"
                    else:
                        text += f" · Geräte-Übersicht: {doff} offline / {int(dtot)} total"
                except Exception:
                    pass
                # Write as knowledge reflection hourly
                try:
                    _api_post("/api/knowledge", {"source":"autonomy","type":"reflection","tags":"reflection,hourly","content": text})
                except Exception:
                    pass
                state[rid] = now
            except Exception:
                pass
        if atype == "config_hash_watch":
            # Compute file hashes and detect changes; files from rule.files or env GUARDIAN_WATCH_FILES
            try:
                import hashlib
                files = rule.get("files") or []
                if not files:
                    env = os.getenv("GUARDIAN_WATCH_FILES", "")
                    files = [p.strip() for p in env.split(",") if p.strip()]
                # read previous hashes
                prev = state.get("cfg_hashes") or {}
                changes = []
                for p in files:
                    try:
                        with open(p, "rb") as f:
                            h = hashlib.sha256(f.read()).hexdigest()
                        old = prev.get(p)
                        if old and old != h:
                            changes.append((p, old, h))
                        prev[p] = h
                    except Exception:
                        continue
                state["cfg_hashes"] = prev
                if changes:
                    # Notify + Knowledge
                    try:
                        text = "Konfigurationsänderung erkannt:\n" + "\n".join([c[0] for c in changes])
                        _api_post("/api/plan", {"title": "Guardian: Config geändert", "steps": [
                            {"type": "os_notify", "payload": {"title": "Guardian", "text": text}},
                            {"type": "knowledge_add", "payload": {"source": "guardian", "type": "note", "tags": "guardian,config,hash", "content": text}}
                        ]})
                    except Exception:
                        pass
                state[rid] = now
            except Exception:
                pass
        if atype == "rule_suggestions":
            # Analyze device offline patterns and suggest rules
            try:
                off = state.get("dev_offline_hist") or {}
                nowi = int(time.time())
                since24 = nowi - 24*3600
                since7d = nowi - 7*86400
                suggestions = []
                for did, arr in (off.items() if isinstance(off, dict) else []):
                    # 24h frequency suggestion
                    cnt24 = sum(1 for t in arr if int(t) >= since24)
                    if cnt24 >= 3:
                        suggestions.append(f"Device {did}: {cnt24}× offline in 24h → Regelvorschlag: device_offline reboot notification")
                    # Time-of-day pattern over 7 days
                    hours = {}
                    for t in arr:
                        it = int(t)
                        if it < since7d:
                            continue
                        hr = (time.localtime(it).tm_hour) % 24
                        hours[hr] = hours.get(hr, 0) + 1
                    if hours:
                        best_hr, best_cnt = max(hours.items(), key=lambda kv: kv[1])
                        # Heuristic threshold: at least 3 events and >= 50% of events in peak hour window
                        total7 = sum(hours.values())
                        if best_cnt >= 3 and best_cnt >= max(3, int(0.5 * total7)):
                            hh = f"{best_hr:02d}:00"
                            suggestions.append(f"Device {did}: Häufung um {hh} (letzte 7 Tage {best_cnt}/{total7}) → Regelvorschlag: geplanter Neustart {hh}")
                    # Weekday-morning pattern (last 21 days): e.g., Mondays morning 3×
                    try:
                        since21d = nowi - 21*86400
                        # map weekday -> count for events in morning window (5-11h)
                        wdc = {i:0 for i in range(7)}  # 0=Mon .. 6=Sun per time.localtime
                        total_wd = 0
                        for t in arr:
                            it = int(t)
                            if it < since21d:
                                continue
                            lt = time.localtime(it)
                            if 5 <= lt.tm_hour <= 11:
                                wdc[ (lt.tm_wday) ] += 1
                                total_wd += 1
                        if total_wd:
                            wd, cnt = max(wdc.items(), key=lambda kv: kv[1])
                            if cnt >= 3:
                                names = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
                                suggestions.append(f"Device {did}: Muster {names[wd]} morgens ({cnt}× in 21 Tagen) → Vorschlag: geplante Wartung {names[wd]} 06:00")
                    except Exception:
                        pass
                # Log correlation: look for frequent log types within 10 minutes before offline events (last 7 days)
                try:
                    # Pull recent logs; API shape may vary, keep defensive
                    logs = []
                    try:
                        lj = _api_get("/api/logs?limit=800")
                        if isinstance(lj, dict) and lj.get("items"):
                            logs = list(lj.get("items") or [])
                        elif isinstance(lj, list):
                            logs = lj
                    except Exception:
                        logs = []
                    # Build per-device correlation
                    idx_by_time = {}
                    for lg in logs:
                        try:
                            ts = int(lg.get("ts") or lg.get("created_at") or 0)
                            typ = str(lg.get("type") or lg.get("level") or lg.get("category") or "").strip() or "log"
                            dev = str(lg.get("device_id") or lg.get("dev") or "").strip()
                            if ts:
                                idx_by_time.setdefault(dev or "*", []).append((ts, typ))
                        except Exception:
                            continue
                    # sort lists
                    for k in list(idx_by_time.keys()):
                        idx_by_time[k].sort(key=lambda x: x[0])
                    window = 600  # 10 minutes
                    for did, arr in (off.items() if isinstance(off, dict) else []):
                        corr = {}
                        events = [int(t) for t in arr if int(t) >= since7d]
                        if not events:
                            continue
                        cand = idx_by_time.get(str(did)) or idx_by_time.get("*") or []
                        if not cand:
                            continue
                        # two-pointer scan
                        j = 0
                        for t in sorted(events):
                            while j < len(cand) and cand[j][0] < t - window:
                                j += 1
                            k = j
                            while k < len(cand) and cand[k][0] <= t:
                                typ = cand[k][1]
                                corr[typ] = corr.get(typ, 0) + 1
                                k += 1
                        if corr:
                            best_typ, cntb = max(corr.items(), key=lambda kv: kv[1])
                            if cntb >= 3 and cntb >= max(3, int(0.5 * len(events))):
                                suggestions.append(f"Device {did}: Vor Offline häufig Log '{best_typ}' (letzte 7 Tage {cntb}/{len(events)}) → Vorschlag: Wenn Log '{best_typ}', dann Neustart")
                except Exception:
                    pass
                # Guardian integration: recent config changes → suggest notify/block
                try:
                    q = _up.urlencode({"q":"tags:guardian,config,hash","limit":50})
                    k = _api_get(f"/api/knowledge/search?{q}")
                    items = list(k.get("items") or []) if isinstance(k, dict) else []
                    recent = [it for it in items if int(it.get("ts") or 0) >= since24]
                    if recent:
                        suggestions.append("Guardian: Jüngste Konfig‑Änderungen erkannt → Vorschlag: autonom alarmieren (os_notify) oder Änderungen blockieren")
                except Exception:
                    pass
                if suggestions:
                    content = "Vorschläge für Autonomy-Regeln (letzte 24h):\n" + "\n".join(f"- {s}" for s in suggestions)
                    try:
                        _api_post("/api/knowledge", {"source":"autonomy","type":"suggestion","tags":"autonomy,suggested_rule,heuristic","content": content})
                    except Exception:
                        pass
                state[rid] = now
            except Exception:
                pass
        if atype in {"daily_report", "weekly_report"}:
            # Aggregate plans and device offline incidents over period
            try:
                period_sec = 86400 if atype == "daily_report" else 7*86400
                since = now - period_sec
                # Plans aggregation
                items = []
                try:
                    j = _api_get("/api/plan?limit=500")
                    items = list(j.get("items") or [])
                except Exception:
                    items = []
                recent = [p for p in items if int(p.get("created_at") or 0) >= since]
                total = len(recent)
                by = {"queued":0, "running":0, "done":0, "failed":0, "canceled":0}
                for p in recent:
                    st = str(p.get("status") or "").lower()
                    if st in by: by[st] += 1
                # Device offline incidents from state
                off = state.get("dev_offline_hist") or {}
                per_dev: list[str] = []
                total_inc = 0
                for did, arr in (off.items() if isinstance(off, dict) else []):
                    try:
                        cnt = sum(1 for t in arr if int(t) >= since)
                        if cnt > 0:
                            per_dev.append(f"Device {did}: {cnt}× offline")
                            total_inc += cnt
                    except Exception:
                        continue
                headline = "Tagesbericht" if atype == "daily_report" else "Wochenbericht"
                lines = [
                    f"{headline} – Pläne: {total} (done {by['done']}, failed {by['failed']}, queued {by['queued']}, running {by['running']}, canceled {by['canceled']})",
                    f"Offline‑Vorfälle: {total_inc}" + ("\n" + "\n".join(per_dev) if per_dev else ""),
                ]
                content = "\n".join([l for l in lines if l])
                tags = "report,daily" if atype == "daily_report" else "report,weekly"
                try:
                    _api_post("/api/knowledge", {"source":"autonomy","type":"report","tags": tags, "content": content})
                except Exception:
                    pass
                state[rid] = now
            except Exception:
                pass
        if steps:
            try:
                _api_post("/api/plan", {"title": title, "steps": steps})
                state[rid] = now
            except Exception:
                pass
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _loop():
    while not _stop:
        try:
            _tick_once()
        except Exception:
            pass
        time.sleep(30)

@router.post("/start", include_in_schema=False)
def start_autonomy(user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    global _thread, _stop
    if _thread and _thread.is_alive():
        return {"ok": True, "running": True}
    _stop = False
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    return {"ok": True, "running": True}

@router.post("/stop", include_in_schema=False)
def stop_autonomy(user = Depends(get_current_user_required)):
    require_role(user, {"creator", "admin"})
    global _stop
    _stop = True
    return {"ok": True}
