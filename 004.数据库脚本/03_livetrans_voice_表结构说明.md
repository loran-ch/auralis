# LiveTrans Voice — 数据库表结构说明

## ER 关系图

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│    users     │────→│  user_tokens      │     │ verification_codes  │
│ (用户)       │     │ (JWT令牌)         │     │ (短信验证码)         │
└──────┬───────┘     └──────────────────┘     └─────────────────────┘
       │
       ├──→ user_settings (偏好设置)
       ├──→ user_stats    (使用统计)
       ├──→ course_schedule (课程表)
       │
       ├──→ lectures (课堂记录)
       │      │
       │      └──→ transcriptions (转录句子)
       │             │
       │             └──→ bookmarks (知识卡片)
       │
       └──→ languages (语言参考表)
```

## 10 张表总览

| # | 表名 | 说明 | 对应前端页面 |
|---|------|------|------------|
| 1 | `users` | 用户账户 | login.html / register.html / profile.html |
| 2 | `verification_codes` | 短信验证码 | register.html |
| 3 | `user_tokens` | JWT令牌管理 | 全站认证 |
| 4 | `user_settings` | 用户偏好 | recorder.html (语言/引擎设置) |
| 5 | `languages` | 语言参考数据 | recorder.html (语言选择器) |
| 6 | `lectures` | 课堂讲座记录 | history.html (列表), review.html (详情) |
| 7 | `transcriptions` | 转录句子 | recorder.html (字幕流), review.html (回放) |
| 8 | `bookmarks` | 知识卡片 | knowledge-cards.html, recorder.html (★收藏) |
| 9 | `user_stats` | 用户统计 | profile.html (12h录制/48知识点) |
| 10 | `course_schedule` | 课程表 | profile.html「我的课程表」 |

## 核心设计

### 课堂→句子→收藏 (一对多关系)
```
lectures (1) ──→ (*) transcriptions ──→ (*) bookmarks
  课堂              每句话                 收藏标记
```

- `transcriptions.sentence_order` 控制字幕流的时间顺序
- `transcriptions.is_bookmarked` 反范式字段加速 history 列表查询
- `bookmarks.tag` 枚举4种标签: `important`/`question`/`exam`/`definition`

### 用户统计
- `user_stats` 独立表，定期由后端定时任务更新
- `profile.html` 的 12h 本周录制、48 知识点直接读此表

## 执行方式

```bash
# 连接 MySQL (Docker)
docker exec -i mysql mysql -uroot -proot123 -h 127.0.0.1 --default-character-set=utf8mb4 < 01_livetrans_voice_建表.sql
docker exec -i mysql mysql -uroot -proot123 -h 127.0.0.1 --default-character-set=utf8mb4 < 02_livetrans_voice_初始化数据.sql
```
