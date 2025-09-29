#!/usr/bin/env bash
set -euo pipefail

# If KI_ana project is mounted at /root/ki_ana, run the subki_server from there
KI_ROOT=${KI_ROOT:-/root/ki_ana}
PYTHONPATH=${PYTHONPATH:-}
export PYTHONPATH="$KI_ROOT:$PYTHONPATH"

# Optional daily cron-like loop for reflect & sync
if [[ "${ENABLE_CRON:-false}" == "true" ]]; then
  echo "[subki] Starting with cron loop (interval ${CRON_INTERVAL_SECONDS:-86400}s)"
  # Start Flask server in background
  python3 "$KI_ROOT/subki_server.py" &
  SERVER_PID=$!
  trap "kill $SERVER_PID || true" EXIT
  while true; do
    echo "[subki] HTTP reflect"
    curl -fsS http://127.0.0.1:5055/reflect || true
    echo "\n[subki] HTTP sync"
    curl -fsS "http://127.0.0.1:5055/sync?mother_url=${MOTHER_KI_URL:-}" || true
    sleep ${CRON_INTERVAL_SECONDS:-86400}
  done
else
  echo "[subki] Starting server only"
  exec python3 "$KI_ROOT/subki_server.py"
fi
