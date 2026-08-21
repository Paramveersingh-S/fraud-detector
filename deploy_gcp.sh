#!/bin/bash
# GCP Compute Engine Startup Script
# This script installs Docker, clones the Fraud-Spike Detector repo, and spins it up.

set -e

echo "Starting Fraud-Spike Detector Deployment..."

# 1. Update and install prerequisites
apt-get update -y
apt-get install -y ca-certificates curl gnupg git python3-venv python3-pip

# 2. Install Docker & Docker Compose
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 3. Clone Repository
cd /opt
if [ -d "fraud-detector" ]; then
    rm -rf fraud-detector
fi
git clone https://github.com/Paramveersingh-S/fraud-detector.git
cd fraud-detector

# 4. Spin up the Core Infrastructure (API, Redis, Frontend, Consumer)
docker compose up --build -d

# 5. Set up the Python environment to run the stream producer
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# 6. Create a systemd service to keep the producer running continuously
cat << 'EOF' > /etc/systemd/system/fraud-producer.service
[Unit]
Description=Fraud-Spike Transaction Producer
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/fraud-detector
ExecStart=/opt/fraud-detector/venv/bin/python -m fraud_spike.streaming.producer
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fraud-producer
systemctl start fraud-producer

echo "Deployment Complete! The system is now live."
