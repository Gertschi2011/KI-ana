#!/usr/bin/env bash
set -euo pipefail
BASE="$HOME/ki_ana"
. "$BASE/.venv/bin/activate"
exec python3 "$BASE/system/auto_learn_loop.py" >> "$BASE/logs/auto_learn.log" 2>&1
