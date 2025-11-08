from __future__ import annotations
import asyncio
import time
import hashlib
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Optional, Dict, Any
import math
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

try:
    from netapi.logging_bridge import RING  # type: ignore
except Exception:  # pragma: no cover
    RING = None  # type: ignore

# Optional memory store for delta hashing
try:
    from netapi import memory_store as _mem  # type: ignore
except Exception:  # pragma: no cover
    _mem = None  # type: ignore


@dataclass
class TimeFlowState:
    # core clock
    ts_ms: int = 0
    tick: int = 0
    # event density
    events_total: int = 0
    events_last_window: int = 0
    events_per_min: float = 0.0
    # http request density
    reqs_total: int = 0
    reqs_last_window: int = 0
    reqs_per_min: float = 0.0
    # memory delta
    mem_hash: str = ""
    mem_delta_score: float = 0.0
    # subjective time accumulator
    subjective_time: float = 0.0
    activation: float = 0.0  # rises with events, decays with silence
    circadian_factor: float = 1.0
    emotion: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TimeFlow:
    """
    Maintains an internal sense of change via a heartbeat.
    - Ticks once per second by default.
    - Samples recent logs for event density.
    - Computes a lightweight memory delta hash (best-effort).
    - Updates a subjective_time by integrating activation over time.
    """
    def __init__(
        self,
        interval_sec: float = 1.0,
        log_window: int = 200,
        activation_decay: float = 0.92,
        stimulus_weight: float = 0.02,
        path_weights: Optional[Dict[str, float]] = None,
        history_len: int = 300,
        persist_path: Optional[str] = None,
        # circadian
        tz: str = "UTC",
        circadian_enabled: bool = False,
        circadian_amplitude: float = 0.25,
        circadian_phase_shift_h: float = 0.0,
        circadian_min_floor: float = 0.5,
        # emotion
        emo_decay: float = 0.98,
        emo_gain: float = 0.10,
        emo_floor: float = 0.0,
        emo_ceil: float = 1.0,
        # countdowns
        countdown_enabled: bool = False,
        countdown_horizon_sec: int = 86400,
        countdown_boost_max: float = 0.4,
        countdown_near_sec: int = 600,
        # alerts
        alert_activation_warn: float = 0.75,
        alert_activation_crit: float = 0.90,
        alert_reqs_per_min_warn: float = 120.0,
        alert_reqs_per_min_crit: float = 300.0,
        alert_emotion_warn: float = 0.75,
        alert_emotion_crit: float = 0.90,
        alert_suppress: Optional[list[str]] = None,
        alert_webhooks: Optional[list[str]] = None,
    ):
        self.interval = max(0.2, float(interval_sec))
        self.log_window = max(20, int(log_window))
        self.state = TimeFlowState(ts_ms=int(time.time() * 1000))
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._prev_log_count: int = 0
        self._last_mem_hash: str = ""
        # request counter (incremented from middleware)
        self._req_counter: int = 0
        self._req_lock: asyncio.Lock = asyncio.Lock()
        # tuning
        self.activation_decay = float(activation_decay)
        self.stimulus_weight = float(stimulus_weight)
        self.path_weights: Dict[str, float] = dict(path_weights or {})
        # history/persistence
        self._history: list[Dict[str, Any]] = []
        self._history_len = max(10, int(history_len))
        self._persist_path = str(persist_path) if persist_path else None
        # circadian
        self.tz = tz or "UTC"
        self._tz = ZoneInfo(self.tz) if ZoneInfo is not None else None
        self.circadian_enabled = bool(circadian_enabled)
        self.circadian_amplitude = float(circadian_amplitude)
        self.circadian_phase_shift_h = float(circadian_phase_shift_h)
        self.circadian_min_floor = float(circadian_min_floor)
        # emotion
        self.emo_decay = float(emo_decay)
        self.emo_gain = float(emo_gain)
        self.emo_floor = float(emo_floor)
        self.emo_ceil = float(emo_ceil)
        # countdowns
        self.countdown_enabled = bool(countdown_enabled)
        self.countdown_horizon_sec = int(countdown_horizon_sec)
        self.countdown_boost_max = float(countdown_boost_max)
        self.countdown_near_sec = int(countdown_near_sec)
        self._upcoming: list[Dict[str, Any]] = []
        # alerts
        self.alert_activation_warn = float(alert_activation_warn)
        self.alert_activation_crit = float(alert_activation_crit)
        self.alert_reqs_per_min_warn = float(alert_reqs_per_min_warn)
        self.alert_reqs_per_min_crit = float(alert_reqs_per_min_crit)
        self.alert_emotion_warn = float(alert_emotion_warn)
        self.alert_emotion_crit = float(alert_emotion_crit)
        self._alert_suppress = set(alert_suppress or [])
        self._alert_webhooks = list(alert_webhooks or [])
        self._alerts: list[Dict[str, Any]] = []
        self._alerts_max = 100
        self._prev_level = {"activation": "none", "reqs": "none", "emotion": "none"}
        self._alerts_total = 0
        self._alert_mute_until: Dict[str, float] = {}
        self._alert_counters: Dict[str, int] = {}
        # cooldowns
        self._cooldowns: Dict[str, float] = {}
        self._cooldown_defaults: Dict[str, float] = {
            "activation_warn": 10.0,
            "activation_crit": 120.0,
            "reqs_per_min_warn": 10.0,
            "reqs_per_min_crit": 120.0,
            "emotion_warn": 10.0,
            "emotion_crit": 120.0,
        }
        self._global_dedup_window = 60.0  # seconds
        self._last_fired: Dict[str, float] = {}  # kind -> ts
        # webhook rate limit & queue
        self._webhook_rate_per_min = 30  # tokens per minute
        self._webhook_tokens = float(self._webhook_rate_per_min)
        self._webhook_last_refill = time.time()
        from collections import deque
        self._webhook_q = deque()  # list of payload dicts
        self._webhook_worker_started = False
        self._webhook_q_max = 1000
        self._webhook_dropped_total = 0
        # anomaly detection (EWMA)
        self._ewma_mean = None
        self._ewma_var = None
        self._ewma_alpha = 2.0 / (60.0 + 1.0)  # ~1h window default
        self._z_last = 0.0
        self._z_alert_threshold = 3.0
        # rotation & retention
        self._retention_days = 14
        self._last_rotated_date = None
        self._last_compact_ts = 0.0
        self._pruned_files_total = 0

    async def note_request(self, path: Optional[str] = None) -> None:
        try:
            # weight by path cluster if provided
            w = 1.0
            if path:
                try:
                    # longest prefix match
                    best = 0
                    for pref, fac in self.path_weights.items():
                        if path.startswith(pref) and len(pref) > best:
                            best = len(pref)
                            w = float(fac)
                except Exception:
                    w = 1.0
            async with self._req_lock:
                # accumulate weighted counter internally
                self._req_counter += max(0.0, float(w))
        except Exception:
            pass

    def get_mute_until(self, kind: str) -> float:
        try:
            return float(self._alert_mute_until.get(str(kind), 0.0))
        except Exception:
            return 0.0

    def webhook_dropped_total(self) -> int:
        try:
            return int(self._webhook_dropped_total)
        except Exception:
            return 0

    def last_compact_ts(self) -> float:
        try:
            return float(self._last_compact_ts)
        except Exception:
            return 0.0

    def compact_daily(self, date_str: str) -> Optional[Path]:
        """Aggregate a day's JSONL into per-minute summaries.
        Input file: timeflow-YYYY-MM-DD.jsonl (in persist dir)
        Output file: timeflow-YYYY-MM-DD.minutely.jsonl
        Returns the output path on success, else None.
        """
        try:
            if not self._persist_path:
                return None
            base = Path(self._persist_path)
            dirp = base if base.is_dir() or self._persist_path.endswith("/") else base.parent
            src = dirp / f"timeflow-{date_str}.jsonl"
            if not src.exists():
                return None
            from collections import defaultdict
            buckets = defaultdict(list)
            with src.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        ts = int(d.get("ts_ms", 0))
                        m = (ts // 60000) * 60000
                        buckets[m].append(d)
                    except Exception:
                        continue
            outp = dirp / f"timeflow-{date_str}.minutely.jsonl"
            if outp.exists():
                # idempotent: already compacted
                self._last_compact_ts = time.time()
                return outp
            tmp = outp.with_suffix(outp.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as fo:
                for m in sorted(buckets.keys()):
                    arr = buckets[m]
                    if not arr:
                        continue
                    def _avg(key):
                        xs = [float(a.get(key, 0.0)) for a in arr]
                        return sum(xs) / max(1, len(xs))
                    def _min(key):
                        xs = [float(a.get(key, 0.0)) for a in arr]
                        return min(xs) if xs else 0.0
                    def _max(key):
                        xs = [float(a.get(key, 0.0)) for a in arr]
                        return max(xs) if xs else 0.0
                    row = {
                        "ts_ms": m,
                        "activation_avg": _avg("activation"),
                        "activation_min": _min("activation"),
                        "activation_max": _max("activation"),
                        "emotion_avg": _avg("emotion"),
                        "events_per_min_avg": _avg("events_per_min"),
                        "reqs_per_min_avg": _avg("reqs_per_min"),
                        "z_score_avg": _avg("z_score"),
                    }
                    fo.write(json.dumps(row, ensure_ascii=False) + "\n")
            # atomic rename
            try:
                tmp.replace(outp)
            except Exception:
                # fallback copy
                import shutil as _sh
                _sh.copyfile(tmp, outp)
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
            self._last_compact_ts = time.time()
            return outp
        except Exception:
            return None

    async def _sample_events(self) -> int:
        if RING is None:
            return 0
        try:
            snap = await RING.snapshot(self.log_window)
            return len(snap or [])
        except Exception:
            return 0

    def _circadian(self, now_epoch: float) -> float:
        if not self.circadian_enabled or self._tz is None:
            return 1.0
        try:
            local_dt = datetime.fromtimestamp(now_epoch, tz=self._tz)
            hour = local_dt.hour + local_dt.minute / 60.0
            h = (hour + self.circadian_phase_shift_h) % 24.0
            val = math.sin((h - 14.0) / 24.0 * 2 * math.pi)
            factor = 1.0 + self.circadian_amplitude * val
            return max(self.circadian_min_floor, factor)
        except Exception:
            return 1.0

    def set_upcoming_events(self, events: list[Dict[str, Any]]) -> None:
        try:
            self._upcoming = [e for e in (events or []) if isinstance(e.get("ts"), (int, float))]
        except Exception:
            self._upcoming = []

    def _countdown_boost(self, now_epoch: float) -> float:
        if not self.countdown_enabled or not self._upcoming:
            return 0.0
        try:
            horizon = max(1, self.countdown_horizon_sec)
            near = max(1, self.countdown_near_sec)
            best = 0.0
            for e in self._upcoming:
                dt = float(e["ts"]) - now_epoch
                if dt < 0 or dt > horizon:
                    continue
                if dt <= near:
                    fac = self.countdown_boost_max
                else:
                    x = 1.0 - (dt - near) / max(1.0, (horizon - near))
                    fac = max(0.0, (x * x) * self.countdown_boost_max)
                if fac > best:
                    best = fac
            return best
        except Exception:
            return 0.0

    def _compute_mem_hash(self) -> str:
        # Prefer memory_store blocks if available; else return empty string
        try:
            if _mem is None:
                return ""
            # gather last N blocks by id order heuristic (store may provide list API)
            ids = getattr(_mem, "list_recent_ids", lambda n=50: [])(50)  # type: ignore
            if not ids:
                return ""
            h = hashlib.sha256()
            for bid in ids[:50]:
                b = _mem.get_block(bid) or {}
                # include title/content/tags for a rough delta
                t = str(b.get("title") or "")
                c = str(b.get("content") or "")
                tags = ",".join(sorted(map(str, b.get("tags") or [])))
                h.update(t.encode("utf-8", errors="ignore"))
                h.update(c.encode("utf-8", errors="ignore"))
                h.update(tags.encode("utf-8", errors="ignore"))
            return h.hexdigest()
        except Exception:
            return ""

    async def _tick_once(self) -> None:
        now = time.time()
        self.state.ts_ms = int(now * 1000)
        self.state.tick += 1

        # events window and density (logs)
        count = await self._sample_events()
        new_events = max(0, count - self._prev_log_count)
        self._prev_log_count = count
        self.state.events_total += new_events
        self.state.events_last_window = new_events
        # capture and reset http requests since last tick
        try:
            async with self._req_lock:
                reqs_weighted = float(self._req_counter)
                self._req_counter = 0
        except Exception:
            reqs_weighted = 0.0
        # expose raw approximation for readability (rounded)
        reqs_approx = int(round(reqs_weighted))
        self.state.reqs_total += reqs_approx
        self.state.reqs_last_window = reqs_approx
        # approximate per-minute rates using tick interval
        window_sec = self.interval
        self.state.events_per_min = float(new_events) * (60.0 / max(1e-6, window_sec))
        self.state.reqs_per_min = float(reqs_approx) * (60.0 / max(1e-6, window_sec))

        # memory delta
        cur_mem_hash = self._compute_mem_hash()
        if cur_mem_hash and self._last_mem_hash and cur_mem_hash != self._last_mem_hash:
            self.state.mem_delta_score = min(1.0, self.state.mem_delta_score + 0.2)
        else:
            # slight decay towards 0
            self.state.mem_delta_score *= 0.95
        if cur_mem_hash:
            self._last_mem_hash = cur_mem_hash
        self.state.mem_hash = self._last_mem_hash

        # activation/subjective time
        # rises with events and request traffic, decays otherwise
        stimulus = float(new_events) + float(reqs_weighted)
        if stimulus > 0:
            self.state.activation = min(1.0, self.state.activation + min(0.5, self.stimulus_weight * stimulus))
        else:
            self.state.activation *= self.activation_decay  # forgetting rate
        # countdown boost (near-time events)
        try:
            cb = self._countdown_boost(now)
            if cb > 0:
                self.state.activation = min(1.0, self.state.activation + cb)
        except Exception:
            pass
        # circadian modulation
        cf = self._circadian(now)
        self.state.activation = min(1.0, self.state.activation * cf)
        self.state.circadian_factor = cf

        # emotional decay model
        emo = self.state.emotion * self.emo_decay + self.emo_gain * self.state.activation
        emo = min(self.emo_ceil, max(self.emo_floor, emo))
        self.state.emotion = emo

        # integrate subjective time: base 1.0 + activation factor
        self.state.subjective_time += (1.0 + 0.5 * self.state.activation + 0.15 * self.state.emotion) * self.interval

        # anomaly detection on circadian-adjusted activation (residual)
        try:
            adj = self.state.activation / max(1e-6, self.state.circadian_factor)
            m = self._ewma_mean if self._ewma_mean is not None else adj
            v = self._ewma_var if self._ewma_var is not None else 0.0
            a = float(self._ewma_alpha)
            # EWMA mean/variance (West 1979 style)
            m_new = (1 - a) * m + a * adj
            v_new = (1 - a) * (v + a * (adj - m) * (adj - m))
            self._ewma_mean, self._ewma_var = m_new, v_new
            std = math.sqrt(max(1e-9, v_new))
            z = (adj - m_new) / std if std > 0 else 0.0
            self._z_last = z
            if abs(z) >= self._z_alert_threshold:
                sev = "crit" if abs(z) >= (self._z_alert_threshold + 1.0) else "warn"
                self._push_alert_with_cooldown(f"anomaly_{sev}", now, {"z": float(z), "adj_activation": float(adj), "severity": sev})
        except Exception:
            pass

        # record to history (ring buffer)
        snap = self.state.to_dict()
        snap["z_score"] = self._z_last
        self._history.append(snap)
        if len(self._history) > self._history_len:
            self._history = self._history[-self._history_len:]
        # persist JSONL best-effort
        if self._persist_path:
            try:
                # rotate by date
                today = datetime.utcnow().strftime("%Y-%m-%d")
                base = Path(self._persist_path)
                if base.is_dir() or self._persist_path.endswith("/"):
                    p = Path(self._persist_path) / f"timeflow-{today}.jsonl"
                else:
                    stem = base.stem
                    p = base.parent / f"{stem}-{today}.jsonl"
                p.parent.mkdir(parents=True, exist_ok=True)
                line = (json.dumps(snap, ensure_ascii=False) + "\n")
                # simple sync append; small line, acceptable
                with p.open("a", encoding="utf-8") as f:
                    f.write(line)
                # retention cleanup
                self._cleanup_retention(p.parent)
            except Exception:
                pass

        # alerts on threshold crossings
        try:
            self._maybe_alert(now)
        except Exception:
            pass

    async def run(self) -> None:
        self._running = True
        try:
            while self._running:
                try:
                    await self._tick_once()
                except Exception:
                    # Never crash the loop
                    pass
                await asyncio.sleep(self.interval)
        finally:
            self._running = False

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        t = self._task
        if t:
            try:
                await asyncio.wait_for(t, timeout=1.0)
            except Exception:
                pass
            self._task = None

    def snapshot(self) -> Dict[str, Any]:
        return self.state.to_dict()

    def history(self, limit: int = 100) -> list[Dict[str, Any]]:
        try:
            if limit <= 0:
                return []
            return self._history[-min(limit, self._history_len):]
        except Exception:
            return []

    def _push_alert(self, kind: str, ts: float, detail: Dict[str, Any]) -> None:
        try:
            item = {"ts": int(ts * 1000), "kind": kind}
            item.update(detail or {})
            if kind in self._alert_suppress:
                return
            # temporary mute window check
            mute_until = float(self._alert_mute_until.get(kind, 0.0))
            if ts < mute_until:
                return
            self._alerts.append(item)
            if len(self._alerts) > self._alerts_max:
                self._alerts = self._alerts[-self._alerts_max:]
            self._alerts_total += 1
            # counters per kind
            try:
                k = str(item.get("kind", ""))
                self._alert_counters[k] = int(self._alert_counters.get(k, 0)) + 1
            except Exception:
                pass
            # async webhook notify (best-effort)
            try:
                if self._alert_webhooks:
                    self._enqueue_webhook(item)
            except Exception:
                pass
        except Exception:
            pass

    def _push_alert_with_cooldown(self, kind: str, ts: float, detail: Dict[str, Any]) -> None:
        # global dedup window
        last = self._last_fired.get(kind, 0.0)
        if ts - last < self._global_dedup_window:
            return
        # per-type cooldown
        cd = float(self._cooldown_defaults.get(kind, 0.0))
        if cd > 0.0 and ts - last < cd:
            return
        self._last_fired[kind] = ts
        self._push_alert(kind, ts, detail)

    def _maybe_alert(self, now_epoch: float) -> None:
        a = float(self.state.activation)
        r = float(self.state.reqs_per_min)
        e = float(self.state.emotion)
        # helper to compute level
        def level(val: float, warn: float, crit: float) -> str:
            if val >= crit:
                return "crit"
            if val >= warn:
                return "warn"
            return "none"
        la = level(a, self.alert_activation_warn, self.alert_activation_crit)
        lr = level(r, self.alert_reqs_per_min_warn, self.alert_reqs_per_min_crit)
        le = level(e, self.alert_emotion_warn, self.alert_emotion_crit)
        # push only on upward transitions
        if la in ("warn","crit") and la != self._prev_level.get("activation", "none"):
            self._push_alert_with_cooldown(f"activation_{la}", now_epoch, {"activation": a, "severity": la})
        if lr in ("warn","crit") and lr != self._prev_level.get("reqs", "none"):
            self._push_alert_with_cooldown(f"reqs_per_min_{lr}", now_epoch, {"reqs_per_min": r, "severity": lr})
        if le in ("warn","crit") and le != self._prev_level.get("emotion", "none"):
            self._push_alert_with_cooldown(f"emotion_{le}", now_epoch, {"emotion": e, "severity": le})
        self._prev_level["activation"] = la
        self._prev_level["reqs"] = lr
        self._prev_level["emotion"] = le

    def _enqueue_webhook(self, item: Dict[str, Any]) -> None:
        try:
            if len(self._webhook_q) >= self._webhook_q_max:
                # drop oldest and count
                try:
                    self._webhook_q.popleft()
                except Exception:
                    pass
                self._webhook_dropped_total += 1
            self._webhook_q.append({"item": item, "attempt": 0, "next": time.time()})
            if not self._webhook_worker_started:
                self._webhook_worker_started = True
                asyncio.create_task(self._webhook_worker())
        except Exception:
            pass

    async def _webhook_worker(self) -> None:
        # token bucket refill once per second
        try:
            import aiohttp  # type: ignore
        except Exception:
            aiohttp = None  # type: ignore
        while self._alert_webhooks:
            try:
                now = time.time()
                # refill tokens
                elapsed = now - self._webhook_last_refill
                if elapsed >= 1.0:
                    self._webhook_tokens = min(self._webhook_rate_per_min, self._webhook_tokens + (self._webhook_rate_per_min/60.0)*elapsed)
                    self._webhook_last_refill = now
                if not self._webhook_q:
                    await asyncio.sleep(0.2)
                    continue
                job = self._webhook_q[0]
                if now < job.get("next", 0):
                    await asyncio.sleep(0.2)
                    continue
                if self._webhook_tokens < 1.0:
                    await asyncio.sleep(0.5)
                    continue
                # send
                self._webhook_tokens -= 1.0
                self._webhook_q.popleft()
                payload = json.dumps({"timeflow_alert": job["item"]}, ensure_ascii=False)
                sent = False
                # try aiohttp
                if aiohttp is not None:
                    try:
                        async with aiohttp.ClientSession() as session:
                            for url in self._alert_webhooks:
                                try:
                                    async with session.post(url, data=payload, headers={"Content-Type":"application/json"}, timeout=5) as resp:
                                        _ = await resp.text()
                                except Exception:
                                    continue
                        sent = True
                    except Exception:
                        sent = False
                if not sent:
                    # fallback requests
                    try:
                        import requests  # type: ignore
                        loop = asyncio.get_running_loop()
                        def _post_all():
                            for url in self._alert_webhooks:
                                try:
                                    requests.post(url, data=payload.encode("utf-8"), headers={"Content-Type":"application/json"}, timeout=5)
                                except Exception:
                                    continue
                        await loop.run_in_executor(None, _post_all)
                        sent = True
                    except Exception:
                        sent = False
                if not sent:
                    # retry with backoff
                    job["attempt"] = int(job.get("attempt", 0)) + 1
                    backoff = min(60.0, 2.0 ** job["attempt"])  # cap at 60s
                    job["next"] = time.time() + backoff
                    self._webhook_q.append(job)
            except Exception:
                await asyncio.sleep(0.5)
        self._webhook_worker_started = False

    def alerts(self, limit: int = 50) -> list[Dict[str, Any]]:
        try:
            if limit <= 0:
                return []
            return self._alerts[-min(limit, self._alerts_max):]
        except Exception:
            return []

    def alerts_total(self) -> int:
        try:
            return int(self._alerts_total)
        except Exception:
            return 0

    def alert_counters(self) -> Dict[str, int]:
        try:
            return dict(self._alert_counters)
        except Exception:
            return {}

    def mute_alert(self, kind: str, duration_sec: float) -> None:
        try:
            self._alert_mute_until[str(kind)] = time.time() + max(0.0, float(duration_sec))
        except Exception:
            pass

    def get_config(self) -> Dict[str, Any]:
        return {
            "interval_sec": self.interval,
            "log_window": self.log_window,
            "activation_decay": self.activation_decay,
            "stimulus_weight": self.stimulus_weight,
            "path_weights": dict(self.path_weights),
            "history_len": self._history_len,
            "persist_path": self._persist_path,
            "tz": self.tz,
            "circadian_enabled": self.circadian_enabled,
            "circadian_amplitude": self.circadian_amplitude,
            "circadian_phase_shift_h": self.circadian_phase_shift_h,
            "circadian_min_floor": self.circadian_min_floor,
            "emo_decay": self.emo_decay,
            "emo_gain": self.emo_gain,
            "alert_activation_warn": self.alert_activation_warn,
            "alert_activation_crit": self.alert_activation_crit,
            "alert_reqs_per_min_warn": self.alert_reqs_per_min_warn,
            "alert_reqs_per_min_crit": self.alert_reqs_per_min_crit,
            "alert_emotion_warn": self.alert_emotion_warn,
            "alert_emotion_crit": self.alert_emotion_crit,
        }

    def apply_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        # whitelist keys
        applied = {}
        def setf(name, cast=float):
            nonlocal applied
            if name in cfg:
                try:
                    val = cast(cfg[name])
                    setattr(self, name, val)
                    applied[name] = val
                except Exception:
                    pass
        def setpmap(name):
            nonlocal applied
            if name in cfg and isinstance(cfg[name], dict):
                try:
                    mp = {str(k): float(v) for k, v in cfg[name].items()}
                    setattr(self, name, mp)
                    applied[name] = mp
                except Exception:
                    pass
        setf("interval_sec")  # note: not used by loop sleep mid-run
        setf("log_window", int)
        setf("activation_decay")
        setf("stimulus_weight")
        setpmap("path_weights")
        setf("circadian_amplitude")
        setf("circadian_phase_shift_h")
        setf("circadian_min_floor")
        # toggles
        if "circadian_enabled" in cfg:
            try:
                self.circadian_enabled = bool(cfg["circadian_enabled"])
                applied["circadian_enabled"] = self.circadian_enabled
            except Exception:
                pass
        # alerts thresholds
        setf("alert_activation_warn")
        setf("alert_activation_crit")
        setf("alert_reqs_per_min_warn")
        setf("alert_reqs_per_min_crit")
        setf("alert_emotion_warn")
        setf("alert_emotion_crit")
        return applied

    def _cleanup_retention(self, dirpath: Path) -> None:
        try:
            # delete jsonl files older than retention
            keep_after = time.time() - self._retention_days * 86400
            for p in dirpath.glob("timeflow-*.jsonl"):
                try:
                    # parse date from filename
                    s = p.stem.split("timeflow-")[-1]
                    dt = datetime.strptime(s, "%Y-%m-%d")
                    if dt.timestamp() < keep_after:
                        try:
                            p.unlink(missing_ok=True)
                            self._pruned_files_total += 1
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass

    def pruned_files_total(self) -> int:
        try:
            return int(self._pruned_files_total)
        except Exception:
            return 0
