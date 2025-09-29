#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/kiana/ki_ana/netapi/static"
PAGES=(
about.html agb.html app.html block_viewer.html blocks.html capabilities.html 
cron.html downloads.html forgot.html guardian.html impressum.html kids.html 
logout.html papa_tools.html privacy.html reset.html search.html submind.html upgrade.html
)
for f in "${PAGES[@]}"; do
  FILE="$ROOT/$f"
  [ -f "$FILE" ] || continue
  cp -n "$FILE" "$FILE.bak" || true
  # 1) Replace legacy navbar container with new placeholder
  sed -i 's#<div id="nav"[^>]*></div>#<div id="navbar"></div>#g' "$FILE"
  # 2) Remove any nav.js script includes
  sed -i '/nav\.js/d' "$FILE"
  # 3) Ensure navbar placeholder exists right after <body> if missing
  if ! grep -q 'id="navbar"' "$FILE"; then
    sed -i '0,/<body>/s//<body>\n<div id="navbar"><\/div>/' "$FILE"
  fi
  # 4) Inject loader snippet before closing body if not already present
  if ! grep -q "fetch('/static/nav.html')" "$FILE"; then
    sed -i 's#</body>#<script>(function(){try{fetch("/static/nav.html").then(r=>r.text()).then(html=>{var n=document.getElementById("navbar"); if(n) n.innerHTML=html;}).catch(()=>{});}catch{}})();</script>\n</body>#' "$FILE"
  fi
  echo "Updated: $FILE"
done
echo "Done."
