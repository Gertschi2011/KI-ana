# M3.2 Rollback + Migration Drill (Staging)

Date: 2026-01-05

## Scope

- Environment: local staging stack via Docker Compose
- Compose project name: `ki_ana_staging`
- Backend: http://localhost:28000
- Frontend: http://localhost:23000
- Database: Postgres (container `ki_ana_staging-postgres-1`, host port 25432)

## Version markers

- Version A (git): `fd60d858ca08` (HEAD at time of drill)
- Version B (git): **TBD**

Note: The workspace currently contains uncommitted changes (dirty tree). For a fully deterministic rollback drill using commits A/B, we should either (a) commit the staging/deploy artifacts and fixes, or (b) stash/clean the tree and deploy from checked-out commits.

## Preconditions

- Staging stack runs under project `ki_ana_staging` and publishes expected ports.

Commands:

```bash
cd /home/kiana/ki_ana

docker compose -p ki_ana_staging -f docker-compose.staging.yml up -d --build

docker compose -p ki_ana_staging -f docker-compose.staging.yml ps
```

Expected:
- backend publishes `0.0.0.0:28000->8000/tcp`
- frontend publishes `0.0.0.0:23000->3000/tcp`

## Evidence (Version A)

### 1) Ping

```bash
curl -fsS http://localhost:28000/api/v2/chat/ping
```

Output:

```json
{"ok":true,"version":"2.0","module":"chat-v2"}
```

### 2) Metrics (head)

```bash
curl -fsS http://localhost:28000/api/metrics | head -n 20
```

Output (sample):

```text
auth_2fa_challenge_total 0
auth_2fa_failed_total 0
auth_login_failed_total 0
auth_login_success_total 0
billing_reconcile_runs_total{result="error"} 0
billing_reconcile_runs_total{result="success"} 0
billing_webhook_received_total{type="unknown"} 0
http_request_duration_seconds_bucket{le="+Inf",method="GET",route="/api/v2/chat/ping"} 1
http_request_duration_seconds_bucket{le="0.005",method="GET",route="/api/v2/chat/ping"} 1
http_request_duration_seconds_bucket{le="0.01",method="GET",route="/api/v2/chat/ping"} 1
...
```

### 3) Ops summary (env)

This endpoint is admin-only; the drill bootstraps a local staging admin user.

#### 3a) Create/update bootstrap admin user in Postgres

Generate bcrypt hash (inside backend container):

```bash
cd /home/kiana/ki_ana

docker compose -p ki_ana_staging -f docker-compose.staging.yml exec -T backend \
  python -c "from netapi.modules.auth.crypto import hash_pw; print(hash_pw('***REDACTED***'))"
```

Insert/update user in Postgres (replace `$HASH` with the printed bcrypt hash):

```bash
HASH='***REDACTED***'

docker compose -p ki_ana_staging -f docker-compose.staging.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "\
INSERT INTO users (
  username,email,password_hash,role,tier,is_papa,daily_quota,quota_reset_at,
  plan,plan_until,email_verified,account_status,subscription_status,subscription_grace_until,
  consent_learning,delete_requested_at,delete_scheduled_for,deleted_at,failed_login_count,locked_until,
  created_at,updated_at
)
VALUES (
  'staging_admin','admin@staging.local','${HASH}','admin','creator',FALSE,20,0,
  'free',0,1,'active','active',0,
  'ask',0,0,0,0,0,
  now(),extract(epoch from now())::int
)
ON CONFLICT (username) DO UPDATE SET
  email=excluded.email,
  password_hash=excluded.password_hash,
  role=excluded.role,
  email_verified=excluded.email_verified,
  account_status=excluded.account_status,
  subscription_status=excluded.subscription_status,
  updated_at=excluded.updated_at;
""
```

#### 3b) Login + fetch ops summary

```bash
tmpc=$(mktemp)

curl -sS -c "$tmpc" \
  -X POST http://localhost:28000/api/login \
  -H 'content-type: application/json' \
  -d '{"username":"staging_admin","password":"***REDACTED***"}' >/dev/null

curl -sS -b "$tmpc" http://localhost:28000/api/ops/summary | python3 -m json.tool

rm -f "$tmpc"
```

Output (sample):

```json
{
  "uptime_seconds": 295,
  "started_at": 1767624825,
  "last_5m": {
    "req_count": 3,
    "five_xx_count": 0,
    "p95_latency_ms": 216.82765427976847,
    "requests": 3,
    "p95_ms": 216.82765427976847
  },
  "limits_exceeded_top": [],
  "billing": {
    "webhook_failures_last_1h": 0,
    "last_reconcile": {
      "ts": 0,
      "result": "unknown",
      "count": 0
    }
  },
  "top_limits_exceeded": [],
  "billing_webhook_failures_last_1h": 0,
  "last_reconcile": {
    "ts": 0,
    "result": "unknown",
    "count": 0
  },
  "ok": true,
  "env": "staging"
}
```

## Rollback drill steps (pending)

Once commits A/B are defined and the working tree is clean enough to deploy deterministically from git:

1. Deploy Version A (`bash infra/scripts/deploy_staging.sh`)
2. Capture evidence (ping, metrics head, ops summary env)
3. Deploy Version B (same deploy script)
4. Roll back to Version A (git checkout A + redeploy)
5. Re-deploy Version B

## Status

- Ping: ✅ (public, returns expected JSON)
- Metrics head: ✅ (curl returns Prometheus text by default)
- Ops summary env: ✅ (admin-only; verified with bootstrap admin)
- Commit-based rollback A/B: ❌ (blocked by dirty git working tree / missing committed Version B)
