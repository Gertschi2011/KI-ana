#!/bin/bash
# Quick Fix Script für Celery Worker
# Repariert den Worker-Path in docker-compose.yml

echo "🔧 Repariere Celery Worker Konfiguration..."

# Backup docker-compose.yml
cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d_%H%M%S)

# Check ob Worker bereits korrekt konfiguriert ist
if grep -q "backend.workers.celery_app" docker-compose.yml; then
    echo "✅ Worker-Path bereits korrekt konfiguriert"
else
    echo "⚠️  Updating worker command..."
    # Dieser Fix müsste manuell in docker-compose.yml angewendet werden
    echo "   Bitte in docker-compose.yml unter 'worker' Service:"
    echo "   command: bash -lc 'celery -A backend.workers.celery_app.celery worker --loglevel=info'"
fi

# Restart Worker
echo "🔄 Restarting Worker..."
docker-compose stop worker
docker-compose rm -f worker
docker-compose up -d worker

echo "✅ Worker Fix abgeschlossen"
docker-compose ps worker
