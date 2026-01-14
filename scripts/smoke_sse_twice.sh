#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://ki-ana.at}"
USER="${KIANA_USER:-}"
PASS="${KIANA_PASS:-}"

if [[ -z "${USER}" || -z "${PASS}" ]]; then
  if [[ -t 0 ]]; then
    if [[ -z "${USER}" ]]; then
      read -r -p "KIANA_USER: " USER
    fi
    if [[ -z "${PASS}" ]]; then
      read -r -s -p "KIANA_PASS: " PASS
      echo
    fi
  fi
fi

if [[ -z "${USER}" || -z "${PASS}" ]]; then
  echo "Usage: KIANA_USER=... KIANA_PASS=... [BASE_URL=https://ki-ana.at] $0" >&2
  echo "Tip: run interactively and you'll be prompted." >&2
  exit 2
fi

JAR="${COOKIEJAR:-}"
if [[ -z "${JAR}" ]]; then
  JAR="$(mktemp /tmp/kiana_cookies.XXXXXX)"
  trap 'rm -f "$JAR"' EXIT
fi

login_payload=$(python3 - <<'PY'
import json, os
print(json.dumps({"username": os.environ.get("KIANA_USER",""), "password": os.environ.get("KIANA_PASS",""), "remember": True}))
PY
)

# Ensure python gets creds even when we prompted.
export KIANA_USER="$USER"
export KIANA_PASS="$PASS"

# Login
curl -sS -c "$JAR" -b "$JAR" \
  -H 'Content-Type: application/json' \
  --data "$login_payload" \
  "$BASE_URL/api/login" \
  >/dev/null

# Stream twice: each run must emit at least one SSE data: line within 30s.
for i in 1 2; do
  payload=$(python3 - <<'PY'
import json
print(json.dumps({
  "message": "smoke: stream twice",
  "conv_id": None,
  "style": "balanced",
  "bullets": 5,
  "web_ok": False,
  "autonomy": 0,
  "request_id": "smoke-{}".format(__import__("uuid").uuid4()),
}))
PY
)

  set +e
  out=$(curl -sS -N --max-time 35 -b "$JAR" \
    -H 'Content-Type: application/json' \
    -H 'Accept: text/event-stream' \
    --data "$payload" \
    "$BASE_URL/api/chat/stream" \
    | grep -m1 '^data:' )
  rc=$?
  set -e

  if [[ $rc -ne 0 || -z "${out}" ]]; then
    echo "FAIL: run $i produced no SSE 'data:' line" >&2
    exit 1
  fi

done

echo "OK: got SSE data: line twice"
