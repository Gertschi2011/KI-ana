import re, json, os
from pathlib import Path
PRIV = Path.home()/ "ki_ana/system/policies/privacy_rules.json"

def redact_text(text: str, source_domain: str = "") -> str:
    cfg = json.loads(PRIV.read_text(encoding="utf-8"))
    if source_domain and source_domain in (cfg.get("exempt_domains") or []):
        return text
    rules = cfg.get("redact",{}).get("patterns",[])
    repl = cfg.get("redact",{}).get("replacement","[REDACTED]")
    out = text
    for r in rules:
        flags = re.I if r.get("flags","") == "i" else 0
        out = re.sub(r["regex"], repl, out, flags=flags)
    return out
