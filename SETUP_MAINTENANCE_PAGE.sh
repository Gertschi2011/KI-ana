#!/bin/bash
# =====================================
# Setup Maintenance Page
# =====================================
# Quick script to enable maintenance mode
# =====================================

echo "🔧 Setting up Maintenance Page..."
echo ""

# Check if running on server
if [ ! -f "/etc/nginx/sites-available/ki-ana.at" ]; then
    echo "⚠️  This script should run on ki-ana.at server"
    echo ""
    echo "Run these commands on the server:"
    echo "  scp maintenance.html kiana@ki-ana.at:/var/www/html/"
    echo "  ssh kiana@ki-ana.at"
    echo "  sudo nano /etc/nginx/sites-available/ki-ana.at"
    echo ""
    exit 1
fi

# Create maintenance directory
sudo mkdir -p /var/www/html/maintenance
echo "✅ Created /var/www/html/maintenance"

# Copy maintenance.html
if [ -f "/home/kiana/maintenance.html" ]; then
    sudo cp /home/kiana/maintenance.html /var/www/html/maintenance/index.html
    echo "✅ Copied maintenance.html"
else
    echo "❌ maintenance.html not found in /home/kiana/"
    exit 1
fi

# Set permissions
sudo chown -R www-data:www-data /var/www/html/maintenance
sudo chmod -R 755 /var/www/html/maintenance
echo "✅ Set permissions"

# Backup current nginx config
sudo cp /etc/nginx/sites-available/ki-ana.at /etc/nginx/sites-available/ki-ana.at.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backed up nginx config"

# Create maintenance nginx config
cat << 'EOF' | sudo tee /etc/nginx/sites-available/ki-ana.at.maintenance
server {
    listen 80;
    listen [::]:80;
    server_name ki-ana.at www.ki-ana.at;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ki-ana.at www.ki-ana.at;

    # SSL Configuration (keep existing certificates)
    ssl_certificate /etc/letsencrypt/live/ki-ana.at/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ki-ana.at/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;

    # Root directory for maintenance page
    root /var/www/html/maintenance;
    index index.html;

    # Serve maintenance page for all requests
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache control for maintenance page
    location ~* \.(html)$ {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0";
    }

    # Logging
    access_log /var/log/nginx/ki-ana-maintenance-access.log;
    error_log /var/log/nginx/ki-ana-maintenance-error.log;
}
EOF

echo "✅ Created maintenance nginx config"

# Enable maintenance mode
sudo ln -sf /etc/nginx/sites-available/ki-ana.at.maintenance /etc/nginx/sites-enabled/ki-ana.at
echo "✅ Enabled maintenance config"

# Test nginx config
echo ""
echo "Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Nginx config is valid"
    echo ""
    read -p "Reload nginx to enable maintenance mode? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl reload nginx
        echo ""
        echo "✅ Nginx reloaded - Maintenance mode is now ACTIVE!"
        echo ""
        echo "Test it: curl https://ki-ana.at/"
        echo ""
        echo "To restore normal mode later:"
        echo "  sudo ln -sf /etc/nginx/sites-available/ki-ana.at /etc/nginx/sites-enabled/ki-ana.at"
        echo "  sudo systemctl reload nginx"
    else
        echo ""
        echo "⚠️  Nginx not reloaded. Run manually:"
        echo "  sudo systemctl reload nginx"
    fi
else
    echo ""
    echo "❌ Nginx config has errors!"
    echo "Check the config manually"
fi

echo ""
echo "======================================"
echo "Maintenance Page Setup Complete!"
echo "======================================"
echo ""
echo "Backup location:"
echo "  /etc/nginx/sites-available/ki-ana.at.backup.*"
echo ""
