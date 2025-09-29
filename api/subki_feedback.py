import os, json, time, hashlib
from typing import Dict, Any
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/subki")

CHAIN_DIR = os.getenv("CHAIN_DIR", "./chain")
os.makedirs(CHAIN_DIR, exist_ok=True)

def write_block(event_type: str, payload: Dict[str, Any]):
    data = {"type": event_type, "payload": payload, "ts": int(time.time()*1000)}
    raw = json.dumps(data, sort_keys=True).encode()
    bh = hashlib.sha256(raw).hexdigest()
    open(os.path.join(CHAIN_DIR, f"{data['ts']}_{event_type}_{bh}.json"), "wb").write(raw)

@router.post("/feedback")
def feedback(body: Dict[str, Any] = Body(...)):
    # body: {block_id, status, result_cid}
    write_block("subki_feedback", body)
    return {"ok": True}
