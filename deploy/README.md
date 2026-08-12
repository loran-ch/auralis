# LiveTrans Voice 生产部署

此模板面向 4 核 4GB Linux 服务器，语音识别和翻译由外部 API 提供，服务器不运行本地 ASR 模型。

## 1. 数据库

全新生产数据库只执行：

1. `004.数据库脚本/01_livetrans_voice_建表.sql`
2. `004.数据库脚本/02_livetrans_voice_生产基础数据.sql`

不要在生产环境执行 `02_livetrans_voice_初始化数据.sql`，其中包含固定测试账号和演示课堂。旧数据库按实际版本依次执行 `03`、`04`、`05`，这些升级脚本可以重复运行。

## 2. 后端环境

创建专用系统用户 `livetrans`，将项目部署到 `/opt/livetrans`，虚拟环境放在 `/opt/livetrans/.venv`。复制：

- `backend.env.example` → `/etc/livetrans/backend.env`
- `livetrans-backend.service.example` → `/etc/systemd/system/livetrans-backend.service`

生产密钥只能写入服务器环境文件或密钥管理服务，不得提交到 Git。环境文件权限应设置为 `600`。

`ENTERPRISE_TRANSLATION_API_URL` 指向企业选定的翻译网关。网关接收 JSON：

```json
{"text":"hello","source":"en","target":"zh-CN"}
```

并返回 `translated_text`、`translation` 或 `text` 字段。这样可在网关内适配腾讯云、阿里云、Azure 等不同签名方式，而无需更新三个客户端。

安装依赖后执行 `systemctl daemon-reload`、`systemctl enable --now livetrans-backend`，并确认 `http://127.0.0.1:8010/health/ready` 返回 `ready`。

## 3. HTTPS 入口

复制 `nginx-livetrans.conf.example` 到 Nginx 配置目录，替换域名和证书路径。模板已包含登录和语音识别接口的基础限流，但多实例部署时仍应使用 Redis/API 网关实现用户级配额。

只开放公网 `80/443`；后端 `8010` 和 MySQL `3306` 仅监听本机或内网。配置完成后检查：

- `https://app.example.com/health/live`
- `https://app.example.com/health/ready`
- `https://app.example.com/html/login.html`

## 4. UniApp 发布

复制 `003.UI/uniapp/.env.production.example` 为 `.env.production`，填写同一个 HTTPS API 域名并保持 `VITE_ENABLE_DEMO_MODE=false`。然后分别构建 H5、微信小程序和 App；小程序后台还需要配置 request、uploadFile 和 downloadFile 合法域名。

## 5. 上线检查

- 备份数据库并验证一次恢复流程。
- 确认生产库没有 `test`、`demo` 固定账号。
- 验证 ASR 的 MP3、WEBM、OGG、WAV、M4A 格式。
- 验证 ASR/翻译超时、欠费和限额场景不会丢失录音。
- 对登录和音频接口进行并发压测，并观察 CPU、内存、数据库连接数和 P95 延迟。
