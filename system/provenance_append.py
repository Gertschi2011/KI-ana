import json, hashlib, time
from pathlib import Path
LOG = Path.home()/ "ki_ana/system/audit/provenance_log.json"

def append_event(event: dict):
    d = json.loads(LOG.read_text(encoding="utf-8"))
    entries = d.get("entries",[])
    # Chain-Hash über Log-Einträge
    prev = entries[-1]["log_hash"] if entries else "GENESIS_LOG_HASH"
    payload = {k: event[k] for k in event}
    payload["prev_log_hash"] = prev
    payload["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    payload["log_hash"] = h
    entries.append(payload)
    d["entries"] = entries
    LOG.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
