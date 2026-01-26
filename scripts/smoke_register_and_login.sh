#!/usr/bin/env bash

set -euo pipefail
# Avoid bash history expansion surprises in some environments
set +H 2>/dev/null || true

# E2E smoke: register (auto-login) + /api/me + /app/chat.
# Usage:
#   BASE_URL=https://ki-ana.at ./scripts/smoke_register_and_login.sh
#   BASE_URL=http://127.0.0.1:8000 ./scripts/smoke_register_and_login.sh   (NOTE: /app/chat likely not available)

BASE_URL="${BASE_URL:-https://ki-ana.at}"

fail(){
  echo "FAIL: $1" >&2
  shift || true
  if [[ $# -gt 0 ]]; then
    echo "$*" >&2
  fi
  exit 1
}

need(){ command -v "$1" >/dev/null 2>&1 || fail "missing dependency" "$1"; }
need curl
need python3

TS="$(date +%Y%m%d_%H%M%S)"
U="smoke_reg_${TS}_$RANDOM"
E="${U}@example.com"
P="Test1234_${TS}"
JAR="/tmp/${U}_cookies.txt"

TMP_BODY="/tmp/${U}_body.txt"

rm -f "$JAR"

echo "==> register: ${U}"
rm -f "$TMP_BODY"

REG_STATUS=""
for attempt in 1 2 3; do
  set +e
  REG_STATUS="$({
    curl -sS -c "$JAR" -o "$TMP_BODY" -w '%{http_code}' \
      -H 'Content-Type: application/json' \
      -H 'Accept: application/json' \
      -d "{\"name\":\"Smoke Test\",\"username\":\"$U\",\"email\":\"$E\",\"password\":\"$P\"}" \
      "${BASE_URL%/}/api/register"
  } )"
  curl_rc=$?
  set -e
  if [[ $curl_rc -ne 0 ]]; then
    fail "register: curl failed" "curl exit=${curl_rc}"
  fi
  if [[ "$REG_STATUS" == "429" ]]; then
    echo "WARN: register rate-limited (429), retrying..." >&2
    sleep 2
    continue
  fi
  break
done

REG_JSON="$(cat "$TMP_BODY" 2>/dev/null || true)"

echo "register http=${REG_STATUS} bytes=$(wc -c < "$TMP_BODY" 2>/dev/null || echo 0)"

if [[ ! -s "$TMP_BODY" ]]; then
  fail "register: empty body" "HTTP=${REG_STATUS}"
fi

if [[ "$REG_STATUS" != "200" && "$REG_STATUS" != "201" ]]; then
  fail "register: bad status" "Expected 200/201, got ${REG_STATUS}. Body: $(printf '%s' "$REG_JSON" | head -c 300)"
fi

python3 -c 'import json,sys
j=json.loads(sys.stdin.read() or "")
assert j.get("ok") is True, j
print("OK: register ok=true")
' <<<"$REG_JSON" || fail "register: invalid JSON" "Endpoint returned non-JSON"

if ! awk 'BEGIN{ok=0} NF>=7 { if ($6=="sid" || $6=="ki_session") ok=1 } END{ exit ok?0:1 }' "$JAR" 2>/dev/null; then
  fail "register: missing session cookie" "Expected session cookie (ki_session or sid) from /api/register"
fi

echo "==> /api/me auth:true"
rm -f "$TMP_BODY"
set +e
ME_STATUS="$({ curl -sS -b "$JAR" -o "$TMP_BODY" -w '%{http_code}' -H 'Accept: application/json' "${BASE_URL%/}/api/me"; } )"
curl_rc=$?
set -e
if [[ $curl_rc -ne 0 ]]; then
  fail "/api/me: curl failed" "curl exit=${curl_rc}"
fi
ME_JSON="$(cat "$TMP_BODY" 2>/dev/null || true)"
if [[ "$ME_STATUS" != "200" ]]; then
  fail "/api/me: status" "Expected 200, got ${ME_STATUS}. Body: $(printf '%s' "$ME_JSON" | head -c 300)"
fi

python3 -c 'import json,sys
j=json.loads(sys.stdin.read() or "")
assert j.get("auth") is True, j
print("OK: /api/me auth=true")
' <<<"$ME_JSON" || fail "/api/me: invariant" "Expected auth:true"

echo "==> /app/chat 200"
STATUS="$({ curl -sS -o /dev/null -b "$JAR" -w '%{http_code}' "${BASE_URL%/}/app/chat"; } )"

if [[ "$STATUS" != "200" ]]; then
  fail "/app/chat: status" "Expected 200, got ${STATUS}. (Tip: BASE_URL must point to the frontend domain that proxies /api/* to backend.)"
fi

echo "OK: smoke_register_and_login"

rm -f "$TMP_BODY" 2>/dev/null || true