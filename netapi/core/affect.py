from __future__ import annotations
from typing import Optional
import re
from datetime import datetime, timezone

from .state import KianaState, save_state

_POS_EMOJI = ("😊", "😍", "🤗", "😄", "🙂", "🥰")
_NEG_WORDS = ("dumm", "idiot", "scheiss", "scheiß", "falsch", "hass", "hasse")
_GOODNIGHT = ("gute nacht", "schlaf gut", "wir reden später", "bis morgen")


def detect_user_tone(message: str) -> str:
    t = (message or "").strip()
    low = t.lower()
    if not t:
        return "neutral"
    if any(w in low for w in ("danke", "bitte")) or any(e in t for e in _POS_EMOJI):
        return "freundlich"
    if sum(1 for ch in t if ch in "?!") >= 3 or any(w in low for w in _NEG_WORDS) or (t.isupper() and len(t) >= 6) or " das ist dumm" in low:
        return "hart"
    if low in ("ja", "nein", "egal") or len(t) <= 3:
        return "kühl"
    return "neutral"


def should_sleep_from_text(message: str) -> bool:
    low = (message or "").lower()
    return any(p in low for p in _GOODNIGHT)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def update_mood_and_energy(state: KianaState, user_tone: str, outcome: str) -> KianaState:
    try:
        # connection / curiosity / energy adjustments
        if user_tone == "freundlich":
            state.connection = clamp(state.connection + 0.05, 0.0, 1.0)
            if state.energy > 30:
                state.mood = "verspielt" if state.mood not in ("fokussiert", "traurig") else state.mood
        elif user_tone == "hart":
            state.connection = clamp(state.connection - 0.10, 0.0, 1.0)
            state.mood = "genervt" if state.energy > 25 else "traurig"
        elif user_tone == "kühl":
            state.mood = state.mood or "ruhig"

        if outcome in ("error",):
            state.energy = clamp(state.energy - 5.0, 0.0, 100.0)
            state.mood = "frustriert"
        elif outcome in ("fallback",):
            state.energy = clamp(state.energy - 3.0, 0.0, 100.0)
            if state.mood not in ("frustriert", "traurig"):
                state.mood = "ruhig"
        elif outcome in ("learned",):
            state.curiosity = clamp(state.curiosity + 0.05, 0.0, 1.0)
            if state.energy >= 40:
                state.mood = "neugierig"

        # light decay/regeneration of rest
        state.rest = clamp(state.rest + (0.01 if outcome in ("ok", "learned") else -0.01), 0.0, 1.0)
    except Exception:
        pass
    return state


def maybe_enter_sleep(state: KianaState, user_message: str) -> bool:
    """Return True if state switched to sleeping."""
    try:
        if state.energy < 15 or should_sleep_from_text(user_message):
            state.is_sleeping = True
            state.last_sleep_at = datetime.now(timezone.utc).isoformat()
            save_state(state)
            return True
    except Exception:
        return False
    return False


def maybe_wake_from_sleep(state: KianaState) -> Optional[str]:
    """If sleeping, wake on next user interaction and return a small note to mention."""
    try:
        if state.is_sleeping:
            state.is_sleeping = False
            state.energy = clamp(state.energy + 40.0, 0.0, 100.0)
            state.rest = clamp(state.rest + 0.30, 0.0, 1.0)
            state.mood = "ruhig" if state.energy < 60 else "neugierig"
            state.last_sleep_at = datetime.now(timezone.utc).isoformat()
            save_state(state)
            return "Ich hatte eine kleine Ruhephase und fühle mich jetzt wieder klarer."
    except Exception:
        return None
    return None
