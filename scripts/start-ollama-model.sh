#!/bin/bash
echo "🔁 Starte Ollama-Modell im Hintergrund …"
# Warm-up via HTTP API and keep the model resident indefinitely (keep_alive=-1)
# Requires that Ollama serve is already running on 127.0.0.1:11434
(
  curl -sS http://127.0.0.1:11434/api/generate \
    -H 'Content-Type: application/json' \
    -d '{"model":"llama3.2:3b","prompt":"warmup","stream":false,"keep_alive":-1}' \
    > /dev/null 2>&1
) &
