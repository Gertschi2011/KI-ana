#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Version markers for evidence capture (used by /api/ops/summary).
export BUILD_SHA="${BUILD_SHA:-$(git rev-parse --short HEAD 2>/dev/null || true)}"
export KIANA_BUILD_SHA="${KIANA_BUILD_SHA:-$BUILD_SHA}"
export KIANA_VERSION="${KIANA_VERSION:-$BUILD_SHA}"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.staging.yml}"
ENV_FILE="${ENV_FILE:-.env.staging}"
PROJECT_NAME="${PROJECT_NAME:-ki_ana_staging}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  echo "Hint: copy .env.staging.example -> .env.staging" >&2
  exit 1
fi

echo "==> Deploy staging (project=$PROJECT_NAME)"

docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build

echo "==> Bringing up dependencies"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres redis qdrant minio

echo "==> Running migrations (best-effort)"
# Prefer host python if available (recommended). Fallback to container if alembic exists there.

HOST_PYTHON=""
if [[ -x ".venv/bin/python" ]]; then
  HOST_PYTHON=".venv/bin/python"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  HOST_PYTHON="${VIRTUAL_ENV}/bin/python"
elif [[ -x "$HOME/.venv/bin/python" ]]; then
  HOST_PYTHON="$HOME/.venv/bin/python"
fi

if [[ -n "$HOST_PYTHON" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  export DATABASE_URL="postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:25432/${POSTGRES_DB}"
  "$HOST_PYTHON" -m alembic -c alembic.ini upgrade head || true
else
  # Fallback: try alembic inside backend container
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend alembic -c alembic.ini upgrade head || true
fi

echo "==> Bringing up app services"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d backend frontend worker

echo "==> Healthchecks"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

BASE_URL="${KIANA_BASE_URL:-http://localhost:28000}"
BASE_URL="${BASE_URL%/}"


retry() {
  local attempts="$1"; shift
  local delay_s="$1"; shift
  local n
  for n in $(seq 1 "$attempts"); do
    if "$@"; then
      return 0
    fi
    sleep "$delay_s"
  done
  return 1
}

# Backend ping
retry 30 1 curl -fsS "${BASE_URL}/api/v2/chat/ping" >/dev/null
# Metrics (Prometheus)
retry 30 1 bash -lc "curl -fsS '${BASE_URL}/api/metrics' | head -n 5 >/dev/null"

echo "OK: staging deployed and healthy"
