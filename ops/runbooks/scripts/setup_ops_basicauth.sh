#!/usr/bin/env bash
set -euo pipefail

HTPASSWD_FILE="/etc/nginx/.htpasswd-ops"
USER_NAME="opsadmin"

echo "Installing apache2-utils (for htpasswd)"
sudo apt-get update
sudo apt-get install -y apache2-utils

echo "Creating/updating $HTPASSWD_FILE for user $USER_NAME"
echo "You will be prompted for a password."
sudo htpasswd -c "$HTPASSWD_FILE" "$USER_NAME"

sudo chmod 640 "$HTPASSWD_FILE"

echo "BasicAuth ready: $HTPASSWD_FILE"
