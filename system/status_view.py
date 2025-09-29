#!/usr/bin/env python3
import json, shutil
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "ki_ana"
MEM  = BASE / "memory"
LT   = MEM / "long_term"
OPEN = MEM / "open_questions.json"
TL   = MEM / "to_learn.txt"
CHAIN= BASE / "system" / "chain"
AUD  = BASE / "system" / "audit" / "provenance_log.json"
HEAL = BASE / "system" / "health" / "status.json"

def read_json(p, default=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except: return default

def last_chain_block():
    files = sorted(CHAIN.glob("block_*.json"), key=lambda x: int(x.stem.split("_")[1]))
    if not files: return None, {}
    f = files[-1]
    d = read_json(f, {})
    return f.name, d

def count_audit():
    d = read_json(AUD, {"entries":[]})
    return len(d.get("entries", []))

def queue_lengths():
    oq = read_json(OPEN, {})
    try:
        tl_lines = [l.strip() for l in Path(TL).read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        tl_lines = []
    return len(oq), len(tl_lines)

def disk_free_gb():
    du = shutil.disk_usage(str(Path.home()))
    return round(du.free/1024/1024/1024, 2)

def main():
    now = datetime.utcnow().isoformat()+"Z"
    hb = read_json(HEAL, {})
    hb_time = hb.get("last_heartbeat", "-")
    hb_cpu  = hb.get("resources",{}).get("cpu_pct","-")
    hb_mem  = hb.get("resources",{}).get("mem_mb","-")
    hb_disk = hb.get("resources",{}).get("disk_free_gb","-")

    oq, tl = queue_lengths()
    fname, blk = last_chain_block()
    audit_n = count_audit()

    print("=== KI_ana Status ===")
    print(f"🕒 Jetzt (UTC):       {now}")
    print(f"💓 Letzter Heartbeat: {hb_time} | CPU {hb_cpu}% | RAM {hb_mem} MB | Free {hb_disk if hb_disk!='-' else disk_free_gb()} GB")
    print(f"🧾 Audit-Events:      {audit_n}")
    print(f"📬 Queues:            open_questions={oq} | to_learn={tl}")
    if blk:
        print(f"🔗 Chain-Head:        {fname} | type={blk.get('type')} | topic={blk.get('topic')} ")
        print(f"   prev={blk.get('previous_hash','')[:12]}… | hash={blk.get('hash','')[:12]}… | sig={'ja' if blk.get('signature') else 'nein'}")
        print(f"   source={blk.get('source')}")
    # letzter Memory-Block (optional)
    try:
        last_mem = max(LT.glob("*.json"), key=lambda p: p.stat().st_mtime)
        md = read_json(last_mem, {})
        print(f"🧠 Last memory:       {last_mem.name} | type={md.get('type')} | ts={md.get('timestamp')}")
    except ValueError:
        print("🧠 Last memory:       n/a")

if __name__ == "__main__":
    main()
