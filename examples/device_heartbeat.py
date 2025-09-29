#!/usr/bin/env python3
"""
Example: Device Heartbeat (Python)

Requirements:
  pip install requests

Usage:
  export KI_HOST="https://ki-ana.at"
  export DEVICE_ID=123
  export DEVICE_TOKEN="<token>"
  python3 examples/device_heartbeat.py
"""
import os, sys, json
import requests

HOST = os.getenv("KI_HOST", "http://127.0.0.1:8000")
DEVICE_ID = os.getenv("DEVICE_ID", "0")
TOKEN = os.getenv("DEVICE_TOKEN", "")
STATUS = os.getenv("DEVICE_STATUS", "ok")

if not DEVICE_ID or DEVICE_ID == "0":
    print("Please set DEVICE_ID.")
    sys.exit(2)

url = f"{HOST}/api/os/devices/heartbeat"
headers = {"Content-Type": "application/json"}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"

body = {"id": int(DEVICE_ID), "status": STATUS}
print("POST", url, "->", body)
r = requests.post(url, headers=headers, data=json.dumps(body))
print(r.status_code, r.text)
