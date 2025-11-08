#!/bin/bash
# KI_ana Security Check Script

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

KIANA_DIR="${KIANA_DIR:-$HOME/ki_ana}"

echo -e "${GREEN}🔒 KI_ana Security Check${NC}"
echo ""

# 1. Check key permissions
echo -e "${YELLOW}1️⃣ Checking key permissions...${NC}"
if [ -d "${KIANA_DIR}/system/keys" ]; then
    INSECURE_KEYS=$(find "${KIANA_DIR}/system/keys" -name "*_private.key" ! -perm 600)
    if [ -z "$INSECURE_KEYS" ]; then
        echo -e "  ${GREEN}✅ All private keys have correct permissions (600)${NC}"
    else
        echo -e "  ${RED}❌ Insecure key permissions found:${NC}"
        echo "$INSECURE_KEYS"
        echo -e "  ${YELLOW}Fix with: chmod 600 system/keys/*_private.key${NC}"
        exit 1
    fi
else
    echo -e "  ${YELLOW}⚠️  Keys directory not found${NC}"
fi

# 2. Check JWT_SECRET
echo -e "\n${YELLOW}2️⃣ Checking JWT_SECRET...${NC}"
if [ -f "${KIANA_DIR}/.env" ]; then
    JWT_SECRET=$(grep JWT_SECRET "${KIANA_DIR}/.env" | cut -d'=' -f2)
    if [ "$JWT_SECRET" = "change-this-secret-key" ] || [ -z "$JWT_SECRET" ]; then
        echo -e "  ${RED}❌ JWT_SECRET not set or using default!${NC}"
        echo -e "  ${YELLOW}Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"${NC}"
        exit 1
    else
        echo -e "  ${GREEN}✅ JWT_SECRET is set${NC}"
    fi
else
    echo -e "  ${RED}❌ .env file not found${NC}"
    exit 1
fi

# 3. Check Trust-Gate
echo -e "\n${YELLOW}3️⃣ Checking Trust-Gate configuration...${NC}"
MIN_TRUST=$(grep MIN_TRUST_LEVEL "${KIANA_DIR}/.env" 2>/dev/null | cut -d'=' -f2 || echo "0.5")
if (( $(echo "$MIN_TRUST >= 0.5" | bc -l) )); then
    echo -e "  ${GREEN}✅ Trust-Gate ≥0.5 (${MIN_TRUST})${NC}"
else
    echo -e "  ${YELLOW}⚠️  Trust-Gate <0.5 (${MIN_TRUST})${NC}"
fi

# 4. Check firewall
echo -e "\n${YELLOW}4️⃣ Checking firewall...${NC}"
if command -v ufw &> /dev/null; then
    if sudo ufw status | grep -q "8000.*ALLOW"; then
        echo -e "  ${GREEN}✅ Port 8000 allowed${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Port 8000 not in firewall rules${NC}"
        echo -e "  ${YELLOW}Add with: sudo ufw allow 8000/tcp${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠️  UFW not installed${NC}"
fi

# 5. Check HTTPS
echo -e "\n${YELLOW}5️⃣ Checking HTTPS configuration...${NC}"
if grep -q "HTTPS_ENABLED=true" "${KIANA_DIR}/.env" 2>/dev/null; then
    echo -e "  ${GREEN}✅ HTTPS enabled${NC}"
else
    echo -e "  ${YELLOW}⚠️  HTTPS not enabled (recommended for production)${NC}"
fi

# 6. Test emergency override
echo -e "\n${YELLOW}6️⃣ Testing emergency override...${NC}"
if [ -f "${KIANA_DIR}/tests/test_emergency_override.py" ]; then
    cd "${KIANA_DIR}"
    if source .venv/bin/activate && python tests/test_emergency_override.py > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Emergency override test passed${NC}"
    else
        echo -e "  ${RED}❌ Emergency override test failed${NC}"
        exit 1
    fi
else
    echo -e "  ${YELLOW}⚠️  Emergency override test not found${NC}"
fi

echo ""
echo -e "${GREEN}✅ Security check complete!${NC}"
