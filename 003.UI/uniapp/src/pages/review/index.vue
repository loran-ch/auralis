<template>
  <view class="page review-page" :class="themeClass">
    <AppHeader :title="lecture.course_name || '课堂回顾'" :subtitle="headerSubtitle" back fallback="/pages/history/index">
      <template #right><button class="share-button" @tap="shareLecture">↗</button></template>
    </AppHeader>

    <scroll-view class="review-scroll" scroll-y>
      <view class="content content-wide">
        <view v-if="loading" class="empty"><text class="empty-icon">◷</text>正在加载课堂内容…</view>
        <template v-else>
          <view class="overview-card card">
            <view class="overview-top"><view><text class="lecture-title">{{ lecture.course_name }}</text><text class="lecture-meta">{{ formatDate(lecture.started_at, true) }} · {{ formatDuration(lecture.duration_seconds) }}</text></view><button class="edit-button" @tap="openEdit">编辑</button></view>
            <view class="overview-stats"><view><text class="stat-value">{{ lecture.sentence_count || transcripts.length }}</text><text class="stat-label">句话</text></view><view><text class="stat-value">{{ lecture.bookmark_count || bookmarkedCount }}</text><text class="stat-label">收藏</text></view><view><text class="stat-value">{{ lecture.source_lang }}→{{ lecture.target_lang }}</text><text class="stat-label">翻译语言</text></view></view>
          </view>

          <view class="player-card card">
            <view class="wave-track"><view v-for="index in 34" :key="index" class="wave-bar" :class="{ played: progressPercent >= (index / 34) * 100 }" :style="{ height: `${22 + (index * 29) % 58}%` }" /></view>
            <slider class="progress-slider" :value="progressPercent" min="0" max="100" activeColor="#005ea1" backgroundColor="#dfe3e8" block-color="#005ea1" block-size="14" @changing="seekTo" @change="seekTo" />
            <view class="time-row"><text>{{ formatClock(currentTime) }}</text><text>{{ formatClock(duration || lecture.duration_seconds) }}</text></view>
            <view class="player-actions"><button class="seek-button" :disabled="!lecture.audio_url" @tap="skip(-10)">↶<text>10</text></button><button class="play-button" :disabled="!lecture.audio_url" @tap="togglePlay">{{ playing ? 'Ⅱ' : '▶' }}</button><button class="seek-button" :disabled="!lecture.audio_url" @tap="skip(10)">↷<text>10</text></button><button class="speed-button" :disabled="!lecture.audio_url" @tap="changeSpeed">{{ speed }}x</button></view>
            <text v-if="!lecture.audio_url" class="no-audio">本课堂没有保存音频，双语转录仍可正常查看</text>
          </view>

          <view class="section-row"><view><text class="section-title">双语课堂笔记</text><text class="section-subtitle">点击星标收藏重点句子</text></view><button class="export-button" :disabled="!transcripts.length" @tap="shareLecture">导出</button></view>
          <view v-if="!transcripts.length" class="empty card"><text class="empty-icon">≡</text>本课堂暂无转录内容</view>
          <view v-else class="transcript-list">
            <view v-for="(item, index) in transcripts" :key="item.id" class="transcript-card card" :class="{ bookmarked: item.is_bookmarked }">
              <view class="sentence-number">{{ String(index + 1).padStart(2, '0') }}</view>
              <view class="sentence-body"><view v-if="item.is_bookmarked" class="tag-badge" :style="{ background: tagMeta[item.bookmark_tag]?.color || '#874e00' }">{{ tagMeta[item.bookmark_tag]?.icon || '⭐' }} {{ tagMeta[item.bookmark_tag]?.label || '已收藏' }}</view><text class="source-text">{{ item.source_text }}</text><text class="translation-text">{{ item.translated_text || '暂无翻译' }}</text></view>
              <button class="bookmark-button" :class="{ active: item.is_bookmarked }" @tap="toggleBookmark(item)">★</button>
            </view>
          </view>
        </template>
      </view>
    </scroll-view>

    <TagSheet v-model="tagOpen" @select="saveBookmark" />
    <view v-if="editOpen" class="modal-mask center" @tap.self="editOpen = false">
      <view class="modal-card">
        <text class="section-title">编辑课堂信息</text>
        <view class="field"><text class="field-label">课程名称</text><input v-model="editForm.course_name" class="input" maxlength="80" /></view>
        <view class="field"><text class="field-label">地点</text><input v-model="editForm.location_name" class="input" maxlength="80" placeholder="例如：教学楼 A" /></view>
        <view class="field"><text class="field-label">教室</text><input v-model="editForm.room" class="input" maxlength="32" placeholder="例如：302" /></view>
        <view class="modal-actions"><button class="btn btn-soft" @tap="editOpen = false">取消</button><button class="btn btn-primary" @tap="saveEdit">保存</button></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad, onShareAppMessage, onUnload } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import TagSheet from '../../components/TagSheet.vue'
import { bookmarkApi, lectureApi } from '../../api'
import { requireAuth } from '../../api/session'
import { createAudioPlayer } from '../../platform/audio-player'
import { shareText } from '../../platform/share'
import { formatClock, formatDate, formatDuration, showError, tagMeta } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const id = ref(0)
const lecture = ref({})
const transcripts = ref([])
const loading = ref(true)
const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const speed = ref(1)
const tagOpen = ref(false)
const selectedTranscript = ref(null)
const editOpen = ref(false)
const editForm = reactive({ course_name: '', location_name: '', room: '' })
const themeClass = useTheme()
let player = null

const headerSubtitle = computed(() => [lecture.value.location_name, lecture.value.room].filter(Boolean).join(' · ') || formatDate(lecture.value.lecture_date))
const bookmarkedCount = computed(() => transcripts.value.filter((item) => item.is_bookmarked).length)
const progressPercent = computed(() => duration.value ? Math.min(100, currentTime.value / duration.value * 100) : 0)

onLoad(async (options) => {
  if (!requireAuth()) return
  id.value = Number(options.id)
  if (!id.value) return uni.reLaunch({ url: '/pages/history/index' })
  await load()
})

onUnload(() => player?.destroy())
onShareAppMessage(() => ({ title: lecture.value.course_name || 'Auralis 智听 课堂笔记', path: `/pages/review/index?id=${id.value}` }))

async function load() {
  loading.value = true
  try {
    const [lectureData, transcriptData] = await Promise.all([lectureApi.detail(id.value), lectureApi.transcriptions(id.value)])
    lecture.value = lectureData
    transcripts.value = transcriptData
    if (lectureData.audio_url) {
      player = createAudioPlayer({
        onReady: (value) => { duration.value = value || lectureData.duration_seconds || 0 },
        onState: (value) => { playing.value = value },
        onTime: (current, total) => { currentTime.value = current; duration.value = total || duration.value },
        onError: () => uni.showToast({ title: '音频播放失败', icon: 'none' }),
      })
      player.setSource(lectureData.audio_url)
    }
  } catch (error) { showError(error, '课堂内容加载失败') }
  finally { loading.value = false }
}

function togglePlay() {
  if (!lecture.value.audio_url) return uni.showToast({ title: '该课堂没有保存音频', icon: 'none' })
  playing.value ? player.pause() : player.play()
}
function skip(seconds) { player?.seek(Math.min(duration.value, Math.max(0, currentTime.value + seconds))) }
function seekTo(event) { if (duration.value) player?.seek(duration.value * Number(event.detail.value) / 100) }
function changeSpeed() {
  const speeds = [1, 1.25, 1.5, 2]
  speed.value = speeds[(speeds.indexOf(speed.value) + 1) % speeds.length]
  player?.setRate(speed.value)
}
function toggleBookmark(item) {
  if (item.is_bookmarked) {
    uni.showModal({ title: '取消收藏', content: '确定取消收藏这句话吗？', success: async (result) => {
      if (!result.confirm) return
      try { await bookmarkApi.removeByTranscription(item.id); item.is_bookmarked = false; item.bookmark_tag = null; lecture.value.bookmark_count = bookmarkedCount.value }
      catch (error) { showError(error, '取消收藏失败') }
    } })
  } else { selectedTranscript.value = item; tagOpen.value = true }
}
async function saveBookmark(tag) {
  try {
    await bookmarkApi.add({ transcription_id: selectedTranscript.value.id, tag })
    selectedTranscript.value.is_bookmarked = true
    selectedTranscript.value.bookmark_tag = tag
    lecture.value.bookmark_count = bookmarkedCount.value
    uni.showToast({ title: '已收藏', icon: 'success' })
  } catch (error) { showError(error, '收藏失败') }
}
function openEdit() {
  Object.assign(editForm, { course_name: lecture.value.course_name || '', location_name: lecture.value.location_name || '', room: lecture.value.room || '' })
  editOpen.value = true
}
async function saveEdit() {
  if (!editForm.course_name.trim()) return uni.showToast({ title: '课程名称不能为空', icon: 'none' })
  try {
    lecture.value = await lectureApi.update(id.value, { course_name: editForm.course_name.trim(), location_name: editForm.location_name.trim() || null, room: editForm.room.trim() || null })
    editOpen.value = false
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (error) { showError(error, '保存失败') }
}
function exportContent() {
  const lines = [`${lecture.value.course_name || '课堂笔记'}`, `${formatDate(lecture.value.started_at, true)} · ${formatDuration(lecture.value.duration_seconds)}`, '']
  transcripts.value.forEach((item, index) => lines.push(`【${index + 1}】${item.is_bookmarked ? ' [已收藏]' : ''}\n${item.source_text}\n${item.translated_text || ''}\n`))
  return lines.join('\n')
}
async function shareLecture() {
  if (!transcripts.value.length) return uni.showToast({ title: '暂无数据可导出', icon: 'none' })
  shareText(lecture.value.course_name || '课堂笔记', exportContent())
  try { lecture.value = await lectureApi.update(id.value, { exported: true }) } catch (_) {}
}
</script>

<style scoped>
.review-page { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }.review-scroll { flex: 1; min-height: 0; }.share-button { width: 80rpx; height: 80rpx; padding: 0; border-radius: 50%; background: transparent; color: var(--primary); font-size: 38rpx; line-height: 80rpx; }
.overview-card { padding: 32rpx; }.overview-top { display: flex; justify-content: space-between; gap: 20rpx; }.lecture-title,.lecture-meta { display: block; }.lecture-title { font-size: 36rpx; font-weight: 850; color: var(--text); }.lecture-meta { margin-top: 10rpx; color: var(--muted); font-size: 22rpx; }.edit-button,.export-button { min-width: 100rpx; height: 62rpx; padding: 0 20rpx; border-radius: 18rpx; background: rgba(0,94,161,.1); color: var(--primary); font-size: 22rpx; line-height: 62rpx; }.overview-stats { margin-top: 30rpx; padding-top: 26rpx; display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1rpx solid rgba(193,199,210,.35); }.overview-stats>view { display: flex; flex-direction: column; align-items: center; }.stat-value { color: var(--primary); font-size: 27rpx; font-weight: 850; }.stat-label { margin-top: 7rpx; color: var(--muted); font-size: 20rpx; }
.player-card { margin-top: 24rpx; padding: 28rpx 30rpx; }.wave-track { height: 90rpx; display: flex; align-items: center; gap: 5rpx; }.wave-bar { flex: 1; min-width: 3rpx; border-radius: 999rpx; background: var(--outline); opacity: .65; }.wave-bar.played { background: var(--primary); opacity: 1; }.progress-slider { margin: -20rpx -16rpx -8rpx; }.time-row { display: flex; justify-content: space-between; color: var(--muted); font-size: 19rpx; font-variant-numeric: tabular-nums; }.player-actions { margin-top: 18rpx; display: flex; align-items: center; justify-content: center; gap: 24rpx; }.seek-button,.play-button,.speed-button { padding: 0; border-radius: 50%; }.seek-button { width: 74rpx; height: 74rpx; background: var(--surface-container); color: var(--muted); font-size: 29rpx; line-height: 74rpx; }.seek-button text { font-size: 15rpx; }.play-button { width: 96rpx; height: 96rpx; background: var(--primary); color: #fff; font-size: 34rpx; line-height: 96rpx; }.speed-button { width: 72rpx; height: 72rpx; background: rgba(0,110,28,.1); color: var(--secondary); font-size: 20rpx; font-weight: 800; line-height: 72rpx; }.no-audio { display: block; margin-top: 20rpx; color: var(--muted); font-size: 21rpx; text-align: center; }
.section-row { margin: 42rpx 4rpx 22rpx; display: flex; align-items: center; justify-content: space-between; }.transcript-list { display: flex; flex-direction: column; gap: 22rpx; padding-bottom: 40rpx; }.transcript-card { padding: 28rpx 20rpx; display: flex; align-items: flex-start; border-left: 5rpx solid rgba(0,94,161,.2); }.transcript-card.bookmarked { border-left-color: var(--tertiary); background: #fffaf3; }.sentence-number { flex: 0 0 auto; width: 64rpx; color: var(--outline); font-size: 20rpx; font-weight: 800; }.sentence-body { flex: 1; min-width: 0; }.tag-badge { display: inline-flex; margin-bottom: 12rpx; padding: 5rpx 12rpx; border-radius: 8rpx; color: #fff; font-size: 17rpx; font-weight: 800; }.source-text,.translation-text { display: block; line-height: 1.65; }.source-text { color: var(--text); font-size: 28rpx; }.translation-text { margin-top: 10rpx; color: var(--secondary); font-size: 27rpx; font-style: italic; }.bookmark-button { flex: 0 0 auto; width: 70rpx; height: 70rpx; margin-left: 14rpx; padding: 0; border-radius: 50%; background: var(--surface-container); color: var(--outline); font-size: 32rpx; line-height: 70rpx; }.bookmark-button.active { background: #ffdcbe; color: var(--tertiary); }
.field { margin-top: 24rpx; margin-bottom: 0; }.modal-actions { margin-top: 32rpx; display: flex; gap: 16rpx; }.modal-actions .btn { flex: 1; }
</style>
