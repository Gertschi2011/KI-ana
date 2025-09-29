#!/bin/bash
set -euo pipefail

# KI_ana backup script - snapshots memory for easy restore
ROOT_DIR="${KI_ROOT:-$HOME/ki_ana}"
SRC_DIR="$ROOT_DIR/memory/long_term"
DEST_ROOT="$ROOT_DIR/backups"
TS=$(date +"%Y%m%d-%H%M%S")
DEST_DIR="$DEST_ROOT/memory_$TS"

mkdir -p "$DEST_DIR"
if [ -d "$SRC_DIR" ]; then
  cp -a "$SRC_DIR" "$DEST_DIR/"
else
  echo "WARN: source directory not found: $SRC_DIR" >&2
fi

# Optional: include blocks in system/chain if present
CHAIN_DIR="$ROOT_DIR/system/chain"
if [ -d "$CHAIN_DIR" ]; then
  mkdir -p "$DEST_DIR/chain"
  cp -a "$CHAIN_DIR"/*.json "$DEST_DIR/chain/" 2>/dev/null || true
fi

echo "Backup complete: $DEST_DIR"
