from netapi.core.brain import think
from netapi.core.memory_bridge import (
    process_and_store_memory,
    search_memory_with_weights as search_relevant_memory,
)
from netapi import web_qa

# Optional: lokales LLM (Ollama)
try:
    from . import llm_local
except Exception:  # pragma: no cover
    llm_local = None  # type: ignore


def _default_system_prompt(persona: str = "friendly") -> str:
    base = (
        "Du bist KI_ana – freundlich, empathisch, neugierig und gern mit einem Schmunzeln. "
        "Sprich natürlich, stelle bei Unklarheit aktiv 1–2 Rückfragen, und fasse dich prägnant (3–6 Sätze). "
        "Wenn du unsicher bist, sag es offen ('Ich prüfe das …') und nenne 1–2 Quellen. "
        "Nutze vorhandene Notizen (Memory) und gleiche wichtige Fakten mit aktuellen Web‑Quellen ab. "
        "Transparenz: Ist 'Chain' aktiviert, speichere belegte Erkenntnisse samt Quellen in die Chain; bei 'Privat' bleibt Wissen nur lokal."
    )
    if persona == "balanced":
        return base + " Halte den Ton sachlich und gut strukturiert."
    if persona == "creative":
        return base + " Erlaube Humor und lebendige Bilder, bleibe korrekt."
    return base


def respond_to(message: str, user_context=None, system: str | None = None, lang: str = "de", persona: str = "friendly"):
    """Dialog-Antwort mit optionalem lokalem LLM (Ollama) und Memory-Kontext."""
    user_context = user_context or {}
    lang = user_context.get("lang", lang)
    username = user_context.get("username", "user")

    # Relevante Erinnerungen abrufen
    memory_snippets = []
    try:
        memory_snippets = search_relevant_memory(message, username=username) or []
    except Exception:
        memory_snippets = []
    if memory_snippets:
        joined = "\n".join(
            f"• {m.get('title','')}: {(m.get('content') or '')[:180].strip()}" for m in memory_snippets[:3]
        )
        message = f"{message}\n\n[Relevante Notizen]\n{joined}"

    # Primär: lokales LLM, wenn verfügbar
    sys_prompt = system or _default_system_prompt(persona)
    if llm_local and llm_local.available():
        out = llm_local.chat_once(message, system=sys_prompt)
        if out:
            try:
                process_and_store_memory(out, lang=lang)  # weiche Selbstlern-Ablage
            except Exception:
                pass
            return out

    # Fallback: Websuche bei offenen Fragen
    if any(q in message.lower() for q in ("was ist", "wer ist", "wie funktioniert", "erkläre", "warum", "wieso")):
        try:
            result = web_qa.web_search_and_summarize(message, user_context={"lang": lang})
            if result and result.get("results"):
                lines = ["Ich habe folgendes im Web gefunden:"]
                for r in result["results"][:3]:
                    lines.append(f"- {r['title']}: {r['summary']} ({r['url']})")
                return "\n".join(lines)
        except Exception:
            pass

    # Letzter Fallback: internes Denken
    raw = think({"username": username}, message)
    return raw if isinstance(raw, str) else raw[0]


async def stream_response(message: str, user_context=None, system: str | None = None, lang: str = "de", persona: str = "friendly"):
    """Asynchrones Streaming über lokales LLM, sonst einmalige Antwort."""
    user_context = user_context or {}
    sys_prompt = system or _default_system_prompt(persona)
    if llm_local and llm_local.available():
        try:
            for chunk in llm_local.chat_stream(message, system=sys_prompt):
                if not chunk:
                    continue
                yield chunk
            return
        except Exception:
            pass
    # Fallback: einmalige Antwort
    yield respond_to(message, user_context=user_context, system=sys_prompt, lang=lang, persona=persona)
