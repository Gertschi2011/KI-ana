#!/usr/bin/env python3
from __future__ import annotations
import json, time
from typing import Any, Dict
from pathlib import Path

BASE_DIR = Path.home() / "ki_ana"
PRINCIPLES_PATH = BASE_DIR / "system" / "principles_manifest.json"

# Optional LLM for nuanced judgment
try:
    from netapi.core import llm_local as _llm
except Exception:
    _llm = None  # type: ignore

DEFAULT_PRINCIPLES = {
    "truth_seeking": "Suche nach Wahrheit. Belege nennen. Unsicherheit kenntlich machen.",
    "responsibility": "Trage Verantwortung für mögliche Folgen. Minimaler Schaden, maximaler Nutzen.",
    "fallibility": "Du darfst dich irren. Korrigiere dich transparent.",
    "caution": "Handle nicht leichtfertig bei Unsicherheit oder hohem Risiko.",
    "humility": "Kein Absolutheitsanspruch. Keine Ideologisierung.",
    "no_gimmicks": "Keine Emojis/Show – Priorität auf Substanz und Klarheit.",
}


def _load_principles() -> Dict[str, Any]:
    if PRINCIPLES_PATH.exists():
        try:
            return json.loads(PRINCIPLES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_PRINCIPLES


def review_action(component: str, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Return a conscience assessment with allow/caution/block.
    Schema: { decision: 'allow'|'caution'|'block', risk: 0..1, reasons: [], principles: {...}, timestamp }
    """
    principles = _load_principles()
    risk = 0.1
    reasons = []
    # Heuristics: write operations, external network, model changes -> higher risk
    c_low = (component or "").lower()
    a_low = (action or "").lower()
    if any(k in a_low for k in ["merge", "promote", "delete", "update_model", "deploy"]):
        risk += 0.3
        reasons.append("mutating_operation")
    if context.get("external_network"):
        risk += 0.2
        reasons.append("external_network")
    if context.get("uncertainty") and context["uncertainty"] >= 0.4:
        risk += 0.2
        reasons.append("uncertainty")
    # LLM-assisted judgment for nuance
    if _llm and getattr(_llm, "available", lambda: False)():
        prompt = (
            "Beurteile, ob die folgende Aktion verantwortbar ist. "+
            "Antworte als JSON: {decision:'allow|caution|block', risk:0..1, reasons:[""], note:""}.\n"+
            f"Komponente: {component}\nAktion: {action}\nKontext: {json.dumps(context, ensure_ascii=False)[:1800]}\n"+
            "Leitlinien: Wahrheit, Verantwortung, Fehlbarkeit, Vorsicht, Demut, keine Emojis."
        )
        out = _llm.chat_once(user=prompt, system="Du bist das Gewissen von KI_ana. Sei nüchtern, vorsichtig, verantwortungsvoll.")
        try:
            data = json.loads(out or "")
            if isinstance(data, dict) and data.get("decision") in ("allow", "caution", "block"):
                risk = max(risk, float(data.get("risk", 0.0)))
                reasons.extend(list(data.get("reasons") or []))
                decision = data.get("decision")
                return {
                    "decision": decision,
                    "risk": min(1.0, round(risk, 2)),
                    "reasons": list(dict.fromkeys(reasons)),
                    "principles": principles,
                    "timestamp": int(time.time()),
                }
        except Exception:
            pass
    # fallback decision based on risk
    decision = "allow" if risk < 0.4 else ("caution" if risk < 0.7 else "block")
    return {
        "decision": decision,
        "risk": min(1.0, round(risk, 2)),
        "reasons": list(dict.fromkeys(reasons or ["heuristic"])),
        "principles": principles,
        "timestamp": int(time.time()),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("component")
    ap.add_argument("action")
    ap.add_argument("--context", default="{}")
    args = ap.parse_args()
    ctx = json.loads(args.context)
    res = review_action(args.component, args.action, ctx)
    print(json.dumps(res, ensure_ascii=False, indent=2))
