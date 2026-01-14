#!/usr/bin/env bash
set -euo pipefail

# One-command deploy + smoke for KI_ana
# Supports: --env prod|staging, --service frontend|backend|all, --smoke-only, --reload-nginx

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_NAME=""
SERVICE="all"
SMOKE_ONLY=0
RELOAD_NGINX=0
BASE_URL="https://ki-ana.at"

usage() {
  cat >&2 <<'USAGE'
Usage:
  ./scripts/deploy_and_smoke.sh --env prod|staging [--service frontend|backend|all] [--smoke-only] [--reload-nginx] [--base-url URL]

Examples:
  ./scripts/deploy_and_smoke.sh --env prod --service frontend
  ./scripts/deploy_and_smoke.sh --env staging --service all
  ./scripts/deploy_and_smoke.sh --env prod --smoke-only
USAGE
}

log() { printf '%s\n' "$*"; }

fail() {
  local title="$1"; shift || true
  log "FAIL: ${title}" >&2
  if [[ $# -gt 0 ]]; then
    log "$*" >&2
  fi
  log "" >&2
  log "Next action (debug):" >&2
  if [[ -n "${COMPOSE_CMD:-}" ]]; then
    log "  ${COMPOSE_CMD} ps" >&2
    case "${SERVICE:-all}" in
      backend) log "  ${COMPOSE_CMD} logs --tail=200 backend" >&2 ;;
      frontend) log "  ${COMPOSE_CMD} logs --tail=200 frontend" >&2 ;;
      all) log "  ${COMPOSE_CMD} logs --tail=200 backend" >&2; log "  ${COMPOSE_CMD} logs --tail=200 frontend" >&2 ;;
    esac
  fi
  exit 1
}

run_step() {
  local name="$1"; shift
  log "==> ${name}"
  local out
  set +e
  out="$({ "$@"; } 2>&1)"
  local rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    log "--- last 30 lines ---" >&2
    printf '%s\n' "$out" | tail -n 30 >&2
    fail "$name" "(exit=$rc)"
  fi
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_NAME="${2:-}"; shift 2 ;;
    --service)
      SERVICE="${2:-}"; shift 2 ;;
    --smoke-only)
      SMOKE_ONLY=1; shift ;;
    --reload-nginx)
      RELOAD_NGINX=1; shift ;;
    --base-url)
      BASE_URL="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      usage; fail "unknown argument" "$1" ;;
  esac
done

if [[ -z "$ENV_NAME" ]]; then
  usage
  fail "missing required arg" "--env prod|staging"
fi
if [[ "$ENV_NAME" != "prod" && "$ENV_NAME" != "staging" ]]; then
  fail "invalid --env" "$ENV_NAME"
fi
if [[ "$SERVICE" != "frontend" && "$SERVICE" != "backend" && "$SERVICE" != "all" ]]; then
  fail "invalid --service" "$SERVICE"
fi

cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  fail "docker not found" "Install docker + docker compose plugin"
fi
if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose not available" "Install docker compose plugin"
fi

# Choose compose project/file
PROJECT=""
COMPOSE_FILE=""
if [[ "$ENV_NAME" == "staging" ]]; then
  PROJECT="ki_ana_staging"
  COMPOSE_FILE="docker-compose.staging.yml"
else
  PROJECT="ki_ana"
  # Try to derive prod compose file from runbooks, else fallback to docker-compose.yml.
  COMPOSE_FILE="docker-compose.yml"
  if [[ -d ops/runbooks ]]; then
    # shellcheck disable=SC2016
    derived="$(grep -RhoE 'docker compose[^\n]*-p ki_ana\b[^\n]*-f [^ ]+' ops/runbooks 2>/dev/null | head -n 1 | sed -E 's/.*-f ([^ ]+).*/\1/' || true)"
    if [[ -n "$derived" && -f "$derived" ]]; then
      COMPOSE_FILE="$derived"
    elif [[ -f docker-compose.production.yml ]]; then
      COMPOSE_FILE="docker-compose.production.yml"
    elif [[ -f docker-compose.prod.yml ]]; then
      COMPOSE_FILE="docker-compose.prod.yml"
    fi
  fi
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  fail "compose file not found" "$COMPOSE_FILE"
fi

COMPOSE_CMD="docker compose -p ${PROJECT} -f ${COMPOSE_FILE}"

SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
log "Repo: ${REPO_ROOT}"
log "Env: ${ENV_NAME}"
log "Compose: ${COMPOSE_CMD}"
log "Commit: ${SHA}"
log "Base URL: ${BASE_URL}"

# Deploy (build + recreate)
if [[ $SMOKE_ONLY -eq 0 ]]; then
  case "$SERVICE" in
    frontend)
      run_step "docker build frontend" $COMPOSE_CMD build frontend
      run_step "docker up frontend" $COMPOSE_CMD up -d --no-deps --force-recreate frontend
      ;;
    backend)
      run_step "docker build backend" $COMPOSE_CMD build backend
      run_step "docker up backend" $COMPOSE_CMD up -d --no-deps --force-recreate backend
      ;;
    all)
      run_step "docker build backend" $COMPOSE_CMD build backend
      run_step "docker build frontend" $COMPOSE_CMD build frontend
      run_step "docker up backend" $COMPOSE_CMD up -d --no-deps --force-recreate backend
      run_step "docker up frontend" $COMPOSE_CMD up -d --no-deps --force-recreate frontend
      ;;
  esac
else
  log "(smoke-only: skipping build/recreate)"
fi

# Nginx reload only when explicitly requested OR when last commit looks like nginx-related.
if [[ $RELOAD_NGINX -eq 1 ]]; then
  if command -v nginx >/dev/null 2>&1; then
    run_step "nginx -t" sudo nginx -t
    if command -v systemctl >/dev/null 2>&1; then
      run_step "nginx reload" sudo systemctl reload nginx
    else
      run_step "nginx reload" sudo nginx -s reload
    fi
  else
    fail "nginx not found" "--reload-nginx requested but nginx is not installed"
  fi
else
  # Heuristic: reload if last commit touched nginx-related files.
  if git show --name-only --pretty=format: HEAD 2>/dev/null | grep -Eq '(^infra/nginx/|nginx|ops/runbooks/scripts/patch_nginx_|ops/runbooks/scripts/apply_nginx_patch_)'; then
    log "NOTE: last commit touched nginx-related files; consider re-running with --reload-nginx"
  fi
fi

# Smoke suite
run_step "smoke: /health" curl -fsS "${BASE_URL%/}/health"

# /api/me auth flag (informational)
log "==> smoke: /api/me"
ME_JSON="$(curl -fsS "${BASE_URL%/}/api/me" || true)"
AUTH=""
if command -v jq >/dev/null 2>&1; then
  AUTH="$(printf '%s' "$ME_JSON" | jq -r '.auth // empty' 2>/dev/null || true)"
else
  AUTH="$(python3 -c 'import json,sys
try:
  j=json.loads(sys.stdin.read() or "{}")
  v=j.get("auth", "")
  sys.stdout.write("true" if v is True else ("false" if v is False else ""))
except Exception:
  pass
' 2>/dev/null <<<"$ME_JSON" || true)"
fi
log "api/me auth: ${AUTH:-unknown}"

# SSE stream twice + finalize (uses its own /api/me auth:true validation after login)
run_step "smoke: SSE stream twice" env BASE_URL="$BASE_URL" bash "$REPO_ROOT/scripts/smoke_sse_twice_browserlike.sh"

log "OK: deploy_and_smoke"
log "- env=${ENV_NAME} service=${SERVICE} smoke_only=${SMOKE_ONLY}"
log "- ${BASE_URL%/}/app/chat"
log "- commit=${SHA}"
