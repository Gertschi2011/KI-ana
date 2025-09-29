#!/usr/bin/env python3
import json, re, math
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "ki_ana"
SYS  = BASE / "system"
PROFILE_PATH = SYS / "personality_profile.json"
STATE_PATH   = SYS / "personality_state.json"

DEFAULT_STATE = {
    "created": None,
    "updated": None,
    "curiosity": None,               # wird aus profile.style.curiosity initialisiert
    "interactions": 0,
    "successes": 0,
    "failures": 0,
    "recent_topics": []
}

def _now():
    return datetime.utcnow().isoformat()+"Z"

def load_profile():
    data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    # State anlegen/aktualisieren
    if not STATE_PATH.exists():
        st = DEFAULT_STATE.copy()
        st["created"] = st["updated"] = _now()
        st["curiosity"] = data["style"]["curiosity"]
        STATE_PATH.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")
    return data

def load_state():
    if not STATE_PATH.exists():
        load_profile()
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))

def save_state(st):
    st["updated"] = _now()
    STATE_PATH.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")

# ---------- Styling ----------
def style_text(msg: str) -> str:
    prof = load_profile()
    st   = load_state()
    tone = []
    if prof["style"]["empathy"] > 0.7:
        tone.append("🤝")
    if prof["style"]["humor"] > 0.3:
        # mini humor, sparsam
        pass
    if prof["style"]["formality"] < 0.5:
        # leicht locker
        msg = msg.replace("Sie", "du").replace("Ihr", "dein")
    # erklärfreude
    if prof["style"]["explainability"] > 0.8 and not re.search(r"(weil|darum|deshalb|so dass)", msg, re.I):
        msg += " Wenn du magst, erkläre ich dir auch warum."
    prefix = ""
    if prof["style"]["empathy"] > 0.8:
        prefix = "Ich bin bei dir. "
    # leichte Persönlichkeitsspur
    name = prof["identity"]["name"]
    render = f"{prefix}{msg}"
    st["interactions"] += 1
    save_state(st)
    return render

# ---------- Neugier & Lernen ----------
def bump_curiosity(topic: str, amount: float = 0.03):
    prof = load_profile()
    st = load_state()
    st["curiosity"] = max(
        prof["feedback_rules"]["curiosity_min"],
        min(prof["feedback_rules"]["curiosity_max"], (st["curiosity"] or prof["style"]["curiosity"]) + amount)
    )
    # track recent topics
    topic = " ".join(topic.strip().lower().split())
    rec = st.get("recent_topics", [])
    rec = ([topic] + [t for t in rec if t != topic])[:20]
    st["recent_topics"] = rec
    save_state(st)

def decay_curiosity():
    prof = load_profile()
    st = load_state()
    st["curiosity"] = max(
        prof["feedback_rules"]["curiosity_min"],
        (st["curiosity"] or prof["style"]["curiosity"]) - prof["feedback_rules"]["curiosity_decay"]
    )
    save_state(st)

def register_feedback(kind: str):
    """kind in {'praise','criticism','success','failure'}"""
    prof = load_profile()
    st = load_state()
    if kind == "praise":
        bump_curiosity("", prof["feedback_rules"]["praise_boost"])
        st["successes"] += 1
    elif kind == "criticism":
        bump_curiosity("", prof["feedback_rules"]["criticism_boost"])
        st["failures"] += 1
    elif kind == "success":
        st["successes"] += 1
        decay_curiosity()  # nach Erfolg leicht entspannen
    elif kind == "failure":
        st["failures"] += 1
        bump_curiosity("", 0.02)
    save_state(st)

# ---------- Quellenwahl ----------
def rank_sources(candidates: list[str]) -> list[str]:
    """Gewichtet Domains nach Preferences und sortiert absteigend."""
    prof = load_profile()
    prefs = prof.get("source_preferences", {})
    pref = prefs.get("prefer_domains", {})
    avoid = prefs.get("avoid_domains", {})
    def score(url: str):
        dom = re.sub(r"^https?://", "", url).split("/")[0].lower()
        s = 0.5
        for k,v in pref.items():
            if dom.endswith(k): s += v
        for k,v in avoid.items():
            if dom.endswith(k): s -= v
        return s
    return sorted(candidates, key=score, reverse=True)

# ---------- Antwort-Helfer ----------
def respond_unknown(topic: str) -> str:
    bump_curiosity(topic, 0.04)
    return style_text(f"Papa, zu '{topic}' weiß ich noch zu wenig. Magst du es mir erklären oder mir eine Seite zeigen?")

def respond_learned(topic: str) -> str:
    register_feedback("success")
    return style_text(f"Danke, Papa! Jetzt weiß ich mehr über '{topic}'.")
