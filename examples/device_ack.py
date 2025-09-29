#!/usr/bin/env python3
"""
Example: Device ACK (Python)

Requirements:
  pip install requests

Usage:
  export KI_HOST="https://ki-ana.at"
  export DEVICE_ID=123
  export DEVICE_TOKEN="<token>"
  python3 examples/device_ack.py config_update ok

Args:
  type   : e.g. config_update | log_upload_request | media_capture
  status : ok | error | received | processing
"""
import os, sys, json
import requests

HOST = os.getenv("KI_HOST", "http://127.0.0.1:8000")
DEVICE_ID = os.getenv("DEVICE_ID", "0")
TOKEN = os.getenv("DEVICE_TOKEN", "")

if len(sys.argv) < 3:
    print("Usage: DEVICE_ID/DEVICE_TOKEN env +: device_ack.py <type> <status>")
    sys.exit(2)

etype = sys.argv[1]
status = sys.argv[2]

if not DEVICE_ID or DEVICE_ID == "0" or not TOKEN:
    print("Please set DEVICE_ID and DEVICE_TOKEN env vars.")
    sys.exit(2)

url = f"{HOST}/api/os/devices/{DEVICE_ID}/ack"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}
body = {"type": etype, "status": status, "meta": {}}
print("POST", url, "->", body)
r = requests.post(url, headers=headers, data=json.dumps(body))
print(r.status_code, r.text)
