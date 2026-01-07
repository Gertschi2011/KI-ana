# Schema Consistency — Users Timestamps

Date/Time (UTC): 2026-01-07

Commit SHA: 93ccbf0c5

## Command

```bash
cd /home/kiana/ki_ana
set -a && source .env.staging && set +a
export DATABASE_URL="postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:25432/${POSTGRES_DB}"
/home/kiana/.venv/bin/python -m pytest -q tests/test_m3_timestamp_consistency_users.py -vv
```

## Output

```text
2 passed in 0.45s
```

## Note

This run uses staging Postgres and is expected to fail (not skip) if `users.updated_at` drifts away from a Postgres timestamp type.
