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
print(json.dumps({
  "username": os.environ.get("KIANA_USER", ""),
  "password": os.environ.get("KIANA_PASS", ""),
  "remember": True,
}))
PY
)

# Ensure python gets creds even when we prompted.
export KIANA_USER="$USER"
export KIANA_PASS="$PASS"

# Login (cookie jar)
rm -f "$JAR"
curl --http2 -sS -c "$JAR" -b "$JAR" \
  -H 'Content-Type: application/json' \
  --data "$login_payload" \
  "$BASE_URL/api/login" \
  >/dev/null

# Validate session
set +e
me=$(curl --http2 -sS -b "$JAR" "$BASE_URL/api/me")
rc=$?
set -e
if [[ $rc -ne 0 ]] || ! echo "$me" | grep -q '"auth"[[:space:]]*:[[:space:]]*true'; then
  echo "FAIL: login/session invalid (api/me not auth:true)" >&2
  echo "--- api/me snippet ---" >&2
  echo "$me" | head -n 30 >&2
  exit 1
fi

run_once() {
  local msg="$1"
  local reqid
  reqid="browserlike-$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"

  local payload
  payload=$(MSG="$msg" REQID="$reqid" python3 - <<'PY'
import json, os
print(json.dumps({
  "message": os.environ.get("MSG", ""),
  "conv_id": None,
  "style": "balanced",
  "bullets": 5,
  "web_ok": False,
  "autonomy": 0,
  "request_id": os.environ.get("REQID", ""),
}))
PY
  )

  # Browserlike: force identity encoding, no buffering on client side.
  # Requirements:
  # - at least one '^data:' line
  # - at least one finalize frame
  set +e
  local output
  output=$(curl --http2 --no-buffer -i -N -sS --max-time 30 -b "$JAR" -c "$JAR" \
    -H 'Accept: text/event-stream' \
    -H 'Content-Type: application/json' \
    -H 'Accept-Encoding: identity' \
    -H 'Cache-Control: no-cache' \
    -H 'Pragma: no-cache' \
    --data "$payload" \
    "$BASE_URL/api/chat/stream")
  local rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    echo "FAIL: curl failed for request_id=$reqid" >&2
    return 1
  fi

  echo "$output" | grep -q '^data:' || {
    echo "FAIL: no data: line (request_id=$reqid)" >&2
    echo "--- response snippet (first 30 lines) ---" >&2
    echo "$output" | head -n 30 >&2
    return 1
  }

  echo "$output" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"finalize"|"done"[[:space:]]*:[[:space:]]*true[[:space:]]*,[[:space:]]*"schema_version"' || {
    echo "FAIL: no finalize frame (request_id=$reqid)" >&2
    echo "--- response snippet (first 30 lines) ---" >&2
    echo "$output" | head -n 30 >&2
    return 1
  }

  echo "OK: message='$msg' request_id=$reqid"
}

run_once "Wie geht es dir?"
run_once "Was weißt du über die Erde?"

echo "OK: got data: + finalize twice"
