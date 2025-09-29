#!/usr/bin/env python3
# system/skill_runner.py
from __future__ import annotations
import os, sys, json, time, shutil, subprocess, textwrap, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # ~/ki_ana
EXP = ROOT / "learning" / "experiments"
PENDING = EXP / "pending"
DONE = EXP / "done"
WORK = EXP / "work"
PYTHON = str((ROOT / ".venv" / "bin" / "python").resolve()) if (ROOT / ".venv" / "bin" / "python").exists() else sys.executable

def _ensure_dirs():
    for d in (PENDING, DONE, WORK):
        d.mkdir(parents=True, exist_ok=True)

def _now_ms() -> int:
    return int(time.time() * 1000)

def _read_json(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(p: Path, obj: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def _safe_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-","_",".")).strip() or f"task_{_now_ms()}"

def _move_to_done(task_path: Path, report: dict):
    done_name = task_path.name
    out_path = DONE / done_name
    # hänge Ergebnis unter "runner_report" an, damit die Original-Task erhalten bleibt
    try:
        original = _read_json(task_path)
    except Exception:
        original = {"kind":"unknown","raw": task_path.read_text("utf-8", errors="ignore")}
    original["runner_report"] = report
    _write_json(out_path, original)
    task_path.unlink(missing_ok=True)

# ---------- Code-Kata Ausführung ----------
def _run_code_kata(task: dict) -> dict:
    title = task.get("title") or "Kata"
    starter = task.get("starter") or ""
    tests = task.get("tests") or []
    if not isinstance(tests, list):
        tests = [str(tests)]

    wdir = WORK / f"{_now_ms()}_{_safe_filename(title)}"
    wdir.mkdir(parents=True, exist_ok=True)
    main_py = wdir / "solution.py"
    test_py = wdir / "test_run.py"
    log_txt = wdir / "runner.log"

    # Schreibe Starter
    main_py.write_text(starter, encoding="utf-8")

    # Baue Test-Läufer: importiere solution.py und führe asserts im try-block
    test_code = [
        "import sys, json, traceback, importlib.util, types",
        "from pathlib import Path",
        "wdir = Path(__file__).parent",
        "spec = importlib.util.spec_from_file_location('solution', str(wdir/'solution.py'))",
        "sol = importlib.util.module_from_spec(spec)",
        "try:",
        "    spec.loader.exec_module(sol)  # type: ignore",
        "except Exception as e:",
        "    print(json.dumps({'ok': False, 'phase':'import', 'error':str(e)})); raise",
        "results = []",
    ]
    for i, t in enumerate(tests, 1):
        test_code += [
            f"# --- test {i}",
            "try:",
            f"    " + t,
            "    results.append({'i':" + str(i) + ",'ok':True})",
            "except AssertionError as ae:",
            "    results.append({'i':" + str(i) + ",'ok':False,'assertion':str(ae)})",
            "except Exception as e:",
            "    results.append({'i':" + str(i) + ",'ok':False,'error':str(e)})",
        ]
    test_code += [
        "print(json.dumps({'ok': all(r.get('ok') for r in results), 'results':results}))"
    ]
    test_py.write_text("\n".join(test_code) + "\n", encoding="utf-8")

    # Führe Test-Läufer in Subprozess aus (Timeout & isoliertes CWD)
    cmd = [PYTHON, str(test_py)]
    try:
        proc = subprocess.run(
            cmd, cwd=str(wdir),
            capture_output=True, text=True,
            timeout=int(os.getenv("KATA_TIMEOUT_SEC", "10"))
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        log_txt.write_text(f"$ {' '.join(cmd)}\n\nSTDOUT:\n{out}\n\nSTDERR:\n{err}\n", encoding="utf-8")
        parsed = {}
        try:
            # letzten JSON-Print parsen
            last_line = [l for l in out.splitlines() if l.strip()][-1] if out else "{}"
            parsed = json.loads(last_line)
        except Exception:
            parsed = {"ok": False, "error": "parse_stdout_failed", "raw_stdout": out[:4000]}
        return {
            "ok": bool(parsed.get("ok")),
            "title": title,
            "work_dir": str(wdir),
            "stdout_last": parsed,
            "returncode": proc.returncode,
            "stderr": err[:4000],
            "when": int(time.time()),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "title": title,
            "error": "timeout",
            "timeout_sec": int(os.getenv("KATA_TIMEOUT_SEC", "10")),
            "when": int(time.time()),
        }
    except Exception as e:
        return {
            "ok": False,
            "title": title,
            "error": "runner_exception",
            "detail": str(e),
            "trace": traceback.format_exc(),
            "when": int(time.time()),
        }

# ---------- Web-Research (Stub → später anbinden) ----------
def _run_web_research(task: dict) -> dict:
    q = task.get("query") or ""
    return {
        "ok": True,
        "note": "web_research stub – später mit netapi/web_qa.py verbinden",
        "query": q,
        "when": int(time.time()),
    }

# ---------- Hauptschleife ----------
def process_once() -> int:
    _ensure_dirs()
    tasks = sorted(PENDING.glob("*.json"))
    count = 0
    for tpath in tasks:
        try:
            task = _read_json(tpath)
            kind = str(task.get("kind") or "unknown").lower()
            if kind == "code_kata":
                report = _run_code_kata(task)
            elif kind == "web_research":
                report = _run_web_research(task)
            else:
                report = {"ok": False, "error": f"unknown_kind:{kind}", "when": int(time.time())}
            _move_to_done(tpath, report)
            count += 1
        except Exception as e:
            # verschiebe defekte Task trotzdem nach done mit Fehlermeldung
            _move_to_done(tpath, {"ok": False, "error": "runner_crash", "detail": str(e), "trace": traceback.format_exc(), "when": int(time.time())})
            count += 1
    return count

def loop(poll_sec: int = 5):
    _ensure_dirs()
    print(f"[skill_runner] loop started; watching {PENDING}")
    while True:
        n = process_once()
        time.sleep(poll_sec if n == 0 else 0.2)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="nur einmal vorhandene Tasks verarbeiten")
    ap.add_argument("--loop", action="store_true", help="dauerhaft PENDING beobachten")
    ap.add_argument("--poll", type=int, default=5, help="Polling-Intervall (Sekunden)")
    args = ap.parse_args()

    _ensure_dirs()
    if args.once:
        c = process_once()
        print(f"processed: {c}")
        sys.exit(0)
    if args.loop:
        loop(args.poll)
    else:
        # Default: einmal
        c = process_once()
        print(f"processed: {c}")
