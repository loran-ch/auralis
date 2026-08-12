<template>
  <view class="page page-with-nav" :class="themeClass">
    <AppHeader title="知识卡片" subtitle="收藏的重点、疑问与考点" />
    <view class="content content-wide">
      <view class="hero-card card"><view><text class="hero-label">我的知识库</text><text class="hero-count">{{ items.length }}</text><text class="hero-unit">张卡片</text></view><view class="hero-icon">★</view></view>
      <scroll-view class="tag-scroll" scroll-x :show-scrollbar="false"><view class="tag-row"><view v-for="item in filters" :key="item.key" class="filter-tag" :class="{ active: activeTag === item.key }" @tap="changeTag(item.key)">{{ item.icon }} {{ item.label }}</view></view></scroll-view>

      <view v-if="loading" class="empty"><text class="empty-icon">★</text>正在加载知识卡片…</view>
      <view v-else-if="!items.length" class="empty card"><text class="empty-icon">☆</text><text class="empty-title">这个分类还没有卡片</text><text class="empty-copy">在录音或课堂回顾中收藏重要句子，它们会出现在这里。</text><button class="btn btn-primary empty-button" @tap="uni.reLaunch({ url: '/pages/recorder/index' })">去录音</button></view>
      <view v-else class="card-grid">
        <view v-for="item in items" :key="item.bookmark_id" class="knowledge-card card">
          <view class="card-top"><view class="tag-badge" :style="{ background: tagMeta[item.tag]?.color || '#005ea1' }">{{ tagMeta[item.tag]?.icon }} {{ tagMeta[item.tag]?.label || item.tag }}</view><text class="date-text">{{ formatDate(item.created_at, true) }}</text></view>
          <text class="course-name">{{ item.course_name || '未命名课堂' }}</text>
          <text class="source-text">{{ item.source_text }}</text>
          <text class="translation-text">{{ item.translated_text || '暂无翻译' }}</text>
          <view v-if="item.note" class="note-box"><text class="note-label">我的笔记</text><text class="note-text">{{ item.note }}</text></view>
          <view class="card-actions"><button class="action-button" @tap="openReview(item)">▶ 回顾课堂</button><button class="action-button" @tap="openEdit(item)">✎ 编辑</button><button class="delete-action" @tap="removeCard(item)">删除</button></view>
        </view>
      </view>
    </view>
    <BottomNav active="cards" />

    <view v-if="editOpen" class="modal-mask center" @tap.self="editOpen = false">
      <view class="modal-card">
        <text class="section-title">编辑知识卡片</text>
        <text class="section-subtitle">补充你的理解，复习时会更高效</text>
        <view class="edit-tags"><view v-for="item in filters.slice(1)" :key="item.key" class="filter-tag" :class="{ active: editTag === item.key }" @tap="editTag = item.key">{{ item.icon }} {{ item.label }}</view></view>
        <textarea v-model="editNote" class="textarea note-editor" maxlength="2000" placeholder="写下笔记、关键词或待解决的问题…" />
        <view class="modal-actions"><button class="btn btn-soft" @tap="editOpen = false">取消</button><button class="btn btn-primary" @tap="saveEdit">保存</button></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import BottomNav from '../../components/BottomNav.vue'
import { bookmarkApi } from '../../api'
import { requireAuth } from '../../api/session'
import { formatDate, showError, tagMeta } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const filters = [
  { key: '', label: '全部', icon: '✦' },
  { key: 'important', label: '重要', icon: '⭐' },
  { key: 'question', label: '疑问', icon: '❓' },
  { key: 'exam', label: '考点', icon: '🎯' },
  { key: 'definition', label: '定义', icon: '📘' },
]
const items = ref([])
const activeTag = ref('')
const loading = ref(false)
const editOpen = ref(false)
const editing = ref(null)
const editTag = ref('important')
const editNote = ref('')
const themeClass = useTheme()

onShow(() => { if (requireAuth()) load() })
onPullDownRefresh(async () => { await load(); uni.stopPullDownRefresh() })
async function load() {
  loading.value = true
  try { items.value = await bookmarkApi.list(activeTag.value) }
  catch (error) { showError(error, '知识卡片加载失败') }
  finally { loading.value = false }
}
function changeTag(tag) { activeTag.value = tag; load() }
function openReview(item) { uni.navigateTo({ url: `/pages/review/index?id=${item.lecture_id}` }) }
function openEdit(item) { editing.value = item; editTag.value = item.tag; editNote.value = item.note || ''; editOpen.value = true }
async function saveEdit() {
  try {
    const updated = await bookmarkApi.update(editing.value.bookmark_id, { tag: editTag.value, note: editNote.value.trim() || null })
    const index = items.value.findIndex((item) => item.bookmark_id === updated.bookmark_id)
    if (index >= 0) items.value[index] = updated
    editOpen.value = false
    uni.showToast({ title: '卡片已保存', icon: 'success' })
  } catch (error) { showError(error, '卡片保存失败') }
}
function removeCard(item) {
  uni.showModal({ title: '删除知识卡片', content: '只会取消收藏，不会删除原课堂内容。', confirmColor: '#ba1a1a', success: async (result) => {
    if (!result.confirm) return
    try { await bookmarkApi.remove(item.bookmark_id); items.value = items.value.filter((value) => value.bookmark_id !== item.bookmark_id); uni.showToast({ title: '已删除', icon: 'success' }) }
    catch (error) { showError(error, '删除失败') }
  } })
}
</script>

<style scoped>
.hero-card { padding: 32rpx 36rpx; display: flex; align-items: center; justify-content: space-between; background: linear-gradient(135deg, #005ea1, #2b78bf); color: #fff; }.hero-label,.hero-count,.hero-unit { display: block; }.hero-label { font-size: 22rpx; opacity: .82; }.hero-count { margin-top: 8rpx; font-size: 54rpx; font-weight: 900; line-height: 1; }.hero-unit { margin-top: 7rpx; font-size: 20rpx; opacity: .75; }.hero-icon { width: 106rpx; height: 106rpx; border-radius: 32rpx; background: rgba(255,255,255,.15); text-align: center; color: #ffdcbe; font-size: 55rpx; line-height: 106rpx; }
.tag-scroll { width: 100%; margin: 28rpx 0; white-space: nowrap; }.tag-row,.edit-tags { display: flex; gap: 14rpx; }.filter-tag { flex: 0 0 auto; min-height: 62rpx; padding: 0 22rpx; border-radius: 999rpx; background: var(--surface-container); color: var(--muted); font-size: 22rpx; line-height: 62rpx; }.filter-tag.active { background: var(--primary); color: #fff; font-weight: 750; }
.card-grid { display: grid; grid-template-columns: 1fr; gap: 24rpx; }.knowledge-card { padding: 30rpx; border-top: 7rpx solid rgba(0,94,161,.35); }.card-top { display: flex; align-items: center; justify-content: space-between; }.tag-badge { padding: 7rpx 15rpx; border-radius: 10rpx; color: #fff; font-size: 18rpx; font-weight: 800; }.date-text { color: var(--muted); font-size: 19rpx; }.course-name { display: block; margin-top: 22rpx; color: var(--muted); font-size: 21rpx; font-weight: 700; }.source-text,.translation-text { display: block; line-height: 1.65; }.source-text { margin-top: 18rpx; color: var(--text); font-size: 29rpx; }.translation-text { margin-top: 12rpx; color: var(--secondary); font-size: 27rpx; font-style: italic; }.note-box { margin-top: 22rpx; padding: 20rpx; border-radius: 20rpx; background: var(--surface-low); }.note-label,.note-text { display: block; }.note-label { color: var(--primary); font-size: 19rpx; font-weight: 800; }.note-text { margin-top: 8rpx; color: var(--muted); font-size: 23rpx; line-height: 1.55; }.card-actions { margin-top: 26rpx; padding-top: 22rpx; display: flex; gap: 10rpx; border-top: 1rpx solid rgba(193,199,210,.3); }.action-button,.delete-action { height: 66rpx; padding: 0 16rpx; border-radius: 18rpx; background: var(--surface-container); color: var(--primary); font-size: 20rpx; line-height: 66rpx; }.delete-action { margin-left: auto; color: var(--error); }
.empty { display: flex; flex-direction: column; align-items: center; }.empty-title { color: var(--text); font-size: 30rpx; font-weight: 800; }.empty-copy { margin-top: 12rpx; max-width: 500rpx; line-height: 1.6; }.empty-button { margin-top: 30rpx; }.edit-tags { margin-top: 28rpx; flex-wrap: wrap; }.note-editor { margin-top: 24rpx; }.modal-actions { margin-top: 28rpx; display: flex; gap: 16rpx; }.modal-actions .btn { flex: 1; }
@media (min-width: 768px) { .card-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
