from __future__ import annotations
from typing import Tuple, List, Dict, Any

"""
Unified deliberate pipeline used by Chat and Agent.

Stages: Planner -> Researcher -> Writer -> Critic -> Refine
Returns: (final_answer, sources, plan_brief, critic_brief)
"""

try:
    from . import tools as T  # type: ignore
except Exception:  # pragma: no cover
    T = None  # type: ignore

try:
    from netapi.core import llm_local  # type: ignore
except Exception:  # pragma: no cover
    llm_local = None  # type: ignore

try:
    from netapi.web_qa import web_search_and_summarize as _web_sum  # type: ignore
except Exception:  # pragma: no cover
    def _web_sum(q: str, user_context=None, max_results: int = 3):  # type: ignore
        return {"results": []}


def _short_lines(text: str, n: int = 4) -> List[str]:
    lines = [l.strip(" -*\t") for l in (text or "").splitlines() if l.strip()]
    out: List[str] = []
    for l in lines:
        out.append(l)
        if len(out) >= n:
            break
    return out


def _call_llm_once(user: str, system: str = "") -> str:
    if llm_local is not None and getattr(llm_local, "available", lambda: False)():
        out = llm_local.chat_once(user, system=system)
        return (out or "").strip()
    return ""


def deliberate_pipeline(user_msg: str, *, persona: str, lang: str, style: str, bullets: int, logic: str, fmt: str) -> Tuple[str, List[dict], str, str]:
    # 1) Planner
    try:
        sys = (
            "Du bist Planer. Erstelle in 2–4 kurzen Punkten einen Plan, wie du die Frage beantwortest. "
            "Nenne dabei 1–3 Teilfragen oder Stichwörter, die recherchiert werden sollten. Nur die Liste."
        )
        plan = _call_llm_once(f"Frage:\n{user_msg}\n\nPlan:", system=sys) or ""
    except Exception:
        plan = "- Kurz antworten\n- 1–2 Quellen prüfen"
    plan_items = _short_lines(plan, n=3)

    # 2) Researcher
    srcs: List[dict] = []
    notes: List[str] = []
    queries = plan_items[:2] or [user_msg]
    for q in queries:
        try:
            res = _web_sum(q, user_context={"lang": (lang or "de").split("-",1)[0]}, max_results=3)
            for it in (res.get("results") or [])[:3]:
                if it.get("summary"):
                    notes.append(it["summary"])  # brief
                if it.get("url") or it.get("title"):
                    srcs.append({"title": it.get("title") or "Web", "url": it.get("url") or ""})
        except Exception:
            continue

    # 3) Writer
    draft = ""
    try:
        research_text = ("\n\n".join(notes)).strip() or user_msg
        sys = (
            "Du bist Schreiber. Verfasse eine hilfreiche, prägnante Antwort basierend auf den Notizen. "
            "Halte dich an {style} und die gewünschte Struktur ({fmt}). Antworte auf {lang}. Gib NUR die Antwort aus."
        ).format(style=style, fmt=fmt, lang=lang)
        draft = _call_llm_once("Notizen:\n" + research_text + "\n\nAntwort:", system=sys)
    except Exception:
        pass

    # 4) Critic
    critic = ""
    try:
        sys = "Du bist Kritiker. Prüfe die Antwort auf Lücken/Unklarheiten und gib 2–4 kurze Verbesserungen (Aufzählung)."
        critic = _call_llm_once("Antwort:\n" + (draft or "") + "\n\nVerbesserungen:", system=sys)
    except Exception:
        pass
    critic_items = _short_lines(critic, n=3)

    # 5) Refine
    final_answer = draft
    if critic_items:
        try:
            sys = (
                "Überarbeite die Antwort gemäß den Verbesserungspunkten. Ziel: Korrektheit, Klarheit, Ergänzung wichtiger Punkte. "
                "Gib NUR die verbesserte Antwort aus."
            )
            improved = _call_llm_once("Antwort:\n" + (draft or "") + "\n\nVerbesserungen:\n- " + "\n- ".join(critic_items) + "\n\nNeu:", system=sys)
            if improved:
                final_answer = improved
        except Exception:
            pass

    plan_brief = "; ".join(plan_items[:2])
    critic_brief = "; ".join(critic_items[:2])
    return (final_answer or draft or "", srcs, plan_brief, critic_brief)

