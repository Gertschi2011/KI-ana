from netapi.memory_store import add_block, auto_update_block, search_blocks, get_block
from datetime import datetime


def should_remember(text: str) -> bool:
    """
    Einfache Entscheidungslogik, ob etwas erinnerungswürdig ist.
    Später durch KI-Modell oder feinere Heuristik ersetzbar.
    """
    keywords = ["wichtig", "merken", "lernen", "erkenntnis", "problem", "ziel", "lösung"]
    return any(kw in text.lower() for kw in keywords) or len(text.strip()) > 200


# Bewertet die Wichtigkeit eines Textes für das Langzeitgedächtnis.
# Skala: 0.0 = unwichtig, 1.0 = sehr wichtig.
# Später ersetzbar durch ein ML-Modell.
def evaluate_importance(text: str) -> float:
    """
    Bewertet die Wichtigkeit eines Textes für das Langzeitgedächtnis.
    Skala: 0.0 = unwichtig, 1.0 = sehr wichtig.
    Später ersetzbar durch ein ML-Modell.
    """
    text = text.lower().strip()
    if not text or len(text) < 10:
        return 0.0

    score = 0.0
    keywords = {
        "wichtig": 0.4,
        "merken": 0.5,
        "lernen": 0.6,
        "problem": 0.7,
        "ziel": 0.6,
        "lösung": 0.8,
        "erkenntnis": 1.0,
    }

    for kw, weight in keywords.items():
        if kw in text:
            score = max(score, weight)

    if len(text) > 250:
        score = max(score, 0.5)

    return round(score, 2)

def process_and_store_memory(input_text: str, lang: str = "de", auto_refine: bool = True) -> dict:
    """
    Erkenntnisse in Langzeitgedächtnis ablegen.
    Automatisch Themen extrahieren, Ähnlichkeit prüfen, ggf. Refinement erzeugen.
    Gibt dict mit Infos zum Ergebnis zurück.
    """
    importance = evaluate_importance(input_text)
    if importance < 0.5:
        return {
            "saved_block": None,
            "refined_block": None,
            "skipped": True,
            "reason": "not deemed important enough",
            "importance": importance
        }
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"Erkenntnis vom {ts}"
    tags = []  # später: automatische Themenanalyse
    url = ""

    block_id = add_block(title=title, content=input_text.strip(), tags=tags, url=url)

    refinement_id = None
    if auto_refine:
        refinement_id = auto_update_block(block_id)

    return {
        "saved_block": block_id,
        "refined_block": refinement_id,
        "importance": importance,
    }

def search_memory(query: str, lang: str = "de", top_k: int = 5) -> list:
    """
    Durchsuche Langzeitgedächtnis semantisch nach relevanten Erkenntnissen.
    Gibt Liste mit Blöcken zurück.
    """
    results = search_blocks(query=query, top_k=top_k)
    out = []
    for bid, score in results:
        obj = get_block(bid)
        if obj:
            out.append({
                "id": bid,
                "score": round(score, 3),
                "title": obj.get("title", ""),
                "content": obj.get("content", ""),
                "tags": obj.get("tags", []),
            })
    return out


# Neue Funktion: search_memory_with_weights
def search_memory_with_weights(query: str, username: str = "user", top_k: int = 5) -> list:
    """
    Führt eine semantische Suche durch und gibt zusätzlich Gewichtungen für Entscheidungshilfe zurück.
    """
    results = search_blocks(query=query, top_k=top_k)
    out = []
    for bid, score in results:
        obj = get_block(bid)
        if obj:
            out.append({
                "id": bid,
                "score": round(score, 3),
                "title": obj.get("title", ""),
                "content": obj.get("content", ""),
                "tags": obj.get("tags", []),
                "weight": round(score, 3)  # Doppelt zur Klarheit für die KI
            })
    return out


__all__ = ["bridge_memory", "process_and_store_memory", "search_memory", "search_memory_with_weights", "evaluate_importance", "should_remember"]

def bridge_memory(input_text: str, lang: str = "de") -> dict:
    """
    Brücke zwischen Nutzerinput und semantischem Gedächtnisabruf.
    Führt Speicherung (bei Relevanz) UND parallele Suche durch.
    """
    store_result = process_and_store_memory(input_text=input_text, lang=lang)
    search_results = search_memory_with_weights(query=input_text)
    return {
        "memory_saved": store_result,
        "search_results": search_results
    }