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

# 国内 CVM 默认走阿里云 APT/PyPI；可用环境变量覆盖。
export APT_MIRROR="${APT_MIRROR:-mirrors.aliyun.com}"
export PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
echo "Build mirrors: APT_MIRROR=$APT_MIRROR"
echo "Build mirrors: PYPI_INDEX_URL=$PYPI_INDEX_URL"

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
# 已有数据库升级（幂等脚本，可重复执行）
for sql in \
  "004.数据库脚本/09_classroom_assistant_upgrade.sql" \
  "004.数据库脚本/10_record_only_mode.sql" \
  "004.数据库脚本/11_courses_p0.sql" \
  "004.数据库脚本/12_lecture_titles.sql" \
  "004.数据库脚本/13_learning_assistant_threads.sql" \
  "004.数据库脚本/14_classroom_media_p0.sql" \
  "004.数据库脚本/15_media_ocr_verification.sql" \
  "004.数据库脚本/16_briefing_edit_p0.sql" \
  "004.数据库脚本/17_lecture_attachments_p0.sql" \
  "004.数据库脚本/18_lecture_materials_export_p0.sql" \
  "004.数据库脚本/19_public_courses_p0.sql" \
  "004.数据库脚本/20_admin_llm_quota_p0.sql"
do
    apply_sql "$sql"
done

echo ""
echo "Deployment started:"
echo "  App:    https://$PUBLIC_DOMAIN/"
echo "  Health: https://$PUBLIC_DOMAIN/health/ready"
echo "  Admin:  https://$PUBLIC_DOMAIN/html/admin.html"
echo ""
docker compose --env-file .env.production ps
