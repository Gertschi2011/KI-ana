def think(user_info, message):
    """Natural fallback thought process used by core.dialog.

    Tries to delegate to netapi.brain.respond_to (the richer pipeline). If that
    is not available, return a short, human-friendly answer or a clarifying
    question instead of echoing prompts.
    """
    try:
        from netapi.brain import respond_to as _rt  # type: ignore
        lang = (user_info or {}).get("lang", "de-DE") if isinstance(user_info, dict) else "de-DE"
        return _rt(str(message or ""), system="", lang=lang, persona="friendly")
    except Exception:
        msg = (str(message or "").strip())
        if not msg:
            return "Hallo! Worum geht’s dir gerade? Dann steige ich ein."
        # simple clarification for vague prompts
        if len(msg.split()) <= 3:
            return f"Meinst du {msg} eher als Definition, Beispiele oder einen kurzen Überblick?"
        return (
            f"Okay – {msg}. Soll ich es kurz erklären, in Stichpunkten zusammenfassen oder einen kleinen Plan vorschlagen?"
        )

def brain_status():
    return {"status": "bereit"}

async def autonomous_tick():
    return {"tick": "durchgeführt"}
