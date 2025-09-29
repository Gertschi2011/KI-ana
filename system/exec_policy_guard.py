import json, os, fnmatch, psutil
from pathlib import Path
POL = Path.home()/ "ki_ana/system/policies/exec_policy.json"

def check_network_domain(domain: str) -> bool:
    cfg = json.loads(POL.read_text(encoding="utf-8"))
    al = cfg["network"]["allowlist_domains"]
    dl = cfg["network"]["denylist_domains"]
    if any(fnmatch.fnmatch(domain, pat) for pat in dl): return False
    return any(domain.endswith(d) for d in al)

def check_fs_path_writable(path: str) -> bool:
    cfg = json.loads(POL.read_text(encoding="utf-8"))
    denies = cfg["filesystem"]["deny_patterns"]
    if any(fnmatch.fnmatch(path, p) for p in denies): return False
    allowed = cfg["filesystem"]["allowed_write_paths"]
    return any(path.startswith(os.path.expanduser(p)) for p in allowed)

def check_resource_limits() -> bool:
    cfg = json.loads(POL.read_text(encoding="utf-8"))
    cpu_ok = psutil.cpu_percent(interval=0.1) <= cfg["process"]["max_cpu_pct"]
    mem_ok = psutil.virtual_memory().used/1024/1024 <= cfg["process"]["max_mem_mb"]
    return cpu_ok and mem_ok
