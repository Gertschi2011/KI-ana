from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from system.knowledge_graph import build_similarity_graph, get_related_blocks  # type: ignore
from system.question_generator import generate_questions_from_blocks  # type: ignore
from system import self_reflection  # type: ignore

router = APIRouter(prefix="/api/insight", tags=["insight"])

BASE_DIR = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
KG_PATH = BASE_DIR / "memory" / "index" / "knowledge_graph.json"


@router.get("/build_kg")
def api_build_kg():
    try:
        res = build_similarity_graph()
        return res
    except Exception as e:
        raise HTTPException(500, f"kg_error: {e}")


@router.get("/graph")
def api_graph():
    try:
        if not KG_PATH.exists():
            build_similarity_graph()
        return json.loads(KG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"graph_error: {e}")


@router.get("/related/{block_id}")
def api_related(block_id: str, threshold: float = 0.5):
    try:
        return {"ok": True, "items": get_related_blocks(block_id, threshold=threshold)}
    except Exception as e:
        raise HTTPException(500, f"related_error: {e}")


@router.get("/ui/knowledge_graph", response_class=HTMLResponse)
def ui_knowledge_graph():
    # Simple vis-network view fetching /api/insight/graph
    html = """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<link rel='stylesheet' href='/static/styles.css'><title>Wissensnetz</title>
<script src='https://unpkg.com/vis-network/standalone/umd/vis-network.min.js'></script>
</head><body class='page'>
<div id='nav' data-src='/static/nav.html'></div>
<main class='container'>
  <section class='card'>
    <h2>📚 Wissensnetz</h2>
    <div id='graph' style='height:70vh;border:1px solid #ddd;border-radius:8px'></div>
    <p class='small'>Knoten sind Blöcke, Kanten verbinden ähnliche Inhalte. Doppelklick auf einen Knoten zeigt verbundene IDs.</p>
    <p><a class='btn' href='/static/papa.html'>Zurück</a></p>
  </section>
</main>
<script defer src='/static/nav.js'></script>
<script>
(async function(){
  const res = await fetch('/api/insight/graph');
  const g = await res.json();
  const nodes = new vis.DataSet((g.nodes||[]).map(n=>({id:n.id, label:n.title||n.id})));
  const edges = new vis.DataSet((g.edges||[]).map(e=>({from:e.source, to:e.target, value:e.weight})));
  const container = document.getElementById('graph');
  const network = new vis.Network(container, {nodes, edges}, {
    edges: { color: { color:'#999' } }, physics: { stabilization: true }
  });
  network.on('doubleClick', params => {
    if(params && params.nodes && params.nodes.length){
      const id = params.nodes[0];
      alert('Block: '+id+'\nVerwandte: '+(g.edges||[]).filter(e=>e.source===id).map(e=>e.target).slice(0,10).join(', '));
    }
  });
})();
</script>
</body></html>
"""
    return HTMLResponse(content=html)


@router.get("/ui/questions", response_class=HTMLResponse)
def ui_questions(num: int = 5):
    try:
        items = generate_questions_from_blocks(num=num)
        rows = ''.join([f"<li><strong>{(i.get('title') or i.get('block_id') or '')}</strong>: {i.get('question')}</li>" for i in items])
        html = f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<link rel='stylesheet' href='/static/styles.css'><title>Intelligente Fragen</title>
</head><body class='page'>
<div id='nav' data-src='/static/nav.html'></div>
<main class='container'>
  <section class='card'>
    <h2>📌 Fragen aus dem Gedächtnis</h2>
    <ul>{rows}</ul>
    <p><a class='btn' href='/api/insight/ui/questions?num=5'>Neu generieren</a>
       <a class='btn' href='/static/papa.html'>Zurück</a></p>
  </section>
</main>
<script defer src='/static/nav.js'></script>
</body></html>
"""
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(500, f"questions_error: {e}")


@router.get("/ui/self_comment", response_class=HTMLResponse)
def ui_self_comment(q: str = Query(default="", description="Thema oder Frage")):
    try:
        txt = q.strip()
        resp = self_reflection.emotional_response_to(txt) if txt else {"text": "Gib ein Thema ein und klicke Bewerten."}
        html = f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<link rel='stylesheet' href='/static/styles.css'><title>Selbstkommentar</title>
</head><body class='page'>
<div id='nav' data-src='/static/nav.html'></div>
<main class='container'>
  <section class='card'>
    <h2>🧭 Selbstkommentar</h2>
    <form method='get' action='/api/insight/ui/self_comment'>
      <input type='text' name='q' placeholder='Thema oder Frage' style='width:70%' value='{json.dumps(txt)[1:-1]}'/>
      <button class='btn' type='submit'>Bewerten</button>
    </form>
    <pre style='white-space:pre-wrap'>{json.dumps(resp, ensure_ascii=False, indent=2)}</pre>
    <p><a class='btn' href='/static/papa.html'>Zurück</a></p>
  </section>
</main>
<script defer src='/static/nav.js'></script>
</body></html>
"""
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(500, f"self_comment_error: {e}")
