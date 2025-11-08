#!/bin/bash
# KI_ana Restore Script
# Stellt Backups wieder her

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup/kiana}"
KIANA_DIR="${KIANA_DIR:-/home/kiana/ki_ana}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: No backup specified${NC}"
    echo "Usage: $0 <backup_name>"
    echo ""
    echo "Available backups:"
    ls -1 "${BACKUP_DIR}"/kiana_backup_*.tar.gz 2>/dev/null | xargs -n 1 basename || echo "  No backups found"
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# Check if backup exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}❌ Error: Backup not found: ${BACKUP_FILE}${NC}"
    exit 1
fi

echo -e "${GREEN}🔄 KI_ana Restore Starting...${NC}"
echo "Backup: ${BACKUP_NAME}"
echo "Target: ${KIANA_DIR}"
echo ""

# Verify checksum
if [ -f "${BACKUP_FILE}.sha256" ]; then
    echo -e "${YELLOW}🔐 Verifying checksum...${NC}"
    cd "${BACKUP_DIR}"
    if sha256sum -c "${BACKUP_NAME}.tar.gz.sha256" >/dev/null 2>&1; then
        echo "✅ Checksum verified"
    else
        echo -e "${RED}❌ Checksum verification failed!${NC}"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}⚠️  No checksum file found, skipping verification${NC}"
fi

# Confirm restore
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will overwrite existing data!${NC}"
read -p "Continue with restore? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled"
    exit 0
fi

# Stop services (if running)
echo -e "${YELLOW}🛑 Stopping services...${NC}"
systemctl stop kiana 2>/dev/null || true
echo "✅ Services stopped"

# Extract backup
echo -e "${YELLOW}📦 Extracting backup...${NC}"
TEMP_DIR=$(mktemp -d)
tar -xzf "${BACKUP_FILE}" -C "${TEMP_DIR}"
echo "✅ Backup extracted"

# Restore data
echo -e "${YELLOW}📦 Restoring data directory...${NC}"
if [ -d "${TEMP_DIR}/${BACKUP_NAME}/data" ]; then
    rm -rf "${KIANA_DIR}/data"
    cp -r "${TEMP_DIR}/${BACKUP_NAME}/data" "${KIANA_DIR}/"
    echo "✅ Data restored"
fi

# Restore keys
echo -e "${YELLOW}🔑 Restoring encryption keys...${NC}"
if [ -d "${TEMP_DIR}/${BACKUP_NAME}/keys" ]; then
    rm -rf "${KIANA_DIR}/system/keys"
    cp -r "${TEMP_DIR}/${BACKUP_NAME}/keys" "${KIANA_DIR}/system/"
    chmod 600 "${KIANA_DIR}/system/keys"/*_private.key 2>/dev/null || true
    echo "✅ Keys restored (permissions secured)"
fi

# Restore configuration
echo -e "${YELLOW}⚙️  Restoring configuration...${NC}"
if [ -f "${TEMP_DIR}/${BACKUP_NAME}/.env" ]; then
    cp "${TEMP_DIR}/${BACKUP_NAME}/.env" "${KIANA_DIR}/"
    echo "✅ Configuration restored"
fi

# Restore database
echo -e "${YELLOW}💾 Restoring database...${NC}"
if [ -f "${TEMP_DIR}/${BACKUP_NAME}/kiana.db" ]; then
    cp "${TEMP_DIR}/${BACKUP_NAME}/kiana.db" "${KIANA_DIR}/data/"
    echo "✅ Database restored"
fi

# Cleanup
rm -rf "${TEMP_DIR}"

# Restart services
echo -e "${YELLOW}🚀 Starting services...${NC}"
systemctl start kiana 2>/dev/null || true
echo "✅ Services started"

# Summary
echo ""
echo -e "${GREEN}✅ Restore Complete!${NC}"
echo ""
echo "Backup Information:"
if [ -f "${TEMP_DIR}/${BACKUP_NAME}/backup_info.txt" ]; then
    cat "${TEMP_DIR}/${BACKUP_NAME}/backup_info.txt"
fi
echo ""
echo "KI_ana has been restored from backup: ${BACKUP_NAME}"
