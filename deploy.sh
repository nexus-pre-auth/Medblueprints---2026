#!/bin/bash
# MedBlueprints — Production deploy script
# Run once on a fresh Ubuntu 22.04 / Debian 12 server
# Usage:  chmod +x deploy.sh && sudo ./deploy.sh
set -euo pipefail

DOMAIN="medblueprints.com"
REPO_DIR="/opt/medblueprints"

echo "==> [1/6] Installing Docker + Compose v2..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | tee /etc/apt/sources.list.d/docker.list >/dev/null
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
echo "    Docker $(docker --version) installed."

echo "==> [2/6] Cloning / updating repo..."
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --ff-only
else
    git clone https://github.com/YOUR_ORG/medblueprints "$REPO_DIR"
fi
cd "$REPO_DIR"

echo "==> [3/6] Writing .env from environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  !! ACTION REQUIRED: edit $REPO_DIR/.env and fill in:"
    echo "     ANTHROPIC_API_KEY, POSTGRES_PASSWORD, DEMO_API_KEY"
    echo "     Then re-run this script."
    exit 1
fi

echo "==> [4/6] Pulling / building images..."
docker compose -f docker-compose.prod.yml pull --ignore-pull-failures
docker compose -f docker-compose.prod.yml build --parallel

echo "==> [5/6] Starting services..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "==> [6/6] Waiting for health checks..."
sleep 10
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=========================================="
echo "  MedBlueprints deployed!"
echo "  Site:   https://$DOMAIN"
echo "  API:    https://api.$DOMAIN/docs"
echo "  Health: https://api.$DOMAIN/health"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  docker compose -f docker-compose.prod.yml logs -f api"
echo "  docker compose -f docker-compose.prod.yml restart api"
echo "  docker compose -f docker-compose.prod.yml down"
