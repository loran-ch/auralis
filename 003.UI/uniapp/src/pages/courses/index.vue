<template>
  <view class="page page-with-nav" :class="themeClass">
    <AppHeader title="课程中心" subtitle="教师发布课程，学生查看已共享内容">
      <template #right><button v-if="canTeach" class="header-add" @tap="formOpen = true">＋</button></template>
    </AppHeader>

    <view class="content content-wide">
      <view class="course-tabs card">
        <view class="course-tab" :class="{ active: tab === 'mine' }" @tap="tab = 'mine'">{{ canTeach ? '我创建的' : '我的课程' }}</view>
        <view class="course-tab" :class="{ active: tab === 'public' }" @tap="tab = 'public'">共享课程</view>
      </view>

      <view v-if="loading" class="empty"><text class="empty-icon">◌</text>正在加载课程…</view>
      <template v-else>
        <view v-if="tab === 'mine' && !courses.length" class="empty card">
          <text class="empty-icon">▦</text><text class="empty-title">还没有课程</text>
          <text class="empty-copy">{{ canTeach ? '创建课程后，可将课堂录音与课后资料归入同一课程。' : '去共享课程中查看教师发布的课堂内容。' }}</text>
          <button v-if="canTeach" class="btn btn-primary empty-button" @tap="formOpen = true">创建课程</button>
        </view>
        <view v-else-if="tab === 'public' && !publicCourses.length" class="empty card"><text class="empty-icon">▦</text><text class="empty-title">暂无共享课程</text><text class="empty-copy">教师发布课程后会显示在这里。</text></view>

        <view v-else class="course-list">
          <view v-for="course in visibleCourses" :key="course.id" class="course-card card" @tap="openCourse(course)">
            <view class="course-color" :style="{ background: course.color || '#2563EB' }" />
            <view class="course-main">
              <view class="course-title-row"><text class="course-name">{{ course.name }}</text><text v-if="course.is_public" class="public-badge">已共享</text></view>
              <text class="course-meta">{{ course.owner_nickname || course.professor_name || '课程教师待补充' }}<text v-if="course.term"> · {{ course.term }}</text></text>
              <text class="course-meta">{{ [course.room, `${course.source_lang} → ${course.target_lang}`].filter(Boolean).join(' · ') }}</text>
            </view>
            <text class="chevron">›</text>
          </view>
        </view>
      </template>

      <view v-if="selected" class="overview-card card">
        <view class="overview-head"><view><text class="section-title">{{ selected.course.name }}</text><text class="section-subtitle">{{ selected.completed_lecture_count || 0 }} 节已完成 · {{ formatDuration(selected.total_duration_seconds) }}</text></view><button class="close-button" @tap="selected = null">×</button></view>
        <view v-if="canManageSelected" class="publish-row"><view><text class="setting-title">发布课程</text><text class="setting-description">学生可浏览已完成课次及课后资料</text></view><switch :checked="selected.course.is_public" color="#005ea1" @change="togglePublish" /></view>
        <view class="lecture-heading"><text class="section-title">最近课次</text><button class="ask-button" @tap="openAssistant(selected.course)">问小橘子</button></view>
        <view v-if="!selected.recent_lectures?.length" class="mini-empty">尚无已完成课堂</view>
        <view v-for="lecture in selected.recent_lectures || []" :key="lecture.id" class="lecture-row" @tap="openLecture(lecture.id)"><view class="lecture-dot" :style="{ background: selected.course.color || '#2563EB' }" /><view class="lecture-info"><text>{{ lecture.title || lecture.course_name }}</text><text>{{ formatDate(lecture.lecture_date) }} · {{ lecture.sentence_count || 0 }} 句</text></view><text class="chevron">›</text></view>
      </view>
    </view>

    <view v-if="formOpen" class="modal-mask center" @tap.self="formOpen = false"><view class="modal-card"><text class="section-title">创建课程</text><text class="section-subtitle">创建后可在课程概览中发布给学生。</text><view class="field"><text class="field-label">课程名称</text><input v-model="form.name" class="input" maxlength="80" placeholder="例如：机器学习导论" /></view><view class="field"><text class="field-label">授课教师</text><input v-model="form.professor_name" class="input" maxlength="64" placeholder="例如：王老师" /></view><view class="form-grid"><view class="field"><text class="field-label">学期</text><input v-model="form.term" class="input" maxlength="32" placeholder="2026 秋季" /></view><view class="field"><text class="field-label">教室</text><input v-model="form.room" class="input" maxlength="32" placeholder="A302" /></view></view><view class="publish-row compact"><view><text class="setting-title">实时翻译</text><text class="setting-description">课堂默认开启双语字幕</text></view><switch :checked="form.translation_enabled" color="#005ea1" @change="form.translation_enabled = $event.detail.value" /></view><view class="modal-actions"><button class="btn btn-soft" @tap="formOpen = false">取消</button><button class="btn btn-primary" :disabled="saving" @tap="createCourse">{{ saving ? '创建中…' : '创建课程' }}</button></view></view></view>
    <BottomNav active="courses" />
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import BottomNav from '../../components/BottomNav.vue'
import { authApi, courseApi } from '../../api'
import { requireAuth } from '../../api/session'
import { formatDate, formatDuration, showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const themeClass = useTheme()
const user = ref({})
const courses = ref([])
const publicCourses = ref([])
const loading = ref(false)
const saving = ref(false)
const tab = ref('mine')
const selected = ref(null)
const formOpen = ref(false)
const form = reactive({ name: '', professor_name: '', term: '', room: '', source_lang: 'en', target_lang: 'zh-CN', translation_enabled: true, color: '#2563EB' })
const canTeach = computed(() => ['admin', 'super_admin'].includes(user.value.role))
const visibleCourses = computed(() => tab.value === 'mine' ? courses.value : publicCourses.value.filter((item) => !item.is_owner))
const canManageSelected = computed(() => Boolean(selected.value?.course?.is_owner && canTeach.value))

onShow(() => { if (requireAuth()) load() })
onPullDownRefresh(async () => { await load(); uni.stopPullDownRefresh() })

async function load() {
  loading.value = true
  try {
    const [me, mine, shared] = await Promise.all([authApi.me(), courseApi.list(), courseApi.listPublic()])
    user.value = me
    courses.value = mine || []
    publicCourses.value = shared || []
  } catch (error) { showError(error, '课程加载失败') }
  finally { loading.value = false }
}
async function openCourse(course) {
  try { selected.value = await courseApi.overview(course.id) }
  catch (error) { showError(error, '课程概览加载失败') }
}
async function createCourse() {
  if (!form.name.trim()) return uni.showToast({ title: '请输入课程名称', icon: 'none' })
  saving.value = true
  try {
    const created = await courseApi.create({ ...form, name: form.name.trim(), professor_name: form.professor_name.trim() || null, term: form.term.trim() || null, room: form.room.trim() || null })
    formOpen.value = false
    Object.assign(form, { name: '', professor_name: '', term: '', room: '', source_lang: 'en', target_lang: 'zh-CN', translation_enabled: true, color: '#2563EB' })
    uni.showToast({ title: '课程已创建', icon: 'success' })
    await load()
    openCourse(created)
  } catch (error) { showError(error, '创建课程失败') }
  finally { saving.value = false }
}
async function togglePublish(event) {
  const next = Boolean(event.detail.value)
  try {
    const course = await courseApi.update(selected.value.course.id, { is_public: next })
    selected.value = { ...selected.value, course }
    uni.showToast({ title: next ? '课程已发布' : '已取消发布', icon: 'success' })
    await load()
  } catch (error) { showError(error, '发布状态更新失败') }
}
function openLecture(id) { uni.navigateTo({ url: `/pages/review/index?id=${id}` }) }
function openAssistant(course) { uni.reLaunch({ url: `/pages/assistant/index?course_id=${course.id}` }) }
</script>

<style scoped>
.header-add { width: 76rpx; height: 76rpx; padding: 0; border-radius: 50%; background: rgba(0,94,161,.1); color: var(--primary); font-size: 42rpx; line-height: 76rpx; }.course-tabs { height: 88rpx; padding: 8rpx; display: flex; }.course-tab { flex: 1; display: flex; align-items: center; justify-content: center; border-radius: 20rpx; color: var(--muted); font-size: 24rpx; font-weight: 700; }.course-tab.active { background: rgba(0,94,161,.1); color: var(--primary); }.course-list { margin-top: 24rpx; display: flex; flex-direction: column; gap: 18rpx; }.course-card { min-height: 152rpx; padding: 24rpx; display: flex; align-items: center; gap: 20rpx; }.course-color { width: 14rpx; align-self: stretch; border-radius: 999rpx; }.course-main { flex: 1; min-width: 0; }.course-title-row { display: flex; align-items: center; gap: 12rpx; }.course-name { overflow: hidden; color: var(--text); font-size: 29rpx; font-weight: 800; text-overflow: ellipsis; white-space: nowrap; }.public-badge { flex: 0 0 auto; padding: 5rpx 11rpx; border-radius: 999rpx; background: rgba(0,110,28,.1); color: var(--secondary); font-size: 17rpx; font-weight: 800; }.course-meta { display: block; margin-top: 8rpx; overflow: hidden; color: var(--muted); font-size: 20rpx; text-overflow: ellipsis; white-space: nowrap; }.chevron { color: var(--outline); font-size: 46rpx; }.overview-card { margin-top: 30rpx; padding: 30rpx; }.overview-head { display: flex; justify-content: space-between; gap: 20rpx; }.close-button { width: 62rpx; height: 62rpx; padding: 0; border-radius: 50%; background: var(--surface-container); color: var(--muted); font-size: 32rpx; line-height: 62rpx; }.publish-row { min-height: 112rpx; margin-top: 24rpx; padding: 20rpx; display: flex; align-items: center; justify-content: space-between; gap: 24rpx; border-radius: 20rpx; background: var(--surface-low); }.publish-row.compact { margin-top: 0; }.setting-title,.setting-description { display: block; }.setting-title { color: var(--text); font-size: 24rpx; font-weight: 750; }.setting-description { margin-top: 5rpx; color: var(--muted); font-size: 19rpx; }.lecture-heading { margin-top: 30rpx; display: flex; align-items: center; justify-content: space-between; }.ask-button { height: 62rpx; padding: 0 18rpx; border-radius: 18rpx; background: rgba(0,94,161,.1); color: var(--primary); font-size: 20rpx; line-height: 62rpx; }.lecture-row { min-height: 96rpx; display: flex; align-items: center; gap: 16rpx; border-bottom: 1rpx solid rgba(193,199,210,.35); }.lecture-dot { width: 12rpx; height: 12rpx; border-radius: 50%; }.lecture-info { flex: 1; min-width: 0; }.lecture-info text { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.lecture-info text:first-child { color: var(--text); font-size: 24rpx; font-weight: 700; }.lecture-info text:last-child { margin-top: 6rpx; color: var(--muted); font-size: 18rpx; }.mini-empty { padding: 36rpx 0; color: var(--muted); font-size: 22rpx; text-align: center; }.empty { margin-top: 24rpx; display: flex; flex-direction: column; align-items: center; }.empty-title { color: var(--text); font-size: 30rpx; font-weight: 800; }.empty-copy { max-width: 520rpx; margin-top: 14rpx; color: var(--muted); font-size: 22rpx; line-height: 1.6; text-align: center; }.empty-button { margin-top: 28rpx; }.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; }.modal-actions { margin-top: 28rpx; display: flex; gap: 16rpx; }.modal-actions .btn { flex: 1; }
</style>
