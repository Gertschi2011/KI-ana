#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-$HOME/submind}"
mkdir -p "$TARGET"
cp -a . "$TARGET/"
cd "$TARGET"

# Python venv erstellen
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
# Minimalabhängigkeiten (hier keine externen nötig; optional: requests/bs4)
deactivate

echo "✅ Submind installiert in $TARGET"
echo "Start:  $TARGET/.venv/bin/python runtime_listener.py"
