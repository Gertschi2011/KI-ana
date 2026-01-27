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

integrity_check() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "(file not present; skip integrity)"
    return 0
  fi

  echo "-- spotcheck: stat"
  stat -c 'size=%s mtime=%y owner=%U:%G mode=%a' "$file" || true

  echo "-- spotcheck: json"
  if json_check "$file"; then
    :
  else
    echo "json:FAIL" >&2
  fi
}

attribution_check() {
  local file="$1"
  if [[ ! -e "$file" ]]; then
    echo "(file not present; skip attribution)"
    return 0
  fi

  echo "-- attribution: lsof/fuser (retry)"
  for i in 1 2 3 4 5; do
    if $SUDO lsof -n -- "$file" 2>/dev/null; then
      break
    fi
    if $SUDO fuser -v "$file" 2>/dev/null; then
      break
    fi
    sleep 0.05
  done

  # Extract PIDs from lsof (best-effort)
  local pids
  pids=$($SUDO lsof -t -- "$file" 2>/dev/null | sort -u || true)

  # Bonus fallback: try to extract a PID from plain fuser output
  if [[ -z "$pids" ]]; then
    local pid
    pid=$($SUDO fuser "$file" 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i ~ /^[0-9]+$/) {print $i; exit}}' || true)
    if [[ -n "$pid" ]]; then
      pids="$pid"
    fi
  fi

  if [[ -n "$pids" ]]; then
    for pid in $pids; do
      echo "-- pid: $pid"
      ps -o pid,ppid,user,cmd -p "$pid" || true
      echo "-- cgroup/docker hint: $pid"
      container_hint "$pid" || true
    done
  fi
}

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

inotifywait -m -e open,create,close_write,move --format '%T|%e|%w%f' --timefmt '%F %T' "$WATCH_DIR" |
while IFS='|' read -r ts event file; do
  printf '\n=== EVENT: %s %s %s\n' "$ts" "$event" "$file"

  case "$event" in
    *OPEN*)
      # Attribution only: maximize chances of catching the writer while fd is open.
      attribution_check "$file"
      ;;
    *CLOSE_WRITE*|*MOVED_TO*)
      # Integrity only: these events indicate the file is in a final-ish state.
      integrity_check "$file"
      ;;
    *)
      echo "(ignore event: $event)"
      ;;
  esac
done
