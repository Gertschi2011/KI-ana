from typing import List, Tuple, Dict
import re

# Memory-Schnittstelle (robust: funktioniert auch, wenn memory_store minimal ist)
try:
    from ... import memory_store as _mem
except Exception:
    _mem = None

QUESTION_HINTS = ("was ist", "warum", "wieso", "wie funktioniert", "erkläre", "?")
UNCERTAIN_RX = re.compile(r"(weiß.*nicht|unsicher|keine.*info|kann.*nicht.*beantworten)", re.I)

def is_question(q: str) -> bool:
    ql = (q or "").lower()
    return ql.endswith("?") or any(k in ql for k in QUESTION_HINTS)

def is_uncertain(text: str) -> bool:
    return bool(UNCERTAIN_RX.search(text or ""))

def search_memory(query: str, top_k: int = 3) -> List[Dict]:
    if not _mem or not hasattr(_mem, "search"):
        return []
    try:
        # erwartetes Format: [{"title":..., "content":..., "score":..., "url":...}, ...]
        return _mem.search(query, top_k=top_k) or []
    except Exception:
        return []

def should_browse(user_query: str, draft_reply: str, mem_hits: List[Dict]) -> bool:
    # Suche nur, wenn es eine Wissensfrage ist & Memory nix/kaum hat oder Entwurf unsicher wirkt
    if not is_question(user_query):
        return False
    if is_uncertain(draft_reply):
        return True
    if len(mem_hits) == 0:
        return True
    # falls Memory da ist, aber offensichtlich nicht passt (sehr niedrige scores), auch suchen
    low = [m for m in mem_hits if float(m.get("score", 0.0)) < 0.25]
    return len(low) == len(mem_hits)