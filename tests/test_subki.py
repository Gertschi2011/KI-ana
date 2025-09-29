#!/usr/bin/env python3
import json
import os
import sys
import time
from urllib.parse import urlencode

import requests

SUBKI_BASE = os.environ.get("SUBKI_BASE", "http://localhost:5055")
MOTHER_API = os.environ.get("MOTHER_KI_API", "http://localhost:8000")


def req(method, url, **kw):
    try:
        r = requests.request(method, url, timeout=8, **kw)
        ctype = r.headers.get("content-type", "")
        if "application/json" in ctype:
            return r.status_code, r.json()
        return r.status_code, r.text
    except Exception as e:
        return -1, {"error": str(e)}


def main():
    print("[1] Learn...")
    code, data = req(
        "POST",
        f"{SUBKI_BASE}/learn",
        json={
            "title": "Testeintrag",
            "content": "Photovoltaik wandelt Sonnenlicht in elektrische Energie um.",
            "tags": ["energie", "wissen", "physik"],
            "source": "unittest",
        },
    )
    print(code, data)

    print("[2] Reflect...")
    code, data = req("GET", f"{SUBKI_BASE}/reflect")
    print(code, data)

    print("[3] Sync → Mother-KI (optional)...")
    q = urlencode({"mother_url": f"{MOTHER_API}/api/subki/sync"})
    code, data = req("POST", f"{SUBKI_BASE}/sync?{q}")
    print(code, data)
    if code != 200 or not (isinstance(data, dict) and data.get("ok")):
        print("[note] Mother-KI scheint nicht erreichbar oder hat abgelehnt – Test fährt fort ohne harten Fehler.")

    print("[4] Trust ansehen (Mother-KI optional)...")
    code, data = req("GET", f"{MOTHER_API}/api/subki/trust")
    print(code, data)

    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
