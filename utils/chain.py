import json
import os
import time
import hashlib
from typing import Dict, Any

CHAIN_DIR = os.getenv("CHAIN_DIR", os.path.join(os.getcwd(), "chain"))


def write_block(event_type: str, payload: Dict[str, Any]) -> str:
    """
    Minimal append-only block writer.
    Returns the filename created.
    """
    os.makedirs(CHAIN_DIR, exist_ok=True)
    ts = int(time.time() * 1000)
    data = {
        "type": event_type,
        "payload": payload,
        "ts": ts,
    }
    raw = json.dumps(data, sort_keys=True).encode()
    bhash = hashlib.sha256(raw).hexdigest()
    fname = f"{ts}_{event_type}_{bhash}.json"
    fpath = os.path.join(CHAIN_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(raw)
    return fpath
