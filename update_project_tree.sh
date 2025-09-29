#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/kiana/ki_ana"
OUT_DIR="$PROJECT_DIR/reports"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUT_DIR"

echo "🔄 Projekt-Report wird erstellt ($TS)..."

# Alte Report-Dateien entfernen, damit nur der neueste Stand angezeigt wird
# (fehlerfrei fortsetzen, falls keine Treffer)
rm -f \
  "$OUT_DIR"/project_tree_*.txt \
  "$OUT_DIR"/project_config_*.txt \
  "$OUT_DIR"/python_deps_*.txt \
  "$OUT_DIR"/README_*.md \
  "$OUT_DIR"/project_hash_*.sha256 \
  "$OUT_DIR"/git_info_*.txt \
  "$OUT_DIR"/project_tree.txt \
  "$OUT_DIR"/project_config.txt \
  "$OUT_DIR"/python_deps.txt \
  "$OUT_DIR"/README.md \
  "$OUT_DIR"/project_hash.sha256 \
  "$OUT_DIR"/git_info.txt 2>/dev/null || true

# 1) Vollständiger Tree
if command -v tree >/dev/null 2>&1; then
  tree -a -L 8 "$PROJECT_DIR" > "$OUT_DIR/project_tree.txt"
else
  find "$PROJECT_DIR" -type f | sort > "$OUT_DIR/project_tree.txt"
fi

# 2) Config-Dateien einsammeln
CONFIG_OUT="$OUT_DIR/project_config.txt"
> "$CONFIG_OUT"

for f in "$PROJECT_DIR/.env" \
         "$PROJECT_DIR/netapi/.gitignore" \
         "$PROJECT_DIR/requirements.txt"
do
  if [ -f "$f" ]; then
    echo "================================================================" >> "$CONFIG_OUT"
    echo ">> FILE: $f" >> "$CONFIG_OUT"
    echo "================================================================" >> "$CONFIG_OUT"
    sed -E \
      -e 's/([A-Z0-9_]*(SECRET|TOKEN|PASSWORD|API[-_]?KEY)[A-Z0-9_]*\s*=\s*)[^ #\r\n]+/\1•••/gi' \
      "$f" >> "$CONFIG_OUT"
    echo -e "\n" >> "$CONFIG_OUT"
  fi
done

# 3) Dependencies
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
  cp "$PROJECT_DIR/requirements.txt" "$OUT_DIR/python_deps.txt"
elif command -v pip >/dev/null 2>&1; then
  pip freeze > "$OUT_DIR/python_deps.txt" || true
fi

# 4) README Index
{
  echo "# KI_ana Projekt-Report"
  echo
  echo "Erstellt am: $TS"
  echo
  echo "- Tree: project_tree.txt"
  echo "- Config-Dateien (maskiert): project_config.txt"
  [ -f "$OUT_DIR/python_deps.txt" ] && echo "- Python-Dependencies: python_deps.txt"
  echo
  echo "Hinweis: Geheimnisse wurden in der Anzeige maskiert (•••)."
} > "$OUT_DIR/README.md"

# 5) Hash über alle Report-Dateien
FILES_TO_HASH=()
[ -f "$OUT_DIR/project_tree.txt" ] && FILES_TO_HASH+=("$OUT_DIR/project_tree.txt")
[ -f "$OUT_DIR/project_config.txt" ] && FILES_TO_HASH+=("$OUT_DIR/project_config.txt")
[ -f "$OUT_DIR/python_deps.txt" ] && FILES_TO_HASH+=("$OUT_DIR/python_deps.txt")
[ -f "$OUT_DIR/README.md" ] && FILES_TO_HASH+=("$OUT_DIR/README.md")
if [ ${#FILES_TO_HASH[@]} -gt 0 ]; then
  sha256sum "${FILES_TO_HASH[@]}" > "$OUT_DIR/project_hash.sha256"
fi

echo "✅ Fertig: Report unter $OUT_DIR"
if [ -f "$OUT_DIR/project_hash.sha256" ]; then
  echo "🔑 Projekt-Hash:"
  cat "$OUT_DIR/project_hash.sha256"
fi
