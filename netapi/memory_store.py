from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
# memory_store.py – einfache Wissensblöcke + Index + semantische (Keyword) Suche
import os, json, time, math, re, random, string, hashlib, sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

ROOT = Path(__file__).resolve().parent.parent
MEM_DIR = ROOT / "memory" / "long_term" / "blocks"
SHORT_DIR = ROOT / "memory" / "short_term" / "blocks"
IDX_DIR = ROOT / "indexes"
INV_PATH = ROOT / "memory" / "index" / "inverted.json"       # inverted (token -> [ids])
TOPIC_IDX_PATH = ROOT / "memory" / "index" / "topics.json"     # topic_path -> [ids]
VEC_PATH = IDX_DIR / "vector" / "index.json"          # vectors (id -> token:weight)
META_PATH = IDX_DIR / "vector" / "meta.json"          # meta (id -> title,tags,ts,url)
RATINGS_PATH = IDX_DIR / "ratings.json"               # ratings (id -> {avg,count,log:[...]})
EMB_DIR  = IDX_DIR / "emb"
EMB_INDEX = EMB_DIR / "index.npy"
EMB_IDS   = EMB_DIR / "ids.json"

STOP = set("""
der die das ein eine einer einem einen den und oder aber nicht ist sind war waren wie was wann wo warum mit ohne bei aus auf zu zum zur von im am an für über unter vor nach seit schon noch sehr mehr auch auch,.
""".replace(",", " ").split())

TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß0-9]{2,}")

def ensure_dirs():
    (IDX_DIR / "vector").mkdir(parents=True, exist_ok=True)
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    SHORT_DIR.mkdir(parents=True, exist_ok=True)
    INV_PATH.parent.mkdir(parents=True, exist_ok=True)

def _tok(text: str) -> List[str]:
    text = text.lower()
    toks = TOKEN_RE.findall(text)
    return [t for t in toks if t not in STOP]

def _read_json(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _write_json(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _canonical_for_hash(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical dict for hashing: exclude transient hash fields."""
    d = dict(data)
    for k in ("hash", "hash_stored", "hash_calc"):
        d.pop(k, None)
    return d

def _calc_hash(data: Dict[str, Any]) -> str:
    """Compute SHA256 over canonical JSON (sorted keys, compact separators)."""
    try:
        raw = json.dumps(_canonical_for_hash(data), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except Exception:
        return ""

def _gen_id() -> str:
    base = int(time.time())
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"BLK_{base}_{rand}"

# -----------------------
# Short-term memory (child learning)
# -----------------------

def create_short_term_block(topic_path: str, info: str, source: str = "user", confidence: float = 0.6) -> str:
    """Create a short-term knowledge block and return its id."""
    ensure_dirs()
    bid = _gen_id()
    data = {
        "id": bid,
        "topic_path": (topic_path or "Unsortiert/UserWissen").strip(),
        "info": (info or "").strip(),
        "source": source or "user",
        "confidence": float(confidence or 0.6),
        "uses": 0,
        "ts": int(time.time()),
        "hash": _calc_hash({"topic_path": topic_path, "info": info, "source": source}),
    }
    out = SHORT_DIR / f"{bid}.json"
    _write_json(out, data)
    try:
        index_topic(data["topic_path"], bid)
    except Exception:
        pass
    return bid

def load_short_term_block(block_id: str) -> Optional[dict]:
    try:
        p = SHORT_DIR / f"{block_id}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def topic_index_list(topic_path: str) -> List[str]:
    """Return list of short-term block ids associated with a topic_path."""
    try:
        idx = _read_json(TOPIC_IDX_PATH)
        lst = idx.get(topic_path, [])
        return list(lst or [])
    except Exception:
        return []

def increment_use(block_id: str) -> None:
    try:
        p = SHORT_DIR / f"{block_id}.json"
        if not p.exists():
            return
        obj = json.loads(p.read_text(encoding="utf-8"))
        obj["uses"] = int(obj.get("uses", 0)) + 1
        _write_json(p, obj)
    except Exception:
        return

def index_topic(topic_path: str, block_id: str) -> None:
    try:
        ensure_dirs()
        idx = _read_json(TOPIC_IDX_PATH)
        lst = list(idx.get(topic_path, []))
        if block_id not in lst:
            lst.append(block_id)
        idx[topic_path] = lst[-50:]
        _write_json(TOPIC_IDX_PATH, idx)
    except Exception:
        return

def maybe_promote(block_id: str) -> Optional[str]:
    """Promote a short-term block to long-term if usage/confidence criteria are met.
    Returns new long-term block id or None.
    """
    try:
        obj = load_short_term_block(block_id)
        if not obj:
            return None
        uses = int(obj.get("uses", 0))
        conf = float(obj.get("confidence", 0.0))
        if uses >= 2 or conf >= 0.7:
            title = obj.get("topic_path", "Wissen/Unsortiert")
            content = obj.get("info", "")
            tags = ["learned", "promoted"]
            new_id = add_block(title=title, content=content, tags=tags, url=None)
            return new_id
        return None
    except Exception:
        return None

def add_block(title: str, content: str, tags: Optional[List[str]] = None, url: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> str:
    """Speichert einen Wissensblock als JSON-Datei und aktualisiert die Indizes."""
    ensure_dirs()
    bid = _gen_id()
    data: Dict[str, Any] = {
        "id": bid,
        "title": title.strip(),
        "content": content.strip(),
        "tags": tags or [],
        "url": url or "",
        "ts": int(time.time()),
        "meta": meta or {},
    }
    # Set deterministic content hash for validation tools (viewer, chain)
    data["hash"] = _calc_hash(data)
    # Datei speichern
    out_path = MEM_DIR / f"{bid}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Indizes aktualisieren
    _update_indexes(bid, data)

    # Optional: in die Chain anhängen (Blockchain‑Gedächtnis)
    try:
        if os.getenv("CHAIN_APPEND", "0") == "1":
            # Nur wenn explizit gewünscht: meta.chain_hint == True
            chain_hint = bool((meta or {}).get("chain_hint", False))
            if not chain_hint:
                return bid
            try:
                from system.chain_writer import write_chain_block  # type: ignore
                payload = {
                    "type": "knowledge",
                    "topic": data.get("title") or (tags[0] if tags else ""),
                    "source": "memory_store",
                    "memory_path": str(out_path),
                    "content_hash": hashlib.sha256(out_path.read_bytes()).hexdigest(),
                    "meta": {"tags": data.get("tags", []), "url": data.get("url", "")},
                }
                write_chain_block(payload)
            except Exception:
                pass
    except Exception:
        pass
    return bid

def _update_indexes(bid: str, data: dict) -> None:
    # inverted
    inv = _read_json(INV_PATH)
    toks = set(_tok(data.get("title","") + " " + data.get("content","") + " " + " ".join(data.get("tags",[]))))
    for t in toks:
        inv.setdefault(t, [])
        if bid not in inv[t]:
            inv[t].append(bid)
    _write_json(INV_PATH, inv)

    # meta
    meta = _read_json(META_PATH)
    meta[bid] = {
        "title": data.get("title",""),
        "tags": data.get("tags", []),
        "ts": data.get("ts", 0),
        "url": data.get("url","")
    }
    _write_json(META_PATH, meta)

    # vector (TF-IDF light)
    _rebuild_vectors()

def _rebuild_vectors():
    inv = _read_json(INV_PATH)   # token -> [ids]
    meta = _read_json(META_PATH) # id -> meta
    vecs: Dict[str, Dict[str, float]] = {}
    # Dokumente laden
    docs: Dict[str, str] = {}
    for bid in meta.keys():
        p = MEM_DIR / f"{bid}.json"
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            docs[bid] = (obj.get("title","") + " " + obj.get("content","") + " " + " ".join(obj.get("tags",[])))
        except Exception:
            continue

    # DF (document frequency)
    df: Dict[str, int] = {t: len(set(ids)) for t, ids in inv.items()}
    N = max(1, len(docs))

    # Vektoren berechnen
    for bid, text in docs.items():
        toks = _tok(text)
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        # tf-idf
        vec = {}
        for t, f in tf.items():
            idf = math.log((N + 1) / (1 + df.get(t, 1))) + 1.0
            vec[t] = (f / len(toks)) * idf
        # normalisieren
        norm = math.sqrt(sum(v*v for v in vec.values())) or 1.0
        for t in list(vec.keys()):
            vec[t] = vec[t] / norm
        vecs[bid] = vec

    _write_json(VEC_PATH, vecs)

# -----------------------
# Semantic embeddings (optional)
# -----------------------
def _embed_available() -> bool:
    try:
        import numpy  # noqa: F401
        from sentence_transformers import SentenceTransformer  # type: ignore
        return True
    except Exception:
        return False

def _load_embed_model():
    from sentence_transformers import SentenceTransformer  # type: ignore
    model_name = os.getenv('KI_EMB_MODEL', 'sentence-transformers/paraphrase-MiniLM-L6-v2')
    return SentenceTransformer(model_name)

def build_embeddings_index(limit: Optional[int] = None) -> bool:
    """Builds an embedding index for memory blocks if sentence_transformers is available.
    Returns True on success, False otherwise.
    """
    if not _embed_available():
        return False
    try:
        import numpy as np
        ensure_dirs()
        EMB_DIR.mkdir(parents=True, exist_ok=True)
        # load docs
        meta = _read_json(META_PATH)
        ids = list(meta.keys())
        if limit:
            ids = ids[: int(limit)]
        texts = []
        kept_ids = []
        for bid in ids:
            p = MEM_DIR / f"{bid}.json"
            if not p.exists():
                continue
            try:
                obj = json.loads(p.read_text(encoding='utf-8'))
                text = (obj.get('title','') + '\n' + obj.get('content','')).strip()
                if not text:
                    continue
                texts.append(text)
                kept_ids.append(bid)
            except Exception:
                continue
        if not texts:
            return False
        model = _load_embed_model()
        vecs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        np.save(EMB_INDEX, vecs)
        _write_json(EMB_IDS, kept_ids)
        return True
    except Exception:
        return False

def search_blocks_semantic(query: str, top_k: int = 5, min_score: float = 0.15) -> List[Tuple[str, float]]:
    if not _embed_available():
        return []
    try:
        import numpy as np
        if not EMB_INDEX.exists() or not EMB_IDS.exists():
            if not build_embeddings_index():
                return []
        ids = json.loads(EMB_IDS.read_text(encoding='utf-8'))
        vecs = np.load(EMB_INDEX)
        if not len(ids) or not vecs.size:
            return []
        model = _load_embed_model()
        qv = model.encode([query], show_progress_bar=False, normalize_embeddings=True)[0]
        sims = (vecs @ qv).tolist()  # cosine if normalized
        ranked = sorted([(ids[i], float(sims[i])) for i in range(len(ids))], key=lambda x: x[1], reverse=True)
        return [(bid, sc) for (bid, sc) in ranked if sc >= min_score][:top_k]
    except Exception:
        return []

def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # aus Effizienz: iteriere über kleinere Menge
    if len(a) > len(b):
        a, b = b, a
    s = 0.0
    for k, v in a.items():
        if k in b:
            s += v * b[k]
    return float(s)

def search_blocks(query: str, top_k: int = 5, min_score: float = 0.12) -> List[Tuple[str, float]]:
    """Sucht relevante Blöcke zu einer Query. Liefert [(id, score), ...]"""
    ensure_dirs()
    vecs = _read_json(VEC_PATH)
    if not vecs:
        return []
    # Query-Vektor
    toks = _tok(query)
    if not toks:
        return []
    # naive TF (ohne IDF) reicht für Query
    q_tf: Dict[str, float] = {}
    for t in toks:
        q_tf[t] = q_tf.get(t, 0.0) + 1.0
    # normalisieren
    norm = math.sqrt(sum(v*v for v in q_tf.values())) or 1.0
    for t in list(q_tf.keys()):
        q_tf[t] = q_tf[t] / norm

    scored = []
    for bid, vec in vecs.items():
        score = _cosine(q_tf, vec)
        if score >= min_score:
            scored.append((bid, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

def get_block(bid: str) -> Optional[dict]:
    p = MEM_DIR / f"{bid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

# -----------------------
# Ratings / Validation
# -----------------------

def rate_block(bid: str, score: float, *, proof_url: Optional[str] = None, reviewer: Optional[str] = None, comment: Optional[str] = None) -> dict:
    """
    Adds a rating entry for a block id, maintains avg/count summary.
    score: 0.0 .. 1.0
    """
    if not (isinstance(score, (int, float)) and 0.0 <= float(score) <= 1.0):
        raise ValueError("score must be between 0.0 and 1.0")
    meta = _read_json(META_PATH)
    if bid not in meta:
        raise KeyError("unknown block id")
    ratings = _read_json(RATINGS_PATH)
    rec = ratings.get(bid) or {"avg": 0.0, "count": 0, "log": []}
    entry = {
        "ts": int(time.time()),
        "score": float(score),
        "proof_url": proof_url or "",
        "reviewer": reviewer or "",
        "comment": comment or "",
    }
    rec["log"].append(entry)
    # update avg
    n = int(rec.get("count", 0)) + 1
    old_sum = float(rec.get("avg", 0.0)) * float(rec.get("count", 0))
    new_avg = (old_sum + float(score)) / n
    rec["count"] = n
    rec["avg"] = round(new_avg, 4)
    ratings[bid] = rec
    _write_json(RATINGS_PATH, ratings)
    return {"id": bid, **rec}

def get_rating(bid: str) -> Optional[dict]:
    ratings = _read_json(RATINGS_PATH)
    r = ratings.get(bid)
    if not r:
        return None
    return {"id": bid, **r}

# -----------------------
# Erweiterungen: Themenindex, Vergleich, Auto-Update
# -----------------------

def list_topics(prefix: str | None = None, limit: int = 200) -> List[str]:
    """
    Liefert eine alphabetisch sortierte Liste bekannter Tokens/Themen.
    Optional auf Präfix filtern.
    """
    ensure_dirs()
    inv = _read_json(INV_PATH)  # token -> [ids]
    toks = sorted(inv.keys())
    if prefix:
        p = prefix.lower()
        toks = [t for t in toks if t.startswith(p)]
    return toks[:limit]

def get_topic_index(term: str) -> List[str]:
    """
    Gibt alle Block-IDs zurück, in denen das Token/der Begriff 'term' vorkommt.
    Beispiel: get_topic_index("quantencomputer") -> ["BLK_...", ...]
    """
    ensure_dirs()
    inv = _read_json(INV_PATH)
    t = term.lower().strip()
    return list(inv.get(t, []))

def _sentences(text: str) -> List[str]:
    """
    Sehr einfache Satzsegmentierung (punkt/frage/ausrufe). Trim + Filter leerer Sätze.
    """
    parts = re.split(r"[\.!?]\s+", text.strip())
    out = []
    for s in parts:
        s = s.strip()
        if s:
            # Punkt wieder anhängen falls nicht vorhanden, rein kosmetisch
            if not s.endswith((".", "!", "?")):
                s = s + "."
            out.append(s)
    return out

def compare_blocks(ids: List[str]) -> dict:
    """
    Vergleicht mehrere Blöcke auf Überschneidungen und Unterschiede.
    Rückgabe:
    {
      'ids': [...],
      'common_tokens': [...],
      'token_union': [...],
      'pairwise': [
          {'a': 'BLK_x', 'b': 'BLK_y', 'jaccard': 0.42,
           'a_unique_sents': [...], 'b_unique_sents': [...]},
          ...
      ]
    }
    """
    ensure_dirs()
    if not ids or len(ids) < 2:
        return {'ids': ids or [], 'common_tokens': [], 'token_union': [], 'pairwise': []}

    # Lade Inhalte
    docs: Dict[str, dict] = {}
    for bid in ids:
        obj = get_block(bid)
        if obj:
            docs[bid] = obj

    # Token-Mengen pro Block
    token_sets: Dict[str, set] = {}
    for bid, obj in docs.items():
        text = (obj.get("title","") + " " + obj.get("content","") + " " + " ".join(obj.get("tags",[])))
        token_sets[bid] = set(_tok(text))

    # common/union
    all_sets = list(token_sets.values())
    if not all_sets:
        return {'ids': ids, 'common_tokens': [], 'token_union': [], 'pairwise': []}

    common = set.intersection(*all_sets) if len(all_sets) > 1 else set()
    union = set.union(*all_sets)

    # Pairwise Vergleich (Jaccard + einzigartige Sätze)
    pairs = []
    bid_list = list(docs.keys())
    for i in range(len(bid_list)):
        for j in range(i+1, len(bid_list)):
            a, b = bid_list[i], bid_list[j]
            A, B = token_sets[a], token_sets[b]
            inter = len(A & B)
            uni = len(A | B) or 1
            jacc = inter / uni

            a_sents = _sentences(docs[a].get("content",""))
            b_sents = _sentences(docs[b].get("content",""))
            # sehr simpel: Sätze die im anderen Text nicht wörtlich vorkommen
            a_unique = [s for s in a_sents if s not in b_sents]
            b_unique = [s for s in b_sents if s not in a_sents]

            pairs.append({
                'a': a, 'b': b,
                'jaccard': round(float(jacc), 4),
                'a_unique_sents': a_unique[:10],
                'b_unique_sents': b_unique[:10],
            })

    pairs.sort(key=lambda x: x['jaccard'], reverse=True)
    return {
        'ids': bid_list,
        'common_tokens': sorted(common),
        'token_union': sorted(union),
        'pairwise': pairs
    }

def auto_update_block(new_block_id: str, jaccard_threshold: float = 0.25) -> Optional[str]:
    """
    Sucht ähnliche vorhandene Blöcke (über Vektor-Kosinus und Token-Jaccard),
    erstellt – falls sinnvoll – einen 'Update/Refinement'-Block, der die Unterschiede festhält.
    Gibt die ID des neu angelegten Update-Blocks zurück oder None.
    """
    ensure_dirs()
    meta = _read_json(META_PATH)
    vecs = _read_json(VEC_PATH)

    new_obj = get_block(new_block_id)
    if not new_obj:
        return None

    # Kandidaten via Cosine
    new_vec = vecs.get(new_block_id)
    if not isinstance(new_vec, dict):
        # Wenn noch kein Vektor (z. B. frisch hinzugefügt): Rebuild anstoßen und neu laden
        _rebuild_vectors()
        vecs = _read_json(VEC_PATH)
        new_vec = vecs.get(new_block_id, {})

    # Cosine Ranking
    sims: List[Tuple[str, float]] = []
    for bid, vec in vecs.items():
        if bid == new_block_id:
            continue
        sims.append((bid, _cosine(new_vec, vec)))
    sims.sort(key=lambda x: x[1], reverse=True)

    top_candidates = [bid for bid, sc in sims[:8] if sc >= 0.10]  # grob filtern

    if not top_candidates:
        return None

    # Jaccard-Check + Sätze vergleichen
    comp = compare_blocks([new_block_id] + top_candidates)
    best_pair = None
    for p in comp.get('pairwise', []):
        if p['a'] == new_block_id or p['b'] == new_block_id:
            if p['jaccard'] >= jaccard_threshold:
                best_pair = p
                break

    if not best_pair:
        return None

    # Update-Block erstellen (diff-artig)
    other_id = best_pair['b'] if best_pair['a'] == new_block_id else best_pair['a']
    other = get_block(other_id) or {}

    title = f"Refinement zu {other.get('title','(ohne Titel)')}"
    lines = []
    lines.append(f"Verglichen mit Block {other_id} → Jaccard: {best_pair['jaccard']}")
    if best_pair['a'] == new_block_id:
        lines.append("Neue Aspekte (nur im neuen Block):")
        lines.extend(f"- {s}" for s in best_pair['a_unique_sents'])
        lines.append("\nAspekte aus bestehendem Block:")
        lines.extend(f"- {s}" for s in best_pair['b_unique_sents'])
    else:
        lines.append("Neue Aspekte (nur im neuen Block):")
        lines.extend(f"- {s}" for s in best_pair['b_unique_sents'])
        lines.append("\nAspekte aus bestehendem Block:")
        lines.extend(f"- {s}" for s in best_pair['a_unique_sents'])

    content = "\n".join(lines)
    tags = list(set((new_obj.get('tags') or []) + (other.get('tags') or []) + ["refinement", "auto"]))
    new_id = add_block(title=title, content=content, tags=tags, url=new_obj.get("url",""))
    return new_id


# -----------------------
# Wrapper zum Speichern eines Eintrags mit API-Rückgabe
# -----------------------
def save_memory_entry(title: str, content: str, tags: Optional[List[str]] = None, url: Optional[str] = None) -> dict:
    """Persist a knowledge entry into the SQLite knowledge_blocks table.

    - Uses DATABASE_URL from environment (expects sqlite:///...)
    - Maps title -> source (VARCHAR(120)), url -> type (VARCHAR(60))
    - Stores tags as comma-separated string
    - Ensures uniqueness by content hash: if hash exists, returns existing row
    - Returns dict with BLK_<rowid> style id and file name
    """
    try:
        # Resolve database path from DATABASE_URL
        db_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
        db_path = db_url
        try:
            if db_url.startswith("sqlite:///"):
                db_path = db_url[len("sqlite:///") :]
            elif db_url.startswith("sqlite://"):
                db_path = db_url[len("sqlite://") :]
            db_path = os.path.expanduser(db_path)
        except Exception:
            db_path = "db.sqlite3"

        # Prepare fields
        now = int(time.time())
        source_val = (title or "").strip()[:120]
        type_val = (url or "").strip()[:60]
        tags_csv = ",".join([t for t in (tags or []) if t])[:400]
        content_val = (content or "").strip()

        # Compute simple SHA256 over content only per spec
        try:
            hval = hashlib.sha256(content_val.encode("utf-8")).hexdigest()
        except Exception:
            hval = ""

        # Connect and insert or fetch existing
        rowid: Optional[int] = None
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # If a unique index exists on hash, we attempt to find existing first
            try:
                cur.execute("SELECT id FROM knowledge_blocks WHERE hash = ? LIMIT 1", (hval,))
                row = cur.fetchone()
                if row and row["id"] is not None:
                    rowid = int(row["id"])
            except Exception:
                # Table might lack index; continue to insert and rely on constraint if present
                pass

            if rowid is None:
                try:
                    cur.execute(
                        """
                        INSERT INTO knowledge_blocks (ts, source, type, tags, content, hash, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (now, source_val, type_val, tags_csv, content_val, hval, now, now),
                    )
                    rowid = int(cur.lastrowid)
                except sqlite3.IntegrityError:
                    # Likely duplicate hash; fetch existing
                    try:
                        cur.execute("SELECT id FROM knowledge_blocks WHERE hash = ? LIMIT 1", (hval,))
                        row = cur.fetchone()
                        if row and row["id"] is not None:
                            rowid = int(row["id"])
                    except Exception:
                        pass

        if not rowid:
            # Fallback: still return a generated id for consistency
            bid = _gen_id()
            return {"ok": True, "scanned": total, "assigned": assigned, "categories": len(tree.keys())}

        bid = f"BLK_{rowid}"
        return {"id": bid, "file": f"{bid}.json", "url": url or "", "tags": (tags or [])}
    except Exception as e:
        try:
            logger.error("save_memory_entry failed: %s", e)
        except Exception:
            pass
        bid = _gen_id()
        return {"id": bid, "file": f"{bid}.json", "url": url or "", "tags": (tags or [])}


# -----------------------
# Autopilot: model update
# -----------------------
def update_model(mode: str = "prompt", topic: Optional[str] = None) -> dict:
    """Wrapper to call system/memory_model.update_model().
    mode: 'prompt' | 'embeddings' | 'lora'
    """
    try:
        from importlib.machinery import SourceFileLoader as _Loader
        root = ROOT
        mod_path = root / "system" / "memory_model.py"
        if not mod_path.exists():
            return {"ok": False, "error": "memory_model_missing"}
        _mod = _Loader("memory_model", str(mod_path)).load_module()  # type: ignore
        if not hasattr(_mod, "update_model"):
            return {"ok": False, "error": "update_model_missing"}
        res = _mod.update_model(mode=mode, topic=topic)  # type: ignore
        return res if isinstance(res, dict) else {"ok": True, "result": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def rebuild_adressbuch_async(limit: Optional[int] = None) -> dict:
    """Async wrapper to rebuild the address book without blocking the event loop."""
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: rebuild_adressbuch(limit=limit))
    except Exception:
        # Fallback to sync if no loop
        return rebuild_adressbuch(limit=limit)
