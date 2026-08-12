# LiveTrans Voice UniApp 多端客户端

本目录是浏览器端 `003.UI/frontend` 的 UniApp Vue 3/Vite 实现，复用同一套 FastAPI 接口和 MySQL 业务数据，目标平台为：

- iOS 13+
- Android 6.0 / API 23+
- 微信小程序
- H5（用于开发联调和视觉回归）

## 已对齐的业务功能

| 模块 | 多端实现 |
| --- | --- |
| 认证 | 用户名/手机号 + 密码登录、短信验证码注册、Access/Refresh Token 自动续期、退出当前/全部设备 |
| 实时课堂 | 选择原文/译文语言、开始/暂停/恢复/结束、状态与计时、识别翻译结果、课堂命名 |
| 录音 | iOS/Android/微信统一录制 MP3；自动切分并串行上传；暂停时安全结束当前分片，恢复时创建新分片 |
| 课堂记录 | 搜索、日期筛选、分页、批量选择和删除、进入课堂回顾 |
| 课堂回顾 | 真实音频播放、进度跳转、前后 10 秒、倍速、双语转录、编辑课堂资料、导出/分享 |
| 知识卡片 | 按标签筛选、编辑标签与笔记、取消收藏、回到原课堂 |
| 个人中心 | 头像、资料、统计、默认语言、翻译/主题/同步偏好、课程表、修改密码 |
| 管理后台 | 概览、用户管理、课堂管理；超级管理员可管理角色、用户和审计日志 |

## 本地开发

建议使用 Node.js 20 LTS。先确保 `http://127.0.0.1:8002/health/ready` 返回 `ready`，然后执行：

```powershell
cd "D:\VSC project\claude-web\003.UI\uniapp"
npm.cmd install
npm.cmd run dev:h5
```

默认开发 API 地址位于 `.env.development`：

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8002
```

H5 开发模式通过 Vite 同源代理连接本机 `8002` 后端，手机或模拟器不会再把 API 请求误发到设备自己的 `127.0.0.1`。Android 模拟器若使用 `adb reverse tcp:5173 tcp:5173`，可从 `http://localhost:5173` 打开页面并获得浏览器安全上下文；真机真实语音录制须使用 HTTPS 页面。测试和生产发布必须使用有效 HTTPS 域名。

## 构建

```powershell
npm.cmd run build:h5
npm.cmd run build:mp-weixin
npm.cmd run build:app-android
npm.cmd run build:app-ios
```

构建产物：

- H5：`dist/build/h5`
- 微信小程序：`dist/build/mp-weixin`
- Android/iOS App 通用资源：`dist/build/app`

CLI 构建 App 生成的是可导入 HBuilderX 的应用资源。APK/AAB 和 IPA 还需要在 HBuilderX 中使用项目自己的 DCloud AppID、Android 签名或 Apple Developer 证书/描述文件打包；这些凭据不应提交到仓库。

## 微信小程序发布配置

1. 在 `src/manifest.json` 的 `mp-weixin.appid` 填写小程序 AppID。
2. 在微信公众平台配置 API 域名为 `request`、`uploadFile` 和 `downloadFile` 合法域名。
3. 域名必须为 HTTPS，证书链有效，且不能使用 IP 或 localhost。
4. 使用微信开发者工具导入 `dist/build/mp-weixin`，检查麦克风授权、录音上传和真机音频播放。

## App 发布配置

1. 将 `src/manifest.json` 顶层 `appid` 替换为在 DCloud 申请的 AppID。
2. Android 包名为 `com.livetrans.voice`，发布前替换为企业实际包名并配置签名。
3. iOS Bundle ID 为 `com.livetrans.voice`，发布前配置团队、证书和描述文件。
4. 麦克风和相册用途说明已配置；上架前仍需补充隐私政策 URL、应用图标、启动图和商店素材。

## 生产环境

复制 `.env.production.example` 为 `.env.production`，设置生产 API：

```dotenv
VITE_API_BASE_URL=https://api.example.com
VITE_ENABLE_DEMO_MODE=false
```

同时在后端显式配置 `CORS_ORIGINS`（H5 域名）、强随机 `JWT_SECRET`、生产数据库和 HTTPS 反向代理。App 与微信小程序不依赖浏览器 CORS，但仍需要合法证书、API 鉴权、上传大小限制和服务端限流。

项目已固定到 DCloud 5.23 正式编译器并锁定 `package-lock.json`。截至 2026-08-11，`npm audit` 仍会报告 DCloud 官方工具链内部的传递依赖告警；`npm audit fix --force` 会错误降级核心 UniApp 包，因此不应执行。CI 应使用隔离、最小权限的构建容器，不向公网暴露 Vite 开发服务器，并持续跟随 DCloud 正式版更新。

## 录音兼容策略

微信小程序支持原生暂停/恢复，但 App 端的录音管理器在部分版本不支持暂停。客户端统一采用“暂停即结束当前 MP3 分片、恢复即启动新分片”，后端用 `append=true` 按顺序追加，避免平台分支导致录音丢失。录音每 8 秒自动切分，下一段会先启动再异步上传上一段，从而兼顾连续录音和低延迟识别；上传失败会在结束课堂前报告错误。

## 真实语音识别

浏览器端可使用 Web Speech API，但 App 和微信小程序没有统一的免配置识别接口。多端客户端使用后端 `POST /api/lectures/{id}/transcribe/audio`，把每个短音频分片交给企业选定的 ASR 服务，然后自动翻译并保存转录。

在服务端配置：

```dotenv
ASR_API_URL=https://speech.example.com/v1/audio/transcriptions
ASR_API_KEY=由密钥管理服务注入
ASR_MODEL=your-model
ASR_TIMEOUT_SECONDS=20
ASR_MAX_SEGMENT_MB=10
```

ASR 服务需接受 `multipart/form-data` 的 `file`、可选 `model` 和 `language` 字段，并返回包含 `text`、`transcript` 或 `result` 文本字段的 JSON。开发环境可使用演示降级；生产构建默认禁用演示内容。未配置或上游不可用时，客户端会明确提示，继续保存录音但不会把预设句子伪装成真实识别结果。
