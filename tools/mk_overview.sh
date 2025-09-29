#!/usr/bin/env bash
set -euo pipefail

# === Pfade anpassen, falls nötig ===
PROJECT_DIR="/home/kiana/ki_ana"
OUT_DIR="$PROJECT_DIR/reports"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUT_DIR"

# Vorherige Report-Dateien entfernen, damit nur die neuesten sichtbar bleiben
rm -f \
  "$OUT_DIR"/project_tree_*.txt \
  "$OUT_DIR"/project_config_*.txt \
  "$OUT_DIR"/config_file_index_*.txt \
  "$OUT_DIR"/python_deps_*.txt \
  "$OUT_DIR"/git_info_*.txt \
  "$OUT_DIR"/README_*.md \
  "$OUT_DIR"/project_tree.txt \
  "$OUT_DIR"/project_config.txt \
  "$OUT_DIR"/config_file_index.txt \
  "$OUT_DIR"/python_deps.txt \
  "$OUT_DIR"/git_info.txt \
  "$OUT_DIR"/README.md 2>/dev/null || true

# 1) Vollständiger Tree (mit Hidden Files)
# Tiefenlimit kannst du erhöhen (z. B. -L 10)
if command -v tree >/dev/null 2>&1; then
  tree -a -L 8 "$PROJECT_DIR" > "$OUT_DIR/project_tree.txt"
else
  # Fallback, falls 'tree' nicht installiert ist
  find "$PROJECT_DIR" -printf "%p\n" | sort > "$OUT_DIR/project_tree.txt"
fi

# 2) Relevante Configs einsammeln (egal, wo sie liegen)
CONFIG_LIST="$OUT_DIR/config_file_index.txt"
> "$CONFIG_LIST"

# Diese Muster kannst du bei Bedarf erweitern
mapfile -t FILES < <(find "$PROJECT_DIR" -type f \
  \( -name ".env*" -o -name "requirements*.txt" -o -name "pyproject.toml" -o -name "poetry.lock" \
     -name "Pipfile" -o -name "Pipfile.lock" -o -name "Dockerfile" -o -name "docker-compose*.yml" \
     -o -name "compose*.yml" -o -name ".dockerignore" -o -name ".gitignore" -o -name "Procfile" \
     -o -name "*.service" -o -name "*.timer" -o -name "*.env.example" \) 2>/dev/null | sort)

CONFIG_OUT="$OUT_DIR/project_config.txt"
> "$CONFIG_OUT"

mask_secrets() {
  # Simple Masking typischer Schlüssel=werte (nur Anzeige; Originaldateien werden NICHT verändert)
  sed -E \
    -e 's/([A-Z0-9_]*(SECRET|TOKEN|PASSWORD|API[-_]?KEY|PASS|KEY)[A-Z0-9_]*\s*=\s*)[^ #\r\n]+/\1•••/gi' \
    -e 's/(Bearer\s+)[A-Za-z0-9._-]+/\1•••/g' \
    -e 's/(postgres:\/\/)[^@]+@/\1•••@/g'
}

for f in "${FILES[@]}"; do
  echo "$f" >> "$CONFIG_LIST"
  {
    echo "================================================================"
    echo ">> FILE: $f"
    echo "================================================================"
    mask_secrets < "$f" || true
    echo -e "\n"
  } >> "$CONFIG_OUT"
done

# 3) Python-Dependencies (je nach Setup)
DEP_OUT="$OUT_DIR/python_deps.txt"
if [ -f "$PROJECT_DIR/pyproject.toml" ] && command -v poetry >/dev/null 2>&1; then
  # Poetry-Export (ohne Hashes für bessere Lesbarkeit)
  (cd "$PROJECT_DIR" && poetry export --without-hashes -f requirements.txt) > "$DEP_OUT" || true
elif [ -f "$PROJECT_DIR/requirements.txt" ]; then
  cp "$PROJECT_DIR/requirements.txt" "$DEP_OUT"
elif command -v pip >/dev/null 2>&1; then
  pip freeze > "$DEP_OUT" || true
fi

# 4) Git-Status (falls Git-Repo)
if [ -d "$PROJECT_DIR/.git" ] && command -v git >/dev/null 2>&1; then
  {
    echo "==== GIT INFO ===="
    (cd "$PROJECT_DIR" && git rev-parse --is-inside-work-tree && git rev-parse --abbrev-ref HEAD && git rev-parse --short HEAD) 2>/dev/null
    echo
    (cd "$PROJECT_DIR" && git status --porcelain) 2>/dev/null
  } > "$OUT_DIR/git_info.txt" || true
fi

# 5) Kurzer Überblick als README
{
  echo "# KI_ana Projekt-Report"
  echo
  echo "Erstellt am: $TS"
  echo
  echo "- Tree: project_tree.txt"
  echo "- Config-Dateien (maskiert): project_config.txt"
  echo "- Gefundene Config-Pfade: config_file_index.txt"
  [ -f "$DEP_OUT" ] && echo "- Python-Dependencies: $(basename "$DEP_OUT")"
  [ -f "$OUT_DIR/git_info.txt" ] && echo "- Git: git_info.txt"
  echo
  echo "Hinweis: Geheimnisse wurden in der Anzeige maskiert (•••)."
} > "$OUT_DIR/README.md"

echo "✅ Fertig: Reports unter $OUT_DIR"
