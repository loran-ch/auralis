<template>
  <view class="page admin-page" :class="themeClass">
    <AppHeader title="管理后台" subtitle="LiveTrans Voice 系统管理" back fallback="/pages/profile/index" />
    <view class="admin-tabs content-wide"><view v-for="item in visibleTabs" :key="item.key" class="admin-tab" :class="{ active: tab === item.key }" @tap="switchTab(item.key)">{{ item.icon }}<text>{{ item.label }}</text></view></view>
    <scroll-view class="admin-scroll" scroll-y>
      <view class="content content-wide">
        <view v-if="loading" class="empty"><text class="empty-icon">◌</text>正在加载管理数据…</view>
        <template v-else-if="tab === 'dashboard'">
          <view class="dashboard-hero"><text class="dashboard-title">系统运行概览</text><text class="dashboard-copy">实时查看用户、课堂和内容增长情况</text></view>
          <view class="metric-grid"><view v-for="item in metrics" :key="item.label" class="metric-card card"><view class="metric-icon" :style="{ background: item.bg, color: item.color }">{{ item.icon }}</view><text class="metric-value">{{ item.value }}</text><text class="metric-label">{{ item.label }}</text></view></view>
          <view class="system-card card"><text class="section-title">系统信息</text><view v-for="(value, key) in dashboard.system_info" :key="key" class="system-row"><text>{{ systemLabels[key] || key }}</text><text>{{ value }}</text></view></view>
        </template>

        <template v-else>
          <view v-if="tab !== 'logs'" class="admin-search card"><text>⌕</text><input v-model="search" confirm-type="search" :placeholder="tab === 'users' ? '搜索用户昵称、手机或邮箱' : '搜索课程名称'" @confirm="loadTab" /><button v-if="search" @tap="search = ''; loadTab()">×</button></view>
          <view class="result-summary"><text>共 {{ total }} 条</text><button @tap="loadTab">刷新</button></view>

          <view v-if="!rows.length" class="empty card"><text class="empty-icon">▤</text>暂无数据</view>
          <view v-if="tab === 'users'" class="admin-list">
            <view v-for="item in rows" :key="item.id" class="admin-card card">
              <view class="admin-card-top"><view class="user-avatar">{{ String(item.nickname || item.phone || 'U').slice(0, 1) }}</view><view class="card-main"><text class="item-title">{{ item.nickname || '未设置昵称' }}</text><text class="item-meta">{{ item.phone || item.email || `用户 #${item.id}` }}</text></view><view class="status-badge" :class="item.status">{{ item.status === 'active' ? '正常' : '已禁用' }}</view></view>
              <view class="detail-grid"><text>角色：{{ roleLabel(item.role) }}</text><text>会员：{{ item.member_level }}</text><text>学校：{{ item.university || '--' }}</text><text>创建：{{ formatDate(item.created_at) }}</text></view>
              <view class="admin-actions"><button @tap="toggleUser(item)">{{ item.status === 'active' ? '禁用' : '启用' }}</button><button v-if="isSuper" @tap="changeRole(item)">修改角色</button><button v-if="isSuper" class="danger" @tap="removeUser(item)">删除</button></view>
            </view>
          </view>

          <view v-else-if="tab === 'lectures'" class="admin-list">
            <view v-for="item in rows" :key="item.id" class="admin-card card"><view class="admin-card-top"><view class="lecture-icon">▤</view><view class="card-main"><text class="item-title">{{ item.course_name }}</text><text class="item-meta">{{ item.user_nickname || `用户 #${item.user_id}` }} · {{ formatDate(item.lecture_date) }}</text></view><view class="status-badge" :class="item.status">{{ statusLabel(item.status) }}</view></view><view class="detail-grid"><text>语言：{{ item.source_lang }} → {{ item.target_lang }}</text><text>时长：{{ formatDuration(item.duration_seconds) }}</text><text>句子：{{ item.sentence_count || 0 }}</text><text>课堂 ID：{{ item.id }}</text></view><view class="admin-actions"><button class="danger" @tap="removeLecture(item)">删除课堂</button></view></view>
          </view>

          <view v-else class="admin-list">
            <view v-for="item in rows" :key="item.id" class="log-card card"><view class="log-head"><text class="action-badge">{{ item.action }}</text><text>{{ formatDate(item.created_at, true) }}</text></view><text class="item-title">{{ item.admin_name || `管理员 #${item.admin_id}` }}</text><text class="item-meta">{{ item.target_type || '--' }} #{{ item.target_id || '--' }} · {{ item.ip_address || '未知 IP' }}</text><text v-if="item.detail" class="detail-json">{{ JSON.stringify(item.detail) }}</text></view>
          </view>
          <view v-if="totalPages > 1" class="pager"><button :disabled="page <= 1" @tap="page -= 1; loadTab()">上一页</button><text>{{ page }} / {{ totalPages }}</text><button :disabled="page >= totalPages" @tap="page += 1; loadTab()">下一页</button></view>
        </template>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import { adminApi, authApi } from '../../api'
import { requireAuth } from '../../api/session'
import { formatDate, formatDuration, showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const user = ref({})
const tab = ref('dashboard')
const dashboard = ref({ system_info: {} })
const rows = ref([])
const search = ref('')
const page = ref(1)
const total = ref(0)
const totalPages = ref(1)
const loading = ref(false)
const tabs = [{ key: 'dashboard', label: '概览', icon: '▦' }, { key: 'users', label: '用户', icon: '♙' }, { key: 'lectures', label: '课堂', icon: '▤' }, { key: 'logs', label: '审计', icon: '⌘' }]
const systemLabels = { version: '系统版本', environment: '运行环境', database: '数据库', server_time: '服务器时间' }
const themeClass = useTheme()
const isSuper = computed(() => user.value.role === 'super_admin')
const visibleTabs = computed(() => isSuper.value ? tabs : tabs.filter((item) => item.key !== 'logs'))
const metrics = computed(() => [
  { label: '总用户', value: dashboard.value.total_users || 0, icon: '♙', color: '#005ea1', bg: 'rgba(0,94,161,.1)' },
  { label: '今日活跃', value: dashboard.value.active_today || 0, icon: '◉', color: '#006e1c', bg: 'rgba(0,110,28,.1)' },
  { label: '课堂总数', value: dashboard.value.total_lectures || 0, icon: '▤', color: '#874e00', bg: '#ffdcbe' },
  { label: '转录句子', value: dashboard.value.total_transcriptions || 0, icon: '≡', color: '#8b5cf6', bg: 'rgba(139,92,246,.1)' },
  { label: '知识卡片', value: dashboard.value.total_bookmarks || 0, icon: '★', color: '#ba1a1a', bg: '#ffdad6' },
  { label: '本周新增', value: dashboard.value.new_this_week || 0, icon: '＋', color: '#005ea1', bg: 'rgba(0,94,161,.1)' },
])

onLoad(async () => {
  if (!requireAuth()) return
  try {
    user.value = await authApi.me()
    if (!['admin', 'super_admin'].includes(user.value.role)) {
      uni.showModal({ title: '无权访问', content: '当前账号不是管理员。', showCancel: false, success: () => uni.reLaunch({ url: '/pages/profile/index' }) })
      return
    }
    loadTab()
  } catch (error) { showError(error, '管理员身份验证失败') }
})
async function loadTab() {
  loading.value = true
  try {
    if (tab.value === 'dashboard') dashboard.value = await adminApi.dashboard()
    else {
      const result = tab.value === 'users' ? await adminApi.users({ page: page.value, page_size: 20, search: search.value }) : tab.value === 'lectures' ? await adminApi.lectures({ page: page.value, page_size: 20, search: search.value }) : await adminApi.auditLogs({ page: page.value, page_size: 20 })
      rows.value = result.items || []; total.value = result.total || 0; totalPages.value = result.total_pages || 1
    }
  } catch (error) { showError(error, '管理数据加载失败') }
  finally { loading.value = false }
}
function switchTab(value) { tab.value = value; page.value = 1; search.value = ''; rows.value = []; loadTab() }
function roleLabel(value) { return { user: '用户', admin: '管理员', super_admin: '超级管理员' }[value] || value }
function statusLabel(value) { return { recording: '录音中', paused: '已暂停', completed: '已完成', failed: '失败' }[value] || value }
function confirmAction(title, content, action) { uni.showModal({ title, content, confirmColor: '#ba1a1a', success: async (result) => { if (!result.confirm) return; try { await action(); uni.showToast({ title: '操作成功', icon: 'success' }); loadTab() } catch (error) { showError(error, '操作失败') } } }) }
function toggleUser(item) { const next = item.status === 'active' ? 'disabled' : 'active'; confirmAction(next === 'active' ? '启用用户' : '禁用用户', `确定${next === 'active' ? '启用' : '禁用'}“${item.nickname || item.id}”吗？`, () => adminApi.updateUserStatus(item.id, next)) }
function changeRole(item) { uni.showActionSheet({ itemList: ['普通用户', '管理员', '超级管理员'], success: (result) => { const role = ['user', 'admin', 'super_admin'][result.tapIndex]; confirmAction('修改角色', `确定将该账号改为${roleLabel(role)}吗？`, () => adminApi.updateUserRole(item.id, role)) } }) }
function removeUser(item) { confirmAction('删除用户', '用户将被软删除并无法继续登录，确定继续吗？', () => adminApi.removeUser(item.id)) }
function removeLecture(item) { confirmAction('删除课堂', `将删除“${item.course_name}”及关联转录和收藏，确定继续吗？`, () => adminApi.removeLecture(item.id)) }
</script>

<style scoped>
.admin-page { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }.admin-scroll { flex: 1; min-height: 0; }.admin-tabs { flex-shrink: 0; height: 104rpx; padding: 0 22rpx; display: flex; align-items: center; justify-content: space-around; background: var(--card); border-bottom: 1rpx solid rgba(193,199,210,.35); }.admin-tab { min-width: 120rpx; height: 70rpx; padding: 0 16rpx; display: flex; align-items: center; justify-content: center; gap: 9rpx; border-radius: 20rpx; color: var(--muted); font-size: 25rpx; }.admin-tab text { font-size: 20rpx; }.admin-tab.active { background: rgba(0,94,161,.1); color: var(--primary); font-weight: 800; }
.dashboard-hero { padding: 38rpx; border-radius: 32rpx; background: linear-gradient(135deg,#1a1c1d,#414751); color: #fff; }.dashboard-title,.dashboard-copy { display: block; }.dashboard-title { font-size: 36rpx; font-weight: 850; }.dashboard-copy { margin-top: 10rpx; font-size: 22rpx; opacity: .75; }.metric-grid { margin-top: 24rpx; display: grid; grid-template-columns: repeat(2,1fr); gap: 18rpx; }.metric-card { padding: 26rpx; }.metric-icon { width: 62rpx; height: 62rpx; border-radius: 20rpx; text-align: center; font-size: 29rpx; line-height: 62rpx; }.metric-value,.metric-label { display: block; }.metric-value { margin-top: 18rpx; color: var(--text); font-size: 36rpx; font-weight: 900; }.metric-label { margin-top: 5rpx; color: var(--muted); font-size: 20rpx; }.system-card { margin-top: 24rpx; padding: 30rpx; }.system-row { min-height: 78rpx; display: flex; align-items: center; justify-content: space-between; color: var(--muted); border-bottom: 1rpx solid rgba(193,199,210,.25); }.system-row text:last-child { color: var(--text); }
.admin-search { height: 86rpx; padding: 0 22rpx; display: flex; align-items: center; gap: 16rpx; }.admin-search text { color: var(--muted); font-size: 34rpx; }.admin-search input { flex: 1; height: 86rpx; }.admin-search button { width: 66rpx; height: 66rpx; padding: 0; background: transparent; color: var(--muted); font-size: 34rpx; line-height: 66rpx; }.result-summary { height: 90rpx; padding: 0 4rpx; display: flex; align-items: center; justify-content: space-between; color: var(--muted); font-size: 21rpx; }.result-summary button { height: 60rpx; padding: 0 20rpx; background: rgba(0,94,161,.08); color: var(--primary); font-size: 20rpx; line-height: 60rpx; }
.admin-list { display: flex; flex-direction: column; gap: 20rpx; padding-bottom: 32rpx; }.admin-card,.log-card { padding: 28rpx; }.admin-card-top { display: flex; align-items: center; gap: 18rpx; }.user-avatar,.lecture-icon { flex: 0 0 auto; width: 72rpx; height: 72rpx; border-radius: 24rpx; background: rgba(0,94,161,.1); color: var(--primary); text-align: center; font-size: 28rpx; font-weight: 850; line-height: 72rpx; }.card-main { flex: 1; min-width: 0; }.item-title,.item-meta { display: block; }.item-title { overflow: hidden; color: var(--text); font-size: 26rpx; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }.item-meta { margin-top: 7rpx; color: var(--muted); font-size: 19rpx; }.status-badge,.action-badge { padding: 6rpx 13rpx; border-radius: 999rpx; background: var(--surface-container); color: var(--muted); font-size: 17rpx; font-weight: 800; }.status-badge.active,.status-badge.completed { background: rgba(0,110,28,.1); color: var(--secondary); }.status-badge.disabled,.status-badge.failed { background: #ffdad6; color: var(--error); }.status-badge.recording { background: rgba(0,94,161,.1); color: var(--primary); }.detail-grid { margin-top: 22rpx; padding: 18rpx; display: grid; grid-template-columns: 1fr 1fr; gap: 14rpx; border-radius: 18rpx; background: var(--surface-low); color: var(--muted); font-size: 19rpx; }.admin-actions { margin-top: 22rpx; display: flex; gap: 12rpx; justify-content: flex-end; }.admin-actions button { height: 62rpx; padding: 0 18rpx; border-radius: 16rpx; background: var(--surface-container); color: var(--primary); font-size: 19rpx; line-height: 62rpx; }.admin-actions .danger { background: #ffdad6; color: var(--error); }.log-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18rpx; color: var(--muted); font-size: 18rpx; }.action-badge { border-radius: 9rpx; background: rgba(0,94,161,.1); color: var(--primary); }.detail-json { display: block; margin-top: 16rpx; padding: 16rpx; border-radius: 14rpx; background: var(--surface-low); color: var(--muted); font-size: 18rpx; word-break: break-all; }.pager { height: 110rpx; display: flex; align-items: center; justify-content: center; gap: 24rpx; }.pager button { height: 64rpx; padding: 0 24rpx; background: var(--surface-container); color: var(--primary); font-size: 20rpx; line-height: 64rpx; }
@media (min-width:768px) { .metric-grid { grid-template-columns: repeat(3,1fr); } }
</style>
