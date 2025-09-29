# netapi/tools/kanactl.py
from __future__ import annotations
import argparse, json, os, sys, textwrap
from pathlib import Path
from typing import Dict, Any
from urllib import request, error

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR   = PROJECT_ROOT / "netapi" / "skills"

TPL_HANDLER = '''\
from __future__ import annotations
from typing import Dict, Any

def run(action: str, args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    action: vom Kernel übergeben (z.B. "scheduled", "do_something")
    args:   freie Argumente (JSON)
    ctx:    {"role","capabilities","skill","version"}
    """
    if action == "scheduled":
        # periodische Aufgabe (falls schedule gesetzt ist)
        return {"tick": True}

    if action in ("echo","demo"):
        text = str(args.get("text","(leer)"))
        return {"message": f"[{ctx.get('skill')}] {text}"}

    return {"ok": False, "error": "unknown_action", "action": action}
'''

TPL_MANIFEST = '''\
{
  "name": "%(name)s",
  "version": "0.1.0",
  "entrypoint": "netapi.skills.%(name)s.handler:run",
  "capabilities": %(caps_json)s,%(schedule_block)s
  "run_mode": "%(run_mode)s"
}
'''

def _http(method: str, url: str, payload: Dict[str, Any] | None = None, cookies: str | None = None) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    if cookies:
        req.add_header("Cookie", cookies)
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as e:
        try:
            return {"ok": False, "status": e.code, "detail": json.loads(e.read().decode("utf-8")).get("detail")}
        except Exception:
            return {"ok": False, "status": e.code, "detail": str(e)}
    except Exception as e:
        return {"ok": False, "detail": str(e)}

def cmd_new(args):
    name = args.name.strip().lower().replace("-", "_")
    caps = [c.strip() for c in (args.capabilities or "").split(",") if c.strip()]
    run_mode = args.run_mode.lower()
    sched_block = ""
    if args.every:
        sched_block = f'\n  "schedule": {{ "every_seconds": {int(args.every)} }},\n'
    elif args.cron:
        sched_block = f'\n  "schedule": {{ "cron": "{args.cron}" }},\n'

    pkg_dir = SKILLS_DIR / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "handler.py").write_text(TPL_HANDLER, encoding="utf-8")
    (pkg_dir / "manifest.json").write_text(
        TPL_MANIFEST % {
            "name": name,
            "caps_json": json.dumps(caps, ensure_ascii=False, indent=2),
            "schedule_block": sched_block,
            "run_mode": run_mode,
        },
        encoding="utf-8"
    )
    readme = textwrap.dedent(f"""\
    # Skill `{name}`

    - entrypoint: `netapi.skills.{name}.handler:run`
    - run_mode: `{run_mode}`
    - capabilities: {caps or []}
    - schedule: {"every_seconds="+str(args.every) if args.every else ("cron="+args.cron if args.cron else "(none)")}

    ## Test
    curl -sS -X POST http://localhost:8000/kernel/exec \\
      -H 'Content-Type: application/json' -b cookiejar \\
      -d '{{"skill":"{name}","action":"demo","args":{{"text":"Hi"}}}}' | jq .
    """)
    (pkg_dir / "README.md").write_text(readme, encoding="utf-8")
    print(f"✔ Skill-Skelett erstellt: netapi/skills/{name}")

def _api_base(args) -> str:
    return args.api.rstrip("/") or "http://localhost:8000"

def cmd_job_add(args):
    base = _api_base(args)
    schedule: Dict[str, Any] = {}
    if args.every:
        schedule["every_seconds"] = int(args.every)
    elif args.cron:
        schedule["cron"] = args.cron
    else:
        print("⚠ Bitte --every oder --cron angeben.")
        sys.exit(2)

    payload = {
        "skill": args.skill,
        "action": args.action,
        "args": json.loads(args.args or "{}"),
        "enabled": True,
        "schedule": schedule,
    }
    cookies = os.getenv("KANACTL_COOKIES")  # z.B. "session=..."
    res = _http("POST", f"{base}/kernel/jobs", payload, cookies)
    print(json.dumps(res, ensure_ascii=False, indent=2))

def cmd_job_list(args):
    base = _api_base(args)
    cookies = os.getenv("KANACTL_COOKIES")
    res = _http("GET", f"{base}/kernel/jobs", None, cookies)
    print(json.dumps(res, ensure_ascii=False, indent=2))

def cmd_job_toggle(args):
    base = _api_base(args)
    cookies = os.getenv("KANACTL_COOKIES")
    enabled = "true" if args.enable else "false"
    res = _http("POST", f"{base}/kernel/jobs/{args.id}/toggle?enabled={enabled}", None, cookies)
    print(json.dumps(res, ensure_ascii=False, indent=2))

def cmd_job_del(args):
    base = _api_base(args)
    cookies = os.getenv("KANACTL_COOKIES")
    res = _http("DELETE", f"{base}/kernel/jobs/{args.id}", None, cookies)
    print(json.dumps(res, ensure_ascii=False, indent=2))

def main():
    p = argparse.ArgumentParser(prog="kanactl", description="KI_ana Skill/Job CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="Neuen Skill erzeugen")
    p_new.add_argument("name")
    p_new.add_argument("--capabilities", "-c", default="")
    p_new.add_argument("--run-mode", choices=["inproc","subproc"], default="subproc")
    g = p_new.add_mutually_exclusive_group()
    g.add_argument("--every", type=int, help="Periodik in Sekunden")
    g.add_argument("--cron", type=str, help='Cron-Ausdruck, z.B. "*/5 * * * *"')
    p_new.set_defaults(func=cmd_new)

    # Jobs
    pjl = sub.add_parser("jobs", help="Jobs auflisten")
    pjl.add_argument("--api", default="http://localhost:8000")
    pjl.set_defaults(func=cmd_job_list)

    pja = sub.add_parser("job-add", help="Job hinzufügen")
    pja.add_argument("skill"); pja.add_argument("action")
    pja.add_argument("--args", default="{}")
    pja.add_argument("--every", type=int)
    pja.add_argument("--cron", type=str)
    pja.add_argument("--api", default="http://localhost:8000")
    pja.set_defaults(func=cmd_job_add)

    pjt = sub.add_parser("job-toggle", help="Job aktivieren/deaktivieren")
    pjt.add_argument("id"); pjt.add_argument("--enable", action="store_true")
    pjt.add_argument("--api", default="http://localhost:8000")
    pjt.set_defaults(func=cmd_job_toggle)

    pjd = sub.add_parser("job-del", help="Job löschen")
    pjd.add_argument("id"); pjd.add_argument("--api", default="http://localhost:8000")
    pjd.set_defaults(func=cmd_job_del)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
