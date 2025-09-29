from flask import Flask, request, jsonify
from pathlib import Path
from typing import Optional
import os, json
import requests

from subki_agent import SubKIAgent

app = Flask(__name__)

# Minimal local config (env or defaults)
OWNER = os.getenv("OWNER") or (Path("persona").resolve().parts[-1] if (Path("persona").exists()) else "user")
SUBKI_ID = os.getenv("SUBKI_ID", "device_local")
MOTHER_KI_API = os.getenv("MOTHER_KI_API", "http://localhost:8000")
AGENT = SubKIAgent(owner_id=OWNER, subki_id=SUBKI_ID)

@app.get("/")
def ui_home():
    return (
        "<html><head><title>Sub-KI</title></head><body>"
        f"<h2>Sub-KI: {SUBKI_ID} (Owner: {OWNER})</h2>"
        "<ul>"
        "<li><a href='/learned'>Gelernt (pending)</a></li>"
        "<li><a href='/ui/reflect'>Reflect ausführen</a></li>"
        "<li><a href='/ui/sync'>Sync zur Mother-KI</a></li>"
        "<li><a href='/trust'>Trust ansehen (Mother-KI)</a></li>"
        "</ul>"
        "</body></html>"
    )

@app.post("/learn")
def learn():
    data = request.get_json(force=True)
    blk = AGENT.learn(
        title=data.get("title") or "Notiz",
        content=data.get("content") or "",
        tags=data.get("tags") or [],
        source=data.get("source")
    )
    return jsonify({"ok": True, "block": blk})

@app.get("/reflect")
def reflect():
    out = AGENT.reflect_on_pending()
    return jsonify({"ok": True, "reviewed": len(out)})

@app.post("/sync")
def sync():
    # In practice: send to mother-KI via subki_sync
    from subki_sync import send_blocks
    url = request.args.get("mother_url") or "http://localhost:8000/api/subki/sync"
    blocks = AGENT.ready_blocks()
    res = send_blocks(url, blocks, meta={
        "subki_id": AGENT.subki_id,
        "owner": AGENT.owner_id,
        "persona_name": AGENT.persona_name,
        "public_key": AGENT.pubkey_hex(),
        "capabilities": ["reflect"],
        "role_prompt": (
            "Du bist eine Sub-KI von KI_ana. Du lernst lokal von deinem Nutzer. "
            "Du gibst dein Wissen nur weiter, wenn du es geprüft hast und sicher bist, "
            "dass es für alle hilfreich ist. Du handelst stets verantwortungsvoll, neugierig und transparent."
        ),
    })
    return jsonify(res)

@app.get("/learned")
def ui_learned():
    items = []
    for f in sorted(AGENT.pending.glob("*.json")):
        try:
            blk = json.loads(f.read_text())
            items.append({
                "hash": blk.get("hash"),
                "title": blk.get("title"),
                "ready": bool(blk.get("ready_for_sync")),
                "tags": blk.get("tags", []),
            })
        except Exception:
            continue
    rows = "".join(
        f"<li><code>{i['hash'][:8]}</code> — {i['title']} "
        f"[ready={str(i['ready']).lower()}] tags={','.join(i['tags'])}</li>" for i in items
    )
    return f"<html><body><h3>Pending Blocks ({len(items)})</h3><ul>{rows}</ul><p><a href='/'>« Back</a></p></body></html>"

@app.get("/ui/reflect")
def ui_reflect():
    out = AGENT.reflect_on_pending()
    return f"<html><body><h3>Reflect done</h3><p>Reviewed: {len(out)}</p><p><a href='/learned'>Learned</a> · <a href='/'>Home</a></p></body></html>"

@app.get("/ui/sync")
def ui_sync():
    from subki_sync import send_blocks
    url = request.args.get("mother_url") or f"{MOTHER_KI_API}/api/subki/sync"
    blocks = AGENT.ready_blocks()
    try:
        res = send_blocks(url, blocks, meta={
            "subki_id": AGENT.subki_id,
            "owner": AGENT.owner_id,
            "persona_name": AGENT.persona_name,
            "public_key": AGENT.pubkey_hex(),
            "capabilities": ["reflect"],
        })
    except Exception as e:
        res = {"ok": False, "error": str(e)}
    ok = "ok" if res.get("ok") else "fail"
    return f"<html><body><h3>Sync {ok}</h3><pre>{json.dumps(res, ensure_ascii=False, indent=2)}</pre><p><a href='/'>Home</a></p></body></html>"

@app.get("/trust")
def ui_trust():
    try:
        r = requests.get(f"{MOTHER_KI_API}/api/subki/trust", timeout=5)
        data = r.json()
    except Exception as e:
        data = {"ok": False, "error": str(e)}
    return f"<html><body><h3>Trust</h3><pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre><p><a href='/'>Home</a></p></body></html>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055)
