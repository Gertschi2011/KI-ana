from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from system.self_diagnosis import current_goals, propose_learning_goal  # type: ignore
from netapi.utils.fs import atomic_write_text

router = APIRouter(prefix="/api/goals", tags=["goals"])

BASE_DIR = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"
INDEX_DIR = BASE_DIR / "memory" / "index"
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


def _progress_for_goal(goal: Dict[str, Any], blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    topic = (goal.get("topic") or "").lower()
    tags = [str(t).lower() for t in (goal.get("tags") or [])]
    total = 0
    for b in blocks:
        bt = str(b.get("topic") or "").lower()
        btags = [str(t).lower() for t in (b.get("tags") or [])]
        if topic and topic in bt:
            total += 1
            continue
        if tags and any(t in btags for t in tags):
            total += 1
    return {"blocks": total}


@router.get("")
def list_goals():
    try:
        goals = current_goals()
        blks = _load_blocks()
        items = []
        for g in goals:
            pr = _progress_for_goal(g, blks)
            items.append({**g, "progress": pr})
        return {"ok": True, "items": items}
    except Exception as e:
        raise HTTPException(500, f"goals_error: {e}")


@router.post("/propose")
@router.get("/propose")
def api_propose():
    try:
        g = propose_learning_goal()
        # write a motivation block for visibility
        _write_motivation_block(g)
        return {"ok": True, "goal": g}
    except Exception as e:
        raise HTTPException(500, f"propose_error: {e}")


def _write_motivation_block(goal: Dict[str, Any]) -> None:
    try:
        BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
        content = (
            f"Zielthema: {goal.get('topic')}\n"
            f"Warum wichtig: {goal.get('why')}\n"
            f"Messung: {goal.get('measure')}\n"
            f"Lernmood: {goal.get('mood')}\n"
            f"Plan: \n - " + "\n - ".join(goal.get("plan") or [])
        )
        block = {
            "id": f"motivation_{goal.get('id')}",
            "title": "Motivation: Lernziel",
            "topic": "meta/learning_goal",
            "content": content,
            "tags": ["motivation", "goal"] + list(goal.get("tags") or []),
            "meta": {"provenance": "self_diagnosis", "goal": goal},
        }
        atomic_write_text(
            BLOCKS_DIR / f"{block['id']}.json",
            json.dumps(block, ensure_ascii=False, indent=2, sort_keys=True),
        )
    except Exception:
        pass


@router.get("/ui", response_class=HTMLResponse)
def goals_ui():
    try:
        data = list_goals()  # type: ignore
        items = data.get("items") or []
        rows = []
        for g in items:
            rows.append(
                f"<li><strong>{g.get('topic')}</strong> — Mood: {g.get('mood')} — Blöcke: {g.get('progress',{}).get('blocks',0)}"  # noqa: E501
                f" <br><span class='small'>Warum: {g.get('why')}</span></li>"
            )
        html = """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<link rel='stylesheet' href='/static/styles.css'><title>Lernziele</title>
</head><body class='page'>
<div id='nav' data-src='/static/nav.html'></div>
<main class='container'>
  <section class='card'>
    <h2>🎯 Lernziele</h2>
    <p><a class='btn' href='/api/goals/propose'>Neues Lernziel vorschlagen</a>
       <a class='btn' href='/api/insight/ui/knowledge_graph'>Wissensnetz</a></p>
    <ul>__ROWS__</ul>
    <p><a class='btn' href='/static/papa.html'>Zurück</a></p>
  </section>
</main>
<script defer src='/static/nav.js'></script>
</body></html>
""".replace("__ROWS__", "".join(rows))
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(500, f"goals_ui_error: {e}")
