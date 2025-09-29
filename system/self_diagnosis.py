from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
INDEX_DIR = BASE_DIR / "memory" / "index"
KG_PATH = INDEX_DIR / "knowledge_graph.json"
GOALS_PATH = INDEX_DIR / "goals.json"


def _load_blocks() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not BLOCKS_DIR.exists():
        return out
    for p in BLOCKS_DIR.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _load_graph() -> Dict[str, Any]:
    if KG_PATH.exists():
        try:
            return json.loads(KG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"nodes": [], "edges": []}


def diagnose_knowledge_gaps() -> List[Dict[str, Any]]:
    """Find isolated nodes (degree 0) and underrepresented tags/topics.
    Returns entries with: {topic, reason, interest, uncertainty}
    """
    blocks = _load_blocks()
    g = _load_graph()
    nodes = {n.get("id"): n for n in g.get("nodes", [])}
    deg: Dict[str, int] = {k: 0 for k in nodes.keys()}
    for e in g.get("edges", []):
        s = e.get("source"); t = e.get("target")
        if s in deg: deg[s] += 1
        if t in deg: deg[t] += 1
    # isolated nodes -> candidate gaps
    isolated_ids = [nid for nid, d in deg.items() if d == 0]
    iso_topics: List[Dict[str, Any]] = []
    for b in blocks:
        if b.get("id") in isolated_ids:
            t = (b.get("topic") or ":misc").strip()
            iso_topics.append({
                "topic": t,
                "reason": "isolated_block",
                "interest": "hoch",
                "uncertainty": "hoch",
            })
    # underrepresented tags
    tag_counts: Dict[str,int] = {}
    for b in blocks:
        for t in (b.get("tags") or []):
            tt = str(t).lower().strip()
            if tt:
                tag_counts[tt] = tag_counts.get(tt, 0) + 1
    low_tags = [k for k, v in tag_counts.items() if v <= 2]
    for tt in low_tags[:10]:
        iso_topics.append({
            "topic": f"tag:{tt}",
            "reason": "underrepresented_tag",
            "interest": "mittel",
            "uncertainty": "mittel",
        })
    # de-duplicate by topic
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in iso_topics:
        if it["topic"] in seen:
            continue
        seen.add(it["topic"])
        out.append(it)
    return out


def propose_learning_goal() -> Dict[str, Any]:
    """Pick a promising gap and propose a learning goal with a simple plan."""
    gaps = diagnose_knowledge_gaps()
    topic = gaps[0]["topic"] if gaps else "Künstliche Ethiksysteme in Multi-Agenten-Umgebungen"
    plan = [
        "Grundlagenrecherche (Wikipedia/Stanford/Arxiv)",
        "Zentrale Begriffe klären und definieren",
        "Pro/Contra und Ethik-Spannungen identifizieren",
        "Anwendungsfälle und Risiken sammeln",
        "Kurze Zusammenfassung als Block ablegen",
    ]
    goal = {
        "id": f"goal_{int(time.time())}",
        "topic": topic,
        "why": "Erkenntnisgewinn und Schließen von Wissenslücken",
        "measure": "# neuer Blöcke zu diesem Thema in den nächsten 48h",
        "mood": "Neugier",
        "plan": plan,
        "created_at": int(time.time()),
        "tags": _goal_tags_from_topic(topic),
    }
    # persist to goals.json (append)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    goals: List[Dict[str, Any]] = []
    if GOALS_PATH.exists():
        try:
            goals = json.loads(GOALS_PATH.read_text(encoding="utf-8")) or []
        except Exception:
            goals = []
    goals.append(goal)
    GOALS_PATH.write_text(json.dumps(goals, ensure_ascii=False, indent=2), encoding="utf-8")
    return goal


def _goal_tags_from_topic(topic: str) -> List[str]:
    t = (topic or "").lower()
    tags: List[str] = []
    for k in ["ethik", "multi-agent", "graph", "lernen", "überwachung", "privatsphäre", "ki", "politik", "ökonomie"]:
        if k in t:
            tags.append(k)
    if topic.startswith("tag:"):
        tags.append(topic.split(":",1)[1])
    return list(sorted(set(tags)))


def current_goals() -> List[Dict[str, Any]]:
    if GOALS_PATH.exists():
        try:
            return json.loads(GOALS_PATH.read_text(encoding="utf-8")) or []
        except Exception:
            return []
    return []
