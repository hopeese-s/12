#!/bin/bash
# ====================================================================
# OmniLoad - Linux VPS 1-Click Deployment Script
# ====================================================================

set -e

echo "================================================================"
echo " Starting OmniLoad Deployment..."
echo "================================================================"

# 1. Check if Docker is installed
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "[✓] Docker & Docker Compose found. Starting with Docker..."
    docker-compose down || true
    docker-compose build
    docker-compose up -d
    echo "[✓] OmniLoad is now running in Docker at: http://<your-server-ip>:8000"
    exit 0
fi

# 2. Native Linux Python setup
echo "[!] Docker not found. Deploying with Python & system FFmpeg..."

# Install system dependencies
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv ffmpeg
elif command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip ffmpeg
fi

# Create virtualenv
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service for 24/7 background running
SERVICE_FILE="/etc/systemd/system/omniload.service"
CURRENT_DIR=$(pwd)

echo "[i] Creating systemd service at $SERVICE_FILE..."
sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=OmniLoad Media Downloader Web App
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PORT=8000
Environment=HOST=0.0.0.0
Environment=AUTO_CLEANUP_HOURS=24

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable omniload
sudo systemctl restart omniload

echo "================================================================"
echo " [✓] Deployment Complete!"
echo " Service Status: sudo systemctl status omniload"
echo " Web App URL: http://<your-server-ip>:8000"
echo "================================================================"
