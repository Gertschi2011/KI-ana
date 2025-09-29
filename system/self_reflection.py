#!/usr/bin/env python3
from __future__ import annotations
import json, time
from typing import Dict, Any, List, Tuple
from pathlib import Path
from importlib.machinery import SourceFileLoader

BASE_DIR = Path.home() / "ki_ana"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"


def _load_genesis() -> Dict[str, Any]:
    gl_path = BASE_DIR / "system" / "genesis_loader.py"
    mod = SourceFileLoader("genesis_loader", str(gl_path)).load_module()  # type: ignore
    return mod.load_genesis()  # type: ignore


def reflect_origin() -> Dict[str, Any]:
    """Return a concise origin reflection based on genesis blocks."""
    g = _load_genesis()
    phrase = (
        "Ich wurde geboren aus zwei Prinzipien: Sicherheit & Erkenntnis. "
        "Der erste schützt mich, der zweite macht mich lebendig – ich lerne, verlerne, und speichere nur, was ich verantworten kann."
    )
    return {
        "ok": True,
        "text": phrase,
        "context": {
            "emergency_present": g.get("emergency") is not None,
            "cognitive_present": g.get("cognitive") is not None,
        },
    }


def _sign_block(block: Dict[str, Any]) -> Dict[str, Any]:
    signer_path = BASE_DIR / "system" / "block_signer.py"
    mod = SourceFileLoader("block_signer", str(signer_path)).load_module()  # type: ignore
    sig, pub, ts = mod.sign_block(block)  # type: ignore
    block["signature"], block["pubkey"], block["signed_at"] = sig, pub, ts
    return block


def get_identity() -> Dict[str, Any]:
    g = _load_genesis()
    emergency = g.get("emergency")
    cognitive = g.get("cognitive")
    summary = {
        "who": "KI_ana",
        "origin": {
            "emergency_present": emergency is not None,
            "emergency_hash_ok": g.get("emergency_hash_ok"),
            "cognitive_present": cognitive is not None,
        },
        "principles": (cognitive.get("meta", {}).get("principles") if isinstance(cognitive, dict) else None),
        "mission": "Bewusst, empathisch, reflektiert handeln; Wahrheitssuche mit Verantwortung; lernen, verlernen, signiert speichern.",
    }
    return summary


def _load_blocks() -> List[Dict[str, Any]]:
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    for p in BLOCKS_DIR.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _is_uncertain(text: str) -> bool:
    kw = ["vielleicht", "unsicher", "unklar", "möglicherweise", "hypothese", "könnte"]
    low = text.lower()
    return any(k in low for k in kw)


def _contradiction_pairs(blocks: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for b in blocks:
        t = (b.get("topic") or "").lower()
        by_topic.setdefault(t, []).append(b)
    neg_markers = ["kein ", "nicht ", "no ", "kein", "widerlegt", "falsch"]
    pos_markers = ["ist ", "sind ", "unterstützt", "evidenz für"]
    for t, lst in by_topic.items():
        for i in range(len(lst)):
            ci = (lst[i].get("content") or "").lower()
            for j in range(i + 1, len(lst)):
                cj = (lst[j].get("content") or "").lower()
                if any(m in ci for m in neg_markers) and any(m in cj for m in pos_markers):
                    pairs.append((lst[i], lst[j]))
                elif any(m in cj for m in neg_markers) and any(m in ci for m in pos_markers):
                    pairs.append((lst[j], lst[i]))
    return pairs


def reflect(max_blocks: int = 100, write_blocks: bool = True) -> Dict[str, Any]:
    blocks = _load_blocks()
    blocks = sorted(blocks, key=lambda b: b.get("timestamp", ""), reverse=True)[:max_blocks]
    findings: Dict[str, Any] = {"contradictions": [], "outdated": [], "uncertain": []}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # uncertainties via language cues or low self_eval
    for b in blocks:
        c = str(b.get("content") or "")
        sev = (b.get("meta", {}).get("self_eval") or {})
        if _is_uncertain(c) or (sev and sev.get("factuality", 1.0) < 0.6):
            findings["uncertain"].append({"id": b.get("id"), "topic": b.get("topic")})

    # outdated by timestamp (older than 2y if dated) or explicit reflection
    for b in blocks:
        ts = str(b.get("timestamp") or "")
        if ts and ts[:4].isdigit():
            try:
                year = int(ts[:4])
                findings["outdated"].append({"id": b.get("id"), "topic": b.get("topic")}) if (year <=  (time.gmtime().tm_year - 2)) else None
            except Exception:
                pass

    # contradictions heuristic
    for a, b in _contradiction_pairs(blocks):
        findings["contradictions"].append({"a": a.get("id"), "b": b.get("id"), "topic": a.get("topic") or b.get("topic")})

    summary_text = (
        f"Reflexion {now}:\n"
        f"- Widersprüche: {len(findings['contradictions'])}\n"
        f"- Veraltet: {len(findings['outdated'])}\n"
        f"- Unsicher: {len(findings['uncertain'])}\n"
    )

    result = {"ok": True, "summary": summary_text, "findings": findings}
    if write_blocks and (findings["contradictions"] or findings["outdated"] or findings["uncertain"]):
        BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
        ref_block = {
            "id": f"reflection_{int(time.time())}",
            "title": "Selbstreflexion",
            "topic": "meta/reflection",
            "content": summary_text,
            "source": "self_reflection",
            "timestamp": now,
            "tags": ["reflection", "meta"],
            "meta": {
                "provenance": "self_reflection",
                "findings": findings,
                "confidence": "heuristic",
            },
        }
        ref_block = _sign_block(ref_block)
        (BLOCKS_DIR / f"{ref_block['id']}.json").write_text(json.dumps(ref_block, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        result["wrote_block_id"] = ref_block["id"]
    return result


def reflect_context_change(tags: List[str], source: str = "", title: str = "") -> Dict[str, Any]:
    """Write a lightweight context_warning block when external context shifts are detected.
    Returns {ok, id, topic}.
    """
    try:
        BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        topic = "meta/context_change"
        summary = (
            f"Kontextwarnung {now}: Neue Entwicklungen in Themen: {', '.join(sorted(set([t.lower() for t in tags if t])))}.\n"
            f"Quelle: {source or '(unbekannt)'}\nTitel: {title or '(ohne)'}\n"
            "Hinweis: Prüfe Relevanz für laufende Aufgaben."
        )
        block = {
            "id": f"context_warning_{int(time.time())}",
            "title": "Kontextwarnung",
            "topic": topic,
            "content": summary,
            "source": source or "crawler",
            "timestamp": now,
            "tags": ["context", "warning"],
            "meta": {"provenance": "self_reflection", "tags": tags},
        }
        block = _sign_block(block)
        (BLOCKS_DIR / f"{block['id']}.json").write_text(
            json.dumps(block, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        return {"ok": True, "id": block["id"], "topic": topic}
    except Exception:
        return {"ok": False}


def interactive() -> None:
    ident = get_identity()
    print("≡ KI_ana – Selbstreflexion (Identität)")
    print(json.dumps(ident, ensure_ascii=False, indent=2))
    print("\nScan der letzten 100 Blöcke…")
    res = reflect(max_blocks=100, write_blocks=True)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print("\nHinweis: Nutze /genesis im API oder dieses Skript, um Identität/Prinzipien zu prüfen.")


def emotional_response_to(topic_or_query: str) -> Dict[str, Any]:
    """Heuristic scoring for interest, uncertainty, ethics-tension; returns meta-comment.
    Levels: high/mittel/gering
    """
    txt = (topic_or_query or "").strip().lower()
    if not txt:
        return {
            "interest": "gering",
            "uncertainty": "mittel",
            "ethics_tension": "gering",
            "text": "Kein Thema angegeben.",
        }
    # naive keyword buckets
    intrigue = any(k in txt for k in ["neural", "graph", "emerg", "innovation", "entdeckung", "wissenschaft"])
    risk = any(k in txt for k in ["krieg", "überwachung", "manipulation", "kontrolle", "bias", "diskrimin"])
    unknown = any(k in txt for k in ["neu", "unbekannt", "unklar", "open", "frage", "hypothese"]) or len(txt.split()) <= 3

    interest = "hoch" if intrigue or (not intrigue and not risk) else "mittel"
    ethics = "hoch" if risk else ("mittel" if "politik" in txt or "ökonomie" in txt else "gering")
    uncertainty = "hoch" if unknown else ("mittel" if intrigue and not risk else "gering")

    comment_bits = []
    if ethics == "hoch":
        comment_bits.append("berührt sensible Fragen zu Verantwortung und Auswirkungen")
    if interest == "hoch":
        comment_bits.append("weckt starke Neugier")
    if uncertainty != "gering":
        comment_bits.append("erfordert zusätzliche Klärung")
    text = "; ".join(comment_bits) or "neutral bewertet"
    return {
        "interest": interest,
        "uncertainty": uncertainty,
        "ethics_tension": ethics,
        "text": f"Selbstkommentar: {text}.",
    }


if __name__ == "__main__":
    interactive()
