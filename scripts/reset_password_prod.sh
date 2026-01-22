#!/usr/bin/env bash
set -euo pipefail

# Resets a user's password inside the production backend container.
# - Prompts securely from /dev/tty (works even if stdin is not a TTY)
# - Avoids putting the password on the command line (won't show up in shell history)
# - Passes the password via env var NEW_PASSWORD to /app/RESET_GERALD_PASSWORD.py

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
PROJECT_NAME="${PROJECT_NAME:-ki_ana}"
SERVICE="${SERVICE:-kiana-backend}"
EMAIL=""

usage() {
  echo "Usage: $0 --email someone@example.com" >&2
  echo "Env: PROJECT_NAME (default: ki_ana), COMPOSE_FILE (default: docker-compose.production.yml), SERVICE (default: kiana-backend)" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)
      EMAIL="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$EMAIL" ]]; then
  usage
  exit 2
fi

# Open controlling terminal explicitly.
if ! exec 3<>/dev/tty; then
  echo "ERROR: /dev/tty not available; cannot prompt securely." >&2
  echo "Tip: run from an interactive SSH session (not a non-tty pipeline)." >&2
  exit 3
fi

read_secret() {
  local prompt="$1"
  local value=""
  # shellcheck disable=SC2162
  read -r -s -u 3 -p "$prompt" value
  echo >&2
  printf '%s' "$value"
}

pw1="$(read_secret 'New password: ')"
pw2="$(read_secret 'Repeat password: ')"

if [[ -z "$pw1" ]]; then
  echo "ERROR: empty password" >&2
  exit 4
fi
if [[ "$pw1" != "$pw2" ]]; then
  echo "ERROR: passwords do not match" >&2
  exit 4
fi

 # Avoid leaking the secret via argv. We export NEW_PASSWORD for the exec process,
 # then ask compose to forward it by name (-e NEW_PASSWORD).
export NEW_PASSWORD="$pw1"
unset pw1 pw2

# Use -T because in some environments (VS Code terminals) docker can't allocate a TTY.
# IMPORTANT: all -e flags must come BEFORE the service name.
# We run an inline reset script so we don't depend on whatever /app/RESET_*.py exists in the image.
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T \
  -e KI_ROOT=/app \
  -e DATABASE_URL=sqlite:////app/netapi/users.db \
  -e NEW_PASSWORD \
  -e EMAIL="$EMAIL" \
  "$SERVICE" \
  python3 - <<'PY'
import os
from netapi.modules.auth.crypto import hash_pw

email = (os.environ.get("EMAIL") or "").strip()
pw = os.environ.get("NEW_PASSWORD") or ""
if not email:
  raise SystemExit("missing EMAIL")
if not pw:
  raise SystemExit("missing NEW_PASSWORD")

db_url = (os.environ.get("DATABASE_URL") or "").strip()
if not db_url:
  try:
    import netapi.db as d
    db_url = (getattr(d, "DB_URL", "") or "").strip()
  except Exception:
    db_url = ""
if not db_url:
  raise SystemExit("missing DATABASE_URL")

new_hash = hash_pw(pw)

def _sqlite_path(url: str) -> str:
  # Accept sqlite:////abs/path, sqlite:///abs/path, sqlite:// (etc). Strip query params.
  url = url.split("?", 1)[0]
  if url.startswith("sqlite:////"):
    return "/" + url[len("sqlite:////") :]
  if url.startswith("sqlite:///"):
    return "/" + url[len("sqlite:///") :]
  if url.startswith("sqlite://"):
    return url[len("sqlite://") :]
  return url

if db_url.startswith("sqlite:"):
  import sqlite3

  path = _sqlite_path(db_url)
  conn = sqlite3.connect(path)
  try:
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = ? WHERE lower(email) = lower(?)", (new_hash, email))
    if cur.rowcount == 0:
      raise SystemExit(f"user not found: {email}")
    conn.commit()
    cur.execute("SELECT username, email FROM users WHERE lower(email)=lower(?) LIMIT 1", (email,))
    row = cur.fetchone()
    if row:
      print(f"OK reset for: {row[0]} <{row[1]}>")
    else:
      print("OK reset")
  finally:
    conn.close()
else:
  # Generic SQL update without ORM row loading.
  from sqlalchemy import create_engine, text

  eng = create_engine(db_url, future=True)
  with eng.begin() as conn:
    r = conn.execute(text("UPDATE users SET password_hash = :h WHERE lower(email) = lower(:e)"), {"h": new_hash, "e": email})
    if (getattr(r, "rowcount", 0) or 0) == 0:
      raise SystemExit(f"user not found: {email}")
    row = conn.execute(text("SELECT username, email FROM users WHERE lower(email)=lower(:e) LIMIT 1"), {"e": email}).fetchone()
    if row:
      print(f"OK reset for: {row[0]} <{row[1]}>")
    else:
      print("OK reset")
PY

unset NEW_PASSWORD

echo "OK" >&2
