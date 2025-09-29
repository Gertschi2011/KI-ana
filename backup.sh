#!/bin/bash
# Backup-Skript für KI_ana netapi

BASE_DIR="$HOME/ki_ana"
SRC="$BASE_DIR/netapi"
DATE=$(date +%Y%m%d_%H%M)
BACKUP_DIR="$BASE_DIR/backups"
BACKUP_NAME="netapi_$DATE"

# Zielordner anlegen, falls er nicht existiert
mkdir -p "$BACKUP_DIR"

# 1) Verzeichnis-Kopie
cp -r "$SRC" "$BACKUP_DIR/$BACKUP_NAME"

# 2) Optional zusätzlich tar.gz Archiv
tar -czf "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" -C "$BASE_DIR" netapi

echo "✅ Backup erstellt:"
echo "   → Ordner: $BACKUP_DIR/$BACKUP_NAME"
echo "   → Archiv: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
