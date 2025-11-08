#!/bin/bash
# =====================================
# QUICK FIX - Copy & Paste auf Server
# =====================================
# Einfach dieses komplette Script auf ki-ana.at ausführen
# =====================================

echo "🚀 KI-ANA Quick Fix - Starting..."

# Zu Home-Verzeichnis
cd /home/kiana/ki_ana || { echo "❌ Verzeichnis nicht gefunden!"; exit 1; }

# Backup
echo "📦 Creating backup..."
mkdir -p backups/quickfix_$(date +%Y%m%d_%H%M%S)
cp db.sqlite3 backups/quickfix_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
cp kiana.db backups/quickfix_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
cp .env backups/quickfix_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true

# Update Code
echo "📥 Pulling latest code..."
git pull origin main || { echo "⚠️  Git pull failed, continuing..."; }

# Dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt --upgrade 2>&1 | tail -5
pip3 install -r netapi/requirements.txt --upgrade 2>&1 | tail -5

# Restart Backend
echo "🔄 Restarting backend..."

# Try Docker first
if command -v docker-compose &> /dev/null && [ -f "docker-compose.yml" ]; then
    echo "Using Docker Compose..."
    docker-compose down
    docker-compose up -d --build
    echo "Waiting for startup..."
    sleep 10
    docker-compose logs --tail=20 mutter-ki
    
# Try systemd
elif systemctl list-unit-files | grep -q "kiana-backend"; then
    echo "Using systemd..."
    sudo systemctl restart kiana-backend
    sleep 5
    sudo systemctl status kiana-backend --no-pager | tail -20
    
# Manual fallback
else
    echo "Starting manually..."
    pkill -f uvicorn || true
    sleep 2
    nohup python3 -m uvicorn netapi.app:app --host 0.0.0.0 --port 8080 --reload > logs/backend.log 2>&1 &
    echo "Started with PID: $!"
    sleep 5
fi

# Test
echo ""
echo "🧪 Testing..."
echo "Local health check:"
curl -s http://localhost:8080/health || echo "❌ Local test failed"

echo ""
echo "External health check:"
curl -s https://ki-ana.at/api/health || echo "❌ External test failed"

echo ""
echo "✅ Quick fix complete!"
echo "Test in Browser: https://ki-ana.at/"
echo ""
