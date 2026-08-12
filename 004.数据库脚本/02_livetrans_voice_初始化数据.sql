-- ============================================================
-- LiveTrans Voice — 开发/演示数据
-- 警告：包含固定测试账号和演示课堂，禁止在生产数据库执行。
-- 演示数据与前端HTML展示内容一致
-- ============================================================
USE livetrans_voice;

-- ============================================================
-- 1. 语言数据
-- ============================================================
INSERT INTO languages (code, name_native, name_en, flag_emoji, region, supports_offline, offline_size_mb, sort_order) VALUES
('zh-CN','简体中文','Simplified Chinese','🇨🇳','东亚',0,NULL,1),
('zh-TW','繁體中文','Traditional Chinese','🇹🇼','东亚',0,NULL,2),
('ja','日本語','Japanese','🇯🇵','东亚',1,62,3),
('ko','한국어','Korean','🇰🇷','东亚',1,55,4),
('en','English','English','🇬🇧','欧洲',1,48,10),
('de','Deutsch','German','🇩🇪','欧洲',1,58,11),
('fr','Français','French','🇫🇷','欧洲',1,52,12),
('es','Español','Spanish','🇪🇸','欧洲',1,50,13),
('pt','Português','Portuguese','🇵🇹','欧洲',1,54,14),
('it','Italiano','Italian','🇮🇹','欧洲',1,51,15),
('ru','Русский','Russian','🇷🇺','欧洲',1,65,16),
('th','ภาษาไทย','Thai','🇹🇭','东南亚',1,60,50),
('vi','Tiếng Việt','Vietnamese','🇻🇳','东南亚',0,NULL,51),
('ar','العربية','Arabic','🇸🇦','南亚',0,NULL,71),
('hi','हिन्दी','Hindi','🇮🇳','南亚',0,NULL,72),
('tr','Türkçe','Turkish','🇹🇷','南亚',0,NULL,73);

-- ============================================================
-- 2. 演示用户 (密码使用 bcrypt 12轮哈希)
-- ============================================================
INSERT INTO users (id, nickname, username, email, email_verified, phone, phone_verified, password_hash, member_level, university, major, focus_area) VALUES
(1, '学霸小李', 'demo', 'demo@livetrans.app', 1, '+8613800000001', 1,
 '$2b$12$v66WW6U5Otk4qaYlNd3X4eY8OrLui4MRBngIpC/sYgUAX.k3DAj9e',
 'premium', '慕尼黑工业大学', '机械工程', 'Computer Science & AI'),
-- 测试账号: 手机号 +8613800000002，密码 123456
(2, 'test', 'test', 'test@livetrans.local', 1, '+8613800000002', 1,
 '$2b$12$ClncTakP0PG9skt4Bxhh5.e2YO4H7SADMVBCY2V7w0mYSyd0NA36G',
 'free', NULL, NULL, NULL);

-- ============================================================
-- 3. 用户设置
-- ============================================================
INSERT INTO user_settings (user_id, default_source_lang, default_target_lang, cloud_sync_enabled) VALUES
(1, 'auto', 'zh-CN', 1),
(2, 'auto', 'zh-CN', 1);

-- ============================================================
-- 4. 用户统计 (对应 profile.html)
-- ============================================================
INSERT INTO user_stats (user_id, weekly_record_seconds, total_bookmark_count, total_lecture_count, total_record_seconds, current_streak_days, weekly_bookmark_count) VALUES
(1, 43200, 48, 12, 864000, 7, 24);

-- ============================================================
-- 5. 课堂记录 (对应 history.html + review.html)
-- ============================================================
INSERT INTO lectures (id, user_id, course_name, source_lang, target_lang, duration_seconds, sentence_count, bookmark_count, location_name, room, subject_tags, status, lecture_date, started_at, ended_at) VALUES
(1, 1, '计算机科学 101', 'de', 'zh-CN', 2700, 14, 4, '大学礼堂', 'R.204', '["计算机科学","算法"]', 'completed', '2026-06-28', '2026-06-28 10:00:00', '2026-06-28 10:45:00'),
(2, 1, '经济学讲座',      'de', 'zh-CN', 2712, 8,  12, '大学礼堂', NULL, '["经济学"]', 'completed', '2023-10-24', '2023-10-24 10:30:00', '2023-10-24 11:15:12'),
(3, 1, '现代艺术史',      'de', 'zh-CN', 3510, 6,  8,  NULL, NULL, '["艺术史"]', 'completed', '2023-10-22', '2023-10-22 14:15:00', '2023-10-22 15:13:30'),
(4, 1, '分子生物学',      'de', 'zh-CN', 1925, 6,  24, NULL, NULL, '["生物学"]', 'completed', '2023-10-20', '2023-10-20 09:00:00', '2023-10-20 09:32:05'),
(5, 1, '高级宏观经济学',  'en', 'zh-CN', 4320, 6,  5,  '大学礼堂', NULL, '["经济学"]', 'completed', '2026-06-27', '2026-06-27 14:00:00', '2026-06-27 15:12:00');

-- ============================================================
-- 6. 转录句子 (recorder.html 演示内容 + review.html 完整回放)
-- ============================================================
-- 课堂1: 计算机科学 101 (recorder.html 当前展示)
INSERT INTO transcriptions (lecture_id, user_id, source_text, source_lang, ocr_confidence, translated_text, target_lang, sentence_order, start_offset_ms, end_offset_ms, is_bookmarked, recorded_at) VALUES
(1, 1, 'Heute werden wir die Grundlagen von Algorithmen besprechen.', 'de', 0.95, '今天我们将讨论算法的基础知识。', 'zh-CN', 1, 0, 8000, 0, '2026-06-28 10:00:10'),
(1, 1, 'Ein Algorithmus ist eine präzise Anweisung zur Lösung eines Problems.', 'de', 0.93, '算法是解决问题的精确指令。', 'zh-CN', 2, 8000, 18000, 0, '2026-06-28 10:00:25'),
(1, 1, 'Effizienz ist hierbei der wichtigste Faktor für die Softwareentwicklung.', 'de', 0.96, '在这里，效率是软件开发中最重要的因素。', 'zh-CN', 3, 18000, 30000, 1, '2026-06-28 10:00:45'),
(1, 1, 'Wir müssen die Big-O-Notation verstehen, um die Komplexität zu messen.', 'de', 0.94, '我们需要理解大O表示法来衡量复杂度。', 'zh-CN', 4, 30000, 45000, 0, '2026-06-28 10:01:00');

-- 课堂5: 高级宏观经济学 (review.html 完整展示)
INSERT INTO transcriptions (lecture_id, user_id, source_text, source_lang, ocr_confidence, translated_text, target_lang, sentence_order, start_offset_ms, end_offset_ms, is_bookmarked, recorded_at) VALUES
(5, 1, 'Welcome everyone. Today we are exploring how asymmetric information fundamentally shifts market outcomes.', 'en', 0.95, '欢迎大家。今天我们将探讨信息不对称如何从根本上改变市场结果。', 'zh-CN', 1, 0, 12000, 0, '2026-06-27 14:00:12'),
(5, 1, 'The Lemons Problem suggests that if buyers cannot distinguish quality, high-quality goods will eventually leave the market.', 'en', 0.93, '柠檬问题表明，如果买家无法区分质量，高质量的商品最终将退出市场。', 'zh-CN', 2, 120000, 135000, 1, '2026-06-27 14:02:04'),
(5, 1, 'This leads to adverse selection, where only the less desirable participants remain active.', 'en', 0.94, '这导致了逆向选择，即只有不太理想的参与者仍然活跃。', 'zh-CN', 3, 310000, 325000, 0, '2026-06-27 14:05:10'),
(5, 1, 'Wait, does this apply to the labor market as well in terms of signaling theory?', 'en', 0.91, '等等，这是否也适用于劳动力市场的信号传递理论？', 'zh-CN', 4, 450000, 465000, 1, '2026-06-27 14:07:30'),
(5, 1, 'Expect a question on the final about Spence Signaling Model vs Akerlof Market for Lemons.', 'en', 0.94, '预计期末考试会有一个关于斯宾塞信号模型与阿克洛夫柠檬市场的题目。', 'zh-CN', 5, 620000, 640000, 1, '2026-06-27 14:10:20'),
(5, 1, 'Signaling: An action taken by an informed party to reveal private information to an uninformed party.', 'en', 0.96, '信号传递：知情方为向不知情方透露私人信息而采取的行动。', 'zh-CN', 6, 800000, 820000, 1, '2026-06-27 14:13:20');

-- ============================================================
-- 7. 知识卡片 (对应 knowledge-cards.html)
-- ============================================================
INSERT INTO bookmarks (user_id, transcription_id, lecture_id, tag) VALUES
-- 课堂5的收藏
(1, 6, 5, 'important'),    -- 柠檬问题 → ⭐重要
(1, 8, 5, 'question'),     -- 劳动力市场 → ❓疑问
(1, 9, 5, 'exam'),         -- 期末考试 → 🎯考点
(1, 10, 5, 'definition'),  -- 信号传递 → 📖定义

-- 课堂1的收藏
(1, 3, 1, 'important'),    -- 效率 → ⭐重要

-- knowledge-cards.html 其他演示卡片
(1, 1, 1, 'definition');   -- 算法基础 → 📖定义

-- ============================================================
-- 8. 课程表
-- ============================================================
INSERT INTO course_schedule (user_id, course_name, source_lang, target_lang, day_of_week, start_time, end_time, room) VALUES
(1, '计算机科学 101', 'de', 'zh-CN', 1, '10:00', '11:30', 'R.204'),
(1, '高级宏观经济学', 'en', 'zh-CN', 3, '14:00', '15:30', NULL),
(1, '热力学 II', 'de', 'zh-CN', 5, '09:00', '10:30', NULL);

-- 更新 lectures 的 bookmark_count
UPDATE lectures SET bookmark_count = (SELECT COUNT(*) FROM bookmarks WHERE bookmarks.lecture_id = lectures.id);
UPDATE lectures SET sentence_count = (SELECT COUNT(*) FROM transcriptions WHERE transcriptions.lecture_id = lectures.id);
