import json, sys
from pathlib import Path
from passlib.hash import bcrypt

p = Path.home()/ "ki_ana/netapi/.auth.json"
if not p.exists():
    print("no auth file, nothing to migrate"); sys.exit(0)

d = json.loads(p.read_text(encoding="utf-8"))
users = d.get("users")
if not isinstance(users, list):
    # evtl. altes Format: {"user": "...", "pass": "..."}
    u = d.get("user"); pw = d.get("pass")
    if u and pw:
        users = [{"user": u, "pass": bcrypt.hash(pw), "role": "creator"}]
        d = {"users": users}
else:
    # transformiere pass->pass_hash wenn noch nicht gehashed
    for u in users:
        if "pass_hash" in u: continue
        pw = u.get("pass")
        if pw:
            u["pass_hash"] = bcrypt.hash(pw)
            u.pop("pass", None)

p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
print("✅ migrated:", p)
