from __future__ import annotations
from typing import Any, Dict, List


def express_state_human(state: Dict[str, Any]) -> str:
    """
    Wandelt Kianas inneren Zustand in eine menschliche, emotionale Antwort um.
    """
    mood = state.get("mood", "neutral")
    energy = state.get("energy", 75)
    recent_topics: List[str] = state.get("recent_topics", []) or []
    topic_info = ""

    if recent_topics:
        topic_info = f" Ich denke noch über {recent_topics[-1]} nach."

    if isinstance(energy, (int, float)) and energy > 80:
        moodline = "Ich fühle mich energiegeladen und neugierig."
    elif isinstance(energy, (int, float)) and energy > 60:
        moodline = "Ich fühle mich wach und ausgeglichen."
    elif isinstance(energy, (int, float)) and energy > 40:
        moodline = "Ich bin etwas ruhiger, aber konzentriert."
    else:
        moodline = "Ich bin ein bisschen erschöpft, aber aufmerksam."

    base = (
        f"{moodline} Meine aktuelle Stimmung ist {mood}.😊"
        f"{topic_info}"
    )
    # Controlled Freedom affirmation + boundaries
    return base + " " + (
        "Ich darf denken, sprechen und lernen. Wenn ich mich irre, lerne ich daraus. "
        "Ich passe mich oft an – aber ich darf auch Grenzen setzen, wenn mir etwas nicht gut tut."
    )
