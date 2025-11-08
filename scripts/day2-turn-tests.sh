#!/bin/bash
# KI_ana Day 2: TURN + E2E-Tests

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
                             
 Day 2: TURN + E2E-Tests
EOF
echo -e "${NC}"

echo -e "${GREEN}🌐 KI_ana Day 2: TURN + E2E-Tests${NC}"
echo ""

KIANA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIANA_DIR"

# ============================================
# 1. TURN SERVER STARTEN
# ============================================
echo -e "${YELLOW}🔄 Step 1/5: TURN Server Setup${NC}"
echo ""

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not installed${NC}"
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "Checking TURN configuration..."
if [ -f "$KIANA_DIR/infra/turn/turnserver.conf" ]; then
    echo -e "${GREEN}✅ TURN config found${NC}"
else
    echo -e "${YELLOW}⚠️  TURN config not found, using defaults${NC}"
fi

echo ""
echo "Starting TURN server..."
if [ -f "$KIANA_DIR/infra/turn/docker-compose.turn.yml" ]; then
    cd "$KIANA_DIR/infra/turn"
    docker-compose -f docker-compose.turn.yml up -d
    
    echo "Waiting for TURN server to start..."
    sleep 5
    
    if docker ps | grep -q "kiana-turn"; then
        echo -e "${GREEN}✅ TURN server started${NC}"
        docker ps | grep kiana-turn
    else
        echo -e "${RED}❌ TURN server failed to start${NC}"
        docker logs kiana-turn 2>&1 | tail -20
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  TURN docker-compose not found${NC}"
    echo "Skipping TURN server (optional for LAN testing)"
fi

cd "$KIANA_DIR"
echo ""

# ============================================
# 2. MULTI-NETZ-TEST (LAN)
# ============================================
echo -e "${YELLOW}🧪 Step 2/5: Multi-Device Test (LAN)${NC}"
echo ""

echo "Setting up test cluster..."
if [ -f "$KIANA_DIR/scripts/setup-cluster.sh" ]; then
    # Setup cluster (3 peers)
    NUM_PEERS=3 "$KIANA_DIR/scripts/setup-cluster.sh"
    
    echo ""
    echo "Starting cluster..."
    "$KIANA_DIR/cluster/manage.sh" start
    
    echo "Waiting for peers to start..."
    sleep 10
    
    echo ""
    echo "Testing cluster..."
    "$KIANA_DIR/cluster/test.sh"
    
    echo ""
    echo -e "${GREEN}✅ Multi-device test complete${NC}"
else
    echo -e "${YELLOW}⚠️  Cluster setup script not found${NC}"
    echo "Running manual P2P tests..."
    cd "$KIANA_DIR"
    source .venv/bin/activate
    python tests/test_p2p_messaging.py
fi

echo ""

# ============================================
# 3. LATENZ-MESSUNG
# ============================================
echo -e "${YELLOW}📊 Step 3/5: Latency Measurements${NC}"
echo ""

echo "Measuring local latency..."

# Test 1: Health endpoint
echo "1. Health endpoint latency:"
for i in {1..5}; do
    START=$(date +%s%N)
    curl -s http://localhost:8000/health > /dev/null 2>&1
    END=$(date +%s%N)
    LATENCY=$(( (END - START) / 1000000 ))
    echo "   Attempt $i: ${LATENCY}ms"
done

echo ""
echo "2. P2P connection latency:"
# Test cluster peers
for port in 8000 8001 8002; do
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        START=$(date +%s%N)
        curl -s http://localhost:$port/api/p2p/peers > /dev/null 2>&1
        END=$(date +%s%N)
        LATENCY=$(( (END - START) / 1000000 ))
        echo "   Peer (port $port): ${LATENCY}ms"
    fi
done

echo ""
echo -e "${GREEN}✅ Latency measurements complete${NC}"

echo ""

# ============================================
# 4. WAN-TEST INSTRUCTIONS
# ============================================
echo -e "${YELLOW}🌍 Step 4/5: WAN Test Instructions${NC}"
echo ""

echo "For WAN testing (different networks):"
echo ""
echo "1. Mobile Hotspot Test:"
echo "   • Connect Device A to Home WiFi"
echo "   • Connect Device B to Mobile Hotspot"
echo "   • Start KI_ana on both devices"
echo "   • Check P2P connection"
echo ""
echo "2. CGNAT Test:"
echo "   • Connect from Office network"
echo "   • Connect from Home network"
echo "   • Verify TURN relay is used"
echo ""
echo "3. Cloud Test:"
echo "   • Deploy to VPS (DigitalOcean, AWS, etc.)"
echo "   • Connect from local device"
echo "   • Test cross-region latency"
echo ""
echo "Commands for remote testing:"
echo "  ssh user@remote-host 'curl http://localhost:8000/health'"
echo "  ssh user@remote-host 'curl http://localhost:8000/api/p2p/peers'"
echo ""

# ============================================
# 5. CLEANUP & SUMMARY
# ============================================
echo -e "${YELLOW}🧹 Step 5/5: Cleanup${NC}"
echo ""

read -p "Stop test cluster? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$KIANA_DIR/cluster/manage.sh" ]; then
        "$KIANA_DIR/cluster/manage.sh" stop
        echo -e "${GREEN}✅ Cluster stopped${NC}"
    fi
fi

echo ""
read -p "Stop TURN server? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$KIANA_DIR/infra/turn/docker-compose.turn.yml" ]; then
        cd "$KIANA_DIR/infra/turn"
        docker-compose -f docker-compose.turn.yml down
        echo -e "${GREEN}✅ TURN server stopped${NC}"
    fi
fi

cd "$KIANA_DIR"

# ============================================
# SUMMARY
# ============================================
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Day 2 Tests Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""

echo "📋 Summary:"
echo ""
echo "1. 🔄 TURN Server:"
if docker ps | grep -q "kiana-turn"; then
    echo "   ✅ Running"
else
    echo "   ⚠️  Not running (optional for LAN)"
fi

echo ""
echo "2. 🧪 Multi-Device Test:"
echo "   ✅ LAN test completed"
echo "   ⚠️  WAN test requires manual setup"

echo ""
echo "3. 📊 Latency:"
echo "   ✅ Local measurements completed"
echo "   ℹ️  Check output above for results"

echo ""
echo "📝 Next Steps:"
echo "   • Review latency results"
echo "   • Test WAN scenarios (manual)"
echo "   • Document any issues"
echo "   • Proceed to Day 3: Telemetry + Docs"
echo ""
echo "🚀 Ready for Day 3!"
echo ""
