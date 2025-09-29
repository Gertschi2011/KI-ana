import requests
from typing import Dict, Any, List

def send_blocks(url: str, blocks: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "meta": meta,
        "blocks": blocks,
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        return {"ok": r.ok, "status": r.status_code, "data": r.json() if r.content else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}
