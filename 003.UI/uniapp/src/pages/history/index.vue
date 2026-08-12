<template>
  <view class="page page-with-nav" :class="themeClass">
    <AppHeader title="课堂记录" subtitle="所有录音与双语笔记">
      <template #right><button class="header-action-button" @tap="toggleManage">{{ managing ? '完成' : '管理' }}</button></template>
    </AppHeader>

    <view class="content content-wide">
      <view class="search-card card">
        <view class="search-row"><text class="search-icon">⌕</text><input v-model="search" class="search-input" confirm-type="search" placeholder="搜索课程名称" @confirm="reload" /><button v-if="search" class="clear-button" @tap="search = ''; reload()">×</button></view>
        <view class="filter-row">
          <picker mode="date" :value="dateFrom" @change="dateFrom = $event.detail.value; reload()"><view class="filter-pill">{{ dateFrom || '开始日期' }}</view></picker>
          <text class="date-arrow">至</text>
          <picker mode="date" :value="dateTo" @change="dateTo = $event.detail.value; reload()"><view class="filter-pill">{{ dateTo || '结束日期' }}</view></picker>
          <button v-if="dateFrom || dateTo" class="reset-filter" @tap="dateFrom = ''; dateTo = ''; reload()">清除</button>
        </view>
      </view>

      <view class="summary-row"><text>共 {{ total }} 节课堂</text><text class="summary-hint">长按可管理记录</text></view>

      <view v-if="loading && !items.length" class="empty"><text class="empty-icon">◷</text>正在加载课堂记录…</view>
      <view v-else-if="!items.length" class="empty card"><text class="empty-icon">◷</text><text class="empty-title">还没有课堂记录</text><text class="empty-copy">开始第一次录音，翻译内容会自动保存在这里。</text><button class="btn btn-primary empty-button" @tap="goRecorder">开始录音</button></view>
      <view v-else class="record-list">
        <view v-for="item in items" :key="item.id" class="record-card card" :class="{ selected: selectedIds.includes(item.id) }" @tap="openLecture(item)" @longpress="startManaging(item)">
          <view v-if="managing" class="check-circle" :class="{ checked: selectedIds.includes(item.id) }">{{ selectedIds.includes(item.id) ? '✓' : '' }}</view>
          <view class="record-main">
            <view class="record-top"><view class="title-block"><text class="record-title">{{ item.course_name || '未命名课堂' }}</text><text class="record-time">{{ formatDate(item.started_at, true) }}</text></view><text class="duration-pill">{{ formatClock(item.duration_seconds) }}</text></view>
            <view class="record-meta"><text>{{ item.source_lang }} → {{ item.target_lang }}</text><text>{{ item.sentence_count || 0 }} 句话</text><text v-if="item.bookmark_count" class="bookmark-meta">★ {{ item.bookmark_count }}</text></view>
            <view v-if="item.location_name || item.room" class="location-row">⌖ {{ [item.location_name, item.room].filter(Boolean).join(' · ') }}</view>
          </view>
          <text v-if="!managing" class="chevron">›</text>
        </view>
      </view>

      <button v-if="items.length < total" class="load-more" :disabled="loading" @tap="loadMore">{{ loading ? '加载中…' : '加载更多' }}</button>
    </view>

    <view v-if="managing" class="manage-bar">
      <view class="manage-inner content-wide"><button class="select-all" @tap="selectAll">{{ selectedIds.length === items.length ? '取消全选' : '全选' }}</button><text>已选 {{ selectedIds.length }} 项</text><button class="delete-button" :disabled="!selectedIds.length" @tap="removeSelected">删除</button></view>
    </view>
    <BottomNav v-else active="history" />
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import BottomNav from '../../components/BottomNav.vue'
import { lectureApi } from '../../api'
import { requireAuth } from '../../api/session'
import { formatClock, formatDate, showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const items = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const search = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const managing = ref(false)
const selectedIds = ref([])
const themeClass = useTheme()

onShow(() => { if (requireAuth()) reload() })
onPullDownRefresh(async () => { await reload(); uni.stopPullDownRefresh() })

async function fetchPage(reset = false) {
  if (loading.value) return
  loading.value = true
  if (reset) page.value = 1
  try {
    const result = await lectureApi.list({ page: page.value, size: 15, search: search.value.trim(), date_from: dateFrom.value, date_to: dateTo.value, status: 'all' })
    const nextItems = Array.isArray(result) ? result : (result.items || [])
    items.value = reset ? nextItems : items.value.concat(nextItems)
    total.value = Array.isArray(result) ? result.length : (result.total || 0)
  } catch (error) { showError(error, '课堂记录加载失败') }
  finally { loading.value = false }
}

function reload() { selectedIds.value = []; return fetchPage(true) }
function loadMore() { page.value += 1; fetchPage(false) }
function goRecorder() { uni.reLaunch({ url: '/pages/recorder/index' }) }
function openLecture(item) {
  if (managing.value) return toggleSelected(item.id)
  uni.navigateTo({ url: `/pages/review/index?id=${item.id}` })
}
function startManaging(item) { managing.value = true; toggleSelected(item.id) }
function toggleManage() { managing.value = !managing.value; if (!managing.value) selectedIds.value = [] }
function toggleSelected(id) { selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter((item) => item !== id) : [...selectedIds.value, id] }
function selectAll() { selectedIds.value = selectedIds.value.length === items.value.length ? [] : items.value.map((item) => item.id) }
function removeSelected() {
  if (!selectedIds.value.length) return
  uni.showModal({
    title: '删除课堂记录',
    content: `确定删除选中的 ${selectedIds.value.length} 条记录及其录音、转录和收藏吗？`,
    confirmColor: '#ba1a1a',
    success: async (result) => {
      if (!result.confirm) return
      try {
        await lectureApi.batchRemove(selectedIds.value)
        uni.showToast({ title: '删除成功', icon: 'success' })
        managing.value = false
        reload()
      } catch (error) { showError(error, '删除失败') }
    },
  })
}
</script>

<style scoped>
.header-action-button { width: 92rpx; height: 72rpx; padding: 0; background: transparent; color: var(--primary); font-size: 24rpx; font-weight: 750; line-height: 72rpx; }
.search-card { padding: 24rpx; }
.search-row { height: 84rpx; display: flex; align-items: center; border-radius: 24rpx; background: var(--surface-low); }
.search-icon { width: 76rpx; color: var(--muted); text-align: center; font-size: 38rpx; }.search-input { flex: 1; height: 84rpx; color: var(--text); }.clear-button { width: 70rpx; height: 70rpx; padding: 0; background: transparent; color: var(--muted); font-size: 38rpx; line-height: 70rpx; }
.filter-row { margin-top: 18rpx; display: flex; align-items: center; gap: 12rpx; }.filter-pill { min-height: 58rpx; padding: 0 20rpx; border-radius: 999rpx; background: rgba(0,94,161,.08); color: var(--primary); font-size: 21rpx; line-height: 58rpx; }.date-arrow { color: var(--muted); font-size: 21rpx; }.reset-filter { height: 58rpx; padding: 0 10rpx; background: transparent; color: var(--error); font-size: 21rpx; line-height: 58rpx; }
.summary-row { padding: 32rpx 4rpx 18rpx; display: flex; justify-content: space-between; color: var(--muted); font-size: 22rpx; }.summary-hint { opacity: .7; }
.record-list { display: flex; flex-direction: column; gap: 22rpx; }.record-card { position: relative; min-height: 190rpx; padding: 28rpx; display: flex; align-items: center; transition: .15s; }.record-card:active { transform: scale(.99); }.record-card.selected { border-color: var(--primary); background: rgba(0,94,161,.04); }.check-circle { flex: 0 0 auto; width: 44rpx; height: 44rpx; margin-right: 22rpx; border: 3rpx solid var(--outline); border-radius: 50%; color: #fff; text-align: center; line-height: 38rpx; }.check-circle.checked { border-color: var(--primary); background: var(--primary); }.record-main { flex: 1; min-width: 0; }.record-top { display: flex; justify-content: space-between; gap: 20rpx; }.title-block { min-width: 0; }.record-title,.record-time { display: block; }.record-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); font-size: 31rpx; font-weight: 800; }.record-time { margin-top: 8rpx; color: var(--muted); font-size: 21rpx; }.duration-pill { flex-shrink: 0; height: 48rpx; padding: 0 16rpx; border-radius: 14rpx; background: rgba(0,94,161,.1); color: var(--primary); font-size: 21rpx; line-height: 48rpx; }.record-meta { margin-top: 22rpx; display: flex; flex-wrap: wrap; gap: 18rpx; color: var(--muted); font-size: 22rpx; }.bookmark-meta { color: var(--tertiary); }.location-row { margin-top: 12rpx; color: var(--muted); font-size: 21rpx; }.chevron { margin-left: 18rpx; color: var(--outline); font-size: 52rpx; }
.empty { display: flex; flex-direction: column; align-items: center; }.empty-title { color: var(--text); font-size: 31rpx; font-weight: 800; }.empty-copy { max-width: 510rpx; margin-top: 14rpx; line-height: 1.6; }.empty-button { margin-top: 34rpx; }.load-more { height: 84rpx; margin: 30rpx auto; padding: 0 40rpx; background: transparent; color: var(--primary); font-size: 24rpx; line-height: 84rpx; }
.manage-bar { position: fixed; z-index: 80; left: 0; right: 0; bottom: 0; padding-bottom: env(safe-area-inset-bottom); background: var(--card); border-top: 1rpx solid var(--outline); }.manage-inner { height: 120rpx; padding: 0 40rpx; display: flex; align-items: center; justify-content: space-between; }.select-all,.delete-button { min-width: 120rpx; height: 72rpx; padding: 0 20rpx; border-radius: 20rpx; font-size: 24rpx; line-height: 72rpx; }.select-all { background: var(--surface-container); color: var(--primary); }.delete-button { background: #ffdad6; color: var(--error); }
</style>
