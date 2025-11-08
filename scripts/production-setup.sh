#!/bin/bash
# KI_ana Production Setup Script

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 KI_ana Production Setup${NC}"
echo ""

# 1. Firewall
echo -e "${YELLOW}🔒 Configuring firewall...${NC}"
if command -v ufw &> /dev/null; then
    sudo ufw allow 8000/tcp
    sudo ufw allow 5353/udp
    echo -e "${GREEN}✅ Firewall configured${NC}"
else
    echo -e "${YELLOW}⚠️  UFW not available${NC}"
fi

# 2. HTTPS (optional)
echo -e "\n${YELLOW}🔐 HTTPS Configuration${NC}"
read -p "Enable HTTPS? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "HTTPS_ENABLED=true" >> .env
    echo -e "${GREEN}✅ HTTPS enabled in .env${NC}"
    echo -e "${YELLOW}⚠️  Don't forget to set SSL_CERT and SSL_KEY!${NC}"
fi

# 3. JWT Secret
echo -e "\n${YELLOW}🔑 Checking JWT_SECRET...${NC}"
if ! grep -q "JWT_SECRET=" .env || grep -q "JWT_SECRET=change-this" .env; then
    NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" .env
    echo -e "${GREEN}✅ New JWT_SECRET generated${NC}"
else
    echo -e "${GREEN}✅ JWT_SECRET already set${NC}"
fi

# 4. Key Permissions
echo -e "\n${YELLOW}🔐 Securing key permissions...${NC}"
chmod 600 system/keys/*_private.key 2>/dev/null || true
echo -e "${GREEN}✅ Key permissions secured${NC}"

# 5. Systemd Service
echo -e "\n${YELLOW}🔧 Systemd Service${NC}"
read -p "Install systemd service? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo tee /etc/systemd/system/kiana.service > /dev/null << EOF
[Unit]
Description=KI_ana OS
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/.venv/bin"
ExecStart=$(pwd)/.venv/bin/uvicorn netapi.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable kiana
    echo -e "${GREEN}✅ Systemd service installed${NC}"
    echo -e "${YELLOW}   Start with: sudo systemctl start kiana${NC}"
fi

echo ""
echo -e "${GREEN}✅ Production setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review .env configuration"
echo "  2. Start KI_ana: sudo systemctl start kiana"
echo "  3. Check status: sudo systemctl status kiana"
echo "  4. View logs: sudo journalctl -u kiana -f"
