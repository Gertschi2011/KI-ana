# netapi/modules/chat/session_state.py
from __future__ import annotations
from typing import Optional, Dict, Any
from time import time
import threading

# ------------------------------------------------------------
# Sehr simple In‑Memory Session – nun robuster:
# - Thread-safe via Lock (uvicorn workers/threads)
# - TTL für last_offer (verfällt nach OFFER_TTL_SECONDS)
# - Pruning alter Sessions, um Memory-Leaks zu vermeiden
# API bleibt kompatibel: get_last_offer / set_last_offer / get_state
# ------------------------------------------------------------

_sessions: Dict[str, Dict[str, Any]] = {}
_lock = threading.RLock()

# Konfiguration
OFFER_TTL_SECONDS = 15 * 60   # 15 Minuten – danach gilt Angebot als abgelaufen
SESSION_TTL_SECONDS = 24 * 60 * 60  # 24h – danach Session-Objekt darf entsorgt werden
MAX_SESSIONS = 2000           # harte Obergrenze – älteste Sessions werden entfernt

# interne Hilfsfunktion
def _now() -> float:
    return time()

def _new_state() -> Dict[str, Any]:
    ts = _now()
    return {
        "last_offer": None,            # "kurz" | "zusammenfassung" | "plan" | None
        "last_offer_ts": 0.0,          # Zeitstempel des Angebots
        # Kontext zum Angebot – hilft, Affirmationen wie "ja, kurz" dem vorherigen Thema zuzuordnen
        "offer_topic": None,           # z. B. "Bäume"
        "offer_seed": None,            # ursprüngliche Nutzerfrage/Text
        "created_ts": ts,              # Session-Anlage
        "touched_ts": ts,              # letzte Aktivität
    }

def _prune_unlocked() -> None:
    """Prune nach Größe/Alter – erwartet bereits gehaltenes _lock."""
    # 1) Alte Sessions entfernen
    now = _now()
    to_del = [sid for sid, st in _sessions.items() if (now - float(st.get("touched_ts", 0))) > SESSION_TTL_SECONDS]
    for sid in to_del:
        _sessions.pop(sid, None)

    # 2) Bei Übergröße: älteste nach touched_ts entfernen
    if len(_sessions) > MAX_SESSIONS:
        # sort by touched_ts asc
        victims = sorted(_sessions.items(), key=lambda kv: float(kv[1].get("touched_ts", 0)))
        for sid, _ in victims[: max(0, len(_sessions) - MAX_SESSIONS) ]:
            _sessions.pop(sid, None)

# ------------------------------------------------------------
# Öffentliche API
# ------------------------------------------------------------

def get_state(session_id: str) -> Dict[str, Any]:
    with _lock:
        st = _sessions.get(session_id)
        if st is None:
            st = _new_state()
            _sessions[session_id] = st
        st["touched_ts"] = _now()
        # gelegentlich aufräumen (amortisiert):
        if len(_sessions) % 50 == 0:
            _prune_unlocked()
        return st


def set_last_offer(session_id: str, offer: Optional[str]) -> None:
    with _lock:
        st = get_state(session_id)  # get_state setzt touched_ts
        st["last_offer"] = offer
        st["last_offer_ts"] = _now() if offer else 0.0


def get_last_offer(session_id: str) -> Optional[str]:
    with _lock:
        st = get_state(session_id)
        offer = st.get("last_offer")
        if not offer:
            return None
        ts = float(st.get("last_offer_ts", 0.0))
        # TTL prüfen
        if ts <= 0 or (_now() - ts) > OFFER_TTL_SECONDS:
            # abgelaufen – zurücksetzen
            st["last_offer"] = None
            st["last_offer_ts"] = 0.0
            return None
        return str(offer)

def set_offer_context(session_id: str, *, topic: Optional[str] = None, seed: Optional[str] = None) -> None:
    """Kontext zum letzten Angebot speichern (Thema und Ursprungsfrage)."""
    with _lock:
        st = get_state(session_id)
        if topic is not None:
            st["offer_topic"] = topic
        if seed is not None:
            st["offer_seed"] = seed

def get_offer_context(session_id: str) -> Dict[str, Any]:
    with _lock:
        st = get_state(session_id)
        return {
            "topic": st.get("offer_topic"),
            "seed": st.get("offer_seed"),
        }

# ------------------------------------------------------------
# Nützliche Extras (optional, von außen verwendbar)
# ------------------------------------------------------------

def clear_session(session_id: str) -> None:
    """Session-Zustand (In-Memory) entfernen."""
    with _lock:
        _sessions.pop(session_id, None)


def stats() -> Dict[str, Any]:
    with _lock:
        return {
            "sessions": len(_sessions),
            "max_sessions": MAX_SESSIONS,
        }
