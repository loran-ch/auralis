# LiveTrans Voice

LiveTrans Voice 是一个 FastAPI + MySQL 的课堂实时翻译原型。后端同时提供营销首页、应用静态页面和 API，避免跨端口造成登录状态丢失。

## 本地运行

1. 启动 MySQL。新库依次执行 `004.数据库脚本/01_livetrans_voice_建表.sql` 与 `02_livetrans_voice_初始化数据.sql`；已有旧库再执行 `03_livetrans_voice_企业级索引升级.sql`。
2. 在项目根目录创建虚拟环境并安装 `003.UI/backend/requirements.txt`。
3. 参考 `.env.example`，通过 PowerShell、进程管理器或部署平台设置环境变量。
4. 从 `003.UI/backend` 启动：

   ```powershell
   $env:PORT='8010'
   ..\..\.venv\Scripts\python.exe main.py
   ```

5. 打开 <http://127.0.0.1:8010/>。本地测试账号为 `13800000002`，密码为 `123456`。

## UniApp 多端客户端

`003.UI/uniapp` 提供与浏览器应用共用账号、数据库和 API 的 iOS、Android、微信小程序及 H5 客户端。页面覆盖登录注册、实时录音翻译、课堂记录/回顾、知识卡片、个人中心和管理后台。

详细配置、构建与发布方法见 [`003.UI/uniapp/README.md`](003.UI/uniapp/README.md)。

## 验证

从 `003.UI/backend` 运行：

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

运行态探针：

- `/health/live`：进程存活
- `/health/ready`：数据库可用

## 已对接业务

- 账号密码登录、Access/Refresh Token 轮换、当前会话/全部会话退出、修改密码。
- 用户资料、头像、语言列表、翻译偏好、主题与云同步设置。
- 课程表新增、查询、修改、停用，并校验时间冲突。
- 课堂开始、暂停、恢复、结束、查询、改名、批量删除及录音上传。
- 实时文本翻译、转录持久化、收藏标签/备注，以及按周动态统计。

开发环境可在 `/docs` 查看完整 OpenAPI 文档；生产环境默认关闭文档与测试页面。

## 生产部署要点

- 设置 `ENVIRONMENT=production`，并注入独立的 `DATABASE_URL` 和至少 32 字符的随机 `JWT_SECRET`。
- 显式配置 `CORS_ORIGINS`；生产模式默认关闭 API 文档和测试页面。
- 在反向代理启用 HTTPS、请求体限制和分布式限流。
- 使用多 worker 部署 API；将语音识别/翻译任务迁移到独立任务队列，并为第三方翻译服务增加超时、熔断、配额与监控。
- 手机 H5 的动态识别需配置百度 `ASR_APP_ID`、`ASR_API_KEY` 和 WSS 反向代理；旧的分片接口仍使用 `ASR_API_URL`、`ASR_API_SECRET` 作为自动降级。
- 将音频和头像迁移到 S3/OSS 等对象存储，并通过 CDN 或签名 URL 访问；当前本地上传目录只适合单机开发。
- 将浏览器令牌迁移到 Secure、HttpOnly、SameSite Cookie，并接入 Redis 会话/限流、数据库迁移工具、集中日志和指标告警。
