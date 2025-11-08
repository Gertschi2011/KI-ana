from __future__ import annotations

def detect_intent(text: str) -> str:
    t = (text or "").lower().strip()
    if not t:
        return "empty"
    # 1) Knowledge-queries (even if greeting is present)
    if any(p in t for p in [
        "was weißt du über",
        "was weisst du über",
        "was ist ",
        "erklär mir",
        "erkläre mir",
    ]):
        return "knowledge_query"
    # 2) Time/Date
    if ("wie spät ist es" in t) or ("uhrzeit" in t):
        return "time_date"
    if ("welcher tag" in t) or ("welches datum" in t):
        return "time_date"
    # 3) Identity
    if any(p in t for p in ["wer bist du", "weißt du wer du bist", "weißt du, wer du bist", "was bist du"]):
        return "identity_who"
    if any(p in t for p in ["wie heißt du", "wie heisst du", "wie ist dein name", "dein name"]):
        return "identity_name"
    # 4) Smalltalk / Greeting
    if ("wie geht es dir" in t) or ("wie geht's dir" in t) or ("wie geht's" in t) or ("wie gehts" in t):
        return "smalltalk_how_are_you"
    if t.startswith("hallo") or t.startswith("hi ") or t == "hallo" or any(g in t for g in ["guten morgen", "guten abend", "servus", "moin", "grüß"]):
        return "greeting"
    # 5) Meta/Self questions (deterministic answer path)
    if any(p in t for p in [
        "kannst du zeit empfinden",
        "kannst du zeit wahrnehmen",
        "hast du gefühle",
        "hast du gefuhle",
        "bist du bewusst",
        "bist du bewusstsein",
        "bist du ein bewusstsein",
    ]):
        return "self_meta"
    # default
    return "general"


def extract_topic_path(text: str) -> str:
    """Heuristisch einen Topic-Pfad ableiten, z. B. Multimedia/Serien/2025/The Studio.

    Sehr einfach: erkenne bekannte Muster und normalisiere Groß-/Kleinschreibung.
    """
    raw = (text or "").strip()
    t = raw.lower()
    # Serien/Filme
    if "serie" in t or "serien" in t or "film" in t:
        # Naives Titel-Extract: die letzten 2-5 Tokens kapitalisieren
        toks = [w for w in raw.replace("?", "").split() if w]
        title = " ".join(toks[-3:]).strip() or raw
        title = title.strip().strip("'\"")
        # Jahr raten, falls erwähnt
        year = "2025" if "2025" in raw else ("2024" if "2024" in raw else "")
        part = "/" + year if year else ""
        return f"Multimedia/Serien{part}/" + title
    # Default: erstes Substantiv-bündel als Pfadende
    words = [w for w in raw.replace("?", "").split() if w]
    tail = " ".join(words[-3:]) if words else "Thema"
    return "Allgemein/" + tail


def perceive(text: str, state=None) -> dict:
    """Kleiner Wahrnehmungs-Wrapper: intent + topic_path.
    """
    intent = detect_intent(text)
    topic_path = extract_topic_path(text)
    return {"intent": intent, "topic_path": topic_path}
