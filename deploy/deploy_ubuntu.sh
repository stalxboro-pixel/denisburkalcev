#!/usr/bin/env bash
# Production deploy helper for Ubuntu 22.04+.
# Usage: sudo ./deploy/deploy_ubuntu.sh
set -euo pipefail

APP_DIR="/opt/wot-seller-bot"
APP_USER="botuser"
SERVICE_NAME="wot-seller-bot"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (use sudo)." >&2
  exit 1
fi

echo "==> apt update + base packages"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git ufw fail2ban

echo "==> create system user"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "==> sync app to $APP_DIR"
mkdir -p "$APP_DIR"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --delete \
  --exclude='.venv' --exclude='.git' --exclude='__pycache__' \
  --exclude='data' --exclude='logs' \
  "$SRC_DIR/" "$APP_DIR/"

mkdir -p "$APP_DIR/data" "$APP_DIR/logs"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> python venv"
sudo -u "$APP_USER" "$PYTHON_BIN" -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> .env"
if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "WARN: edit $APP_DIR/.env and put real BOT_TOKEN before starting service."
fi

echo "==> initialise database"
sudo -u "$APP_USER" bash -c "cd '$APP_DIR' && '.venv/bin/python' -c 'import asyncio; from app import db; asyncio.run(db.init_db())'"

echo "==> systemd service"
install -m 0644 "$APP_DIR/deploy/bot.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

echo "==> firewall (ufw)"
ufw --force enable || true
ufw default deny incoming || true
ufw default allow outgoing || true
ufw allow OpenSSH || true

echo "==> fail2ban"
systemctl enable --now fail2ban || true

echo "==> start service"
systemctl restart "${SERVICE_NAME}.service" || true

echo "==> done"
echo "Status: systemctl status ${SERVICE_NAME}.service"
echo "Logs:   journalctl -u ${SERVICE_NAME}.service -f"
