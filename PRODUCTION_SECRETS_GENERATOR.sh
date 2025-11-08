#!/bin/bash
# =====================================
# Production Secrets Generator
# =====================================
# Generates secure random secrets for .env.production
# Run before deployment!
# =====================================

set -e

echo "🔐 KI-ANA Production Secrets Generator"
echo "======================================"
echo ""

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo "❌ Error: .env.production not found!"
    echo "Please create it first from the template."
    exit 1
fi

# Create backup
BACKUP_FILE=".env.production.backup.$(date +%Y%m%d_%H%M%S)"
cp .env.production "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"
echo ""

# Generate secrets
echo "🔑 Generating secure secrets..."
echo ""

JWT_SECRET=$(openssl rand -hex 32)
KI_SECRET=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
MINIO_ACCESS=$(openssl rand -hex 16)
MINIO_SECRET=$(openssl rand -hex 32)
MINIO_ROOT_USER="kiana_admin"
MINIO_ROOT_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
EMERGENCY_KEY=$(echo -n "emergency_override_$(date +%s)" | sha256sum | cut -d' ' -f1)

echo "Generated Secrets:"
echo "=================="
echo "JWT_SECRET:        $JWT_SECRET"
echo "KI_SECRET:         $KI_SECRET"
echo "DB_PASSWORD:       $DB_PASSWORD"
echo "MINIO_ACCESS:      $MINIO_ACCESS"
echo "MINIO_SECRET:      $MINIO_SECRET"
echo "MINIO_ROOT_USER:   $MINIO_ROOT_USER"
echo "MINIO_ROOT_PASS:   $MINIO_ROOT_PASSWORD"
echo "EMERGENCY_KEY:     $EMERGENCY_KEY"
echo ""

# Ask for confirmation
read -p "Apply these secrets to .env.production? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled. Backup preserved at: $BACKUP_FILE"
    exit 0
fi

# Apply secrets
echo "📝 Applying secrets to .env.production..."

sed -i "s|JWT_SECRET=CHANGE_THIS_GENERATE_NEW_JWT_SECRET_WITH_OPENSSL_RAND_HEX_32|JWT_SECRET=$JWT_SECRET|g" .env.production
sed -i "s|KI_SECRET=CHANGE_THIS_GENERATE_NEW_SECRET_KEY_WITH_OPENSSL_RAND_HEX_32|KI_SECRET=$KI_SECRET|g" .env.production
sed -i "s|POSTGRES_PASSWORD=CHANGE_THIS_SECURE_PASSWORD|POSTGRES_PASSWORD=$DB_PASSWORD|g" .env.production
sed -i "s|DATABASE_URL=postgresql+psycopg2://kiana:CHANGE_THIS_SECURE_PASSWORD@localhost:5432/kiana|DATABASE_URL=postgresql+psycopg2://kiana:$DB_PASSWORD@localhost:5432/kiana|g" .env.production
sed -i "s|MINIO_ACCESS_KEY=CHANGE_THIS_MINIO_ACCESS_KEY|MINIO_ACCESS_KEY=$MINIO_ACCESS|g" .env.production
sed -i "s|MINIO_SECRET_KEY=CHANGE_THIS_MINIO_SECRET_KEY_SECURE_PASSWORD|MINIO_SECRET_KEY=$MINIO_SECRET|g" .env.production
sed -i "s|MINIO_ROOT_USER=CHANGE_THIS_MINIO_ROOT_USER|MINIO_ROOT_USER=$MINIO_ROOT_USER|g" .env.production
sed -i "s|MINIO_ROOT_PASSWORD=CHANGE_THIS_MINIO_ROOT_PASSWORD|MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD|g" .env.production
sed -i "s|EMERGENCY_OVERRIDE_SHA256=CHANGE_THIS_GENERATE_NEW_EMERGENCY_KEY|EMERGENCY_OVERRIDE_SHA256=$EMERGENCY_KEY|g" .env.production

echo "✅ Secrets applied successfully!"
echo ""

# Ask for admin credentials
echo "📧 Admin Credentials Setup"
echo "========================="
read -p "Admin Email: " ADMIN_EMAIL
read -p "Admin Username: " ADMIN_USERNAME

sed -i "s|DEFAULT_ADMIN_EMAIL=YOUR_ADMIN_EMAIL@domain.com|DEFAULT_ADMIN_EMAIL=$ADMIN_EMAIL|g" .env.production
sed -i "s|DEFAULT_ADMIN_USERNAME=admin|DEFAULT_ADMIN_USERNAME=$ADMIN_USERNAME|g" .env.production

echo "✅ Admin credentials configured"
echo ""

# Save secrets to secure file
SECRETS_FILE="secrets_$(date +%Y%m%d_%H%M%S).txt"
cat > "$SECRETS_FILE" << EOF
# =====================================
# KI-ANA Production Secrets
# Generated: $(date)
# =====================================
# ⚠️  KEEP THIS FILE SECURE! ⚠️
# Store in password manager and delete after deployment
# =====================================

JWT_SECRET=$JWT_SECRET
KI_SECRET=$KI_SECRET
DB_PASSWORD=$DB_PASSWORD
MINIO_ACCESS_KEY=$MINIO_ACCESS
MINIO_SECRET_KEY=$MINIO_SECRET
MINIO_ROOT_USER=$MINIO_ROOT_USER
MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD
EMERGENCY_OVERRIDE_SHA256=$EMERGENCY_KEY

ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_USERNAME=$ADMIN_USERNAME

# Database Connection String:
DATABASE_URL=postgresql+psycopg2://kiana:$DB_PASSWORD@localhost:5432/kiana

# Emergency Override (plain text for reference):
# Generate SHA256 of this to get EMERGENCY_OVERRIDE_SHA256:
emergency_override_$(date +%s)

# =====================================
# IMPORTANT NOTES:
# =====================================
# 1. Store this file in a secure password manager
# 2. Delete this file after backing up to password manager
# 3. Never commit this file to git
# 4. Rotate secrets every 90 days
# 5. Use different secrets for staging/production
# =====================================
EOF

chmod 600 "$SECRETS_FILE"

echo "✅ Secrets saved to: $SECRETS_FILE"
echo "⚠️  IMPORTANT: Store in password manager and DELETE this file!"
echo ""
echo "🎉 Production secrets generation complete!"
echo ""
echo "Next steps:"
echo "1. Copy .env.production to production server"
echo "2. Review and adjust remaining settings (domain, SSL, etc.)"
echo "3. Store $SECRETS_FILE in password manager"
echo "4. Delete $SECRETS_FILE from disk"
echo "5. Deploy with: docker-compose -f docker-compose.gpu.yml up -d"
echo ""
