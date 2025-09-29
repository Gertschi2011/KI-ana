import json, time
from collections import deque
from pathlib import Path

POL = Path.home()/ "ki_ana/system/policies/rate_limits.json"
STATE = Path.home()/ "ki_ana/system/health/ratelimit_state.json"

def now(): return time.time()

def load_cfg():
    return json.loads(POL.read_text(encoding="utf-8"))

def load_state():
    if not STATE.exists(): return {}
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(s):
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")

def allow(action: str, domain: str | None = None) -> bool:
    cfg = load_cfg()
    st = load_state()
    t = now()
    st.setdefault(action, [])
    st[action] = [x for x in st[action] if t - x < 3600]  # 1h Fenster
    # per-hour global
    hour_limit = cfg["global"]["per_hour"].get(action)
    if hour_limit and len(st[action]) >= hour_limit: return False
    # per-minute
    minute = [x for x in st[action] if t - x < 60]
    per_min = cfg["global"]["per_minute"].get(action)
    if per_min and len(minute) >= per_min: return False
    # per-domain (hour)
    if domain:
        key = f"{action}:{domain}"
        st.setdefault(key, [])
        st[key] = [x for x in st[key] if t - x < 3600]
        dlim = cfg.get("per_domain", {}).get(domain, {}).get("per_hour")
        if dlim and len(st[key]) >= dlim: return False
        st[key].append(t)
    st[action].append(t)
    save_state(st)
    return True
