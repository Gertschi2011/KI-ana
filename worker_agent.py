import os
import time
import json
import base64
import requests
import hashlib
import threading
import datetime as dt
from typing import Dict, Any
from dotenv import load_dotenv
from nacl.signing import VerifyKey
from nacl.encoding import Base64Encoder
from nacl.exceptions import BadSignatureError

# Load environment variables from .env file (MVP convenience)
load_dotenv()

COORD_URL = os.getenv("COORD_URL", "http://127.0.0.1:8000")
WORKER_ID = os.getenv("WORKER_ID", "worker-local-1")
JWT = os.getenv("JWT", None)


def get_server_info() -> Dict[str, Any]:
    r = requests.get(f"{COORD_URL}/api/nodes/hello", timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_next_job() -> Dict[str, Any] | None:
    r = requests.get(f"{COORD_URL}/api/jobs/next", timeout=10)
    if r.status_code == 204:
        return None
    r.raise_for_status()
    return r.json()


def verify_ticket(ticket: Dict[str, Any], signature_b64: str, server_pubkey_b64: str) -> bool:
    if not signature_b64 or not server_pubkey_b64:
        # No signature enforcement in MVP
        return True
    ticket_bytes = json.dumps(ticket, separators=(",", ":"), sort_keys=True).encode()
    sig = base64.b64decode(signature_b64)
    vk = VerifyKey(server_pubkey_b64.encode(), encoder=Base64Encoder)
    try:
        vk.verify(ticket_bytes, sig)
        return True
    except BadSignatureError:
        return False


def send_ping():
    try:
        payload = {
            "worker_id": WORKER_ID,
            "caps": {"os": os.uname().sysname, "pid": os.getpid()},
            "version": "0.1",
        }
        headers = {}
        if JWT:
            headers["Authorization"] = f"Bearer {JWT}"
        requests.post(f"{COORD_URL}/api/nodes/ping", json=payload, headers=headers, timeout=10)
    except Exception as e:
        print("ping error:", e)


def compute(job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Dummy compute implementations
    if job_type == "dummy_sum":
        nums = payload.get("numbers", [])
        s = sum(nums)
        return {"sum": s, "count": len(nums)}
    elif job_type == "dummy_upper":
        text = payload.get("text", "")
        return {"upper": text.upper()}
    # Fallback: echo
    return {"echo": payload}


def post_result(job_id: str, output: Dict[str, Any], result_cid: str | None = None):
    body = {
        "status": "ok",
        "output": output,
        "finished_at": time.time(),
        "worker_id": WORKER_ID,
        "result_cid": result_cid,
    }
    r = requests.post(f"{COORD_URL}/api/jobs/{job_id}/result", json=body, timeout=10)
    r.raise_for_status()
    return r.json()


def main_once():
    _ = get_server_info()  # health check

    job_pack = fetch_next_job()
    if not job_pack:
        print("No job available (204).")
        return

    ticket = job_pack["ticket"]
    signature = job_pack.get("signature", "")

    if not verify_ticket(ticket, signature, ""):
        print("Invalid job ticket signature. Dropping job.")
        return

    # Prefer artifact_url if provided; verify SHA-256 equals CID
    payload: Dict[str, Any] = {}
    artifact_url = job_pack.get("artifact_url")
    if artifact_url:
        resp = requests.get(artifact_url, timeout=60)
        resp.raise_for_status()
        blob = resp.content
        cid_hex = hashlib.sha256(blob).hexdigest()
        if cid_hex != ticket["cid"]:
            raise RuntimeError("CID mismatch – downloaded artifact hash does not match ticket CID")
        # assume JSON payload for demo
        payload = json.loads(blob)
    else:
        # Fallback: inline payload
        payload = job_pack.get("payload", {})

    output = compute(ticket["type"], payload)
    # Optionally compute a result CID from serialized output
    out_bytes = json.dumps(output, sort_keys=True).encode()
    result_cid = hashlib.sha256(out_bytes).hexdigest()
    res = post_result(ticket["id"], output, result_cid=result_cid)
    print("Result accepted:", res)


if __name__ == "__main__":
    # heartbeat background thread
    def heartbeat_loop():
        while True:
            send_ping()
            time.sleep(30)

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    # Single-shot execution for simplicity
    main_once()
