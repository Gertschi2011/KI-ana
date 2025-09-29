import os, json, glob
from typing import List
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

CHAIN_DIR = os.getenv("CHAIN_DIR", "./chain")
app = FastAPI(title="Block Viewer")

def list_blocks() -> List[str]:
    os.makedirs(CHAIN_DIR, exist_ok=True)
    return sorted(glob.glob(os.path.join(CHAIN_DIR, "*.json")))

@app.get("/", response_class=HTMLResponse)
def index(q_type: str = Query(default=""), since: str = Query(default="")):
    items = []
    for fp in list_blocks():
        name = os.path.basename(fp)
        try:
            data = json.load(open(fp, "r"))
            if q_type and data.get("type") != q_type:
                continue
            if since:
                ts = data.get("ts") or data.get("payload", {}).get("ts") or 0
                if ts and int(ts) < int(since):
                    continue
            items.append((name, json.dumps(data, indent=2)))
        except Exception as e:
            items.append((name, f'{{"error":"{e}"}}'))
    options = ["", "job_submitted", "job_result", "artifact_indexed", "subki_feedback"]
    opt_html = "".join([f'<option {"selected" if o==q_type else ""}>{o}</option>' for o in options])
    rows = "".join([f"<details><summary>{n}</summary><pre>{c}</pre></details>" for n, c in items])
    return f"""
<!doctype html><html><head><meta charset=\"utf-8\"><title>Blocks</title>
<style>body{{font-family:sans-serif;max-width:1000px;margin:20px auto}} pre{{white-space:pre-wrap}}</style></head>
<body>
<h2>Blockchain Blocks</h2>
<form method=\"get\" action=\"/\">
  <label>Type:</label>
  <select name=\"q_type\">{opt_html}</select>
  <label>Since (epoch ms):</label>
  <input type=\"text\" name=\"since\" value=\"{since}\">
  <button>Filter</button>
</form>
<hr/>{rows if rows else "<p>No blocks</p>"}
</body></html>
"""
