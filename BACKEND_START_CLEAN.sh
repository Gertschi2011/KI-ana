#!/bin/bash
# KI_ana Backend Clean Start Script
# Stoppt ALLE laufenden Backends und startet NUR EINEN sauber

echo "🛑 Stopping all backends..."
sudo pkill -9 -f "uvicorn netapi.app"
sleep 2

echo "🚀 Starting clean backend..."
cd /home/kiana/ki_ana
export DATABASE_URL="postgresql+psycopg2://kiana:kiana_pass@localhost:5432/kiana"

nohup /home/kiana/.local/bin/uvicorn netapi.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info \
  > /tmp/backend_clean.log 2>&1 &

NEW_PID=$!
echo "✅ Backend started with PID: $NEW_PID"
echo "📋 Logs: tail -f /tmp/backend_clean.log"

sleep 5

# Test
curl -s http://localhost:8000/health | head -3
echo ""
echo "✅ Backend is ready!"
