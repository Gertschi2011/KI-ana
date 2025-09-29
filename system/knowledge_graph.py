from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
INDEX_DIR = BASE_DIR / "memory" / "index"
KG_PATH = INDEX_DIR / "knowledge_graph.json"


def _load_blocks() -> List[Dict[str, Any]]:
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    for p in BLOCKS_DIR.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _tfidf_vectors(texts: List[str]):
    """Return (matrix-like, vocabulary) using sklearn if available, else a naive TF-IDF.
    For the naive variant, we return (List[Dict[str,float]], vocab:set).
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        vec = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        mat = vec.fit_transform(texts)
        return (mat, vec)
    except Exception:
        # naive TF-IDF
        import re
        docs_tokens: List[List[str]] = []
        df: Dict[str, int] = {}
        for t in texts:
            toks = re.findall(r"[\wäöüÄÖÜß]+", (t or "").lower())
            uniq = set(toks)
            docs_tokens.append(toks)
            for w in uniq:
                df[w] = df.get(w, 0) + 1
        N = max(1, len(texts))
        # compute tf-idf per doc
        vecs: List[Dict[str, float]] = []
        for toks in docs_tokens:
            tf: Dict[str, float] = {}
            for w in toks:
                tf[w] = tf.get(w, 0.0) + 1.0
            for w in list(tf.keys()):
                tf[w] = tf[w] / float(len(toks) or 1)
            tfidf: Dict[str, float] = {}
            for w, v in tf.items():
                idf = math.log((N + 1) / (1 + df.get(w, 1))) + 1.0
                tfidf[w] = v * idf
            vecs.append(tfidf)
        return (vecs, None)


def _cosine(a, b) -> float:
    try:
        # sklearn sparse
        import numpy as np  # type: ignore
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float((a @ b.T).A[0][0] / denom)
    except Exception:
        # dict variant
        if not a or not b:
            return 0.0
        common = set(a.keys()) & set(b.keys())
        num = sum(a[w] * b[w] for w in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return float(num / (na * nb))


def build_similarity_graph(threshold: float = 0.3, max_edges_per_node: int = 20) -> Dict[str, Any]:
    blocks = _load_blocks()
    texts = [((b.get("title") or "") + "\n" + (b.get("content") or "")) for b in blocks]
    mat, vec = _tfidf_vectors(texts)

    nodes = []
    id_by_idx: List[str] = []
    for b in blocks:
        bid = str(b.get("id") or "")
        if not bid:
            continue
        nodes.append({"id": bid, "title": b.get("title") or "(ohne Titel)"})
        id_by_idx.append(bid)

    edges: List[Dict[str, Any]] = []
    n = len(id_by_idx)
    if n <= 1:
        graph = {"nodes": nodes, "edges": []}
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        KG_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "nodes": len(nodes), "edges": 0}

    if hasattr(mat, "toarray"):
        # sklearn path: compute top similarities per node efficiently
        import numpy as np  # type: ignore
        arr = mat.toarray()
        for i in range(n):
            sims = []
            ai = arr[i]
            for j in range(n):
                if i == j:
                    continue
                bj = arr[j]
                denom = (np.linalg.norm(ai) * np.linalg.norm(bj))
                sim = 0.0 if denom == 0 else float(np.dot(ai, bj) / denom)
                if sim >= threshold:
                    sims.append((j, sim))
            sims.sort(key=lambda t: t[1], reverse=True)
            for j, s in sims[:max_edges_per_node]:
                edges.append({"source": id_by_idx[i], "target": id_by_idx[j], "weight": round(float(s), 4)})
    else:
        # naive dict path
        vecs = mat  # type: ignore
        for i in range(n):
            sims: List[Tuple[int, float]] = []
            for j in range(n):
                if i == j:
                    continue
                s = _cosine(vecs[i], vecs[j])
                if s >= threshold:
                    sims.append((j, s))
            sims.sort(key=lambda t: t[1], reverse=True)
            for j, s in sims[:max_edges_per_node]:
                edges.append({"source": id_by_idx[i], "target": id_by_idx[j], "weight": round(float(s), 4)})

    graph = {"nodes": nodes, "edges": edges}
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    KG_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "nodes": len(nodes), "edges": len(edges)}


def get_related_blocks(block_id: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
    try:
        if not KG_PATH.exists():
            build_similarity_graph()
        g = json.loads(KG_PATH.read_text(encoding="utf-8"))
        edges = g.get("edges") or []
        out: List[Dict[str, Any]] = []
        for e in edges:
            if e.get("source") == block_id and float(e.get("weight", 0.0)) >= threshold:
                out.append({"id": e.get("target"), "score": float(e.get("weight", 0.0))})
        out.sort(key=lambda x: x["score"], reverse=True)
        return out
    except Exception:
        return []
