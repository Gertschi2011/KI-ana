from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class GateState:
    active: Tuple[str, ...]
    reasons: Dict[str, str]
    enforced: bool
    enforced_gates: Tuple[str, ...]


def _env_bool(name: str, default: str = "0") -> bool:
    try:
        return (os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"})
    except Exception:
        return (default.strip().lower() in {"1", "true", "yes", "on"})


def _redis_client():
    try:
        import redis  # type: ignore

        host = (os.getenv("REDIS_HOST") or "redis").strip() or "redis"
        port = int((os.getenv("REDIS_PORT") or "6379").strip() or 6379)
        return redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
        )
    except Exception:
        return None


def _bucket_ts(now: Optional[float] = None, *, bucket_seconds: int = 60) -> int:
    t = float(time.time() if now is None else now)
    b = int(bucket_seconds)
    if b <= 0:
        b = 60
    return int(t // b) * b


def _roll_key(metric: str, bucket_ts: int, suffix: str = "") -> str:
    m = (str(metric or "").strip().lower() or "unknown").replace(" ", "_")
    sfx = (str(suffix or "").strip().lower() or "")
    if sfx:
        sfx = sfx.replace(" ", "_")
        return f"kiana:quality:roll:{m}:{sfx}:{int(bucket_ts)}"
    return f"kiana:quality:roll:{m}:{int(bucket_ts)}"


def _gate_key(name: str) -> str:
    n = (str(name or "").strip().lower() or "unknown").replace(" ", "_")
    return f"kiana:quality:gate:{n}"


def _incr_roll(*, metric: str, suffix: str = "", ttl_seconds: int = 1200) -> None:
    r = _redis_client()
    if r is None:
        return
    try:
        ts = _bucket_ts()
        key = _roll_key(metric, ts, suffix)
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, int(ttl_seconds))
        pipe.execute()
    except Exception:
        return


def _sum_roll(*, metric: str, suffix: str = "", window_seconds: int = 600) -> int:
    r = _redis_client()
    if r is None:
        return 0
    try:
        now = time.time()
        end = _bucket_ts(now)
        step = 60
        n = max(1, int(window_seconds) // step)
        keys = [_roll_key(metric, end - i * step, suffix) for i in range(n)]
        vals = r.mget(keys)  # type: ignore
        total = 0
        for v in vals or []:
            try:
                total += int(float(v))
            except Exception:
                continue
        return int(total)
    except Exception:
        return 0


def record_tool_call(*, ok: bool) -> None:
    metric = "tool_ok" if bool(ok) else "tool_err"
    _incr_roll(metric=metric, ttl_seconds=60 * 20)


def record_answer(*, intent: str, source_expected: bool, sources_count: int) -> None:
    i = (str(intent or "unknown").strip().lower() or "unknown")
    _incr_roll(metric="answers_total", ttl_seconds=60 * 20)
    _incr_roll(metric="answers_total", suffix=f"intent={i}", ttl_seconds=60 * 20)

    if bool(source_expected) and int(sources_count or 0) <= 0:
        _incr_roll(metric="answers_without_sources", suffix=f"intent={i}", ttl_seconds=60 * 20)


def record_learning_prompt(*, kind: str = "style") -> None:
    k = (str(kind or "unknown").strip().lower() or "unknown")
    _incr_roll(metric="learning_prompt", suffix=f"kind={k}", ttl_seconds=60 * 40)


def set_gate_active(*, gate: str, ttl_seconds: int, reason: str) -> None:
    r = _redis_client()
    if r is None:
        return
    try:
        r.set(_gate_key(gate), str(reason or "1")[:200], ex=int(ttl_seconds))
    except Exception:
        return


def get_gate_reason(gate: str) -> Optional[str]:
    r = _redis_client()
    if r is None:
        return None
    try:
        v = r.get(_gate_key(gate))
        if v is None:
            return None
        return str(v)
    except Exception:
        return None


def is_gate_active(gate: str) -> bool:
    r = _redis_client()
    if r is None:
        return False
    try:
        return bool(r.exists(_gate_key(gate)))
    except Exception:
        return False


def evaluate_gates() -> GateState:
    """Evaluate gates based on rolling counters and refresh TTL-based gate keys.

    Observational is default: enforcement depends on env flags.
    This must never raise.
    """

    # Config (conservative, low-noise defaults)
    window_s = 10 * 60

    TOOL_ERR_TRIGGER = 0.06
    TOOL_GATE_TTL = 10 * 60

    NO_SOURCES_TRIGGER = 0.10
    SOURCES_GATE_TTL = 20 * 60

    CONSENT_PROMPT_TRIGGER = 0.30
    LEARNING_GATE_TTL = 30 * 60

    reasons: Dict[str, str] = {}

    # Tool error rate gate
    tool_err = _sum_roll(metric="tool_err", window_seconds=window_s)
    tool_ok = _sum_roll(metric="tool_ok", window_seconds=window_s)
    tool_total = max(0, int(tool_err + tool_ok))
    tool_rate = (float(tool_err) / float(tool_total)) if tool_total > 0 else 0.0
    if tool_total >= 10 and tool_rate > TOOL_ERR_TRIGGER:
        reasons["tools_disabled"] = f"tool_error_rate_high:{tool_rate:.3f}"
        set_gate_active(gate="tools_disabled", ttl_seconds=TOOL_GATE_TTL, reason=reasons["tools_disabled"])

    # No-sources gate (proxy) for factual|research intents
    ns_factual = _sum_roll(metric="answers_without_sources", suffix="intent=factual", window_seconds=window_s)
    ns_research = _sum_roll(metric="answers_without_sources", suffix="intent=research", window_seconds=window_s)
    ans_factual = _sum_roll(metric="answers_total", suffix="intent=factual", window_seconds=window_s)
    ans_research = _sum_roll(metric="answers_total", suffix="intent=research", window_seconds=window_s)
    ns_total = int(ns_factual + ns_research)
    ans_total = int(ans_factual + ans_research)
    ns_rate = (float(ns_total) / float(ans_total)) if ans_total > 0 else 0.0
    if ans_total >= 10 and ns_rate > NO_SOURCES_TRIGGER:
        reasons["sources_required"] = f"no_sources_rate_high:{ns_rate:.3f}"
        set_gate_active(gate="sources_required", ttl_seconds=SOURCES_GATE_TTL, reason=reasons["sources_required"])

    # Learning consent prompt cooldown gate (anti-spam)
    prompts_style = _sum_roll(metric="learning_prompt", suffix="kind=style", window_seconds=window_s)
    answers_all = _sum_roll(metric="answers_total", window_seconds=window_s)
    prompt_rate = (float(prompts_style) / float(answers_all)) if answers_all > 0 else 0.0
    if answers_all >= 10 and prompt_rate > CONSENT_PROMPT_TRIGGER:
        reasons["learning_cooldown"] = f"consent_prompt_rate_high:{prompt_rate:.3f}"
        set_gate_active(gate="learning_cooldown", ttl_seconds=LEARNING_GATE_TTL, reason=reasons["learning_cooldown"])

    active = []
    for g in ("tools_disabled", "sources_required", "learning_cooldown"):
        if is_gate_active(g):
            active.append(g)
            if g not in reasons:
                r = get_gate_reason(g)
                if r:
                    reasons[g] = r

    enforced = _env_bool("QUALITY_GATES_ENABLED", "0")
    enforced_gates = []
    if enforced and _env_bool("QUALITY_GATE_TOOLS_DISABLED", "0") and "tools_disabled" in active:
        enforced_gates.append("tools_disabled")
    if enforced and _env_bool("QUALITY_GATE_SOURCES_REQUIRED", "0") and "sources_required" in active:
        enforced_gates.append("sources_required")
    if enforced and _env_bool("QUALITY_GATE_LEARNING_COOLDOWN", "0") and "learning_cooldown" in active:
        enforced_gates.append("learning_cooldown")

    return GateState(
        active=tuple(active),
        reasons=reasons,
        enforced=bool(enforced),
        enforced_gates=tuple(enforced_gates),
    )
