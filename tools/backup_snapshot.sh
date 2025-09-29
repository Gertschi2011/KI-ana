#!/usr/bin/env bash
set -euo pipefail

# Creates a timestamped snapshot of chain + memory blocks.

ROOT="${KI_ROOT:-$HOME/ki_ana}"
OUTDIR="$ROOT/backups"
TS=$(date +%Y%m%d_%H%M%S)
DEST="$OUTDIR/snapshot_${TS}.tar.gz"

mkdir -p "$OUTDIR"
cd "$ROOT"

tar -czf "$DEST" \
  system/chain \
  memory/long_term/blocks \
  --exclude='*.tmp' --exclude='__pycache__'

echo "Snapshot: $DEST"

