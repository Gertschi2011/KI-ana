#!/bin/bash
# KI_ana Backup Script
# Erstellt tägliche Backups von Daten, Keys und Config

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup/kiana}"
KIANA_DIR="${KIANA_DIR:-/home/kiana/ki_ana}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="kiana_backup_${TIMESTAMP}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 KI_ana Backup Starting...${NC}"
echo "Timestamp: ${TIMESTAMP}"
echo "Backup Directory: ${BACKUP_DIR}"
echo ""

# Create backup directory
mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"

# Backup data directory
echo -e "${YELLOW}📦 Backing up data directory...${NC}"
if [ -d "${KIANA_DIR}/data" ]; then
    cp -r "${KIANA_DIR}/data" "${BACKUP_DIR}/${BACKUP_NAME}/"
    echo "✅ Data backed up"
else
    echo "⚠️  Data directory not found"
fi

# Backup keys
echo -e "${YELLOW}🔑 Backing up encryption keys...${NC}"
if [ -d "${KIANA_DIR}/system/keys" ]; then
    cp -r "${KIANA_DIR}/system/keys" "${BACKUP_DIR}/${BACKUP_NAME}/"
    chmod 600 "${BACKUP_DIR}/${BACKUP_NAME}/keys"/*_private.key 2>/dev/null || true
    echo "✅ Keys backed up (permissions secured)"
else
    echo "⚠️  Keys directory not found"
fi

# Backup configuration
echo -e "${YELLOW}⚙️  Backing up configuration...${NC}"
if [ -f "${KIANA_DIR}/.env" ]; then
    cp "${KIANA_DIR}/.env" "${BACKUP_DIR}/${BACKUP_NAME}/"
    echo "✅ Configuration backed up"
else
    echo "⚠️  .env file not found"
fi

# Backup database
echo -e "${YELLOW}💾 Backing up database...${NC}"
if [ -f "${KIANA_DIR}/data/kiana.db" ]; then
    cp "${KIANA_DIR}/data/kiana.db" "${BACKUP_DIR}/${BACKUP_NAME}/"
    echo "✅ Database backed up"
fi

# Create backup metadata
echo -e "${YELLOW}📝 Creating backup metadata...${NC}"
cat > "${BACKUP_DIR}/${BACKUP_NAME}/backup_info.txt" << EOF
KI_ana Backup Information
========================
Timestamp: ${TIMESTAMP}
Date: $(date)
Hostname: $(hostname)
KI_ana Directory: ${KIANA_DIR}
Backup Size: $(du -sh "${BACKUP_DIR}/${BACKUP_NAME}" | cut -f1)

Contents:
- data/          (Application data)
- keys/          (Encryption keys)
- .env           (Configuration)
- kiana.db       (Database)

Restore with: ./restore.sh ${BACKUP_NAME}
EOF

echo "✅ Metadata created"

# Compress backup
echo -e "${YELLOW}🗜️  Compressing backup...${NC}"
cd "${BACKUP_DIR}"
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
rm -rf "${BACKUP_NAME}"
echo "✅ Backup compressed: ${BACKUP_NAME}.tar.gz"

# Calculate checksum
echo -e "${YELLOW}🔐 Calculating checksum...${NC}"
sha256sum "${BACKUP_NAME}.tar.gz" > "${BACKUP_NAME}.tar.gz.sha256"
echo "✅ Checksum created"

# Cleanup old backups
echo -e "${YELLOW}🧹 Cleaning up old backups (older than ${RETENTION_DAYS} days)...${NC}"
find "${BACKUP_DIR}" -name "kiana_backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "kiana_backup_*.tar.gz.sha256" -mtime +${RETENTION_DAYS} -delete
echo "✅ Cleanup complete"

# Summary
BACKUP_SIZE=$(du -sh "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)
echo ""
echo -e "${GREEN}✅ Backup Complete!${NC}"
echo "Backup File: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
echo "Backup Size: ${BACKUP_SIZE}"
echo "Checksum: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz.sha256"
echo ""
echo "To restore this backup:"
echo "  ./restore.sh ${BACKUP_NAME}"
