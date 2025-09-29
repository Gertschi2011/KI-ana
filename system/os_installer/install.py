#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    try:
        return subprocess.call(cmd)
    except Exception as e:
        print("error:", e)
        return 1

def main() -> int:
    print("KI_ana OS Installer – probing device…")
    # Load user config if present
    cfg = {}
    if (BASE / "config.json").exists():
        try:
            cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    # Probe hardware/software
    try:
        import probe  # local module
    except Exception:
        print("probe not found")
        return 1
    info = probe.probe()
    print(json.dumps(info, indent=2))

    # Optional: consult Mother‑KI for best‑practice advice using web_qa via server API
    server_base = str(cfg.get("server_base") or "").strip()
    advice = {}
    if server_base:
        import requests
        queries = []
        osname = info.get("os")
        rel = info.get("os_release")
        mach = info.get("machine")
        if osname and rel:
            queries.append(f"Optimale Ollama Installation für {osname} {rel} {mach}")
        if info.get("gpus"):
            g0 = info["gpus"][0]
            gname = g0.get("name") if isinstance(g0, dict) else str(g0)
            queries.append(f"Beste GPU‑Einstellungen und Treiber für {gname} unter {osname} {rel}")
        if not queries:
            queries = [f"Empfohlene KI‑Laufzeitumgebung für {osname} {rel} {mach}"]

        advice = {"items": []}
        for q in queries:
            try:
                r = requests.post(server_base.rstrip('/') + "/api/web/qa", json={"question": q, "max_results": 3}, timeout=20)
                data = r.json() if r.ok else {"ok": False}
                advice["items"].append({"query": q, "response": data})
            except Exception:
                advice["items"].append({"query": q, "error": "fetch_failed"})
        # store advice report
        report_dir = BASE / "reports"; report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "advice.json").write_text(json.dumps({"probe": info, "advice": advice}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Simple recommendations / actions
    actions: list[str] = []
    osname = info.get("os")
    if osname == "Linux":
        # Ensure Python3/pip and recommended packages
        actions.append("sudo apt-get update || true")
        actions.append("sudo apt-get install -y python3 python3-venv curl || true")
        if not info.get("has_ollama"):
            actions.append("curl -fsSL https://ollama.com/install.sh | sh")
        if info.get("has_nvidia_smi"):
            actions.append("echo 'NVIDIA GPU erkannt – erwäge CUDA/treiber Feinabstimmung' ")
    elif osname == "Darwin":
        actions.append("/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        actions.append("brew install ollama || true")
    elif osname == "Windows":
        actions.append("echo Bitte Chocolatey installieren und Ollama Setup ausführen.")

    print("\n— Vorschlag: folgende Schritte ausführen —")
    for a in actions:
        print("  ", a)

    # Auto‑Modus: führe Befehle aus
    auto = os.getenv("AUTO_INSTALL", "0") == "1" or "--auto" in sys.argv
    if auto:
        print("\n[auto] Starte automatische Installation…")
        for a in actions:
            run(["bash", "-lc", a])

        # Modellwahl und Pull
        try:
            # Heuristik: GPU VRAM? sonst RAM
            model = "llama3.1:8b"
            if info.get("gpus"):
                # naive: für GPUs mit >=16GB z. B. 13b
                model = "llama3.1:13b"
            elif (info.get("ram_gb") or 0) >= 24:
                model = "llama3.1:13b"
            run(["bash", "-lc", f"ollama pull {model}"])
        except Exception:
            pass

        # Optional: KI_ana Service einrichten (falls Repo vorhanden)
        try:
            root = Path.home() / "ki_ana"
            venv_uvicorn = root / ".venv" / "bin" / "uvicorn"
            app_path = root / "netapi" / "app.py"
            if root.exists() and venv_uvicorn.exists() and app_path.exists():
                svc = (
                    "[Unit]\n"
                    "Description=KI_ana API (FastAPI + Uvicorn)\nAfter=network.target\n\n"
                    "[Service]\n"
                    f"User={os.getenv('USER','kiana')}\n"
                    f"WorkingDirectory={str(root)}\n"
                    f"ExecStart={str(venv_uvicorn)} netapi.app:app --host 127.0.0.1 --port 8000\n"
                    "Restart=on-failure\nRestartSec=3\nKillSignal=SIGINT\nTimeoutStopSec=10\n\n"
                    "[Install]\nWantedBy=multi-user.target\n"
                )
                tmp = Path("/tmp/kiana.service")
                tmp.write_text(svc, encoding="utf-8")
                run(["bash", "-lc", "sudo mv /tmp/kiana.service /etc/systemd/system/kiana.service && sudo systemctl daemon-reload && sudo systemctl enable --now kiana"])
        except Exception:
            pass

    # Create a local venv for KI_ana if not present
    root = Path.home() / "ki_ana"
    venv = root / ".venv"
    if not venv.exists():
        print("Erzeuge Python‑Umgebung…")
        run([sys.executable, "-m", "venv", str(venv)])
    print("Fertig. Lies README für weitere Schritte.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
