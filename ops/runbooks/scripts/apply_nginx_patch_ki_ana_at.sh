#!/usr/bin/env bash
set -euo pipefail

FILE="/etc/nginx/sites-available/ki-ana.at"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHER="$SCRIPT_DIR/patch_nginx_ki_ana_at.py"

if [[ ! -f "$PATCHER" ]]; then
  echo "ERROR: patcher not found: $PATCHER" >&2
  exit 2
fi

echo "Patching: $FILE"
sudo python3 "$PATCHER" --file "$FILE"

echo "Testing nginx config"
sudo nginx -t

echo "Reloading nginx"
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl reload nginx
else
  sudo nginx -s reload
fi

echo "Done. Quick checks:"
echo "  curl -I https://ki-ana.at/app/chat"
echo "  curl -I https://ki-ana.at/chat"
echo "  curl -I https://ki-ana.at/static/chat.html"
echo "  curl -I https://ki-ana.at/openapi.json"
echo "  curl -I https://ki-ana.at/docs"
echo "  curl -I https://ki-ana.at/redoc"
echo "  curl -I https://ki-ana.at/ops/grafana/"
echo "  curl -I https://ki-ana.at/ops/prometheus/"
