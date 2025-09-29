#!/usr/bin/env bash
set -euo pipefail

# Bootstrap host for KI_ana 2.0 on Ubuntu 22.04

if ! command -v docker >/dev/null 2>&1; then
  echo "[+] Installing Docker..."
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg lsb-release
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
fi

if ! command -v docker compose >/dev/null 2>&1; then
  echo "[!] docker compose plugin not found – ensure Docker >= 24 installed"
fi

echo "[+] Creating volumes directories (if using local bind mounts)..."
# nothing to do; using named volumes in compose

echo "[+] Copying .env template if missing..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[+] Wrote .env"
fi

echo "[+] Bootstrap complete. You may need to log out/in for docker group to apply."
