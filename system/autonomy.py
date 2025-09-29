#!/usr/bin/env python3
from __future__ import annotations
import asyncio, os, random, time
from typing import List, Dict, Any
from pathlib import Path
from importlib.machinery import SourceFileLoader

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"


def _load(module: str, rel: str):
    return SourceFileLoader(module, str(BASE_DIR / rel)).load_module()  # type: ignore


def _conscience_allow(action: str, context: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cons = _load("conscience", "system/conscience.py")
        res = cons.review_action(component="autonomy", action=action, context=context)  # type: ignore
        return res or {"decision": "allow", "risk": 0.0}
    except Exception:
        return {"decision": "allow", "risk": 0.0, "reasons": ["conscience_error"]}


def _recent_topics(limit: int = 5) -> List[str]:
    topics: List[str] = []
    for p in sorted(BLOCKS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:200]:
        try:
            import json
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        t = (b.get("topic") or "").strip()
        if t and t not in topics:
            topics.append(t)
        if len(topics) >= limit:
            break
    return topics


async def loop_self_reflection(stop: asyncio.Event):
    sr = _load("self_reflection", "system/self_reflection.py")
    base_wait = int(os.getenv("KI_AUTONOMY_REFLECT_SECS", "3600"))  # default hourly
    while not stop.is_set():
        jitter = random.randint(-300, 300)
        ctx = {"external_network": False, "loop": "self_reflection"}
        if _conscience_allow("self_reflection", ctx).get("decision") != "block":
            try:
                sr.reflect(max_blocks=200, write_blocks=True)  # type: ignore
            except Exception:
                pass
        await asyncio.wait_for(stop.wait(), timeout=max(60, base_wait + jitter))


async def loop_knowledge_update(stop: asyncio.Event):
    ku = _load("knowledge_update", "system/knowledge_update.py")
    base_wait = int(os.getenv("KI_AUTONOMY_UPDATE_SECS", "21600"))  # default 6h
    while not stop.is_set():
        jitter = random.randint(-900, 900)
        topics = _recent_topics(limit=3)
        for t in topics:
            ctx = {"external_network": True, "topic": t, "loop": "knowledge_update"}
            res = _conscience_allow("knowledge_update", ctx)
            if res.get("decision") == "block":
                continue
            try:
                ku.propose_updates(topic=t, max_sources=3)  # type: ignore
            except Exception:
                continue
        await asyncio.wait_for(stop.wait(), timeout=max(300, base_wait + jitter))


class AutonomyManager:
    def __init__(self):
        self.stop = asyncio.Event()
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        if os.getenv("KI_AUTONOMY_ENABLED", "1") not in ("1", "true", "True"):  # opt-out
            return
        self.tasks.append(asyncio.create_task(loop_self_reflection(self.stop)))
        self.tasks.append(asyncio.create_task(loop_knowledge_update(self.stop)))

    async def shutdown(self):
        self.stop.set()
        for t in self.tasks:
            try:
                await asyncio.wait_for(t, timeout=5)
            except Exception:
                pass
        self.tasks.clear()


# For manual run
if __name__ == "__main__":
    async def _main():
        mgr = AutonomyManager()
        await mgr.start()
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await mgr.shutdown()
    asyncio.run(_main())
