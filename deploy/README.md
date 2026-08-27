# LiveTrans Voice 腾讯云生产部署

本方案面向 Ubuntu 22.04/24.04 CVM，通过 Docker Compose 运行 MySQL、FastAPI 和 Nginx。Nginx 镜像会自动构建 UniApp H5，云服务器无需单独安装 Node.js。

## 1. 上线前提

- 将公网域名 A 记录解析到 CVM 公网 IP。
- 中国大陆 CVM 使用的网站和 App 必须先完成 ICP 备案。
- 腾讯云安全组对公网开放 TCP `80/443`；`22` 只向管理 IP 开放。不要开放 `3306/8010`。
- 准备匹配该域名的公网 SSL 证书，不能使用自签名证书。
- 安装 Git、Docker Engine 和 Docker Compose plugin。

## 2. 下载项目

```bash
sudo mkdir -p /opt/livetrans
sudo chown "$USER":"$USER" /opt/livetrans
git clone git@github.com:loran-ch/stock.git /opt/livetrans
cd /opt/livetrans
```

## 3. 生产环境变量

```bash
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

替换所有 `replace-*` 和 `example.com`。可使用 `openssl rand -hex 24` 生成 MySQL 密码，使用 `openssl rand -hex 48` 生成 `JWT_SECRET`。`DATABASE_URL` 中的密码必须和 `MYSQL_APP_PASSWORD` 相同，建议只用随机十六进制字符，避免 URL 转义问题。

中国大陆服务器不建议把 Google/MyMemory 作为生产翻译依赖。模板默认使用百度翻译和百度 ASR，需要填入对应的 App ID/API Key/Secret。

若改用阿里云百炼实时识别（Fun-ASR），在 `.env.production` 中设置：

```dotenv
ASR_PROVIDER=aliyun
DASHSCOPE_API_KEY=sk-xxxxxxxx
ASR_ALIYUN_MODEL=fun-asr-realtime
```

分片降级仍可保留百度短语音（`ASR_API_URL` 等）。切换后重启 backend 容器即可。

## 4. HTTPS 证书

在腾讯云 SSL 证书控制台下载 Nginx 格式证书，将证书链和私钥放到：

```text
deploy/ssl/fullchain.pem
deploy/ssl/privkey.pem
```

例如：

```bash
mkdir -p deploy/ssl
cp /path/to/your_domain_bundle.crt deploy/ssl/fullchain.pem
cp /path/to/your_domain.key deploy/ssl/privkey.pem
chmod 600 deploy/ssl/privkey.pem
```

## 5. 启动

```bash
bash deploy/deploy.sh
```

脚本会检查环境变量和证书，然后构建 H5/后端镜像，初始化新数据库并启动三个服务。全新数据卷只会执行建表脚本和生产基础数据，不会创建演示账号。

```bash
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs -f backend
curl -I "https://YOUR_DOMAIN/"
curl "https://YOUR_DOMAIN/health/ready"
```

`/health/ready` 应返回 `{"status":"ready"}`。

## 6. Android/iOS 发布包

H5 已使用同域 API。Android/iOS 安装包仍需要在本地项目中创建 `003.UI/uniapp/.env.production`：

```dotenv
VITE_API_BASE_URL=https://YOUR_DOMAIN
VITE_ENABLE_DEMO_MODE=false
```

然后在 HBuilderX 重新发行 Android/iOS；旧安装包不会自动知道新的腾讯云域名。

## 7. 更新版本

```bash
cd /opt/livetrans
git pull --ff-only
bash deploy/deploy.sh
```

不要删除 Docker volume；MySQL 数据和上传文件保存在命名卷中。执行升级 SQL 前应先备份数据库。

## 8. 修复语言名称或国旗乱码

如果语言列表出现 `FranÃ§ais`、`ðŸ...` 等内容，说明语言基础数据曾通过非 UTF-8 的 MySQL 客户端导入。先拉取本修复，再在项目根目录执行一次：

```bash
git pull --ff-only
docker compose --env-file .env.production exec -T db sh -c \
  'exec mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" livetrans_voice' \
  < "004.数据库脚本/06_languages_utf8mb4_修复.sql"
```

随后重新构建服务并验证接口：

```bash
bash deploy/deploy.sh
curl "https://YOUR_DOMAIN/api/languages"
```

响应应包含 `Français`、`Español` 和正常国旗。浏览器若仍显示旧内容，请强制刷新页面或清除站点缓存。
