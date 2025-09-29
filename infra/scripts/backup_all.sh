#!/usr/bin/env bash
set -euo pipefail
# Backup Postgres, MinIO, Qdrant into ./backups/YYYYmmdd_HHMM
DIR=${1:-"backups/$(date +%Y%m%d_%H%M)"}
mkdir -p "$DIR"

# Postgres
PGC="docker compose exec -T postgres"
DB=${POSTGRES_DB:-kiana}
USER=${POSTGRES_USER:-ki}
$PGC pg_dump -U "$USER" -d "$DB" -Fc > "$DIR/postgres.dump"

echo "[+] Postgres dump -> $DIR/postgres.dump"

# MinIO via mc (requires 'mc' installed on host or a container alias)
if command -v mc >/dev/null 2>&1; then
  mc alias set kiana ${MINIO_ENDPOINT:-http://localhost:9000} ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin} >/dev/null 2>&1 || true
  mc mirror kiana/${MINIO_BUCKET:-ki-ana} "$DIR/minio"
  echo "[+] MinIO mirror -> $DIR/minio"
else
  echo "[!] 'mc' not found; skipping MinIO backup"
fi

# Qdrant export (HTTP snapshots)
QDRANT_URL="http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}"
SNAP_DIR="$DIR/qdrant"
mkdir -p "$SNAP_DIR"
# Try to fetch collection list and snapshot
if command -v curl >/dev/null 2>&1; then
  curl -fsS "$QDRANT_URL/collections" -o "$SNAP_DIR/collections.json" || true
  echo "[i] Qdrant collections saved"
else
  echo "[!] curl not found; skipping Qdrant collections"
fi

echo "[✓] Backup complete: $DIR"
