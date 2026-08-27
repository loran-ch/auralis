<template>
  <view class="page page-with-nav" :class="themeClass">
    <AppHeader title="个人中心" subtitle="账号、学习统计与偏好设置" />
    <view class="content content-wide">
      <view class="profile-hero card">
        <view class="avatar-wrap" @tap="chooseAvatar"><image v-if="user.avatar_url" class="avatar" :src="absoluteAssetUrl(user.avatar_url)" mode="aspectFill" /><view v-else class="avatar-placeholder">{{ initials }}</view><view class="camera-badge">✎</view></view>
        <view class="identity"><text class="display-name">{{ user.nickname || user.username || '用户' }}</text><text class="identity-meta">{{ identityMeta }}</text><view class="member-badge">{{ user.member_level === 'premium' ? '高级会员' : '免费账户' }}</view></view>
        <button class="edit-name" @tap="profileOpen = true">编辑</button>
      </view>

      <view class="stats-grid">
        <view class="stat-card card"><text class="stat-icon blue">◷</text><text class="stat-value">{{ stats.total_hours || 0 }}h</text><text class="stat-label">总录音</text></view>
        <view class="stat-card card"><text class="stat-icon gold">★</text><text class="stat-value">{{ stats.bookmark_count || 0 }}</text><text class="stat-label">知识卡片</text></view>
        <view class="stat-card card"><text class="stat-icon green">▤</text><text class="stat-value">{{ stats.lecture_count || 0 }}</text><text class="stat-label">课堂记录</text></view>
      </view>

      <view class="section-heading"><view><text class="section-title">学习偏好</text><text class="section-subtitle">设置默认翻译语言和应用体验</text></view></view>
      <view class="settings-card card">
        <view class="setting-row"><view><text class="setting-title">原文语言</text><text class="setting-description">开始录音时自动选择</text></view><picker :range="sourceLanguageNames" :value="sourceLanguageIndex" @change="changeSource"><view class="setting-value">{{ languageName(settings.default_source_lang, true) }} ›</view></picker></view>
        <view class="divider" />
        <view class="setting-row"><view><text class="setting-title">翻译语言</text><text class="setting-description">译文输出语言</text></view><picker :range="languageNames" :value="targetLanguageIndex" @change="changeTarget"><view class="setting-value">{{ languageName(settings.default_target_lang) }} ›</view></picker></view>
        <view class="divider" />
        <view class="setting-row"><view><text class="setting-title">翻译模式</text><text class="setting-description">优先速度或离线可用性</text></view><picker :range="modeNames" :value="modeIndex" @change="settings.translation_mode = modes[$event.detail.value].key"><view class="setting-value">{{ modes[modeIndex].label }} ›</view></picker></view>
        <view class="divider" />
        <view class="setting-row"><view><text class="setting-title">深色模式</text><text class="setting-description">跟随系统或固定主题</text></view><picker :range="themeNames" :value="themeIndex" @change="settings.dark_mode = themes[$event.detail.value].key"><view class="setting-value">{{ themes[themeIndex].label }} ›</view></picker></view>
        <view class="divider" />
        <view class="setting-row"><view><text class="setting-title">云端同步</text><text class="setting-description">同步历史、收藏与设置</text></view><switch :checked="settings.cloud_sync_enabled" color="#005ea1" @change="settings.cloud_sync_enabled = $event.detail.value" /></view>
        <button class="btn btn-primary save-settings" :disabled="saving" @tap="saveSettings">{{ saving ? '保存中…' : '保存偏好' }}</button>
      </view>

      <view class="section-heading"><view><text class="section-title">课程表</text><text class="section-subtitle">预先设置常用课堂和语言</text></view><button class="add-button" @tap="scheduleOpen = true">＋ 添加</button></view>
      <view class="schedule-card card">
        <view v-if="!schedules.length" class="mini-empty">暂未添加课程</view>
        <view v-for="(item, index) in schedules" :key="item.id">
          <view class="schedule-row"><view class="day-badge">{{ dayNames[item.day_of_week].replace('周', '') }}</view><view class="schedule-main"><text class="schedule-name">{{ item.course_name }}</text><text class="schedule-meta">{{ dayNames[item.day_of_week] }} {{ shortTime(item.start_time) }}–{{ shortTime(item.end_time) }}{{ item.room ? ` · ${item.room}` : '' }}{{ item.professor_name ? ` · ${item.professor_name}` : '' }}</text></view><button class="remove-schedule" @tap="removeSchedule(item)">×</button></view>
          <view v-if="index < schedules.length - 1" class="divider" />
        </view>
      </view>

      <view class="section-heading"><view><text class="section-title">学习空间</text><text class="section-subtitle">查看课程资料并向课堂助手提问</text></view></view>
      <view class="account-card card"><view class="account-row" @tap="uni.reLaunch({ url: '/pages/courses/index' })"><view><text class="setting-title">课程中心</text><text class="setting-description">浏览我创建的课程和教师共享课程</text></view><text class="chevron">›</text></view><view class="divider" /><view class="account-row" @tap="uni.reLaunch({ url: '/pages/assistant/index' })"><view><text class="setting-title">课堂助手</text><text class="setting-description">根据课堂记录、简报和作业进行复习</text></view><text class="chevron">›</text></view></view>

      <view class="section-heading"><view><text class="section-title">账号与安全</text><text class="section-subtitle">管理密码和登录设备</text></view></view>
      <view class="account-card card"><view class="account-row" @tap="passwordOpen = true"><view><text class="setting-title">修改密码</text><text class="setting-description">定期更换密码可提升安全性</text></view><text class="chevron">›</text></view><view class="divider" /><view v-if="isAdmin" class="account-row admin-row" @tap="uni.navigateTo({ url: '/pages/admin/index' })"><view><text class="setting-title">管理后台</text><text class="setting-description">用户、课堂与审计日志</text></view><text class="chevron">›</text></view><view v-if="isAdmin" class="divider" /><view class="account-row" @tap="logoutAll"><view><text class="setting-title error-text">退出所有设备</text><text class="setting-description">撤销当前账号的全部登录会话</text></view><text class="chevron">›</text></view></view>
      <button class="btn logout-button" @tap="logout">退出当前账号</button>
      <text class="version-text">LiveTrans Voice · UniApp 多端版</text>
    </view>
    <BottomNav active="profile" />

    <view v-if="profileOpen" class="modal-mask center" @tap.self="profileOpen = false"><view class="modal-card"><text class="section-title">编辑个人资料</text><view class="field"><text class="field-label">昵称</text><input v-model="profileForm.nickname" class="input" maxlength="64" /></view><view class="field"><text class="field-label">学校</text><input v-model="profileForm.university" class="input" maxlength="128" /></view><view class="field"><text class="field-label">专业</text><input v-model="profileForm.major" class="input" maxlength="128" /></view><view class="field"><text class="field-label">学习方向</text><input v-model="profileForm.focus_area" class="input" maxlength="128" /></view><view class="modal-actions"><button class="btn btn-soft" @tap="profileOpen = false">取消</button><button class="btn btn-primary" @tap="saveProfile">保存</button></view></view></view>

    <view v-if="scheduleOpen" class="modal-mask center" @tap.self="scheduleOpen = false"><view class="modal-card"><text class="section-title">添加课程</text><view class="field"><text class="field-label">课程名称</text><input v-model="scheduleForm.course_name" class="input" maxlength="80" placeholder="例如：商务英语" /></view><view class="form-grid"><view class="field"><text class="field-label">上课日</text><picker :range="dayNames.slice(1)" :value="scheduleForm.day_of_week - 1" @change="scheduleForm.day_of_week = Number($event.detail.value) + 1"><view class="picker-field">{{ dayNames[scheduleForm.day_of_week] }} ›</view></picker></view><view class="field"><text class="field-label">教室</text><input v-model="scheduleForm.room" class="input" maxlength="32" placeholder="可选" /></view></view><view class="form-grid"><view class="field"><text class="field-label">开始</text><picker mode="time" :value="scheduleForm.start_time" @change="scheduleForm.start_time = $event.detail.value"><view class="picker-field">{{ scheduleForm.start_time }} ›</view></picker></view><view class="field"><text class="field-label">结束</text><picker mode="time" :value="scheduleForm.end_time" @change="scheduleForm.end_time = $event.detail.value"><view class="picker-field">{{ scheduleForm.end_time }} ›</view></picker></view></view><view class="field"><text class="field-label">教师</text><input v-model="scheduleForm.professor_name" class="input" maxlength="64" placeholder="可选" /></view><view class="modal-actions"><button class="btn btn-soft" @tap="scheduleOpen = false">取消</button><button class="btn btn-primary" @tap="createSchedule">添加</button></view></view></view>

    <view v-if="passwordOpen" class="modal-mask center" @tap.self="passwordOpen = false"><view class="modal-card"><text class="section-title">修改密码</text><view class="field"><text class="field-label">当前密码</text><input v-model="passwordForm.current_password" class="input" password maxlength="72" /></view><view class="field"><text class="field-label">新密码</text><input v-model="passwordForm.new_password" class="input" password maxlength="72" /></view><view class="field"><text class="field-label">确认新密码</text><input v-model="passwordForm.confirm" class="input" password maxlength="72" /></view><view class="modal-actions"><button class="btn btn-soft" @tap="passwordOpen = false">取消</button><button class="btn btn-primary" @tap="changePassword">确认修改</button></view></view></view>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import BottomNav from '../../components/BottomNav.vue'
import { authApi, preferenceApi } from '../../api'
import { clearAuth, requireAuth, updateStoredUser } from '../../api/session'
import { absoluteAssetUrl } from '../../config/env'
import { showError } from '../../platform/format'
import { setThemeMode, useTheme } from '../../platform/theme'

const user = ref({})
const stats = ref({})
const languages = ref([])
const schedules = ref([])
const settings = reactive({ default_source_lang: 'auto', default_target_lang: 'zh-CN', translation_mode: 'auto', dark_mode: 'system', cloud_sync_enabled: false })
const saving = ref(false)
const profileOpen = ref(false)
const scheduleOpen = ref(false)
const passwordOpen = ref(false)
const profileForm = reactive({ nickname: '', university: '', major: '', focus_area: '' })
const scheduleForm = reactive({ course_name: '', day_of_week: 1, start_time: '09:00', end_time: '10:00', room: '', professor_name: '' })
const passwordForm = reactive({ current_password: '', new_password: '', confirm: '' })
const dayNames = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']
const modes = [{ key: 'auto', label: '自动' }, { key: 'online', label: '在线' }, { key: 'offline', label: '离线' }]
const themes = [{ key: 'system', label: '跟随系统' }, { key: 'light', label: '浅色' }, { key: 'dark', label: '深色' }]
const themeClass = useTheme()
const languageNames = computed(() => languages.value.map((item) => `${item.flag_emoji || '🌐'} ${item.name_native}`))
const sourceLanguageNames = computed(() => ['🌐 自动检测', ...languageNames.value])
const sourceLanguageIndex = computed(() => settings.default_source_lang === 'auto' ? 0 : Math.max(1, languages.value.findIndex((item) => item.code === settings.default_source_lang) + 1))
const targetLanguageIndex = computed(() => Math.max(0, languages.value.findIndex((item) => item.code === settings.default_target_lang)))
const modeNames = computed(() => modes.map((item) => item.label))
const themeNames = computed(() => themes.map((item) => item.label))
const modeIndex = computed(() => Math.max(0, modes.findIndex((item) => item.key === settings.translation_mode)))
const themeIndex = computed(() => Math.max(0, themes.findIndex((item) => item.key === settings.dark_mode)))
const initials = computed(() => String(user.value.nickname || user.value.username || 'L').slice(0, 1).toUpperCase())
const identityMeta = computed(() => [user.value.university, user.value.major].filter(Boolean).join(' · ') || user.value.username || user.value.phone || '')
const isAdmin = computed(() => ['admin', 'super_admin'].includes(user.value.role))

onShow(() => { if (requireAuth()) load() })
onPullDownRefresh(async () => { await load(); uni.stopPullDownRefresh() })
async function load() {
  try {
    const [userData, statsData, languageData, settingData, scheduleData] = await Promise.all([authApi.me(), authApi.stats(), preferenceApi.languages(), preferenceApi.settings(), preferenceApi.schedules()])
    user.value = userData; stats.value = statsData; languages.value = languageData; Object.assign(settings, settingData); schedules.value = scheduleData; setThemeMode(settingData.dark_mode)
    Object.assign(profileForm, { nickname: userData.nickname || '', university: userData.university || '', major: userData.major || '', focus_area: userData.focus_area || '' })
    updateStoredUser(userData)
  } catch (error) { showError(error, '个人中心加载失败') }
}
function languageName(code, allowAuto = false) { if (allowAuto && code === 'auto') return '🌐 自动检测'; const item = languages.value.find((value) => value.code === code); return item ? `${item.flag_emoji || '🌐'} ${item.name_native}` : code }
function changeSource(event) { const index = Number(event.detail.value); settings.default_source_lang = index === 0 ? 'auto' : languages.value[index - 1]?.code || 'auto' }
function changeTarget(event) { settings.default_target_lang = languages.value[Number(event.detail.value)]?.code || 'zh-CN' }
function shortTime(value) { return String(value || '').slice(0, 5) }
async function saveSettings() { saving.value = true; try { const data = await preferenceApi.saveSettings({ default_source_lang: settings.default_source_lang, default_target_lang: settings.default_target_lang, translation_mode: settings.translation_mode, dark_mode: settings.dark_mode, cloud_sync_enabled: settings.cloud_sync_enabled }); Object.assign(settings, data); setThemeMode(data.dark_mode); uni.showToast({ title: '偏好已保存', icon: 'success' }) } catch (error) { showError(error, '保存失败') } finally { saving.value = false } }
async function saveProfile() { try { const result = await authApi.updateProfile({ nickname: profileForm.nickname.trim(), university: profileForm.university.trim(), major: profileForm.major.trim(), focus_area: profileForm.focus_area.trim() }); user.value = result.user || { ...user.value, ...profileForm }; updateStoredUser(user.value); profileOpen.value = false; uni.showToast({ title: '资料已保存', icon: 'success' }) } catch (error) { showError(error, '资料保存失败') } }
function chooseAvatar() { uni.chooseImage({ count: 1, sizeType: ['compressed'], sourceType: ['album', 'camera'], success: async (result) => { try { const data = await authApi.uploadAvatar(result.tempFilePaths[0]); user.value.avatar_url = data.avatar_url; updateStoredUser(user.value); uni.showToast({ title: '头像已更新', icon: 'success' }) } catch (error) { showError(error, '头像上传失败') } } }) }
async function createSchedule() { if (!scheduleForm.course_name.trim()) return uni.showToast({ title: '请输入课程名称', icon: 'none' }); try { await preferenceApi.createSchedule({ course_name: scheduleForm.course_name.trim(), source_lang: settings.default_source_lang === 'auto' ? 'en' : settings.default_source_lang, target_lang: settings.default_target_lang, day_of_week: scheduleForm.day_of_week, start_time: scheduleForm.start_time, end_time: scheduleForm.end_time, room: scheduleForm.room.trim() || null, professor_name: scheduleForm.professor_name.trim() || null }); scheduleOpen.value = false; scheduleForm.course_name = ''; schedules.value = await preferenceApi.schedules(); uni.showToast({ title: '课程已添加', icon: 'success' }) } catch (error) { showError(error, '课程添加失败') } }
function removeSchedule(item) { uni.showModal({ title: '移除课程', content: `确定移除“${item.course_name}”吗？`, success: async (result) => { if (!result.confirm) return; try { await preferenceApi.removeSchedule(item.id); schedules.value = schedules.value.filter((value) => value.id !== item.id) } catch (error) { showError(error, '移除失败') } } }) }
async function changePassword() { if (passwordForm.new_password.length < 6) return uni.showToast({ title: '新密码至少 6 位', icon: 'none' }); if (passwordForm.new_password !== passwordForm.confirm) return uni.showToast({ title: '两次新密码不一致', icon: 'none' }); try { await authApi.changePassword({ current_password: passwordForm.current_password, new_password: passwordForm.new_password }); Object.assign(passwordForm, { current_password: '', new_password: '', confirm: '' }); passwordOpen.value = false; uni.showToast({ title: '密码已修改', icon: 'success' }) } catch (error) { showError(error, '密码修改失败') } }
function finishLogout() { clearAuth(); uni.reLaunch({ url: '/pages/login/index' }) }
function logout() { uni.showModal({ title: '退出登录', content: '确定退出当前账号吗？', success: async (result) => { if (!result.confirm) return; try { await authApi.logout() } catch (_) {} finishLogout() } }) }
function logoutAll() { uni.showModal({ title: '退出所有设备', content: '此操作会撤销所有设备上的登录状态，需要重新登录。', confirmColor: '#ba1a1a', success: async (result) => { if (!result.confirm) return; try { await authApi.logoutAll(); finishLogout() } catch (error) { showError(error, '操作失败') } } }) }
</script>

<style scoped>
.profile-hero { padding: 34rpx; display: flex; align-items: center; gap: 26rpx; }.avatar-wrap { position: relative; flex: 0 0 auto; width: 126rpx; height: 126rpx; }.avatar,.avatar-placeholder { width: 126rpx; height: 126rpx; border-radius: 42rpx; }.avatar-placeholder { display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg,#005ea1,#2b78bf); color: #fff; font-size: 52rpx; font-weight: 900; }.camera-badge { position: absolute; right: -8rpx; bottom: -8rpx; width: 48rpx; height: 48rpx; border: 5rpx solid var(--card); border-radius: 50%; background: var(--secondary); color: #fff; text-align: center; font-size: 20rpx; line-height: 38rpx; }.identity { flex: 1; min-width: 0; }.display-name,.identity-meta { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.display-name { font-size: 34rpx; font-weight: 850; }.identity-meta { margin-top: 8rpx; color: var(--muted); font-size: 21rpx; }.member-badge { display: inline-flex; margin-top: 12rpx; padding: 6rpx 14rpx; border-radius: 999rpx; background: #ffdcbe; color: var(--tertiary); font-size: 18rpx; font-weight: 750; }.edit-name { flex: 0 0 auto; width: 84rpx; height: 66rpx; padding: 0; background: var(--surface-container); color: var(--primary); font-size: 21rpx; line-height: 66rpx; border-radius: 18rpx; }
.stats-grid { margin-top: 24rpx; display: grid; grid-template-columns: repeat(3,1fr); gap: 16rpx; }.stat-card { padding: 25rpx 10rpx; display: flex; flex-direction: column; align-items: center; }.stat-icon { width: 54rpx; height: 54rpx; border-radius: 18rpx; text-align: center; line-height: 54rpx; font-size: 27rpx; }.blue { background: rgba(0,94,161,.1); color: var(--primary); }.gold { background: #ffdcbe; color: var(--tertiary); }.green { background: rgba(0,110,28,.1); color: var(--secondary); }.stat-value { margin-top: 12rpx; color: var(--text); font-size: 29rpx; font-weight: 850; }.stat-label { margin-top: 4rpx; color: var(--muted); font-size: 19rpx; }
.section-heading { margin: 42rpx 4rpx 20rpx; display: flex; align-items: center; justify-content: space-between; }.settings-card,.schedule-card,.account-card { padding: 4rpx 30rpx; }.setting-row,.account-row { min-height: 126rpx; display: flex; align-items: center; justify-content: space-between; gap: 20rpx; }.setting-title,.setting-description { display: block; }.setting-title { color: var(--text); font-size: 26rpx; font-weight: 750; }.setting-description { margin-top: 6rpx; color: var(--muted); font-size: 20rpx; }.setting-value { max-width: 300rpx; overflow: hidden; color: var(--primary); font-size: 22rpx; text-overflow: ellipsis; white-space: nowrap; }.save-settings { margin: 24rpx 0 30rpx; }.add-button { min-width: 120rpx; height: 64rpx; padding: 0 18rpx; border-radius: 18rpx; background: rgba(0,94,161,.1); color: var(--primary); font-size: 21rpx; line-height: 64rpx; }
.mini-empty { padding: 50rpx; color: var(--muted); text-align: center; }.schedule-row { min-height: 126rpx; display: flex; align-items: center; gap: 20rpx; }.day-badge { flex: 0 0 auto; width: 62rpx; height: 62rpx; border-radius: 20rpx; background: rgba(0,94,161,.1); color: var(--primary); text-align: center; font-size: 24rpx; font-weight: 850; line-height: 62rpx; }.schedule-main { flex: 1; min-width: 0; }.schedule-name,.schedule-meta { display: block; }.schedule-name { color: var(--text); font-size: 25rpx; font-weight: 750; }.schedule-meta { margin-top: 7rpx; overflow: hidden; color: var(--muted); font-size: 19rpx; text-overflow: ellipsis; white-space: nowrap; }.remove-schedule { flex: 0 0 auto; width: 64rpx; height: 64rpx; padding: 0; background: transparent; color: var(--error); font-size: 34rpx; line-height: 64rpx; }.chevron { color: var(--outline); font-size: 45rpx; }.admin-row { color: var(--primary); }.logout-button { width: 100%; margin-top: 28rpx; background: #ffdad6; color: var(--error); }.version-text { display: block; margin: 30rpx 0 10rpx; color: var(--muted); font-size: 19rpx; text-align: center; opacity: .7; }
.field { margin-top: 24rpx; margin-bottom: 0; }.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; }.modal-actions { margin-top: 30rpx; display: flex; gap: 16rpx; }.modal-actions .btn { flex: 1; }
</style>
