#!/usr/bin/env bash
# scripts/ensure_ollama_model.sh
set -euo pipefail

MODEL="${OLLAMA_MODEL:?Env OLLAMA_MODEL fehlt}"
HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
STATUS_FILE="${KIANA_STATUS_FILE:-./runtime/llm_status.json}"

mkdir -p "$(dirname "$STATUS_FILE")"

write_status() {
  # $1 = status (loading|ready|error), $2 = message
  printf '{ "model": "%s", "status": "%s", "message": "%s", "ts": "%s" }\n' \
    "$MODEL" "$1" "$2" "$(date -Is)" > "$STATUS_FILE"
}

# signal loading
write_status "loading" "Prüfe/verfügbarmache Modell"

# ensure Ollama is reachable (best-effort)
if command -v curl >/dev/null 2>&1; then
  if ! curl -sS "${HOST%/}/api/tags" -m 2 >/dev/null 2>&1; then
    # try to start ollama service (best-effort)
    if command -v ollama >/dev/null 2>&1; then
      if command -v systemctl >/dev/null 2>&1; then
        systemctl --user start ollama >/dev/null 2>&1 || sudo systemctl start ollama >/dev/null 2>&1 || true
      fi
      if ! pgrep -f "ollama serve" >/dev/null 2>&1; then
        nohup ollama serve > "$HOME/ollama.out" 2>&1 &
      fi
    fi
    # wait briefly
    for i in $(seq 1 10); do
      if curl -sS "${HOST%/}/api/tags" -m 2 >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
  fi
fi

# check and pull model if missing
pull_needed=1
if command -v curl >/dev/null 2>&1; then
  if rt=$(curl -sS "${HOST%/}/api/tags" -m 3); then
    if echo "$rt" | grep -q '"models"'; then
      # try to find exact name match for the model
      if echo "$rt" | grep -E '"name"\s*:\s*"'${MODEL//\//\\/}'"' >/dev/null 2>&1; then
        pull_needed=0
      fi
    fi
  fi
fi

if [ $pull_needed -eq 1 ]; then
  write_status "loading" "Modell wird geladen (ollama pull)"
  pulled=1
  if command -v ollama >/dev/null 2>&1; then
    if ! ollama pull "$MODEL"; then
      pulled=0
    fi
  elif command -v docker >/dev/null 2>&1; then
    if ! docker exec ollama ollama pull "$MODEL" >/dev/null 2>&1; then
      pulled=0
    fi
  else
    pulled=0
  fi
  if [ $pulled -eq 0 ]; then
    write_status "error" "Fehler beim Laden des Modells"
    echo "Fehler: Konnte Modell $MODEL nicht laden." >&2
    exit 1
  fi
fi

write_status "ready" "KI bereit"
echo "Ollama-Modell OK: $MODEL"
