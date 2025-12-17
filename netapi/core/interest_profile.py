from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _clamp(v: float, lo: float, hi: float) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def apply_interest_signal(
    profile: Optional[Dict[str, Any]],
    *,
    signal_type: str,
    domain: Optional[str] = None,
    category: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Apply one implicit-learning signal to an interest_profile meta dict.

    Returns (updated_profile, delta_debug).

    Mapping (Phase 4):
    - followup_request: +0.05 domain +0.05 category; implicit_positive++
    - open_source: +0.08 domain; implicit_positive++
    - dismiss: -0.05 domain; implicit_negative++

    Clamps:
    - domain/category weights in [-0.3, +0.3]
    """

    out: Dict[str, Any] = dict(profile or {})
    dom = (domain or "").strip().lower() or None
    cat = (category or "").strip().lower() or None
    sig = (signal_type or "").strip().lower()

    domain_affinity = out.get("domain_affinity") if isinstance(out.get("domain_affinity"), dict) else {}
    category_weights = out.get("category_weights") if isinstance(out.get("category_weights"), dict) else {}
    signals_count = out.get("signals_count") if isinstance(out.get("signals_count"), dict) else {}

    delta_dom = 0.0
    delta_cat = 0.0
    pos = 0
    neg = 0

    if sig == "followup_request":
        delta_dom = 0.05
        delta_cat = 0.05
        pos = 1
    elif sig == "open_source":
        delta_dom = 0.08
        pos = 1
    elif sig == "dismiss":
        delta_dom = -0.05
        neg = 1

    if dom:
        prev = float(domain_affinity.get(dom) or 0.0)
        domain_affinity[dom] = _clamp(prev + float(delta_dom), -0.3, 0.3)

    if cat:
        prev = float(category_weights.get(cat) or 0.0)
        category_weights[cat] = _clamp(prev + float(delta_cat), -0.3, 0.3)

    signals_count["implicit_positive"] = int(signals_count.get("implicit_positive") or 0) + int(pos)
    signals_count["implicit_negative"] = int(signals_count.get("implicit_negative") or 0) + int(neg)

    out["domain_affinity"] = domain_affinity
    out["category_weights"] = category_weights
    out["signals_count"] = signals_count

    return out, {
        "signal_type": sig,
        "domain": dom,
        "category": cat,
        "delta_domain": float(delta_dom),
        "delta_category": float(delta_cat),
    }
