#!/bin/bash
# Firewall Setup Script
# Run with: sudo bash setup_firewall.sh

echo "🔒 Setting up UFW Firewall..."
echo "================================"

# Set defaults
echo "1. Setting defaults..."
ufw default deny incoming
ufw default allow outgoing

# Allow essential ports
echo "2. Allowing essential ports..."
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Enable firewall
echo "3. Enabling firewall..."
ufw --force enable

# Show status
echo ""
echo "================================"
echo "✅ Firewall Status:"
ufw status numbered

echo ""
echo "================================"
echo "✅ Firewall is active!"
echo "   Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)"
echo "   All other ports: BLOCKED"
