from __future__ import annotations
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json, time, re, uuid, heapq, os

from netapi.utils.fs import atomic_write_json, atomic_write_text

# ------------------------------------------------------------
# Speicher-Layout (Systempfad, wie bei dir beschrieben)
#   ~/ki_ana/memory/
#     ├─ long_term/
#     │   └─ blocks/*.json
#     ├─ short_term/
#     │   └─ chat_*.json
#     ├─ known_topics.txt
#     └─ open_questions.json
# ------------------------------------------------------------

def _detect_root() -> Path:
    env_root = (os.getenv("KI_ROOT") or os.getenv("KIANA_ROOT") or os.getenv("APP_ROOT") or "").strip()
    if env_root:
        try:
            p = Path(env_root).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p
        except Exception:
            pass
    # netapi/modules/chat/memory_adapter.py -> <root>/netapi/modules/chat/...
    return Path(__file__).resolve().parents[3]


ROOT = _detect_root()
MEM_DIR = ROOT / "memory"
LT_BLOCKS = MEM_DIR / "long_term" / "blocks"
ST_DIR = MEM_DIR / "short_term"
KNOWN_TOPICS = MEM_DIR / "known_topics.txt"
OPEN_QUESTIONS = MEM_DIR / "open_questions.json"

for p in [LT_BLOCKS, ST_DIR]:
    p.mkdir(parents=True, exist_ok=True)
if not KNOWN_TOPICS.exists():
    atomic_write_text(KNOWN_TOPICS, "", encoding="utf-8")
if not OPEN_QUESTIONS.exists():
    atomic_write_text(OPEN_QUESTIONS, "[]", encoding="utf-8")

# --------- Simple Tokenizer/Scorer (keine externen Deps) ---------
_WORD = re.compile(r"[A-Za-zÄÖÜäöüß0-9_-]+")
STOPWORDS = {
    # Deutsch – häufige Funktionswörter/Pronomen/Artikel/Präpositionen
    "der","die","das","ein","eine","einer","einem","einen","eines",
    "und","oder","aber","nicht","kein","keine","ohne","mit","für","von","im","in","am","an","auf","zu","zum","zur","des","den","dem","dass","weil","wenn","dann","so","nur","noch","auch","schon","sehr","mehr","weniger",
    "ist","sind","war","waren","wird","werden","wurde","wurden","hat","haben","habe","hast","hatte","hatten",
    "ich","du","er","sie","es","wir","ihr","man","mein","dein","sein","ihr","unser","euer",
    "wie","was","wo","wann","warum","wieso","über","unter","zwischen","gegen","bei","nach","vor","hinter",
    "ja","nein","bitte","hallo","hey","servus","grüß","dich",
    # Wissens-Verb generisch – mindert Pseudo-Treffer auf Titel à la "Was weißt du ..."
    "weiß","weiss","weißt"
}

def tokenize(s: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(s or "")]

def _sig_tokens(s: str) -> List[str]:
    toks = [t for t in tokenize(s) if len(t) > 2 and t not in STOPWORDS]
    return toks

def score_query(query: str, text: str, title_boost: float = 1.4) -> float:
    """Sehr simple Relevanz: Term-Overlap (ohne Stoppwörter) + leichte Längen-Normalisierung."""
    q = _sig_tokens(query)
    t = _sig_tokens(text)
    if not q or not t:
        return 0.0
    qset = set(q)
    match = sum(1 for tok in t if tok in qset)
    return match / (len(t) ** 0.25)

@dataclass
class Block:
    id: str
    title: str
    content: str
    tags: List[str]
    url: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    meta: Optional[Dict] = None
    path: Optional[str] = None
    score: Optional[float] = None

    @staticmethod
    def from_json(p: Path) -> "Block":
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        return Block(
            id = data.get("id") or p.stem,
            title = data.get("title") or "",
            content = data.get("content") or "",
            tags = data.get("tags") or [],
            url = data.get("url"),
            created_at = float(data.get("created_at") or time.time()),
            meta = data.get("meta"),
            path = str(p),
        )

# ------------------------ Internals ------------------------

def _iter_blocks() -> List[Block]:
    items: List[Block] = []
    for p in sorted(LT_BLOCKS.glob("*.json")):
        try:
            items.append(Block.from_json(p))
        except Exception:
            continue
    return items

def _iter_shortterm_latest(n: int = 6) -> List[Tuple[str, str]]:
    """Grobe Extraktion aus den letzten Chat-Protokollen (Text nur best effort)."""
    pairs: List[Tuple[str,str]] = []
    files = sorted(ST_DIR.glob("chat_*.json"))[-n:]
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        msgs = data if isinstance(data, list) else data.get("messages") or []
        text = []
        for m in msgs:
            if isinstance(m, dict):
                t = m.get("text") or m.get("content") or ""
                if t:
                    text.append(str(t))
        if text:
            pairs.append((p.stem, "\n".join(text)))
    return pairs

# -------------------------- PUBLIC API --------------------------

def recall(query: str, top_k: int = 3, include_shortterm: bool = True) -> List[Dict]:
    """Suche in long_term (und optional short_term). Rückgabe: Liste mit {title, content, score, url, path}.
    Kompatibel zum Chat-Router: score >= 0.25 gilt als "starker Treffer".
    """
    q = query.strip()
    if not q:
        return []

    # Use a tie-breaker index to avoid comparing dicts when scores are equal
    heap: List[Tuple[float, int, Dict]] = []
    _idx = 0

    # long_term blocks
    for b in _iter_blocks():
        s = score_query(q, b.title + "\n" + b.content)
        if s <= 0:
            continue
        item = {
            "title": b.title,
            "content": b.content,
            "score": round(float(s), 4),
            "url": b.url,
            "path": b.path,
            "tags": b.tags,
            "meta": b.meta,
            "created_at": b.created_at,
        }
        heapq.heappush(heap, (-s, _idx, item)); _idx += 1

    # short_term schwächer gewichten
    if include_shortterm:
        for stem, text in _iter_shortterm_latest():
            s = 0.6 * score_query(q, text)  # gedämpft
            if s <= 0:
                continue
            item = {
                "title": f"Chatlog {stem}",
                "content": text[:800],
                "score": round(float(s), 4),
                "url": None,
                "path": str((ST_DIR / f"{stem}.json")),
                "tags": ["short_term"],
                "created_at": None,
            }
            heapq.heappush(heap, (-s, _idx, item)); _idx += 1

    results: List[Dict] = []
    for _ in range(min(top_k, len(heap))):
        _, __, it = heapq.heappop(heap)
        results.append(it)
    return results


def store(title: str, content: str, tags: List[str], url: Optional[str] = None, meta: Optional[Dict] = None) -> Path:
    """Lege neuen Wissensblock im long_term ab und pflege known_topics.txt.
    Gibt den Pfad der angelegten JSON-Datei zurück.
    """
    blk = Block(
        id = f"BLK_{int(time.time())}_{uuid.uuid4().hex[:6]}",
        title = (title or "").strip()[:200] or "Notiz",
        content = (content or "").strip(),
        tags = list(tags or []),
        url = url,
        created_at = time.time(),
        meta = meta or {},
    )
    path = LT_BLOCKS / f"{blk.id}.json"
    data = asdict(blk); data["path"] = None  # keine absoluten Pfade im JSON ablegen
    atomic_write_json(path, data, kind="block", min_bytes=32)

    # known_topics pflegen (einfach: jede Zeile ein Topic/Tag/Title-Snippet)
    try:
        topics = set([t.strip() for t in KNOWN_TOPICS.read_text(encoding="utf-8").splitlines() if t.strip()])
        topics.add(blk.title)
        for t in blk.tags:
            topics.add(t)
        atomic_write_text(KNOWN_TOPICS, "\n".join(sorted(topics)), encoding="utf-8")
    except Exception:
        pass

    return path


def add_open_question(question: str, context: Optional[Dict] = None) -> None:
    """Frage vormerken – z. B. wenn die KI unsicher ist."""
    try:
        items = json.loads(OPEN_QUESTIONS.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    items.append({
        "question": question.strip(),
        "context": context or {},
        "created_at": time.time(),
        "id": uuid.uuid4().hex[:10],
        "status": "open",
    })
    atomic_write_json(OPEN_QUESTIONS, items, kind="index", min_bytes=2)


def list_open_questions() -> List[Dict]:
    try:
        items = json.loads(OPEN_QUESTIONS.read_text(encoding="utf-8"))
        return items if isinstance(items, list) else []
    except Exception:
        return []
