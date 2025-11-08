import os
import json
import uuid
import datetime as dt
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple

# Basis-Verzeichnis für Wissensblöcke
KNOWLEDGE_BASE_DIR = os.path.join("runtime", "knowledge")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


@dataclass
class KnowledgeBlock:
    id: str
    topic_path: str               # z.B. "Multimedia/Serien/2025/The Studio"
    title: str
    summary: str
    content: str                  # ausführlicher Text
    source: str                   # "user", "web", "llm", "mixed"
    tags: List[str]
    confidence: float             # 0.0–1.0
    uses: int
    learned_at: str
    last_used_at: Optional[str] = None
    meta: Dict[str, Any] = None

    def touch(self, used_delta: int = 1, conf_delta: float = 0.0) -> None:
        self.uses += used_delta
        if conf_delta != 0:
            self.confidence = max(0.0, min(1.0, self.confidence + conf_delta))
        self.last_used_at = _now_iso()


# 1️⃣ Topic-Pfad bestimmen
def guess_topic_path(query: str,
                     hints: Optional[Dict[str, Any]] = None) -> str:
    """
    Versucht einen semantischen Pfad aus Query + Hints zu bauen.

    Beispiele:
    - query: "Was weißt du über die Serie The Studio?"
      → "Multimedia/Serien/2025/The Studio" (wenn year=2025 in hints)
    - query: "Wie funktioniert Quantenverschränkung?"
      → "Wissen/Physik/Quantenmechanik/Quantenverschränkung"

    Heuristik:
    - Wenn hints.topic_path da ist → direkt verwenden.
    - Wenn hints.category == "series" → unter Multimedia/Serien/...
    - Sonst grobe Kategorie "Wissen/Allgemein/..."
    """
    hints = hints or {}
    if "topic_path" in hints and hints["topic_path"]:
        return hints["topic_path"]

    q = (query or "").strip()
    year = hints.get("year")
    category = hints.get("category")  # z.B. "series", "movie", "person", "tech"
    main_label = hints.get("label") or hints.get("title")

    # sehr einfache Keyword-Heuristik
    lower = q.lower()

    # Serien / Multimedia
    if category == "series" or "serie" in lower or "staffel" in lower:
        # Serienname grob extrahieren
        label = main_label or _extract_main_title(q)
        parts = ["Multimedia", "Serien"]
        if year:
            parts.append(str(year))
        if label:
            parts.append(label)
        return "/".join(parts)

    # Filme
    if category == "movie" or "film" in lower or "kino" in lower:
        label = main_label or _extract_main_title(q)
        parts = ["Multimedia", "Filme"]
        if year:
            parts.append(str(year))
        if label:
            parts.append(label)
        return "/".join(parts)

    # Personen
    if category == "person" or "wer ist" in lower or "who is" in lower:
        label = main_label or _extract_main_title(q)
        parts = ["Menschen"]
        if label:
            parts.append(label)
        return "/".join(parts)

    # Default: Allgemeinwissen
    label = main_label or _extract_main_title(q) or "Allgemeines Wissen"
    parts = ["Wissen", "Allgemein", label]
    return "/".join(parts)


def _extract_main_title(text: str) -> Optional[str]:
    """
    Sehr einfache Heuristik, um einen 'Titel' aus einer Frage zu ziehen.

    - Entfernt Fragewörter ("was", "wer", "wie") und Füllwörter.
    - Entfernt Zeichen wie "?", "!".
    """
    if not text:
        return None
    t = text.strip().replace("?", "").replace("!", "")
    # primitive Splits
    for prefix in ["was weißt du über", "was kannst du mir über",
                   "was ist", "wer ist", "was weißt du über die serie",
                   "erzähl mir etwas über"]:
        if t.lower().startswith(prefix):
            t = t[len(prefix):].strip()
            break
    # Groß-/Kleinschreibung vereinfachen, aber erste Buchstaben beibehalten
    return t if t else None


# 2️⃣ Filesystem-Pfade
def _block_dir_for_topic(topic_path: str) -> str:
    return os.path.join(KNOWLEDGE_BASE_DIR, *topic_path.split("/"))


def _block_path(topic_path: str, block_id: str) -> str:
    return os.path.join(_block_dir_for_topic(topic_path), f"{block_id}.json")


# 3️⃣ Speichern & Laden
def save_knowledge_block(block: KnowledgeBlock) -> None:
    _ensure_dir(_block_dir_for_topic(block.topic_path))
    path = _block_path(block.topic_path, block.id)
    data = asdict(block)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_knowledge_block(path: str) -> KnowledgeBlock:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return KnowledgeBlock(**data)


def iter_blocks(topic_prefix: Optional[str] = None) -> List[KnowledgeBlock]:
    """
    Lädt alle Blöcke (optional nur unterhalb eines topic_prefix).
    Hinweis: Für große Datenmengen sollte später optimiert werden.
    """
    base = KNOWLEDGE_BASE_DIR
    if not os.path.isdir(base):
        return []

    blocks: List[KnowledgeBlock] = []
    if topic_prefix:
        root = os.path.join(base, *topic_prefix.split("/"))
        dirs = [root] if os.path.isdir(root) else []
    else:
        # einmal durchlauf durch alle Unterordner
        dirs = []
        for root, _, files in os.walk(base):
            if any(f.endswith(".json") for f in files):
                dirs.append(root)

    for d in dirs:
        for fname in os.listdir(d):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(d, fname)
            try:
                blocks.append(load_knowledge_block(fpath))
            except Exception:
                # soft-fail bei korrupten Files
                continue
    return blocks


# 4️⃣ Relevante Blöcke finden
def find_relevant_blocks(query: str,
                         limit: int = 5,
                         topic_hints: Optional[Dict[str, Any]] = None
                         ) -> List[Tuple[KnowledgeBlock, float]]:
    """
    Sucht nach Wissensblöcken, die semantisch zum Query passen.
    Erste Version: keyword-basierte Ähnlichkeit + Topic-Path-Filter.

    Rückgabe: Liste aus (block, score) sortiert nach score.
    """
    if not query:
        return []

    topic_prefix = None
    if topic_hints and topic_hints.get("topic_path"):
        topic_prefix = topic_hints["topic_path"]

    blocks = iter_blocks(topic_prefix=topic_prefix)
    if not blocks:
        # Versuch: alle durchsuchen
        blocks = iter_blocks()

    query_lower = query.lower()
    scores: List[Tuple[KnowledgeBlock, float]] = []

    for b in blocks:
        text = " ".join([b.title, b.summary, b.content] + b.tags).lower()
        if not text:
            continue

        # primitive keyword-overlap-score
        score = 0.0
        for token in query_lower.split():
            if len(token) <= 2:
                continue
            if token in text:
                score += 1.0

        # leichtes Bonusgewicht für häufig genutzte Blöcke
        score += min(2.0, b.uses * 0.1)
        score += b.confidence * 0.5

        if score > 0:
            scores.append((b, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:limit]


# 5️⃣ Promotion aus Lern-Items
def promote_learning_item_to_block(
    teaching_text: str,
    query: str,
    source: str = "user",
    hints: Optional[Dict[str, Any]] = None,
    base_confidence: float = 0.5,
    tags: Optional[List[str]] = None,
) -> KnowledgeBlock:
    """
    Wandelt einen Lern-Eintrag (z.B. aus learning_buffer) in einen KnowledgeBlock um
    und speichert ihn.

    - query: ursprüngliche Frage ("Was weißt du über The Studio?")
    - teaching_text: Erklärung des Users oder konsolidierter Text
    - hints: optionale Metadaten (topic_path, year, category, label, tags)
    """
    hints = hints or {}
    topic_path = guess_topic_path(query, hints=hints)

    block_id = str(uuid.uuid4())
    title = hints.get("title") or _extract_main_title(query) or "Wissensblock"
    summary = hints.get("summary") or _shorten(teaching_text, max_chars=200)

    kb = KnowledgeBlock(
        id=block_id,
        topic_path=topic_path,
        title=title,
        summary=summary,
        content=teaching_text,
        source=source,
        tags=tags or hints.get("tags") or [],
        confidence=max(0.0, min(1.0, base_confidence)),
        uses=0,
        learned_at=_now_iso(),
        last_used_at=None,
        meta={"query": query, "hints": hints},
    )

    save_knowledge_block(kb)
    return kb


def _shorten(text: str, max_chars: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
