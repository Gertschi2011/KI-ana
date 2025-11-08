#!/bin/bash
# KI_ana Test Cluster Setup
# Erstellt 3-5 Peer Test-Netzwerk

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
NUM_PEERS="${NUM_PEERS:-3}"
BASE_PORT="${BASE_PORT:-8000}"
KIANA_DIR="${KIANA_DIR:-$HOME/ki_ana}"

echo -e "${BLUE}"
cat << "EOF"
  _  ___   _                 
 | |/ (_) / \   _ __   __ _ 
 | ' /| |/ _ \ | '_ \ / _` |
 | . \| / ___ \| | | | (_| |
 |_|\_\_/_/   \_\_| |_|\__,_|
                             
 Test Cluster Setup
EOF
echo -e "${NC}"

echo -e "${GREEN}🌐 KI_ana Test Cluster Setup${NC}"
echo "Number of Peers: ${NUM_PEERS}"
echo "Base Port: ${BASE_PORT}"
echo ""

# Check if KI_ana is installed
if [ ! -d "${KIANA_DIR}" ]; then
    echo -e "${RED}❌ KI_ana not found at ${KIANA_DIR}${NC}"
    echo "Install KI_ana first: curl -sSL https://get.kiana.ai | bash"
    exit 1
fi

# Create cluster directory
CLUSTER_DIR="${KIANA_DIR}/cluster"
mkdir -p "${CLUSTER_DIR}"

echo -e "${YELLOW}📁 Creating peer directories...${NC}"

# Create peer directories
for i in $(seq 1 ${NUM_PEERS}); do
    PEER_DIR="${CLUSTER_DIR}/peer${i}"
    PORT=$((BASE_PORT + i - 1))
    
    echo "Creating peer${i} (port ${PORT})..."
    
    # Create peer directory structure
    mkdir -p "${PEER_DIR}/data/chroma"
    mkdir -p "${PEER_DIR}/data/message_queue"
    mkdir -p "${PEER_DIR}/system/keys"
    
    # Copy system files
    cp -r "${KIANA_DIR}/system"/*.py "${PEER_DIR}/system/" 2>/dev/null || true
    cp -r "${KIANA_DIR}/netapi" "${PEER_DIR}/" 2>/dev/null || true
    
    # Create .env for peer
    cat > "${PEER_DIR}/.env" << ENVEOF
# Peer ${i} Configuration
SERVER_MODE=0
P2P_PORT=${PORT}
P2P_DISCOVERY=true
ENCRYPTION_ENABLED=true
JWT_SECRET=peer${i}-secret-key-$(date +%s)
ENVEOF
    
    # Create start script
    cat > "${PEER_DIR}/start.sh" << STARTEOF
#!/bin/bash
cd "${PEER_DIR}"
source "${KIANA_DIR}/.venv/bin/activate"
export PYTHONPATH="${KIANA_DIR}:${PEER_DIR}"
uvicorn netapi.app:app --host 0.0.0.0 --port ${PORT}
STARTEOF
    
    chmod +x "${PEER_DIR}/start.sh"
    
    echo "✅ peer${i} created"
done

# Create cluster management script
cat > "${CLUSTER_DIR}/manage.sh" << 'MANAGEEOF'
#!/bin/bash

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NUM_PEERS=$(ls -d ${CLUSTER_DIR}/peer* 2>/dev/null | wc -l)

case "$1" in
    start)
        echo "🚀 Starting ${NUM_PEERS} peers..."
        for peer_dir in ${CLUSTER_DIR}/peer*; do
            peer_name=$(basename ${peer_dir})
            echo "Starting ${peer_name}..."
            cd ${peer_dir}
            ./start.sh > ${peer_dir}/output.log 2>&1 &
            echo $! > ${peer_dir}/pid
            echo "✅ ${peer_name} started (PID: $(cat ${peer_dir}/pid))"
        done
        echo "✅ All peers started"
        ;;
    
    stop)
        echo "🛑 Stopping ${NUM_PEERS} peers..."
        for peer_dir in ${CLUSTER_DIR}/peer*; do
            peer_name=$(basename ${peer_dir})
            if [ -f ${peer_dir}/pid ]; then
                pid=$(cat ${peer_dir}/pid)
                kill ${pid} 2>/dev/null || true
                rm ${peer_dir}/pid
                echo "✅ ${peer_name} stopped"
            fi
        done
        echo "✅ All peers stopped"
        ;;
    
    status)
        echo "📊 Cluster Status:"
        for peer_dir in ${CLUSTER_DIR}/peer*; do
            peer_name=$(basename ${peer_dir})
            if [ -f ${peer_dir}/pid ]; then
                pid=$(cat ${peer_dir}/pid)
                if ps -p ${pid} > /dev/null 2>&1; then
                    port=$(grep P2P_PORT ${peer_dir}/.env | cut -d'=' -f2)
                    echo "  ✅ ${peer_name} (PID: ${pid}, Port: ${port})"
                else
                    echo "  ❌ ${peer_name} (not running)"
                    rm ${peer_dir}/pid
                fi
            else
                echo "  ⚪ ${peer_name} (not started)"
            fi
        done
        ;;
    
    logs)
        peer=${2:-peer1}
        if [ -f "${CLUSTER_DIR}/${peer}/output.log" ]; then
            tail -f "${CLUSTER_DIR}/${peer}/output.log"
        else
            echo "❌ No logs for ${peer}"
        fi
        ;;
    
    clean)
        echo "🧹 Cleaning cluster data..."
        read -p "This will delete all peer data. Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf ${CLUSTER_DIR}/peer*/data/*
            echo "✅ Cluster data cleaned"
        fi
        ;;
    
    *)
        echo "Usage: $0 {start|stop|status|logs [peer]|clean}"
        exit 1
        ;;
esac
MANAGEEOF

chmod +x "${CLUSTER_DIR}/manage.sh"

# Create test script
cat > "${CLUSTER_DIR}/test.sh" << 'TESTEOF'
#!/bin/bash

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_PORT=8000

echo "🧪 Testing Cluster..."
echo ""

# Check health of all peers
echo "1️⃣ Health Checks:"
for i in 1 2 3; do
    port=$((BASE_PORT + i - 1))
    if curl -s http://localhost:${port}/health > /dev/null 2>&1; then
        echo "  ✅ Peer ${i} (port ${port}): healthy"
    else
        echo "  ❌ Peer ${i} (port ${port}): not responding"
    fi
done

echo ""
echo "2️⃣ Discovery:"
for i in 1 2 3; do
    port=$((BASE_PORT + i - 1))
    devices=$(curl -s http://localhost:${port}/api/discovery/devices 2>/dev/null | jq -r '.devices | length' 2>/dev/null || echo "0")
    echo "  Peer ${i} discovered: ${devices} device(s)"
done

echo ""
echo "3️⃣ P2P Connections:"
for i in 1 2 3; do
    port=$((BASE_PORT + i - 1))
    peers=$(curl -s http://localhost:${port}/api/p2p/peers 2>/dev/null | jq -r '.peers | length' 2>/dev/null || echo "0")
    echo "  Peer ${i} connected: ${peers} peer(s)"
done

echo ""
echo "✅ Cluster test complete!"
TESTEOF

chmod +x "${CLUSTER_DIR}/test.sh"

# Summary
echo ""
echo -e "${GREEN}✅ Test Cluster Setup Complete!${NC}"
echo ""
echo "📍 Cluster Directory: ${CLUSTER_DIR}"
echo "🔢 Number of Peers: ${NUM_PEERS}"
echo ""
echo "🚀 To start cluster:"
echo "   ${CLUSTER_DIR}/manage.sh start"
echo ""
echo "📊 To check status:"
echo "   ${CLUSTER_DIR}/manage.sh status"
echo ""
echo "🧪 To test cluster:"
echo "   ${CLUSTER_DIR}/test.sh"
echo ""
echo "🛑 To stop cluster:"
echo "   ${CLUSTER_DIR}/manage.sh stop"
echo ""
echo "📝 To view logs:"
echo "   ${CLUSTER_DIR}/manage.sh logs peer1"
echo ""
echo "🧹 To clean data:"
echo "   ${CLUSTER_DIR}/manage.sh clean"
