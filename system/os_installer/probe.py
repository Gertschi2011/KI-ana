#!/usr/bin/env python3
from __future__ import annotations
import json, os, platform, shutil, subprocess
from pathlib import Path

def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=5)
        return out.strip()
    except Exception:
        return ""

def probe() -> dict:
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "ram_gb": None,
        "gpus": [],
        "has_ollama": bool(shutil.which("ollama")),
        "has_nvidia_smi": bool(shutil.which("nvidia-smi")),
    }
    # RAM (Linux)
    try:
        if info["os"] == "Linux":
            with open("/proc/meminfo") as f:
                first = f.readline()
                kb = int(first.split()[1])
                info["ram_gb"] = round(kb/1024/1024, 2)
    except Exception:
        pass

    # GPUs
    if info["has_nvidia_smi"]:
        out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
        if out:
            for line in out.splitlines():
                parts = [x.strip() for x in line.split(",", 1)]
                if parts:
                    info["gpus"].append({"name": parts[0], "memory": parts[1] if len(parts)>1 else ""})
    else:
        # Fallback: simple lspci grep
        if shutil.which("lspci"):
            out = _run(["lspci"])
            hits = [l for l in out.splitlines() if " VGA " in l or " 3D " in l]
            for h in hits:
                info["gpus"].append({"name": h})
    return info

if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))

