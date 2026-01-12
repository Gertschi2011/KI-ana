#!/usr/bin/env bash
set -euo pipefail

# Fresh-DB migration smoke test (Postgres)
# - starts an ephemeral Postgres
# - runs `alembic upgrade head` using the existing worker image
# - verifies alembic_version.version_num max length >= 255

PROJ="kiana_freshdb_smoke_$$"
NET="${PROJ}_net"
PG="${PROJ}_pg"

DB_USER="kiana"
DB_PASS="kiana"
DB_NAME="kiana"
DB_HOST="${PG}"
DB_PORT="5432"

WORKER_IMAGE=${WORKER_IMAGE:-ki_ana_staging-worker}

cleanup() {
  docker rm -f "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "$NET" >/dev/null

docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_USER="$DB_USER" \
  -e POSTGRES_PASSWORD="$DB_PASS" \
  -e POSTGRES_DB="$DB_NAME" \
  postgres:15-alpine >/dev/null

echo "Waiting for Postgres..."
for i in $(seq 1 80); do
  if docker exec "$PG" psql -U "$DB_USER" -d "$DB_NAME" -tAc 'SELECT 1' >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo "Running alembic upgrade head against fresh DB"
docker run --rm --network "$NET" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e KI_ROOT=/app \
  "$WORKER_IMAGE" \
  sh -lc 'alembic upgrade head'

echo "Verifying alembic_version column size"

max_len=$(docker exec "$PG" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -tAc \
  "SELECT character_maximum_length
   FROM information_schema.columns
   WHERE table_schema='public'
     AND table_name='alembic_version'
     AND column_name='version_num';" | tr -d '[:space:]')

if [[ -z "${max_len}" ]]; then
  echo "ERROR: alembic_version.version_num not found in information_schema" >&2
  exit 1
fi

if ! [[ "${max_len}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: alembic_version.version_num has non-numeric max_len='${max_len}'" >&2
  exit 1
fi

if (( max_len < 255 )); then
  echo "ERROR: alembic_version.version_num is too small: ${max_len} (<255)" >&2
  exit 1
fi

echo "alembic_version.version_num length=${max_len} (OK)"

echo "OK"
