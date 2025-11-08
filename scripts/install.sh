#!/bin/bash
# KI_ana One-Line Installer
# curl -sSL https://get.kiana.ai | bash

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="${INSTALL_DIR:-$HOME/ki_ana}"
REPO_URL="https://github.com/your-org/ki_ana.git"
BRANCH="${BRANCH:-main}"

echo -e "${BLUE}"
cat << "EOF"
  _  ___   _                 
 | |/ (_) / \   _ __   __ _ 
 | ' /| |/ _ \ | '_ \ / _` |
 | . \| / ___ \| | | | (_| |
 |_|\_\_/_/   \_\_| |_|\__,_|
                             
 Dezentrales P2P KI-System
EOF
echo -e "${NC}"

echo -e "${GREEN}🚀 KI_ana Installer${NC}"
echo "Version: 2.0"
echo "Installation Directory: ${INSTALL_DIR}"
echo ""

# Check system requirements
echo -e "${YELLOW}📋 Checking system requirements...${NC}"

# Check OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "✅ OS: Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "✅ OS: macOS"
else
    echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✅ Python: $PYTHON_VERSION"
    
    # Check Python version (need 3.10+)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        echo -e "${RED}❌ Python 3.10+ required (found $PYTHON_VERSION)${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Python 3 not found${NC}"
    echo "Install Python 3.10+:"
    echo "  Ubuntu/Debian: sudo apt install python3.10 python3.10-venv"
    echo "  macOS: brew install python@3.10"
    exit 1
fi

# Check pip
if command -v pip3 &> /dev/null; then
    echo "✅ pip3: $(pip3 --version | cut -d' ' -f2)"
else
    echo -e "${YELLOW}⚠️  pip3 not found, will install${NC}"
fi

# Check git
if command -v git &> /dev/null; then
    echo "✅ git: $(git --version | cut -d' ' -f3)"
else
    echo -e "${RED}❌ git not found${NC}"
    echo "Install git:"
    echo "  Ubuntu/Debian: sudo apt install git"
    echo "  macOS: brew install git"
    exit 1
fi

# Check disk space (need at least 5GB)
AVAILABLE_SPACE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 5 ]; then
    echo -e "${YELLOW}⚠️  Low disk space: ${AVAILABLE_SPACE}GB available (5GB+ recommended)${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Disk space: ${AVAILABLE_SPACE}GB available"
fi

echo ""

# Clone or update repository
if [ -d "${INSTALL_DIR}" ]; then
    echo -e "${YELLOW}📂 KI_ana directory exists${NC}"
    read -p "Update existing installation? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🔄 Updating KI_ana...${NC}"
        cd "${INSTALL_DIR}"
        git pull origin ${BRANCH}
        echo "✅ Updated"
    fi
else
    echo -e "${YELLOW}📥 Cloning KI_ana repository...${NC}"
    git clone -b ${BRANCH} ${REPO_URL} "${INSTALL_DIR}"
    echo "✅ Cloned"
fi

cd "${INSTALL_DIR}"

# Create virtual environment
echo -e "${YELLOW}🐍 Creating virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment exists"
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}📦 Upgrading pip...${NC}"
pip install --upgrade pip > /dev/null 2>&1
echo "✅ pip upgraded"

# Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
echo "   This may take a few minutes..."

pip install -r requirements.txt > /dev/null 2>&1
echo "✅ Core dependencies installed"

# Install Phase 2 & 3 dependencies
echo -e "${YELLOW}📦 Installing Phase 2 & 3 dependencies...${NC}"
pip install sentence-transformers chromadb qdrant-client > /dev/null 2>&1
pip install openai-whisper piper-tts > /dev/null 2>&1
pip install zeroconf aiortc pynacl > /dev/null 2>&1
pip install psutil > /dev/null 2>&1
echo "✅ All dependencies installed"

# Create data directories
echo -e "${YELLOW}📁 Creating data directories...${NC}"
mkdir -p data/chroma data/message_queue system/keys
echo "✅ Directories created"

# Create .env file if not exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚙️  Creating configuration file...${NC}"
    cat > .env << 'ENVEOF'
# KI_ana Configuration

# Server Mode
SERVER_MODE=0  # 0=SQLite, 1=PostgreSQL

# Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333

# LLM
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2

# P2P Network
P2P_PORT=8000
P2P_DISCOVERY=true

# Security
JWT_SECRET=change-this-secret-key
ENCRYPTION_ENABLED=true
ENVEOF
    echo "✅ Configuration created (.env)"
    echo "   ⚠️  Please edit .env and set JWT_SECRET!"
else
    echo "✅ Configuration exists"
fi

# Test installation
echo -e "${YELLOW}🧪 Testing installation...${NC}"
if python -c "import sentence_transformers, chromadb, whisper, nacl" 2>/dev/null; then
    echo "✅ All modules imported successfully"
else
    echo -e "${YELLOW}⚠️  Some modules failed to import (may be normal)${NC}"
fi

# Create systemd service (optional)
if [ "$OS" == "linux" ] && command -v systemctl &> /dev/null; then
    echo ""
    read -p "Install systemd service? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🔧 Creating systemd service...${NC}"
        sudo tee /etc/systemd/system/kiana.service > /dev/null << SERVICEEOF
[Unit]
Description=KI_ana P2P AI System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${INSTALL_DIR}/.venv/bin"
ExecStart=${INSTALL_DIR}/.venv/bin/uvicorn netapi.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable kiana
        echo "✅ Systemd service created"
        echo "   Start with: sudo systemctl start kiana"
    fi
fi

# Summary
echo ""
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo ""
echo "📍 Installation Directory: ${INSTALL_DIR}"
echo ""
echo "🚀 To start KI_ana:"
echo "   cd ${INSTALL_DIR}"
echo "   source .venv/bin/activate"
echo "   uvicorn netapi.app:app --host 0.0.0.0 --port 8000"
echo ""
echo "🌐 Dashboard:"
echo "   http://localhost:8000/dashboard.html"
echo ""
echo "📚 Documentation:"
echo "   ${INSTALL_DIR}/README.md"
echo "   ${INSTALL_DIR}/DEPLOYMENT_GUIDE.md"
echo ""
echo "💡 Next Steps:"
echo "   1. Edit .env file (set JWT_SECRET)"
echo "   2. Start KI_ana"
echo "   3. Open dashboard in browser"
echo ""
echo -e "${BLUE}Welcome to KI_ana 2.0! 🤖${NC}"
