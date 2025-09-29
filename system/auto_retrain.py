#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, shlex
from typing import Any, Dict, List, Optional
from pathlib import Path

BASE_DIR = Path.home() / "ki_ana"
SYSTEM_DIR = BASE_DIR / "system"

try:
    from importlib.machinery import SourceFileLoader
    REFLECT_PATH = SYSTEM_DIR / "reflection_engine.py"
    _reflect = SourceFileLoader("reflection_engine", str(REFLECT_PATH)).load_module() if REFLECT_PATH.exists() else None  # type: ignore
except Exception:
    _reflect = None  # type: ignore

try:
    from system.thought_logger import log_decision  # type: ignore
except Exception:
    def log_decision(**kwargs):
        pass

TRUSTED_SEEDS = [
    "https://de.wikipedia.org/wiki/{}",
    "https://en.wikipedia.org/wiki/{}",
    "https://www.bbc.co.uk/search?q={}",
    "https://www.nature.com/search?q={}",
    "https://www.who.int/search?q={}",
]


def _topic_to_urls(topic: str) -> List[str]:
    q = topic.strip().replace(" ", "%20")
    urls = [u.format(q) for u in TRUSTED_SEEDS]
    # dewiki page lookup prefers underscores
    urls[0] = TRUSTED_SEEDS[0].format(topic.strip().replace(" ", "_"))
    urls[1] = TRUSTED_SEEDS[1].format(topic.strip().replace(" ", "_"))
    return urls


def identify_gaps(topic: str) -> Dict[str, Any]:
    blocks = []
    try:
        mem_dir = BASE_DIR / "memory" / "long_term" / "blocks"
        for p in mem_dir.glob("*.json"):
            try:
                b = json.loads(p.read_text(encoding="utf-8"))
                if (b.get("topic") or "").lower() == topic.lower():
                    blocks.append(b)
            except Exception:
                continue
    except Exception:
        pass
    if _reflect and hasattr(_reflect, "reflect_blocks_by_topic"):
        return _reflect.reflect_blocks_by_topic(topic, blocks)  # type: ignore
    return {"topic": topic, "insights": "", "corrections": []}


def fetch_sources(topic: str) -> List[Dict[str, Any]]:
    urls = _topic_to_urls(topic)
    results: List[Dict[str, Any]] = []
    crawler = SYSTEM_DIR / "web_crawler.py"
    for u in urls:
        try:
            cmd = f"python {shlex.quote(str(crawler))} {shlex.quote(u)}"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(BASE_DIR))
            ok = proc.returncode == 0
            results.append({
                "url": u,
                "ok": ok,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-2000:],
                "code": proc.returncode,
            })
        except Exception as e:
            results.append({"url": u, "ok": False, "error": str(e)})
    return results


def auto_retrain(topic: str, max_sources: int = 5) -> Dict[str, Any]:
    gaps = identify_gaps(topic)
    log_decision(component="self_opt", action="identify_gaps", outcome="ok", reasons=["reflection"], meta={"topic": topic})
    fetched = fetch_sources(topic)[:max_sources]
    log_decision(component="self_opt", action="fetch_sources", outcome="ok", reasons=["trusted_seeds"], meta={"topic": topic, "count": len(fetched)})
    return {"ok": True, "topic": topic, "gaps": gaps, "fetched": fetched}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", type=str)
    ap.add_argument("--max_sources", type=int, default=5)
    args = ap.parse_args()
    res = auto_retrain(args.topic, max_sources=args.max_sources)
    print(json.dumps(res, ensure_ascii=False, indent=2))
