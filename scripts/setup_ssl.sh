#!/bin/bash
# SSL/TLS Setup Script für ki-ana.at
# Generiert Let's Encrypt Zertifikate mit Certbot

DOMAIN="ki-ana.at"
WWW_DOMAIN="www.ki-ana.at"
EMAIL="admin@ki-ana.at"  # Bitte anpassen

echo "🔒 SSL/TLS Setup für ${DOMAIN}..."

# Check ob Certbot läuft
if ! docker-compose ps certbot | grep -q "Up\|running"; then
    echo "⚠️  Certbot Container nicht aktiv"
fi

# Generiere Zertifikate
echo "📜 Generiere Let's Encrypt Zertifikate..."
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email ${EMAIL} \
    --agree-tos \
    --no-eff-email \
    -d ${DOMAIN} \
    -d ${WWW_DOMAIN}

if [ $? -eq 0 ]; then
    echo "✅ Zertifikate erfolgreich generiert!"
    
    # Aktiviere SSL Nginx Config
    echo "🔧 Aktiviere SSL Konfiguration..."
    if [ -f "infra/nginx/ki_ana.conf.bak" ]; then
        mv infra/nginx/default.conf infra/nginx/default.conf.http_only
        mv infra/nginx/ki_ana.conf.bak infra/nginx/ki_ana.conf
        echo "✅ SSL Config wiederhergestellt"
    fi
    
    # Restart Nginx
    echo "🔄 Restart Nginx..."
    docker-compose restart nginx
    
    # Setup Certbot Renewal
    echo "⏰ Setup Auto-Renewal..."
    docker-compose run --rm certbot renew --dry-run
    
    echo "✅ SSL Setup abgeschlossen!"
    echo "🌐 HTTPS sollte jetzt auf https://${DOMAIN} verfügbar sein"
else
    echo "❌ Zertifikat-Generierung fehlgeschlagen"
    echo "   Prüfe:"
    echo "   1. Domain DNS zeigt auf diesen Server (152.53.128.59)"
    echo "   2. Port 80 ist erreichbar"
    echo "   3. Nginx läuft und liefert /.well-known/acme-challenge/"
    exit 1
fi
