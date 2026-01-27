#!/usr/bin/env python3
"""LiveLog producer: watches blocks directory and pushes events to /api/livelog/event.

Design goals:
- Separate process (no backend request-path impact)
- Attribution on OPEN (best chance to catch PID/command)
- Integrity check on CLOSE_WRITE / MOVED_TO (file is final-ish)
- Best-effort, non-fatal operation (never crashes the system)
- Dedupe/rate-limit to avoid flooding

Auth options:
- --token or env ADMIN_API_TOKEN / KIANA_ADMIN_API_TOKEN
- --cookie "name=value; ..."
- --cookiejar (Netscape cookie file) best-effort

Requires: inotifywait (package: inotify-tools)
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _safe_str(v: Any, limit: int = 800) -> str:
    try:
        s = str(v)
    except Exception:
        return ""
    return s[:limit]


def _which(cmd: str) -> Optional[str]:
    try:
        return shutil.which(cmd)
    except Exception:
        return None


def _need_sudo() -> bool:
    try:
        return os.geteuid() != 0
    except Exception:
        return True


def _run(cmd: List[str], *, use_sudo: bool, timeout: float = 1.5) -> Tuple[int, str, str]:
    full = cmd
    if use_sudo and _need_sudo() and _which("sudo"):
        # -n => non-interactive; if it fails, we still continue best-effort.
        full = ["sudo", "-n"] + cmd

    try:
        p = subprocess.run(
            full,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return int(p.returncode), p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 127, "", f"exec_failed:{e}"


def _stat_file(path: Path) -> Dict[str, Any]:
    try:
        st = path.stat()
        return {
            "size": int(st.st_size),
            "owner": f"{st.st_uid}:{st.st_gid}",
            "mode": oct(st.st_mode & 0o777),
            "mtime": int(st.st_mtime),
        }
    except Exception as e:
        return {"stat_error": _safe_str(e, 200)}


def _json_ok(path: Path, max_bytes: int = 2_000_000) -> Tuple[bool, Optional[str]]:
    try:
        raw = path.read_bytes()
        if not raw:
            return False, "empty"
        if len(raw) > max_bytes:
            # Still validate prefix to avoid huge reads; but we already read it.
            pass
        json.loads(raw.decode("utf-8"))
        return True, None
    except Exception as e:
        return False, _safe_str(e, 240)


_CID_RE = re.compile(r"([0-9a-f]{64})")


def _container_hint(pid: str, *, use_sudo: bool) -> Dict[str, Any]:
    # Usually readable without sudo; but be tolerant.
    out: Dict[str, Any] = {}

    cg = Path("/proc") / str(pid) / "cgroup"
    try:
        txt = cg.read_text(encoding="utf-8", errors="replace")
        lines = txt.splitlines()[:5]
        out["cgroup_head"] = lines
        m = _CID_RE.search(txt)
        if m:
            out["container_id"] = m.group(1)
    except Exception:
        return out

    # Optional docker mapping
    cid = out.get("container_id")
    if cid and _which("docker"):
        rc, stdout, _ = _run(
            ["docker", "ps", "--no-trunc", "--format", "{{.ID}} {{.Names}}"],
            use_sudo=use_sudo,
            timeout=2.5,
        )
        if rc == 0 and stdout:
            for line in stdout.splitlines():
                if str(cid) in line:
                    out["docker_match"] = line.strip()
                    break
    return out


def _attribution(file_path: Path, *, use_sudo: bool) -> Dict[str, Any]:
    # Best-effort: lsof -t first, fallback to fuser
    res: Dict[str, Any] = {}

    pids: List[str] = []

    rc, stdout, _ = _run(["lsof", "-n", "-t", "--", str(file_path)], use_sudo=use_sudo, timeout=1.5)
    if rc == 0 and stdout.strip():
        pids = sorted({ln.strip() for ln in stdout.splitlines() if ln.strip().isdigit()})
    else:
        rc2, stdout2, _ = _run(["fuser", str(file_path)], use_sudo=use_sudo, timeout=1.5)
        if rc2 == 0 and stdout2.strip():
            # fuser output can be: "/path: 123 456" or "123" depending on version.
            pids = re.findall(r"\b(\d+)\b", stdout2)

    if not pids:
        return res

    res["pids"] = pids

    # pick first PID as primary
    pid = pids[0]
    res["pid"] = pid

    rc3, ps_out, _ = _run(["ps", "-o", "pid=,ppid=,user=,cmd=", "-p", pid], use_sudo=False, timeout=1.5)
    if rc3 == 0 and ps_out.strip():
        # Format: " 123  1 user cmd..."
        line = ps_out.strip().splitlines()[0]
        parts = line.split(None, 3)
        if len(parts) >= 4:
            res["ppid"] = parts[1]
            res["user"] = parts[2]
            res["cmd"] = parts[3]

    # container hints
    try:
        hint = _container_hint(pid, use_sudo=use_sudo)
        if hint:
            res["container_hint"] = hint
            # Provide a single flattened container string if possible.
            if isinstance(hint.get("docker_match"), str):
                # "<id> <name>"
                res["container"] = hint["docker_match"].split(None, 1)[1] if " " in hint["docker_match"] else hint["docker_match"]
    except Exception:
        pass

    return res


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float = 4.0) -> Tuple[bool, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return True, raw[:500]
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return False, f"http_{e.code}:{body[:500]}"
    except Exception as e:
        return False, f"post_failed:{e}"


def _load_netscape_cookiejar(cookiejar_path: Path, base_url: str) -> Optional[str]:
    # Very small Netscape cookiejar parser to build a Cookie header.
    try:
        u = urllib.parse.urlparse(base_url)
        host = (u.hostname or "").lower()
        if not host:
            return None

        now = int(time.time())
        cookies: Dict[str, str] = {}
        for line in cookiejar_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _flag, path, _secure, exp, name, value = parts[:7]
            domain = domain.lstrip(".").lower()
            if domain and not (host == domain or host.endswith("." + domain)):
                continue
            try:
                exp_i = int(float(exp))
                if exp_i and exp_i < now:
                    continue
            except Exception:
                pass
            cookies[name] = value

        if not cookies:
            return None

        return "; ".join([f"{k}={v}" for k, v in cookies.items()])
    except Exception:
        return None


def _auth_headers(args: argparse.Namespace) -> Dict[str, str]:
    headers: Dict[str, str] = {}

    token = (args.token or "").strip()
    if not token:
        token = (os.getenv("ADMIN_API_TOKEN") or os.getenv("KIANA_ADMIN_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    cookie = (args.cookie or "").strip()
    if not cookie and args.cookiejar:
        cj = Path(args.cookiejar)
        ch = _load_netscape_cookiejar(cj, args.base_url)
        if ch:
            cookie = ch

    if cookie:
        headers["Cookie"] = cookie

    return headers


@dataclasses.dataclass
class Dedupe:
    ttl_s: float = 2.0
    _last: Dict[str, float] = dataclasses.field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = time.time()
        t = self._last.get(key)
        if t is not None and now - t < self.ttl_s:
            return False
        self._last[key] = now
        return True


def main() -> int:
    ap = argparse.ArgumentParser(description="LiveLog producer for block writes (inotify -> /api/livelog/event)")
    ap.add_argument(
        "watch_dir",
        nargs="?",
        default=str(Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana"))) / "memory" / "long_term" / "blocks"),
        help="Directory to watch (default: $KI_ROOT/memory/long_term/blocks)",
    )
    ap.add_argument("--base-url", default=os.getenv("KIANA_BASE_URL", "http://127.0.0.1:8000"), help="Base URL for API")
    ap.add_argument("--token", default="", help="Bearer token (creator/admin). Falls back to env ADMIN_API_TOKEN")
    ap.add_argument("--cookie", default="", help="Raw Cookie header value (e.g. 'ki_session=...; ...')")
    ap.add_argument("--cookiejar", default="", help="Path to Netscape cookiejar file")
    ap.add_argument("--use-sudo", action="store_true", default=False, help="Try sudo -n for lsof/fuser/docker")
    ap.add_argument("--dedupe-seconds", type=float, default=2.0, help="Dedupe TTL per (event,file,pid)")
    ap.add_argument("--dry-run", action="store_true", help="Print events but do not POST")
    ap.add_argument("--print", dest="print_events", action="store_true", help="Also print each event JSON")
    ap.add_argument("--quiet", action="store_true", help="Less console output")

    args = ap.parse_args()

    watch_dir = Path(args.watch_dir).expanduser().resolve()
    if not watch_dir.exists() or not watch_dir.is_dir():
        print(f"watch_dir missing/not a dir: {watch_dir}", file=sys.stderr)
        return 2

    if not _which("inotifywait"):
        print("missing dependency: inotifywait (package: inotify-tools)", file=sys.stderr)
        return 2

    if not _which("lsof"):
        print("warning: lsof not found (attribution will be weaker)", file=sys.stderr)
    if not _which("fuser"):
        print("warning: fuser not found (attribution will be weaker)", file=sys.stderr)

    api = urllib.parse.urljoin(args.base_url.rstrip("/") + "/", "api/livelog/event")
    headers = _auth_headers(args)

    if not headers.get("Authorization") and not headers.get("Cookie"):
        print(
            "warning: no auth provided; POST will likely be 401/403. "
            "Use --token/--cookie/--cookiejar or env ADMIN_API_TOKEN.",
            file=sys.stderr,
        )

    dedupe = Dedupe(ttl_s=float(args.dedupe_seconds))

    cmd = [
        "inotifywait",
        "-m",
        "-e",
        "open,create,close_write,move",
        "--format",
        "%T|%e|%w%f",
        "--timefmt",
        "%F %T",
        str(watch_dir),
    ]

    if not args.quiet:
        print(f"Watching: {watch_dir}")
        print(f"Posting to: {api}")

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def send(evt: Dict[str, Any]) -> None:
        evt.setdefault("ts", _iso_now())
        evt.setdefault("topic", "blocks")
        if args.print_events and not args.quiet:
            print(json.dumps(evt, ensure_ascii=False))
        if args.dry_run:
            return
        ok, info = _post_json(api, evt, headers)
        if not ok and not args.quiet:
            print(f"POST failed: {info}", file=sys.stderr)

    try:
        assert p.stdout is not None
        for line in p.stdout:
            line = line.strip()
            if not line:
                continue

            # Parse: ts|EVENTS|/path
            parts = line.split("|", 2)
            if len(parts) != 3:
                continue
            ts, ev, file_s = parts
            file_path = Path(file_s)

            # Normalize event string: can be "OPEN" or "OPEN,ISDIR" etc.
            ev_up = ev.upper()

            # Attribution on OPEN
            if "OPEN" in ev_up:
                attrib: Dict[str, Any] = {}
                # do a few small retries: the fd might appear a tick later
                for _ in range(5):
                    attrib = _attribution(file_path, use_sudo=bool(args.use_sudo))
                    if attrib.get("pid") or attrib.get("pids"):
                        break
                    time.sleep(0.05)

                pid = _safe_str(attrib.get("pid") or "")
                key = f"open|{file_path}|{pid}"
                if not dedupe.allow(key):
                    continue

                evt: Dict[str, Any] = {
                    "ts": ts,
                    "kind": "blocks_open",
                    "path": _safe_str(str(file_path)),
                    "pid": attrib.get("pid"),
                    "user": attrib.get("user"),
                    "cmd": attrib.get("cmd"),
                    "container": attrib.get("container"),
                    "data": {k: v for (k, v) in attrib.items() if k not in {"pid", "user", "cmd", "container"}},
                }
                send(evt)
                continue

            # Integrity on close_write / moved_to
            if "CLOSE_WRITE" in ev_up or "MOVED_TO" in ev_up:
                key = f"final|{file_path}"
                if not dedupe.allow(key):
                    continue

                evt: Dict[str, Any] = {
                    "ts": ts,
                    "kind": "blocks_integrity",
                    "path": _safe_str(str(file_path)),
                }
                if file_path.exists() and file_path.is_file():
                    evt.update(_stat_file(file_path))
                    ok, err = _json_ok(file_path)
                    evt["json_ok"] = bool(ok)
                    if err:
                        evt["json_error"] = err
                else:
                    evt["missing"] = True

                send(evt)
                continue

    except KeyboardInterrupt:
        return 130
    finally:
        try:
            p.terminate()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
