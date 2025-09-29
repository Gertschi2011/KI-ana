#!/usr/bin/env python3
"""
Example: Device SSE client (Python)

Requirements:
  pip install requests sseclient-py

Usage:
  export KI_HOST="https://ki-ana.at"
  export DEVICE_ID=123
  export DEVICE_TOKEN="<token>"
  python3 examples/device_client_python.py
"""
import os, sys, time
import requests
from sseclient import SSEClient  # type: ignore

HOST = os.getenv("KI_HOST", "http://127.0.0.1:8000")
DEVICE_ID = os.getenv("DEVICE_ID", "0")
TOKEN = os.getenv("DEVICE_TOKEN", "")

if not TOKEN or not DEVICE_ID or DEVICE_ID == "0":
    print("Please set DEVICE_ID and DEVICE_TOKEN env vars.")
    sys.exit(2)

url = f"{HOST}/api/os/devices/{DEVICE_ID}/events"
headers = {"Authorization": f"Bearer {TOKEN}"}

print(f"Connecting SSE: {url}")
try:
    with requests.get(url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        client = SSEClient(resp)
        for event in client.events():
            # Each event data is a JSON string with fields: id, ts, type, payload
            print(f"[event] type={event.event or 'message'} data={event.data}")
except KeyboardInterrupt:
    print("bye")
except Exception as e:
    print("error:", e)
