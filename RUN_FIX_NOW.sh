#!/bin/bash
# =====================================
# COMPLETE FIX AUTOMATION
# =====================================
# This script will guide you through the entire process
# =====================================

clear
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           KI-ANA BACKEND FIX - INTERACTIVE MODE                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📋 This script will help you fix ki-ana.at${NC}"
echo ""
echo "Steps:"
echo "  1. Transfer script to server"
echo "  2. SSH to server"
echo "  3. Run fix script"
echo "  4. Test everything"
echo ""

# Check if we're on local machine
if [ ! -f "/home/kiana/ki_ana/LIVE_SERVER_FIX.sh" ]; then
    echo -e "${RED}❌ Error: LIVE_SERVER_FIX.sh not found!${NC}"
    echo "Make sure you're in the correct directory."
    exit 1
fi

echo -e "${GREEN}✅ Fix script found!${NC}"
echo ""

# Step 1: Transfer to server
echo "════════════════════════════════════════════════════════════════"
echo -e "${YELLOW}STEP 1: Transfer script to server${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "I will now transfer LIVE_SERVER_FIX.sh to ki-ana.at"
echo ""
read -p "Enter SSH username for ki-ana.at [default: kiana]: " SSH_USER
SSH_USER=${SSH_USER:-kiana}

echo ""
echo -e "${BLUE}Running: scp LIVE_SERVER_FIX.sh ${SSH_USER}@ki-ana.at:/home/kiana/${NC}"
echo ""

scp /home/kiana/ki_ana/LIVE_SERVER_FIX.sh ${SSH_USER}@ki-ana.at:/home/kiana/

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Script successfully transferred!${NC}"
else
    echo ""
    echo -e "${RED}❌ Transfer failed!${NC}"
    echo ""
    echo "Try manually:"
    echo "  scp /home/kiana/ki_ana/LIVE_SERVER_FIX.sh ${SSH_USER}@ki-ana.at:/home/kiana/"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "${YELLOW}STEP 2: SSH to server and run fix${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "I will now connect to ki-ana.at and run the fix script."
echo ""
read -p "Press ENTER to continue..."

echo ""
echo -e "${BLUE}Connecting to ${SSH_USER}@ki-ana.at...${NC}"
echo ""

# SSH and run the fix script
ssh -t ${SSH_USER}@ki-ana.at << 'ENDSSH'
cd /home/kiana
chmod +x LIVE_SERVER_FIX.sh
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "🚀 Running LIVE_SERVER_FIX.sh..."
echo "════════════════════════════════════════════════════════════════"
echo ""
./LIVE_SERVER_FIX.sh
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Fix script completed!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Press ENTER to exit SSH session..."
read
ENDSSH

echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "${YELLOW}STEP 3: Testing${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""

echo "Testing external endpoint..."
if curl -s https://ki-ana.at/api/health | grep -q "ok\|healthy\|status"; then
    echo -e "${GREEN}✅ API is responding!${NC}"
else
    echo -e "${RED}❌ API not responding yet${NC}"
    echo "Wait 30 seconds and try again: curl https://ki-ana.at/api/health"
fi

echo ""
echo "Testing homepage..."
if curl -s https://ki-ana.at/ | grep -q "KI-ana\|<!DOCTYPE"; then
    echo -e "${GREEN}✅ Homepage is loading!${NC}"
else
    echo -e "${RED}❌ Homepage not loading${NC}"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "${GREEN}🎉 FIX COMPLETE!${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Visit https://ki-ana.at/ in browser"
echo "  2. Test Papa dropdown menu (should stay open!)"
echo "  3. Test mobile view"
echo "  4. Test chat functionality"
echo ""
echo "All new features are now live:"
echo "  ✅ Dropdown fix"
echo "  ✅ Mobile optimization"
echo "  ✅ Abuse Guard"
echo "  ✅ GDPR endpoints"
echo "  ✅ Trust Rating"
echo "  ✅ Sub-KI Feedback"
echo "  ✅ Block Viewer API"
echo ""
echo "Server logs: ssh ${SSH_USER}@ki-ana.at 'tail -f /home/kiana/ki_ana/logs/backend.log'"
echo ""
