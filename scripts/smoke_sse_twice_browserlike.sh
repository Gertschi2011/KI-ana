#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://ki-ana.at}"
USER="${KIANA_USER:-}"
PASS="${KIANA_PASS:-}"
NON_INTERACTIVE="${KIANA_NON_INTERACTIVE:-}"

warn() {
  # Always one line per warning.
  echo "WARN: $1" >&2
}

fail() {
  # Always one line per failure, plus a snippet.
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
  return 1
}

_http_status_from_response() {
  # Extract the first HTTP status code from a curl -i response.
  # Prints empty string if unknown.
  local resp="$1"
  echo "$resp" | sed -nE 's/^HTTP\/[^ ]+[[:space:]]+([0-9]{3}).*/\1/p' | head -n 1 | tr -d '\r\n'
}

register_and_get_cookiejar() {
  # Register a throwaway user and return a cookie jar path on stdout.
  # Uses /api/register which should set a session cookie.
  local ts u e p jar tmp status curl_rc

  ts="$(date +%Y%m%d_%H%M%S)"
  u="smoke_sse_${ts}_$RANDOM"
  e="${u}@example.com"
  p="Test1234_${ts}"
  jar="$(mktemp /tmp/kiana_sse_reg_cookies.XXXXXX)"
  tmp="$(mktemp /tmp/kiana_sse_reg_body.XXXXXX)"

  # Try a few times in case of 429.
  for _attempt in 1 2 3; do
    set +e
    status="$({
      curl --http2 -sS -c "$jar" -o "$tmp" -w '%{http_code}' \
        -H 'Content-Type: application/json' \
        -H 'Accept: application/json' \
        -d "{\"name\":\"Smoke Test\",\"username\":\"$u\",\"email\":\"$e\",\"password\":\"$p\"}" \
        "${BASE_URL%/}/api/register"
    } )"
    curl_rc=$?
    set -e
    if [[ $curl_rc -ne 0 ]]; then
      rm -f "$jar" "$tmp" 2>/dev/null || true
      echo "FAIL: register curl_error" >&2
      return 1
    fi
    if [[ "$status" == "429" ]]; then
      warn "register rate_limited=429 (retrying)"
      sleep 2
      continue
    fi
    break
  done

  if [[ "$status" != "200" && "$status" != "201" ]]; then
    local body
    body="$(cat "$tmp" 2>/dev/null || true)"
    rm -f "$jar" "$tmp" 2>/dev/null || true
    echo "FAIL: register bad_status expected=200/201 got=$status" >&2
    echo "--- response snippet (first 30 lines) ---" >&2
    echo "$body" | head -n 30 >&2
    return 1
  fi

  # Cleanup body file; keep cookie jar.
  rm -f "$tmp" 2>/dev/null || true
  printf '%s' "$jar"
}

AUTO_REGISTER=0
if [[ -n "${NON_INTERACTIVE}" && ( -z "${USER}" || -z "${PASS}" ) ]]; then
  # In CI/non-interactive environments we cannot prompt.
  # Prefer auto-registering a throwaway user so smoke can run without secrets.
  AUTO_REGISTER=1
fi

if [[ $AUTO_REGISTER -eq 0 && ( -z "${USER}" || -z "${PASS}" ) ]]; then
  # Read from /dev/tty so prompting works even if stdin is not a TTY.
  # Also ensure prompts are visible even when caller captures stdout/stderr.
  # IMPORTANT: only prompt in truly interactive runs. In CI/non-interactive runs,
  # prompting will hang and is not answerable.
  if [[ -t 0 && -t 1 && -e /dev/tty && -r /dev/tty && -w /dev/tty ]]; then
    if ! exec 3<>/dev/tty; then
      # No controlling TTY (non-interactive). Skip prompting.
      true
    else
    if [[ -z "${USER}" ]]; then
      printf '%s' "KIANA_USER: " >&3
      if ! IFS= read -r -t 30 USER <&3; then
        USER=""
        printf '%s\n' "(timed out waiting for KIANA_USER)" >&3
      fi
    fi
    if [[ -z "${PASS}" ]]; then
      for _try in 1 2 3; do
        printf '%s' "KIANA_PASS: " >&3
        # Hide input on tty while reading password.
        stty -echo <&3 2>/dev/null || true
        if ! IFS= read -r -t 30 PASS <&3; then
          PASS=""
        fi
        stty echo <&3 2>/dev/null || true
        printf '\n' >&3
        if [[ -n "${PASS}" ]]; then
          break
        fi
        if [[ -z "${PASS}" ]]; then
          printf '%s\n' "(timed out waiting for KIANA_PASS)" >&3
          break
        fi
        printf '%s\n' "(empty password, try again)" >&3
      done
    fi
    exec 3>&- 3<&- || true
    fi
  fi
fi

JAR="${COOKIEJAR:-}"
if [[ -z "${JAR}" ]]; then
  JAR="$(mktemp /tmp/kiana_cookies.XXXXXX)"
  trap 'rm -f "$JAR"' EXIT
fi

if [[ $AUTO_REGISTER -eq 1 ]]; then
  log_jar="$(register_and_get_cookiejar || true)"
  if [[ -z "$log_jar" ]]; then
    echo "FAIL: missing KIANA_USER/KIANA_PASS and auto-register failed" >&2
    echo "Tip: set KIANA_USER/KIANA_PASS, or ensure /api/register is enabled." >&2
    exit 2
  fi
  rm -f "$JAR" 2>/dev/null || true
  mv "$log_jar" "$JAR"
else
  if [[ -z "${USER}" || -z "${PASS}" ]]; then
    if [[ -z "${PASS}" ]]; then
      echo "FAIL: missing KIANA_PASS (set KIANA_USER/KIANA_PASS or run interactively)" >&2
    fi
    echo "Usage: KIANA_USER=... KIANA_PASS=... [BASE_URL=https://ki-ana.at] $0" >&2
    echo "Tip: run interactively and you'll be prompted." >&2
    exit 2
  fi

  # Ensure python/curl get creds even when we prompted.
  export KIANA_USER="$USER"
  export KIANA_PASS="$PASS"

  login_payload=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "username": os.environ.get("KIANA_USER", ""),
  "password": os.environ.get("KIANA_PASS", ""),
  "remember": True,
}))
PY
  )

  # Login (cookie jar)
  rm -f "$JAR"
  set +e
  login_resp=$(curl --http2 -sS -i -c "$JAR" -b "$JAR" \
    -H 'Content-Type: application/json' \
    --data "$login_payload" \
    "$BASE_URL/api/login")
  login_rc=$?
  set -e
  if [[ $login_rc -ne 0 ]]; then
    fail "invariant=http_status" "expected=200 got=curl_error" "$login_resp"
    exit 1
  fi
  login_status=$(_http_status_from_response "$login_resp")
  if [[ -n "$login_status" && "$login_status" != "200" ]]; then
    fail "invariant=http_status" "expected=200 got=$login_status" "$login_resp"
    exit 1
  fi
fi

# Validate session (shared path)
set +e
me=$(curl --http2 -sS -b "$JAR" "$BASE_URL/api/me")
rc=$?
set -e
if [[ $rc -ne 0 ]] || ! echo "$me" | grep -q '"auth"[[:space:]]*:[[:space:]]*true'; then
  fail "invariant=session_invalid" "expected=auth:true" "$me"
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
    fail "invariant=http_status" "expected=200 got=curl_error" "$output"
    return 1
  fi

  # HTTP status must be 200 (we used -i)
  status=$(_http_status_from_response "$output")
  if [[ -n "$status" && "$status" != "200" ]]; then
    fail "invariant=http_status" "expected=200 got=$status" "$output"
    return 1
  fi

  echo "$output" | grep -q '^data:' || {
    fail "invariant=data_missing" "" "$output"
    return 1
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
    return 1
  }

  # Double-finalize proof: exactly one finalize frame per request.
  local fin_count
  fin_count=$(echo "$output" | grep -E '"type"[[:space:]]*:[[:space:]]*"finalize"' -c || true)
  if [[ "${fin_count}" != "1" ]]; then
    fail "invariant=finalize_count" "expected=1 got=${fin_count}" "$output"
    return 1
  fi

  # Finalize must carry a real conversation id.
  echo "$output" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"finalize".*("conversation_id"|"conv_id")[[:space:]]*:[[:space:]]*[1-9][0-9]*' || {
    fail "invariant=finalize_missing_conversation_id" "" "$output"
    return 1
  }

  echo "OK: message='$msg' request_id=$reqid"
}

run_once "Wie geht es dir?"
run_once "Was weißt du über die Erde?"

echo "OK: got data: + finalize twice"
