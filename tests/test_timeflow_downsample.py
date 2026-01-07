from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from netapi.app import app, TIMEFLOW


@pytest.fixture(autouse=True)
def _no_auth(monkeypatch):
    # If admin auth is enforced globally elsewhere,
    # stub it out for these endpoints.
    from netapi import app as appmod
    monkeypatch.setattr(
        appmod,
        "get_current_user_required",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        appmod,
        "has_any_role",
        lambda *a, **k: True,
        raising=False,
    )


def _ts(dt_iso: str) -> int:
    dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def _gen_points(from_iso: str, to_iso: str, step_minutes: int = 5):
    start = datetime.fromisoformat(from_iso)
    end = datetime.fromisoformat(to_iso)
    cur = start
    out = []
    tick = 0
    while cur < end:
        out.append({
            "ts_ms": int(cur.timestamp() * 1000),
            "tick": tick,
            "activation": 0.3,
            "emotion": 0.1,
            "events_per_min": 0.0,
            "reqs_per_min": 0.0,
        })
        cur += timedelta(minutes=step_minutes)
        tick += 1
    return out


def test_downsample_dst_spring_forward(monkeypatch):
    client = TestClient(app)
    # Europe/Vienna DST forward: 2025-03-30 is 23h day
    f = "2025-03-30T00:00:00+01:00"
    t = "2025-03-31T00:00:00+02:00"
    data = _gen_points(f, t, step_minutes=5)
    monkeypatch.setattr(TIMEFLOW, "history", lambda limit: data)

    resp = client.get(
        "/api/system/timeflow/history",
        params={
            "downsample": "minute",
            "from": f,
            "to": t,
            "tz": "Europe/Vienna",
            "fill_empty": True,
            "limit": 999999,
        },
    )
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("ok") is True
    hist = j.get("history")
    assert isinstance(hist, list)
    # Expected minutes = 23 * 60
    assert len(hist) == 23 * 60
    # First/last minute bounds
    assert hist[0]["ts_ms"] == (hist[0]["ts_ms"] // 60000) * 60000
    assert hist[-1]["ts_ms"] == (hist[-1]["ts_ms"] // 60000) * 60000


def test_downsample_dst_fall_back(monkeypatch):
    client = TestClient(app)
    # Europe/Vienna DST backward: 2025-10-26 is 25h day
    f = "2025-10-26T00:00:00+02:00"
    t = "2025-10-27T00:00:00+01:00"
    data = _gen_points(f, t, step_minutes=5)
    monkeypatch.setattr(TIMEFLOW, "history", lambda limit: data)

    resp = client.get(
        "/api/system/timeflow/history",
        params={
            "downsample": "minute",
            "from": f,
            "to": t,
            "tz": "Europe/Vienna",
            "fill_empty": True,
            "limit": 999999,
        },
    )
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("ok") is True
    hist = j.get("history")
    assert isinstance(hist, list)
    # Expected minutes = 25 * 60
    assert len(hist) == 25 * 60
    # Empty-minute fill included
    # At least one bucket should have count==0 due to 5-min sampling
    assert any((row.get("count", 0) == 0) for row in hist)
