# E2E Enablement — Staging Evidence

**Timestamp (UTC):** 2026-01-07T06:52:46Z  
**RUN_ID:** `20260107_065246`  
**Base URL:** `http://localhost:28000`  
**Backend SHA:** `e95ebca07` (also returned by `/api/v2/chat/ping`)

## 1) Redeploy staging

```bash
cd /home/kiana/ki_ana
bash infra/scripts/deploy_staging.sh
```

## 2) Evidence run (copy/paste)

This flow is deterministic and does **not** require DB manipulation. It uses a unique `RUN_ID` so the user/email cannot collide.

```bash
set +H
BASE_URL='http://localhost:28000'
RUN_ID="$(date -u +%Y%m%d_%H%M%S)"
EMAIL="e2e_${RUN_ID}@example.com"
USERNAME="e2e_${RUN_ID}"
PASSWORD='Passw0rd!x'
COOKIE_JAR="/tmp/e2e_cookies_${RUN_ID}.txt"

# (A) chat-v2 ping
curl -sS -D "/tmp/e2e_enablement_ping_${RUN_ID}.http" \
  -o "/tmp/e2e_enablement_ping_${RUN_ID}.json" \
  "$BASE_URL/api/v2/chat/ping"

# (B) register (TEST_MODE returns a verification token on staging)
curl -sS -D "/tmp/e2e_enablement_register_${RUN_ID}.http" \
  -o "/tmp/e2e_enablement_register_${RUN_ID}.json" \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/api/register" \
  -d "{\"username\":\"$USERNAME\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"

TOKEN=$(jq -r '.email_verification_token' < "/tmp/e2e_enablement_register_${RUN_ID}.json")

# (C) verify email
curl -sS -D "/tmp/e2e_enablement_verify_${RUN_ID}.http" \
  -o "/tmp/e2e_enablement_verify_${RUN_ID}.json" \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/api/verify-email" \
  -d "{\"token\":\"$TOKEN\"}"

# (D) login (writes cookie jar)
rm -f "$COOKIE_JAR"
curl -sS -D "/tmp/e2e_enablement_login_${RUN_ID}.http" \
  -o "/tmp/e2e_enablement_login_${RUN_ID}.json" \
  -c "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/api/login" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\",\"remember\":false}"

# (E) account (cookie auth)
curl -sS -D "/tmp/e2e_enablement_account_${RUN_ID}.http" \
  -o "/tmp/e2e_enablement_account_${RUN_ID}.json" \
  -b "$COOKIE_JAR" \
  "$BASE_URL/api/account"

# (F) v2 chat (cookie auth + stable contract)
curl -sS -D "/tmp/e2e_enablement_v2chat_${RUN_ID}.http" \
  -o "/tmp/e2e_enablement_v2chat_${RUN_ID}.json" \
  -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/api/v2/chat" \
  -d '{"message":"ping","persona":"helpful","lang":"en"}'

# (G) plans
curl -sS -D "/tmp/e2e_enablement_plans_${RUN_ID}.http" \
  -o "/tmp/e2e_enablement_plans_${RUN_ID}.json" \
  "$BASE_URL/api/plans"

# Assertions (required contract)
jq -e '.ok==true and .module=="chat-v2"' "/tmp/e2e_enablement_ping_${RUN_ID}.json" > /dev/null
jq -e '(.reply|type)=="string" and ((.meta|type)=="object") and ((.sources|type)=="array") and ((.trace|type)=="array")' "/tmp/e2e_enablement_v2chat_${RUN_ID}.json" > /dev/null

echo ASSERTS_OK
```

## 3) Outputs (short)

### Ping
From `/tmp/e2e_enablement_ping_20260107_065246.json`:

```json
{"ok":true,"version":"2.0","module":"chat-v2","sha":"e95ebca07","build":"e95ebca07"}
```

### Register
From `/tmp/e2e_enablement_register_20260107_065246.json` (token redacted):

```json
{"ok":true,"user":{"id":11,"username":"e2e_20260107_065246","role":"family","plan":"free","plan_until":0},"email_verification_token":"<redacted>"}
```

### Verify email
From `/tmp/e2e_enablement_verify_20260107_065246.json`:

```json
{"ok":true,"user_id":11}
```

### Account
From `/tmp/e2e_enablement_account_20260107_065246.json`:

```json
{"auth":true,"user":{"id":11,"username":"e2e_20260107_065246","role":"family","plan":"free"}}
```

### v2 chat (contract)
From `/tmp/e2e_enablement_v2chat_20260107_065246.json` (reply may vary; keys are stable):

```json
{"ok":true,"reply":"","meta":{},"sources":[],"trace":[]}
```

### Plans
From `/tmp/e2e_enablement_plans_20260107_065246.json` (truncated):

```json
{"items":[{"id":"submind_monthly"},{"id":"submind_yearly"}]}
```
