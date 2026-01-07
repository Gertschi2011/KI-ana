from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from netapi.app import app, TIMEFLOW


def _mk_points(start: datetime, n: int, step_sec: int, above_idx: set, thr: float):
    data = []
    t = int(start.timestamp() * 1000)
    for i in range(n):
        act = thr + 0.01 if i in above_idx else thr - 0.01
        data.append({
            "ts_ms": t,
            "tick": i,
            "activation": act,
            "emotion": 0.0,
            "events_per_min": 0.0,
            "reqs_per_min": 0.0,
        })
        t += step_sec * 1000
    return data


def test_slo_edge_exact_pass(monkeypatch):
    client = TestClient(app)
    thr = 0.85
    max_frac = 0.01
    # Build 100 slices of 60s -> total 6000s; 1% = 60s -> one slice above threshold
    start = datetime.utcnow() - timedelta(hours=2)
    data = _mk_points(start, n=100, step_sec=60, above_idx={0}, thr=thr)
    monkeypatch.setattr(TIMEFLOW, "history", lambda limit: data)
    from_iso = start.isoformat() + "Z"
    to_iso = (start + timedelta(seconds=100*60)).isoformat() + "Z"

    resp = client.get("/api/system/timeflow/slo", params={
        "threshold": thr,
        "window_min": 100,
        "max_fraction": max_frac,
        "from": from_iso,
        "to": to_iso,
        "time_weighted": True,
    })
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("ok") is True
    assert j.get("pass") is True
    assert abs(j.get("fraction") - max_frac) < 1e-6


def test_rate_limit_history_alerts():
    client = TestClient(app)
    # Hit history more than 10 times quickly
    code = []
    for _ in range(12):
        r = client.get("/api/system/timeflow/history")
        code.append(r.status_code)
    # Last calls should be 429.
    # Depending on timing, allow at least one 429.
    assert any(c == 429 for c in code)

    # Hit alerts more than 10 times quickly
    code2 = []
    for _ in range(12):
        r = client.get("/api/system/timeflow/alerts")
        code2.append(r.status_code)
    assert any(c == 429 for c in code2)
