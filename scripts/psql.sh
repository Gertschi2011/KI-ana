#!/usr/bin/env bash
set -euo pipefail

# Run psql inside the compose-managed Postgres container.
# Usage:
#   ./scripts/psql.sh -c "SELECT 1;"
#   ./scripts/psql.sh -c "SELECT username, role FROM users LIMIT 5;"

cd "$(dirname "$0")/.."

POSTGRES_USER="${POSTGRES_USER:-kiana}"
POSTGRES_DB="${POSTGRES_DB:-kiana}"

exec docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
