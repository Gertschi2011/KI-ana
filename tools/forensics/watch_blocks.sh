#!/usr/bin/env bash
set -euo pipefail

# Forensic live-watch for writes under memory/long_term/blocks
# - inotifywait trigger
# - spotcheck: size/owner/mode + JSON parse
# - attribution: lsof + fuser + PID -> cgroup -> docker container hint

WATCH_DIR=${1:-"/home/kiana/ki_ana/memory/long_term/blocks"}

if ! command -v inotifywait >/dev/null 2>&1; then
  echo "Missing dependency: inotifywait (usually package: inotify-tools)" >&2
  exit 2
fi

need_sudo() {
  # If not root, prefer sudo if available
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || return 1
    echo "sudo"
  else
    echo ""
  fi
}

SUDO=$(need_sudo || true)

json_check() {
  local f="$1"
  python3 - <<'PY' "$f" || return 1
import json,sys
p=sys.argv[1]
with open(p,'rb') as fh:
    raw=fh.read()
if len(raw)==0:
    raise SystemExit(1)
json.loads(raw.decode('utf-8'))
print('json:ok')
PY
}

container_hint() {
  local pid="$1"
  if [[ ! -r "/proc/$pid/cgroup" ]]; then
    return 0
  fi
  # Print first few cgroup lines
  sed -n '1,5p' "/proc/$pid/cgroup" || true

  # Try to extract container id fragments (docker/containerd)
  local cid
  cid=$(grep -Eo '([0-9a-f]{64})' "/proc/$pid/cgroup" | head -n1 || true)
  if [[ -n "$cid" ]] && command -v docker >/dev/null 2>&1; then
    echo "docker: possible container id: $cid"
    $SUDO docker ps --no-trunc --format '{{.ID}} {{.Names}}' | grep -F "${cid}" || true
  fi
}

echo "Watching: $WATCH_DIR"
echo "Tip: run chats now; this will print attribution per event."

inotifywait -m -e create,close_write,move --format '%T %e %w%f' --timefmt '%F %T' "$WATCH_DIR" |
while IFS= read -r line; do
  echo "\n=== EVENT: $line"
  file=$(echo "$line" | awk '{print $NF}')

  # Only check files that currently exist
  if [[ -f "$file" ]]; then
    echo "-- spotcheck: stat"
    stat -c 'size=%s mtime=%y owner=%U:%G mode=%a' "$file" || true

    echo "-- spotcheck: json"
    if json_check "$file"; then
      :
    else
      echo "json:FAIL" >&2
    fi

    echo "-- attribution: lsof"
    $SUDO lsof -n -- "$file" 2>/dev/null || true

    echo "-- attribution: fuser"
    $SUDO fuser -v "$file" 2>/dev/null || true

    # Extract PIDs from lsof (best-effort)
    pids=$($SUDO lsof -t -- "$file" 2>/dev/null | sort -u || true)
    if [[ -n "$pids" ]]; then
      for pid in $pids; do
        echo "-- pid: $pid"
        ps -fp "$pid" || true
        echo "-- cgroup/docker hint: $pid"
        container_hint "$pid" || true
      done
    fi
  else
    echo "(file not present; skip spotcheck/attribution)"
  fi

done
