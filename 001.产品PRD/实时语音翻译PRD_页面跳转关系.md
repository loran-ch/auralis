# 实时语音翻译 — 页面跳转关系规格（已实现）

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.1 |
| 创建日期 | 2026-06-28 |
| 更新日期 | 2026-06-28 |
| 产品代号 | LiveTrans Voice |
| 来源 | frontend/html/ 已实现页面 |
| 更新说明 | 基于已实现的前端页面更新跳转关系 |

---

## 1. 页面清单

| 页面文件 | 页面名 | 功能说明 |
|---------|--------|---------|
| `login.html` | 登录 | 手机号+密码登录，第三方登录入口 |
| `register.html` | 注册 | 手机号+验证码+密码注册 |
| `recorder.html` | 实时录音 | 课堂语音录制+实时翻译字幕+一键收藏 |
| `history.html` | 课堂记录 | 历史课堂记录列表，按日期分组 |
| `profile.html` | 个人中心 | 用户信息+数据统计+设置入口 |
| `review.html` | 课堂回顾 | 已完成课堂回放+音频播放+知识点标签 |
| `knowledge-cards.html` | 知识卡片 | 收藏知识点管理+分类筛选+去听原文 |

---

## 2. 页面跳转关系图

```
                        ┌──────────────┐
                        │    登录       │
                        │  login.html  │
                        └──────┬───────┘
                 「立即注册」 │     │ 「登录」按钮
              ┌──────────────┘     └───────────────┐
              ▼                                      ▼
      ┌──────────────┐                      ┌──────────────┐
      │    注册       │──「注册并登录」───→  │  实时录音     │
      │ register.html│                      │ recorder.html│
      └──────┬───────┘                      └──────┬───────┘
             │ 「立即登录」                          │
             └──────────→ 登录                      │
                                          ┌────────┼────────┐
                                          │        │        │
                                          ▼        │        ▼
                              ┌──────────┐    │  ┌──────────┐
                              │个人中心   │    │  │课堂记录   │
                              │profile   │    │  │history   │
                              └────┬─────┘    │  └────┬─────┘
                     「开始记录」 │            │       │ 点击卡片
                                 ▼            │       ▼
                              实时录音         │  ┌──────────┐
                                              │  │课堂回顾   │
                                              │  │review    │
                                              │  └────┬─────┘
                                              │  ←返回 │
                                              │    课堂记录
                                              │
                                              ▼
                                      ┌──────────────┐
                                      │  知识卡片     │
                                      │knowledge-cards│
                                      └──────────────┘

   ┌─────────────────────────────────────────────┐
   │  menu 下拉菜单（recorder / history /        │
   │  knowledge-cards 页面通用）                  │
   │                                             │
   │  🎤 实时录音   → recorder.html              │
   │  📋 课堂记录   → history.html               │
   │  ⭐ 知识卡片   → knowledge-cards.html        │
   │  👤 个人中心   → profile.html               │
   │  ─────────────────────────                  │
   │  🚪 退出登录   → login.html                 │
   └─────────────────────────────────────────────┘
```

---

## 3. 各页面跳转详情（已实现）

### 3.1 登录页 (login.html)

| 触发元素 | 类型 | 跳转目标 | 说明 |
|---------|------|---------|------|
| 「登录」按钮 | onclick | `recorder.html` | 登录成功后进入主界面 |
| 「立即注册」链接 | href | `register.html` | 跳转注册页 |

### 3.2 注册页 (register.html)

| 触发元素 | 类型 | 跳转目标 | 说明 |
|---------|------|---------|------|
| 「注册并登录」按钮 | onclick | `recorder.html` | 注册成功后直接进入 |
| 「立即登录」链接 | href | `login.html` | 已有账户去登录 |
| ← 返回按钮 | onclick | `login.html` | 返回登录页 |

### 3.3 实时录音页 (recorder.html)

| 触发元素 | 类型 | 跳转目标 | 说明 |
|---------|------|---------|------|
| 左上 menu 按钮 | onclick(下拉) | 5个选项菜单 | 见 §3.8 下拉菜单 |
| 右上账户按钮 | href | `profile.html` | 进入个人中心 |
| 底部「标记」按钮 | — | 无跳转 | 收藏标签功能 |
| 底部「暂停」按钮 | — | 无跳转 | 暂停录音 |
| 底部「停止」按钮 | — | 无跳转 | 停止录音 |
| 底部「历史」按钮 | href | `history.html` | 查看课堂记录 |
| 底部「收藏」按钮 | href | `knowledge-cards.html` | 查看收藏知识点 |

### 3.4 课堂记录页 (history.html)

| 触发元素 | 类型 | 跳转目标 | 说明 |
|---------|------|---------|------|
| 左上 menu 按钮 | onclick(下拉) | 5个选项菜单 | 见 §3.8 下拉菜单 |
| 右上账户按钮 | onclick | `profile.html` | 进入个人中心 |
| 记录卡片点击 | onclick | `review.html` | 查看课堂详情 |
| 底部「历史」Tab | href | `history.html` | 当前激活 |
| 底部「记录」Tab | onclick | `recorder.html` | 开始新录音 |
| 底部「回查」Tab | onclick | `profile.html` | 查看个人数据 |
| FAB「+」按钮 | onclick | `recorder.html` | 快速开始录音 |

### 3.5 个人中心页 (profile.html)

| 触发元素 | 类型 | 跳转目标 | 说明 |
|---------|------|---------|------|
| 「开始记录」按钮 | href | `recorder.html` | 进入录音主界面 |
| 「退出登录」链接 | href | `login.html` | 退出返回登录 |
| 底部 History Tab | href | `history.html` | 查看课堂记录 |
| 底部 Record Tab | href | `recorder.html` | 开始录音 |
| 底部 Card Tab | href | `knowledge-cards.html` | 查看知识卡片 |
| 底部 Profile Tab | href | `profile.html` | 当前激活 |

### 3.6 课堂回顾页 (review.html)

| 触发元素 | 类型 | 跳转目标 | 说明 |
|---------|------|---------|------|
| ← 返回按钮 | onclick | `history.html` | 返回课堂记录 |
| 右上分享按钮 | onclick | `review.html` | 分享（当前页） |
| 右上账户按钮 | onclick | `profile.html` | 进入个人中心 |

### 3.7 知识卡片页 (knowledge-cards.html)

| 触发元素 | 类型 | 跳转目标 | 说明 |
|---------|------|---------|------|
| 左上 menu 按钮 | onclick(下拉) | 5个选项菜单 | 见 §3.8 下拉菜单 |
| 右上账户按钮 | href | `knowledge-cards.html` | 当前页 |
| 卡片「去听录音」 | href | `recorder.html` | 跳回对应音频位置 |
| 底部「历史」Tab | href | `history.html` | 查看课堂记录 |
| 底部「记录」Tab | href | `recorder.html` | 开始新录音 |
| 底部「复习」Tab | href | `knowledge-cards.html` | 当前激活 |

### 3.8 menu 下拉菜单（通用组件）

以下页面左上角 menu 按钮点击后弹出下拉菜单，非直接跳转：

| 所在页面 | 菜单项 | 跳转目标 |
|---------|--------|---------|
| recorder.html | 🎤 实时录音 | `recorder.html` |
| history.html | 📋 课堂记录 | `history.html` |
| knowledge-cards.html | ⭐ 知识卡片 | `knowledge-cards.html` |
| | 👤 个人中心 | `profile.html` |
| | 🚪 退出登录 | `login.html` |

---

## 4. 核心用户路径

### 路径 A：首次使用
```
login.html → register.html → recorder.html
```

### 路径 B：上课录音
```
recorder.html → 停止 → history.html → 点击卡片 → review.html → ←返回 → history.html
```

### 路径 C：复习收藏
```
recorder.html → menu下拉 → knowledge-cards.html → 去听录音 → recorder.html
```

### 路径 D：个人管理
```
recorder.html → menu下拉 → profile.html → 退出登录 → login.html
```

---

## 5. 底部导航栏状态

| 页面 | Tab1 | Tab2 | Tab3 | Tab4 |
|------|------|------|------|------|
| recorder | 标记 | 暂停/停止 | 历史(`history`) | 收藏(`knowledge-cards`) |
| history | 历史(激活) | 记录(`recorder`) | 回查(`profile`) | — |
| profile | History(`history`) | Record(`recorder`) | Card(`knowledge-cards`) | Profile(激活) |
| knowledge-cards | 历史(`history`) | 记录(`recorder`) | 复习(激活) | — |
| review | —(隐藏) | — | — | — |

---

> **关联文档**: 实时语音翻译PRD.md | 摄像头实时翻译PRD.md
