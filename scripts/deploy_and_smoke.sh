#!/usr/bin/env bash
set -euo pipefail

# One-command deploy + smoke for KI_ana
# Supports: --env prod|staging, --service frontend|backend|all, --smoke-only, --reload-nginx, --skip-sse

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_NAME=""
SERVICE="all"
SMOKE_ONLY=0
RELOAD_NGINX=0
SKIP_SSE=0
BASE_URL="https://ki-ana.at"

usage() {
  cat >&2 <<'USAGE'
Usage:
  ./scripts/deploy_and_smoke.sh --env prod|staging [--service frontend|backend|all] [--smoke-only] [--reload-nginx] [--skip-sse] [--base-url URL]

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

  # Interactive: run directly so output and prompts are visible live.
  if [[ -t 0 && -t 1 ]]; then
    set +e
    "$@"
    local rc=$?
    set -e
    if [[ $rc -ne 0 ]]; then
      fail "$name" "(exit=$rc)"
    fi
    return 0
  fi

  # Non-interactive: capture output for logs (avoid infinite hangs).
  local out
  set +e
  if command -v timeout >/dev/null 2>&1; then
    out="$({ timeout 120s "$@"; } 2>&1)"
  else
    out="$({ "$@"; } 2>&1)"
  fi
  local rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    log "--- last 30 lines ---" >&2
    printf '%s\n' "$out" | tail -n 30 >&2
    if [[ $rc -eq 124 ]]; then
      fail "$name" "(timeout)" "Command exceeded 120s in non-interactive mode"
    fi
    fail "$name" "(exit=$rc)"
  fi
  # Print captured output for transparency.
  printf '%s\n' "$out"
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
    --skip-sse)
      SKIP_SSE=1; shift ;;
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
    derived="$(grep -RhoE 'docker compose[^\n]*-p ki_ana\b[^\n]*-f [^ ]+' ops/runbooks 2>/dev/null | head -n 1 | sed -E 's/.*-f ([^ ]+).*/\1/' | tr -d '\r' | tr -d '\n' | xargs || true)"
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

SERVICES="$($COMPOSE_CMD config --services 2>/dev/null || true)"

pick_service() {
  local role="$1"; shift
  local svc
  for svc in "$@"; do
    if printf '%s\n' "$SERVICES" | grep -qx "$svc"; then
      printf '%s' "$svc"
      return 0
    fi
  done
  return 1
}

BACKEND_SVC=""
FRONTEND_SVC=""
if [[ -n "$SERVICES" ]]; then
  BACKEND_SVC="$(pick_service backend backend kiana-backend netapi api server || true)"
  FRONTEND_SVC="$(pick_service frontend frontend kiana-frontend web nextjs ui || true)"
fi

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
      if [[ -z "$FRONTEND_SVC" ]]; then
        fail "frontend service not found in compose" "Available: $(printf '%s' "$SERVICES" | tr '\n' ' ')"
      fi
      run_step "docker build frontend" $COMPOSE_CMD build --build-arg NEXT_PUBLIC_BUILD_SHA="$SHA" "$FRONTEND_SVC"
      run_step "docker up frontend" $COMPOSE_CMD up -d --no-deps --force-recreate "$FRONTEND_SVC"
      ;;
    backend)
      if [[ -z "$BACKEND_SVC" ]]; then
        fail "backend service not found in compose" "Available: $(printf '%s' "$SERVICES" | tr '\n' ' ')"
      fi
      run_step "docker build backend" $COMPOSE_CMD build "$BACKEND_SVC"
      run_step "docker up backend" $COMPOSE_CMD up -d --no-deps --force-recreate "$BACKEND_SVC"
      ;;
    all)
      if [[ -z "$BACKEND_SVC" ]]; then
        fail "backend service not found in compose" "Available: $(printf '%s' "$SERVICES" | tr '\n' ' ')"
      fi
      run_step "docker build backend" $COMPOSE_CMD build "$BACKEND_SVC"
      if [[ -n "$FRONTEND_SVC" ]]; then
        run_step "docker build frontend" $COMPOSE_CMD build --build-arg NEXT_PUBLIC_BUILD_SHA="$SHA" "$FRONTEND_SVC"
      fi
      run_step "docker up backend" $COMPOSE_CMD up -d --no-deps --force-recreate "$BACKEND_SVC"
      if [[ -n "$FRONTEND_SVC" ]]; then
        run_step "docker up frontend" $COMPOSE_CMD up -d --no-deps --force-recreate "$FRONTEND_SVC"
      fi
      ;;
  esac
else
  log "(smoke-only: skipping build/recreate)"
fi

# Nginx reload only when explicitly requested OR when last commit looks like nginx-related.
if [[ $RELOAD_NGINX -eq 1 ]]; then
  if command -v nginx >/dev/null 2>&1; then
    # Avoid hanging on sudo password prompts in non-interactive environments.
    if ! command -v sudo >/dev/null 2>&1; then
      fail "sudo not found" "--reload-nginx requested but sudo is not installed"
    fi

    # Interactive TTY: allow sudo to prompt.
    if [[ -t 0 && -t 1 ]]; then
      run_step "nginx -t" sudo nginx -t
      if command -v systemctl >/dev/null 2>&1; then
        run_step "nginx reload" sudo systemctl reload nginx
      else
        run_step "nginx reload" sudo nginx -s reload
      fi
    else
      # Non-interactive: require passwordless sudo.
      if ! sudo -n true >/dev/null 2>&1; then
        fail "nginx reload requires sudo" "Non-interactive run: configure passwordless sudo for nginx reload, or run interactively (TTY)."
      fi
      run_step "nginx -t" sudo -n nginx -t
      if command -v systemctl >/dev/null 2>&1; then
        run_step "nginx reload" sudo -n systemctl reload nginx
      else
        run_step "nginx reload" sudo -n nginx -s reload
      fi
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
  AUTH="$(printf '%s' "$ME_JSON" | jq -r '.auth' 2>/dev/null || true)"
else
  AUTH="$(python3 -c 'import json,sys
try:
  j=json.loads(sys.stdin.read() or "{}")
  v=j.get("auth", None)
  if v is True:
    sys.stdout.write("true")
  elif v is False:
    sys.stdout.write("false")
  else:
    sys.stdout.write("unknown")
except Exception:
  sys.stdout.write("unknown")
' 2>/dev/null <<<"$ME_JSON" || true)"
fi
case "${AUTH}" in
  true|false) log "api/me auth: ${AUTH}" ;;
  *) log "api/me auth: unknown" ;;
esac

# SSE stream twice + finalize (uses its own /api/me auth:true validation after login)
if [[ $SKIP_SSE -eq 1 ]]; then
  log "==> smoke: SSE stream twice (skipped: --skip-sse)"
else
  run_step "smoke: SSE stream twice" env KIANA_NON_INTERACTIVE=1 BASE_URL="$BASE_URL" bash "$REPO_ROOT/scripts/smoke_sse_twice_browserlike.sh"
fi

# Optional proof: verify frontend has current build SHA (only visible to creator/admin).
# Enable explicitly to avoid leaking build markers to normal users.
# Usage:
#   PROOF_BUILD=1 KIANA_USER=creator KIANA_PASS=... ./scripts/deploy_and_smoke.sh --env prod --service frontend
if [[ "${PROOF_BUILD:-0}" == "1" ]]; then
  if [[ -z "${KIANA_USER:-}" || -z "${KIANA_PASS:-}" ]]; then
    # Interactive prompt (no password in logs)
    if [[ -t 0 && -t 1 ]]; then
      if [[ -z "${KIANA_USER:-}" ]]; then
        printf 'Creator/Admin username: ' > /dev/tty
        IFS= read -r KIANA_USER < /dev/tty
        export KIANA_USER
      fi
      if [[ -z "${KIANA_PASS:-}" ]]; then
        printf 'Creator/Admin password: ' > /dev/tty
        IFS= read -r -s KIANA_PASS < /dev/tty
        printf '\n' > /dev/tty
        export KIANA_PASS
      fi
    fi
  fi
  if [[ -z "${KIANA_USER:-}" || -z "${KIANA_PASS:-}" ]]; then
    fail "proof: missing creds" "Set KIANA_USER/KIANA_PASS (creator/admin) or run interactively with PROOF_BUILD=1"
  fi
  run_step "proof: build sha visible for creator" bash -lc '
    set -euo pipefail
    BASE_URL="'"${BASE_URL%/}"'"
    SHA="'"$SHA"'"
    JAR="$(mktemp /tmp/kiana_proof_cookies.XXXXXX)"
    trap "rm -f $JAR" EXIT

    payload=$(python3 - <<PY
import json, os
print(json.dumps({"username": os.environ.get("KIANA_USER",""), "password": os.environ.get("KIANA_PASS",""), "remember": True}))
PY
)

    curl -sS --http2 -c "$JAR" -b "$JAR" -H "Content-Type: application/json" --data "$payload" "$BASE_URL/api/login" >/dev/null
    # NOTE: Navbar is a client component, so Build markers will not appear in curl HTML reliably.
    # Use a server-rendered, admin-only proof page.
    html=$(curl -sS --http2 -b "$JAR" "$BASE_URL/app/buildproof" | head -n 80)
    echo "$html" | grep -F "Build" >/dev/null
    echo "$html" | grep -F "$SHA" >/dev/null
  '
fi

log "OK: deploy_and_smoke"
log "- env=${ENV_NAME} service=${SERVICE} smoke_only=${SMOKE_ONLY}"
log "- ${BASE_URL%/}/app/chat"
log "- commit=${SHA}"
