#!/usr/bin/env python3
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path.home() / "ki_ana"
LOGS_DIR = BASE_DIR / "logs"
THOUGHTS_LOG = LOGS_DIR / "thoughts.jsonl"


def _iso(ts: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts or time.time()))


def log_decision(
    *,
    component: str,
    action: str,
    input_ref: Optional[str] = None,
    outcome: str,
    reasons: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a structured decision record as JSONL for meta-cognition and audits.
    Fields:
      - component: subsystem making the decision (e.g., "crawler")
      - action: verb (e.g., "fetch", "store", "skip", "abort")
      - input_ref: URL, file path, or identifier
      - outcome: result (e.g., "saved", "skipped", "denied", "error")
      - reasons: brief human-readable rationale
      - meta: free-form additional data (hashes, sizes, policy flags)
    """
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": _iso(),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "component": component,
            "action": action,
            "input_ref": input_ref or "",
            "outcome": outcome,
            "reasons": reasons or "",
            "meta": meta or {},
        }
        with THOUGHTS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # Never crash callers due to logging
        pass


def log_reflection(topic: str, block: Dict[str, Any]) -> None:
    """Convenience wrapper to log a reflection outcome."""
    try:
        summary = (block.get("content") or "")[:160]
        log_decision(
            component="reflection",
            action="reflect_on_topic",
            input_ref=topic,
            outcome="saved",
            reasons="auto_reflection",
            meta={
                "block_id": block.get("id"),
                "topic": block.get("topic"),
                "linked_to": block.get("meta", {}).get("linked_to", []),
                "preview": summary,
            },
        )
    except Exception:
        pass


if __name__ == "__main__":
    log_decision(component="selftest", action="write", outcome="ok", reasons="initialization")
    print(f"logged to {THOUGHTS_LOG}")
