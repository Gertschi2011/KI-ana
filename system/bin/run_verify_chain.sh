#!/usr/bin/env bash
set -euo pipefail
BASE="$HOME/ki_ana"
. "$BASE/.venv/bin/activate"
python3 "$BASE/system/verify_chain.py" >> "$BASE/logs/verify_chain.log" 2>&1 || true
