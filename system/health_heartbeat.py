import json, shutil, psutil, time
from pathlib import Path
STATUS = Path.home()/ "ki_ana/system/health/status.json"
OPEN_Q = Path.home()/ "ki_ana/memory/open_questions.json"
TO_LEARN = Path.home()/ "ki_ana/memory/to_learn.txt"

def heartbeat():
    disk = shutil.disk_usage(str(Path.home()))
    with open(OPEN_Q, "r", encoding="utf-8") as f: oq = len(json.load(f))
    tl = 0
    try:
        tl = len([l for l in open(TO_LEARN,"r",encoding="utf-8").read().splitlines() if l.strip()])
    except FileNotFoundError:
        pass
    data = {
        "last_heartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "queue": {"open_questions": oq, "to_learn": tl},
        "resources": {
            "cpu_pct": psutil.cpu_percent(interval=0.2),
            "mem_mb": psutil.virtual_memory().used/1024/1024,
            "disk_free_gb": round(disk.free/1024/1024/1024,2)
        },
        "anomalies": []
    }
    STATUS.write_text(json.dumps(data, indent=2), encoding="utf-8")

if __name__ == "__main__":
    heartbeat()
