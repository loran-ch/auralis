#!/bin/bash
# LiveTrans Voice - Docker production deployment
# Usage: bash deploy/deploy.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=========================================="
echo " LiveTrans Voice production deployment"
echo "=========================================="

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker Engine is required"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: Docker Compose plugin is required"
    exit 1
fi

if [ ! -f .env.production ]; then
    cp .env.production.example .env.production
    chmod 600 .env.production
    echo "Created .env.production. Fill in all real values, then run this script again."
    exit 1
fi

if grep -Eq "replace-|example\.com" .env.production; then
    echo "ERROR: .env.production still contains placeholders"
    exit 1
fi

PUBLIC_DOMAIN="$(sed -n 's/^PUBLIC_DOMAIN=//p' .env.production | tail -1 | tr -d '\r')"
if [ -z "$PUBLIC_DOMAIN" ]; then
    echo "ERROR: PUBLIC_DOMAIN is required in .env.production"
    exit 1
fi

if [ ! -s deploy/ssl/fullchain.pem ] || [ ! -s deploy/ssl/privkey.pem ]; then
    echo "ERROR: valid HTTPS certificate files are required:"
    echo "  deploy/ssl/fullchain.pem"
    echo "  deploy/ssl/privkey.pem"
    echo "Self-signed certificates are not supported by the Android/iOS production apps."
    exit 1
fi

chmod 600 .env.production deploy/ssl/privkey.pem
mkdir -p deploy/certbot

docker compose --env-file .env.production config >/dev/null
docker compose --env-file .env.production up -d --build

apply_sql() {
    local file="$1"
    if [ -f "$file" ]; then
        echo "Applying $file"
        docker compose --env-file .env.production exec -T db sh -c \
          'exec mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" livetrans_voice' \
          < "$file"
    fi
}

apply_sql "004.数据库脚本/07_lecture_briefings.sql"
apply_sql "004.数据库脚本/08_app_guides.sql"

echo ""
echo "Deployment started:"
echo "  App:    https://$PUBLIC_DOMAIN/"
echo "  Health: https://$PUBLIC_DOMAIN/health/ready"
echo "  Admin:  https://$PUBLIC_DOMAIN/html/admin.html"
echo ""
docker compose --env-file .env.production ps
