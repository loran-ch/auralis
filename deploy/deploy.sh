#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# LiveTrans Voice — 一键部署脚本
# 用法: bash deploy/deploy.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
UNIAPP_DIR="$PROJECT_DIR/003.UI/uniapp"
H5_OUT_DIR="$SCRIPT_DIR/h5_dist"

echo "=========================================="
echo " LiveTrans Voice 部署脚本"
echo "=========================================="

# ─── 1. 检查前置条件 ──────────────────────
echo ""
echo "[1/4] 检查环境..."

if ! command -v node &>/dev/null; then
    echo "❌ 需要 Node.js 18+，请先安装"
    exit 1
fi

if ! command -v docker &>/dev/null; then
    echo "❌ 需要 Docker，请先安装"
    exit 1
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
    echo "❌ 需要 Docker Compose"
    exit 1
fi

echo "✅ 环境检查通过"

# ─── 2. 构建 H5 前端 ──────────────────────
echo ""
echo "[2/4] 构建 H5 移动端..."

cd "$UNIAPP_DIR"
npm install --silent
npx uni build --outDir "$H5_OUT_DIR" 2>&1 | tail -5

if [ ! -f "$H5_OUT_DIR/index.html" ]; then
    echo "❌ H5 构建失败，未生成 index.html"
    exit 1
fi
echo "✅ H5 构建完成 → $H5_OUT_DIR"

# ─── 3. 准备配置文件 ──────────────────────
echo ""
echo "[3/4] 检查配置..."

cd "$PROJECT_DIR"

if [ ! -f .env.production ]; then
    echo "⚠ 未找到 .env.production，从模板创建..."
    cp deploy/.env.production .env.production
    echo "❗ 请编辑 .env.production 填入真实值后重新运行"
    exit 1
fi

# 检查关键配置是否已修改
if grep -q "replace-with-" .env.production; then
    echo "❌ .env.production 中包含未修改的占位符，请先填入真实值"
    exit 1
fi

if ! grep -q "MYSQL_ROOT_PASSWORD" .env.production; then
    echo "⚠ 建议在 .env.production 中设置 MYSQL_ROOT_PASSWORD 环境变量"
fi

echo "✅ 配置文件就绪"

# ─── 4. 启动服务 ──────────────────────────
echo ""
echo "[4/4] 启动 Docker 服务..."

# 准备 SSL 证书占位（如未配置 Let's Encrypt）
mkdir -p deploy/ssl
if [ ! -f deploy/ssl/fullchain.pem ]; then
    echo "⚠ 尚无 SSL 证书，生成自签名证书用于测试..."
    openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
        -keyout deploy/ssl/privkey.pem \
        -out deploy/ssl/fullchain.pem \
        -subj "/CN=localhost" 2>/dev/null
fi

# 启动
docker compose up -d --build

echo ""
echo "=========================================="
echo " 部署完成！"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  H5 移动端: https://你的域名/"
echo "  管理后台:  https://你的域名/html/admin.html"
echo ""
echo "常用命令:"
echo "  docker compose logs -f backend   # 查看后端日志"
echo "  docker compose ps                # 查看服务状态"
echo "  docker compose restart backend   # 重启后端"
echo "  docker compose down              # 停止所有服务"
echo ""
echo "配置 Let's Encrypt SSL 免费证书:"
echo "  sudo apt install certbot"
echo "  certbot certonly --webroot -w /var/www/certbot -d 你的域名"
echo "  然后把证书复制到 deploy/ssl/ 并重启 nginx"
