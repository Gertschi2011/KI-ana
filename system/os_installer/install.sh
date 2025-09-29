#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "KI_ana OS Installer"
python3 install.py || true
echo "Done."

