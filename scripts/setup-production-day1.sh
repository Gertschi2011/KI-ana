#!/bin/bash
# KI_ana Production Day 1 Setup
# Firewall + Backup-Cron + Health-Check

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
  _  ___   _                 
 | |/ (_) / \   _ __   __ _ 
 | ' /| |/ _ \ | '_ \ / _` |
 | . \| / ___ \| | | | (_| |
 |_|\_\_/_/   \_\_| |_|\__,_|
                             
 Production Day 1 Setup
EOF
echo -e "${NC}"

echo -e "${GREEN}🚀 KI_ana Production Day 1 Setup${NC}"
echo ""

KIANA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIANA_DIR"

# ============================================
# 1. FIREWALL KONFIGURIEREN
# ============================================
echo -e "${YELLOW}🔒 Step 1/3: Firewall Configuration${NC}"
echo ""

if command -v ufw &> /dev/null; then
    echo "UFW detected. Configuring firewall..."
    
    # Check if UFW is active
    UFW_STATUS=$(sudo ufw status | grep "Status:" | awk '{print $2}')
    
    if [ "$UFW_STATUS" != "active" ]; then
        echo -e "${YELLOW}⚠️  UFW is inactive${NC}"
        read -p "Enable UFW? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo ufw --force enable
            echo -e "${GREEN}✅ UFW enabled${NC}"
        fi
    fi
    
    # Add rules
    echo "Adding firewall rules..."
    sudo ufw allow 8000/tcp comment "KI_ana API"
    sudo ufw allow 5353/udp comment "mDNS Discovery"
    
    echo -e "${GREEN}✅ Firewall configured${NC}"
    echo ""
    sudo ufw status numbered
    
else
    echo -e "${YELLOW}⚠️  UFW not available on this system${NC}"
    echo "Firewall configuration skipped"
fi

echo ""

# ============================================
# 2. BACKUP-CRON EINRICHTEN
# ============================================
echo -e "${YELLOW}💾 Step 2/3: Backup Cron Setup${NC}"
echo ""

# Check if backup script exists
if [ ! -f "$KIANA_DIR/scripts/backup.sh" ]; then
    echo -e "${RED}❌ Backup script not found!${NC}"
    exit 1
fi

# Make backup script executable
chmod +x "$KIANA_DIR/scripts/backup.sh"

# Check if cron job already exists
CRON_EXISTS=$(crontab -l 2>/dev/null | grep -c "backup.sh" || true)

if [ "$CRON_EXISTS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Backup cron job already exists${NC}"
    echo "Current crontab:"
    crontab -l | grep backup.sh
else
    echo "Setting up daily backup at 2:00 AM..."
    
    # Create backup directory
    mkdir -p /backup/kiana
    
    # Add cron job
    (crontab -l 2>/dev/null; echo "0 2 * * * $KIANA_DIR/scripts/backup.sh >> /var/log/kiana-backup.log 2>&1") | crontab -
    
    echo -e "${GREEN}✅ Backup cron job created${NC}"
    echo "Schedule: Daily at 2:00 AM"
    echo "Log: /var/log/kiana-backup.log"
fi

# Test backup script
echo ""
echo "Testing backup script..."
if $KIANA_DIR/scripts/backup.sh; then
    echo -e "${GREEN}✅ Backup test successful${NC}"
else
    echo -e "${RED}❌ Backup test failed${NC}"
fi

echo ""

# ============================================
# 3. HEALTH-CHECK AKTIVIEREN
# ============================================
echo -e "${YELLOW}🏥 Step 3/3: Health-Check Activation${NC}"
echo ""

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is already running${NC}"
    
    # Show health status
    echo ""
    echo "Health Status:"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
    
else
    echo -e "${YELLOW}⚠️  Backend is not running${NC}"
    echo ""
    echo "To start backend:"
    echo "  Option 1 (Manual):"
    echo "    cd $KIANA_DIR"
    echo "    source .venv/bin/activate"
    echo "    uvicorn netapi.app:app --host 0.0.0.0 --port 8000"
    echo ""
    echo "  Option 2 (Systemd):"
    echo "    sudo systemctl start kiana"
    echo ""
    
    read -p "Start backend now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Starting backend..."
        cd "$KIANA_DIR"
        source .venv/bin/activate
        nohup uvicorn netapi.app:app --host 0.0.0.0 --port 8000 > /var/log/kiana.log 2>&1 &
        echo $! > /tmp/kiana.pid
        
        echo "Waiting for backend to start..."
        sleep 5
        
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Backend started successfully${NC}"
            echo "PID: $(cat /tmp/kiana.pid)"
            echo "Log: /var/log/kiana.log"
        else
            echo -e "${RED}❌ Backend failed to start${NC}"
            echo "Check logs: tail -f /var/log/kiana.log"
        fi
    fi
fi

echo ""

# ============================================
# SUMMARY
# ============================================
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Production Day 1 Setup Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""

echo "📋 Summary:"
echo ""
echo "1. 🔒 Firewall:"
if command -v ufw &> /dev/null; then
    echo "   ✅ Configured"
    echo "   Ports: 8000/tcp (API), 5353/udp (mDNS)"
else
    echo "   ⚠️  Not available"
fi

echo ""
echo "2. 💾 Backup:"
echo "   ✅ Cron job: Daily at 2:00 AM"
echo "   ✅ Script: $KIANA_DIR/scripts/backup.sh"
echo "   ✅ Log: /var/log/kiana-backup.log"

echo ""
echo "3. 🏥 Health-Check:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Active: http://localhost:8000/health"
else
    echo "   ⚠️  Backend not running"
fi

echo ""
echo "📊 Next Steps:"
echo "   • View crontab: crontab -l"
echo "   • Test backup: ./scripts/backup.sh"
echo "   • Check health: curl http://localhost:8000/health"
echo "   • View logs: tail -f /var/log/kiana.log"
echo ""
echo "🚀 Ready for Day 2: TURN + E2E-Tests"
echo ""
