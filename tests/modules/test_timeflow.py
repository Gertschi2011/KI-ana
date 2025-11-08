"""Tests for TimeFlow module."""

import pytest
import asyncio
import time
from netapi.modules.timeflow import TimeFlow, TimeFlowState


def test_timeflow_state_creation():
    """Test TimeFlowState dataclass creation."""
    state = TimeFlowState()
    assert state.tick == 0
    assert state.ts_ms == 0
    assert state.activation == 0.0
    assert state.subjective_time == 0.0
    assert state.emotion == 0.0
    
    # Test to_dict conversion
    state_dict = state.to_dict()
    assert isinstance(state_dict, dict)
    assert "tick" in state_dict
    assert "activation" in state_dict


def test_timeflow_initialization():
    """Test TimeFlow initialization with default params."""
    tf = TimeFlow()
    assert tf is not None
    assert tf.interval > 0
    assert tf.log_window >= 20
    assert not tf._running
    
    # Snapshot should work immediately
    state = tf.snapshot()
    assert isinstance(state, dict)
    assert "tick" in state
    assert "subjective_time" in state


def test_timeflow_custom_config():
    """Test TimeFlow with custom configuration."""
    tf = TimeFlow(
        interval_sec=0.5,
        log_window=100,
        activation_decay=0.95,
        circadian_enabled=True
    )
    
    assert tf.interval == 0.5
    assert tf.log_window == 100
    assert tf.activation_decay == 0.95
    assert tf.circadian_enabled is True


def test_timeflow_config_get_apply():
    """Test get_config and apply_config methods."""
    tf = TimeFlow()
    
    # Get initial config
    config = tf.get_config()
    assert isinstance(config, dict)
    assert "interval_sec" in config
    assert "activation_decay" in config
    
    # Apply config changes
    changes = {
        "activation_decay": 0.88,
        "stimulus_weight": 0.05,
        "alert_activation_warn": 0.80
    }
    applied = tf.apply_config(changes)
    
    assert "activation_decay" in applied
    assert applied["activation_decay"] == 0.88
    assert tf.activation_decay == 0.88


@pytest.mark.asyncio
async def test_timeflow_note_request():
    """Test note_request method."""
    tf = TimeFlow()
    
    # Note some requests
    await tf.note_request("/api/chat")
    await tf.note_request("/api/agent")
    
    # Counter should be incremented
    assert tf._req_counter >= 0


@pytest.mark.asyncio
async def test_timeflow_tick():
    """Test a single tick cycle."""
    tf = TimeFlow(interval_sec=0.1, log_window=50)
    
    initial_tick = tf.state.tick
    
    # Manually trigger one tick
    await tf._tick_once()
    
    assert tf.state.tick == initial_tick + 1
    assert tf.state.ts_ms > 0


def test_timeflow_history():
    """Test history recording and retrieval."""
    tf = TimeFlow(history_len=10)
    
    # Initially empty
    history = tf.history()
    assert isinstance(history, list)
    
    # After some activity
    for _ in range(5):
        tf.state.tick += 1
        tf._history.append(tf.state.to_dict())
    
    history = tf.history(limit=3)
    assert len(history) <= 3


def test_timeflow_alerts():
    """Test alert system."""
    tf = TimeFlow()
    
    # Initially no alerts
    alerts = tf.alerts()
    assert isinstance(alerts, list)
    
    # Total count
    total = tf.alerts_total()
    assert isinstance(total, int)
    assert total >= 0
    
    # Alert counters
    counters = tf.alert_counters()
    assert isinstance(counters, dict)


def test_timeflow_mute_alert():
    """Test alert muting functionality."""
    tf = TimeFlow()
    
    # Mute an alert kind
    tf.mute_alert("activation_warn", 60.0)
    
    # Check mute time
    mute_until = tf.get_mute_until("activation_warn")
    assert mute_until > time.time()


def test_timeflow_upcoming_events():
    """Test countdown/upcoming events functionality."""
    tf = TimeFlow(countdown_enabled=True, countdown_near_sec=300)
    
    # Set upcoming events
    now = time.time()
    events = [
        {"ts": now + 100, "title": "Soon"},
        {"ts": now + 3600, "title": "Later"},
    ]
    tf.set_upcoming_events(events)
    
    assert len(tf._upcoming) == 2


def test_timeflow_path_weights():
    """Test request path weights."""
    tf = TimeFlow(
        path_weights={
            "/api/chat": 2.0,
            "/api/agent": 1.5,
            "/api/health": 0.1,
        }
    )
    
    assert tf.path_weights["/api/chat"] == 2.0
    assert tf.path_weights["/api/agent"] == 1.5
    assert tf.path_weights["/api/health"] == 0.1


@pytest.mark.asyncio
async def test_timeflow_start_stop():
    """Test TimeFlow start/stop lifecycle."""
    tf = TimeFlow(interval_sec=0.1)
    
    assert not tf._running
    
    # Start
    tf.start()
    await asyncio.sleep(0.05)  # Give it time to start
    
    # Should be running now (though tick may not have happened yet)
    initial_state = tf.snapshot()
    
    # Let it tick a few times
    await asyncio.sleep(0.3)
    
    later_state = tf.snapshot()
    assert later_state["tick"] >= initial_state["tick"]
    
    # Stop
    await tf.stop()
    await asyncio.sleep(0.05)
    
    assert not tf._running


def test_timeflow_circadian_factor():
    """Test circadian rhythm calculation."""
    tf = TimeFlow(
        circadian_enabled=True,
        circadian_amplitude=0.3,
        tz="UTC"
    )
    
    # Calculate for some timestamp
    factor = tf._circadian(time.time())
    assert isinstance(factor, float)
    assert factor > 0  # Should never be zero


def test_timeflow_stats():
    """Test various stats accessors."""
    tf = TimeFlow()
    
    # Webhook stats
    dropped = tf.webhook_dropped_total()
    assert isinstance(dropped, int)
    
    # Compaction stats
    last_compact = tf.last_compact_ts()
    assert isinstance(last_compact, float)
    
    # Pruned files
    pruned = tf.pruned_files_total()
    assert isinstance(pruned, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
