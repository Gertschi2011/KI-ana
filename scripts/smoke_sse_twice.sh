#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://ki-ana.at}"
USER="${KIANA_USER:-}"
PASS="${KIANA_PASS:-}"

warn() {
  echo "WARN: $1" >&2
}

fail() {
  # Usage: fail "invariant=name" ["k=v ..."] ["snippet_text"]
  local inv="$1"
  local extra="${2:-}"
  local snippet="${3:-}"
  if [[ -n "$extra" ]]; then
    echo "FAIL: ${inv} ${extra}" >&2
  else
    echo "FAIL: ${inv}" >&2
  fi
  if [[ -n "$snippet" ]]; then
    echo "--- response snippet (first 30 lines) ---" >&2
    echo "$snippet" | head -n 30 >&2
  fi
  exit 1
}

if [[ -z "${USER}" || -z "${PASS}" ]]; then
  # Read from /dev/tty so prompting works even if stdin is not a TTY (e.g. VS Code tasks/pipes).
  if [[ -e /dev/tty ]]; then
    exec 3<>/dev/tty || true
    if [[ -z "${USER}" ]]; then
      read -r -p "KIANA_USER: " USER <&3
    fi
    if [[ -z "${PASS}" ]]; then
      for _try in 1 2 3; do
        read -r -s -p "KIANA_PASS: " PASS <&3 || PASS=""
        printf '\n' >&3
        if [[ -n "${PASS}" ]]; then
          break
        fi
        printf '%s\n' "(empty password, try again)" >&3
      done
    fi
    exec 3>&- 3<&- || true
  fi
fi

if [[ -z "${USER}" || -z "${PASS}" ]]; then
  if [[ -z "${PASS}" ]]; then
    echo "FAIL: empty KIANA_PASS (prompt did not capture input)" >&2
  fi
  echo "Usage: KIANA_USER=... KIANA_PASS=... [BASE_URL=https://ki-ana.at] $0" >&2
  echo "Tip: run interactively and you'll be prompted." >&2
  exit 2
fi

# Ensure python/curl get creds even when we prompted.
export KIANA_USER="$USER"
export KIANA_PASS="$PASS"

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

# Login
curl -sS -c "$JAR" -b "$JAR" \
  -H 'Content-Type: application/json' \
  --data "$login_payload" \
  "$BASE_URL/api/login" \
  >/dev/null

# Stream twice: each run must emit at least one SSE data: line within 35s,
# plus exactly one finalize frame carrying conversation_id/conv_id > 0.
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
  output=$(curl -sS -N --max-time 35 -b "$JAR" \
    -H 'Content-Type: application/json' \
    -H 'Accept: text/event-stream' \
    --data "$payload" \
    "$BASE_URL/api/chat/stream")
  rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    fail "invariant=http_status" "expected=200 got=curl_error" "$output"
  fi

  echo "$output" | grep -q '^data:' || {
    fail "invariant=data_missing" "" "$output"
  }

  # Meta is best-effort: warn (but pass) if missing.
  if ! echo "$output" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"meta"'; then
    warn "invariant=meta_missing"
  else
    if ! echo "$output" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"meta".*("conversation_id"|"conv_id")[[:space:]]*:[[:space:]]*[1-9][0-9]*'; then
      warn "invariant=meta_missing_conversation_id"
    fi
  fi

  echo "$output" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"finalize"|"done"[[:space:]]*:[[:space:]]*true[[:space:]]*,[[:space:]]*"schema_version"' || {
    fail "invariant=finalize_missing" "" "$output"
  }

  # Double-finalize proof: exactly one finalize frame per request.
  fin_count=$(echo "$output" | grep -E '"type"[[:space:]]*:[[:space:]]*"finalize"' -c || true)
  if [[ "${fin_count}" != "1" ]]; then
    fail "invariant=finalize_count" "expected=1 got=${fin_count}" "$output"
  fi

  # Finalize must carry a real conversation id.
  echo "$output" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"finalize".*("conversation_id"|"conv_id")[[:space:]]*:[[:space:]]*[1-9][0-9]*' || {
    fail "invariant=finalize_missing_conversation_id" "" "$output"
  }

done

echo "OK: got data: + finalize twice"
