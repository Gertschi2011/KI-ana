#!/usr/bin/env bash
set -euo pipefail
# Restore Postgres (custom dump), MinIO (mirror), Qdrant (collections.json only placeholder)
DIR=${1:-"backups/latest"}
[ -d "$DIR" ] || { echo "Backup dir not found: $DIR"; exit 1; }

# Postgres
PGC="docker compose exec -T postgres"
DB=${POSTGRES_DB:-kiana}
USER=${POSTGRES_USER:-ki}
if [ -f "$DIR/postgres.dump" ]; then
  $PGC pg_restore -U "$USER" -d "$DB" --clean --if-exists < "$DIR/postgres.dump"
  echo "[+] Postgres restored"
else
  echo "[!] Postgres dump missing"
fi

# MinIO
if command -v mc >/dev/null 2>&1 && [ -d "$DIR/minio" ]; then
  mc alias set kiana ${MINIO_ENDPOINT:-http://localhost:9000} ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin} >/dev/null 2>&1 || true
  mc mirror "$DIR/minio" kiana/${MINIO_BUCKET:-ki-ana}
  echo "[+] MinIO mirror restored"
else
  echo "[!] 'mc' not found or no minio backup dir"
fi

echo "[✓] Restore completed (Qdrant manual restore may be needed depending on snapshot format)"
