#!/usr/bin/env bash
set -euo pipefail

# Query basic user status fields from Postgres (inside docker compose).
# Usage:
#   ./scripts/pg_user_status.sh gerald

cd "$(dirname "$0")/.."

u="${1:-}"
if [[ -z "$u" ]]; then
  echo "Usage: $0 <username>" >&2
  exit 2
fi

./scripts/psql.sh -c "\
SELECT username, role, is_active, locked_until, account_status
FROM users
WHERE lower(username)=lower('${u}');\
"
