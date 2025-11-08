#!/bin/bash
# =====================================
# KI-ANA Live Server Fix Script
# =====================================
# Run this on ki-ana.at server to fix the 502 error
# Date: 2025-10-26
# =====================================

set -e

echo "🔧 KI-ANA Live Server Fix"
echo "========================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -eq 0 ]; then 
    SUDO=""
else 
    SUDO="sudo"
fi

echo "📍 Step 1: Checking current status..."
echo "======================================"

# Check if backend is running
if ps aux | grep -q "[u]vicorn"; then
    echo -e "${YELLOW}⚠️  Backend process found (but not responding)${NC}"
    echo "Killing existing processes..."
    pkill -f uvicorn || true
    sleep 2
else
    echo -e "${RED}❌ No backend process running${NC}"
fi

# Check docker
if command -v docker &> /dev/null; then
    echo ""
    echo "🐳 Checking Docker containers..."
    docker ps -a | grep -E "(kiana|mutter)" || echo "No KI-ana containers found"
fi

echo ""
echo "📍 Step 2: Checking logs..."
echo "======================================"

# Check recent logs
if [ -d "/home/kiana/ki_ana/logs" ]; then
    echo "Last 20 lines of error log:"
    tail -20 /home/kiana/ki_ana/logs/error.log 2>/dev/null || echo "No error.log found"
fi

echo ""
echo "📍 Step 3: Pulling latest code..."
echo "======================================"

cd /home/kiana/ki_ana || exit 1

# Backup current state
BACKUP_DIR="backups/pre_fix_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "Creating backup in $BACKUP_DIR..."

# Backup database
if [ -f "db.sqlite3" ]; then
    cp db.sqlite3 "$BACKUP_DIR/" || true
fi
if [ -f "kiana.db" ]; then
    cp kiana.db "$BACKUP_DIR/" || true
fi

# Backup .env
if [ -f ".env" ]; then
    cp .env "$BACKUP_DIR/" || true
fi

echo -e "${GREEN}✅ Backup created${NC}"

# Pull latest code
echo ""
echo "Pulling latest code from git..."
git fetch origin main
git pull origin main || {
    echo -e "${YELLOW}⚠️  Git pull failed, continuing with current code${NC}"
}

echo ""
echo "📍 Step 4: Installing dependencies..."
echo "======================================"

# Update Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt --upgrade || {
        echo -e "${YELLOW}⚠️  Some dependencies failed, continuing...${NC}"
    }
fi

# Install netapi dependencies
if [ -f "netapi/requirements.txt" ]; then
    echo "Installing netapi dependencies..."
    pip3 install -r netapi/requirements.txt --upgrade || {
        echo -e "${YELLOW}⚠️  Some dependencies failed, continuing...${NC}"
    }
fi

echo ""
echo "📍 Step 5: Database migrations..."
echo "======================================"

# Run migrations if alembic exists
if [ -f "alembic.ini" ]; then
    echo "Running database migrations..."
    cd /home/kiana/ki_ana
    alembic upgrade head || {
        echo -e "${YELLOW}⚠️  Migrations failed, continuing...${NC}"
    }
fi

echo ""
echo "📍 Step 6: Starting backend..."
echo "======================================"

# Check if using Docker
if [ -f "docker-compose.yml" ] && command -v docker-compose &> /dev/null; then
    echo "🐳 Starting with Docker Compose..."
    
    # Stop existing containers
    docker-compose down || true
    
    # Start services
    docker-compose up -d --build
    
    echo "Waiting for services to start..."
    sleep 10
    
    # Check status
    docker-compose ps
    
    # Check logs
    echo ""
    echo "Recent logs:"
    docker-compose logs --tail=50 mutter-ki
    
elif [ -f "netapi/app.py" ]; then
    echo "🚀 Starting with systemd service..."
    
    # Check if systemd service exists
    if systemctl list-unit-files | grep -q "kiana-backend"; then
        echo "Restarting kiana-backend service..."
        $SUDO systemctl restart kiana-backend
        sleep 3
        $SUDO systemctl status kiana-backend --no-pager
    else
        echo "No systemd service found, starting manually..."
        
        # Kill any existing processes
        pkill -f "uvicorn netapi.app" || true
        sleep 2
        
        # Start in background
        cd /home/kiana/ki_ana
        nohup python3 -m uvicorn netapi.app:app --host 0.0.0.0 --port 8080 --reload > logs/backend.log 2>&1 &
        
        echo "Backend started in background (PID: $!)"
        echo "Logs: tail -f logs/backend.log"
        sleep 5
    fi
else
    echo -e "${RED}❌ Cannot find backend application!${NC}"
    exit 1
fi

echo ""
echo "📍 Step 7: Health check..."
echo "======================================"

# Wait a bit for startup
echo "Waiting for backend to start..."
sleep 5

# Check local health
echo "Testing local health endpoint..."
for i in {1..10}; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is responding locally!${NC}"
        break
    elif [ $i -eq 10 ]; then
        echo -e "${RED}❌ Backend not responding after 10 attempts${NC}"
        echo "Check logs: tail -f logs/backend.log"
        exit 1
    else
        echo "Attempt $i/10... waiting..."
        sleep 3
    fi
done

# Check external health
echo ""
echo "Testing external health endpoint..."
if curl -s https://ki-ana.at/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ External endpoint working!${NC}"
else
    echo -e "${YELLOW}⚠️  External endpoint not responding yet${NC}"
    echo "Checking nginx configuration..."
    
    if [ -f "/etc/nginx/sites-available/ki-ana.at" ]; then
        $SUDO nginx -t
        $SUDO systemctl reload nginx
        echo "Nginx reloaded, testing again in 5 seconds..."
        sleep 5
        
        if curl -s https://ki-ana.at/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ External endpoint now working!${NC}"
        else
            echo -e "${RED}❌ Still not working, check nginx logs:${NC}"
            echo "$SUDO tail -50 /var/log/nginx/error.log"
        fi
    fi
fi

echo ""
echo "📍 Step 8: Final verification..."
echo "======================================"

# Test main endpoints
echo "Testing key endpoints..."

# Home page
if curl -s https://ki-ana.at/ | grep -q "KI-ana"; then
    echo -e "${GREEN}✅ Homepage working${NC}"
else
    echo -e "${RED}❌ Homepage not loading${NC}"
fi

# API health
if curl -s https://ki-ana.at/api/health | grep -q "ok\|healthy"; then
    echo -e "${GREEN}✅ API health endpoint working${NC}"
else
    echo -e "${YELLOW}⚠️  API health endpoint not responding correctly${NC}"
fi

# Static files
if curl -s https://ki-ana.at/static/styles.css | grep -q "KI_ana"; then
    echo -e "${GREEN}✅ Static files working${NC}"
else
    echo -e "${RED}❌ Static files not loading${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}🎉 Fix script complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Visit https://ki-ana.at/ and verify it works"
echo "2. Test the dropdown fix in the Papa menu"
echo "3. Test mobile view"
echo "4. Check admin panel"
echo ""
echo "If issues persist:"
echo "- Check logs: tail -f /home/kiana/ki_ana/logs/backend.log"
echo "- Check nginx: sudo tail -f /var/log/nginx/error.log"
echo "- Check docker: docker-compose logs -f"
echo ""
echo "Backup location: $BACKUP_DIR"
echo ""
