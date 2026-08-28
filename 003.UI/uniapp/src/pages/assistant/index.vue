<template>
  <view class="page page-with-nav assistant-page" :class="themeClass">
    <AppHeader title="小橘子" :subtitle="selectedCourse?.name || '选择课程后，基于课堂资料提问'">
      <template #right><button class="new-thread" @tap="newThread">＋</button></template>
    </AppHeader>

    <view class="assistant-content content-wide">
      <view class="scope-card card"><text class="scope-label">当前课程</text><picker :range="courseNames" :value="courseIndex" @change="changeCourse"><view class="scope-picker">{{ selectedCourse?.name || '请选择课程' }} <text>⌄</text></view></picker></view>
      <view v-if="!selectedCourse" class="empty card"><text class="empty-icon">✦</text><text class="empty-title">先选择一门课程</text><text class="empty-copy">助手会仅检索该课程中你有权限查看的课堂记录、简报和附件。</text><button class="btn btn-primary empty-button" @tap="goCourses">前往课程中心</button></view>
      <template v-else>
        <scroll-view class="thread-strip" scroll-x :show-scrollbar="false"><view class="thread-row"><view v-for="thread in threads" :key="thread.id" class="thread-chip" :class="{ active: activeThread?.id === thread.id }" @tap="openThread(thread.id)"><text>{{ thread.title || '新学习会话' }}</text><text v-if="activeThread?.id === thread.id" class="thread-remove" @tap.stop="removeThread(thread)">×</text></view><button class="thread-create" @tap="newThread">新会话</button></view></scroll-view>

        <scroll-view class="messages" scroll-y :scroll-into-view="scrollTarget">
          <view v-if="loading" class="loading-text">正在加载对话…</view>
          <view v-else-if="!messages.length" class="welcome-card card"><text class="welcome-title">我可以帮你回顾本课程</text><text class="welcome-copy">提问会优先使用课堂转录、简报、作业和附件，并在回答中保留来源线索。</text><view class="quick-list"><button @tap="quickAsk('get_notebook_overview', '这门课有哪些学习资料？')">资料概览</button><button @tap="quickAsk('list_assignments', '本课程有哪些作业或通知？')">查看作业</button><button @tap="quickAsk('search_notebook', '本节课的重点和考点是什么？')">课堂重点</button></view></view>
          <view v-for="(message, index) in messages" :key="message.id || index" class="message" :class="message.role === 'user' ? 'user-message' : 'assistant-message'"><view class="bubble"><text class="message-content">{{ message.content || (message.streaming ? '正在思考…' : '') }}</text><view v-if="message.toolStatus" class="tool-status">{{ message.toolStatus }}</view><view v-if="message.citations?.length" class="citation-row"><text v-for="(citation, citationIndex) in message.citations.slice(0, 3)" :key="citationIndex" class="citation">{{ citation.lecture_title || citation.ref || '课堂证据' }}</text></view></view></view>
          <view id="assistant-end" />
        </scroll-view>
      </template>
    </view>

    <view v-if="selectedCourse" class="composer"><view class="composer-inner content-wide"><textarea v-model="question" class="question-input" :maxlength="500" auto-height confirm-type="send" placeholder="询问课堂概念、原话、作业或复习步骤…" @confirm="send" /><button class="send-button" :disabled="sending || !question.trim()" @tap="send">{{ sending ? '…' : '↑' }}</button></view></view>
    <BottomNav active="assistant" />
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import BottomNav from '../../components/BottomNav.vue'
import { assistantApi, courseApi } from '../../api'
import { streamAssistantAnswer } from '../../api/http'
import { requireAuth } from '../../api/session'
import { showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const themeClass = useTheme()
const courses = ref([])
const selectedCourse = ref(null)
const activeThread = ref(null)
const threads = ref([])
const messages = ref([])
const question = ref('')
const loading = ref(false)
const sending = ref(false)
const scrollTarget = ref('')
const pendingCourseId = ref(null)
const courseNames = computed(() => courses.value.map((item) => item.name))
const courseIndex = computed(() => Math.max(0, courses.value.findIndex((item) => item.id === selectedCourse.value?.id)))

onLoad((options) => { pendingCourseId.value = Number(options.course_id) || null })
onShow(() => { if (requireAuth()) loadCourses() })

async function loadCourses() {
  try {
    const [mine, shared] = await Promise.all([courseApi.list(), courseApi.listPublic()])
    const seen = new Set()
    courses.value = [...(mine || []), ...(shared || [])].filter((item) => !seen.has(item.id) && seen.add(item.id))
    const preferred = courses.value.find((item) => item.id === pendingCourseId.value) || selectedCourse.value || courses.value[0]
    if (preferred && preferred.id !== selectedCourse.value?.id) await selectCourse(preferred)
  } catch (error) { showError(error, '课程加载失败') }
}
async function selectCourse(course) {
  selectedCourse.value = course
  pendingCourseId.value = null
  await loadThreads()
}
function changeCourse(event) { const course = courses.value[Number(event.detail.value)]; if (course) selectCourse(course) }
async function loadThreads() {
  if (!selectedCourse.value) return
  loading.value = true
  try {
    threads.value = await assistantApi.listThreads(selectedCourse.value.id)
    if (threads.value.length) await openThread(threads.value[0].id)
    else { activeThread.value = null; messages.value = [] }
  } catch (error) { showError(error, '学习会话加载失败') }
  finally { loading.value = false }
}
async function newThread() {
  if (!selectedCourse.value) return uni.showToast({ title: '请先选择课程', icon: 'none' })
  try {
    const thread = await assistantApi.createThread({ course_id: selectedCourse.value.id, lecture_ids: [] })
    threads.value = [thread, ...threads.value]
    activeThread.value = thread
    messages.value = []
  } catch (error) { showError(error, '新会话创建失败') }
}
async function openThread(id) {
  loading.value = true
  try {
    const detail = await assistantApi.detail(id)
    activeThread.value = detail
    messages.value = detail.messages || []
    scrollToEnd()
  } catch (error) { showError(error, '会话加载失败') }
  finally { loading.value = false }
}
function removeThread(thread) {
  uni.showModal({ title: '删除学习会话', content: '删除后无法恢复，确定继续吗？', confirmColor: '#ba1a1a', success: async (result) => {
    if (!result.confirm) return
    try {
      await assistantApi.removeThread(thread.id)
      threads.value = threads.value.filter((item) => item.id !== thread.id)
      activeThread.value = null; messages.value = []
      if (threads.value.length) openThread(threads.value[0].id)
    } catch (error) { showError(error, '删除会话失败') }
  } })
}
function quickAsk(hint, text) { question.value = text; send(hint) }
async function send(hint = null) {
  const value = question.value.trim()
  if (!value || sending.value) return
  if (!activeThread.value) await newThread()
  if (!activeThread.value) return
  question.value = ''
  sending.value = true
  const answer = { role: 'assistant', content: '', citations: [], streaming: true, toolStatus: '正在检索课堂资料…' }
  messages.value = [...messages.value, { role: 'user', content: value }, answer]
  scrollToEnd()
  try {
    await streamAssistantAnswer(activeThread.value.id, { question: value, hint }, {
      tool_start: (event) => { answer.toolStatus = `正在使用 ${toolLabel(event.tool)}…` },
      tool_result: () => { answer.toolStatus = '已找到课堂证据，正在整理回答…' },
      delta: (event) => { answer.content += event.content || ''; scrollToEnd() },
      done: (event) => {
        answer.content = event.answer || answer.content
        answer.citations = event.citations || []
        answer.streaming = false; answer.toolStatus = ''
        if (event.thread) activeThread.value = event.thread
        const index = threads.value.findIndex((item) => item.id === activeThread.value.id)
        if (index >= 0) threads.value[index] = activeThread.value
        scrollToEnd()
      },
      error: (event) => { answer.content = event.message || '小橘子回答失败，请重试。'; answer.streaming = false; answer.toolStatus = '' },
    })
  } catch (error) {
    answer.content = answer.content || '回答暂时失败，请稍后重试。'
    answer.streaming = false; answer.toolStatus = ''
    showError(error, '小橘子回答失败')
  } finally { sending.value = false }
}
function toolLabel(value) { return { search_notebook: '课堂笔记检索', list_assignments: '作业清单', breakdown_assignment: '作业拆解', get_notebook_overview: '资料概览' }[value] || '课堂工具' }
function scrollToEnd() { setTimeout(() => { scrollTarget.value = ''; scrollTarget.value = 'assistant-end' }, 40) }
function goCourses() { uni.reLaunch({ url: '/pages/courses/index' }) }
</script>

<style scoped>
.assistant-page { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }.assistant-content { flex: 1; min-height: 0; display: flex; flex-direction: column; padding-top: 22rpx; padding-bottom: 164rpx; }.new-thread { width: 74rpx; height: 74rpx; padding: 0; border-radius: 50%; background: rgba(0,94,161,.1); color: var(--primary); font-size: 40rpx; line-height: 74rpx; }.scope-card { min-height: 94rpx; padding: 12rpx 22rpx; display: flex; align-items: center; gap: 16rpx; }.scope-label { color: var(--muted); font-size: 21rpx; }.scope-picker { min-width: 0; overflow: hidden; color: var(--primary); font-size: 25rpx; font-weight: 750; text-overflow: ellipsis; white-space: nowrap; }.scope-picker text { margin-left: 8rpx; }.thread-strip { flex: 0 0 96rpx; margin-top: 14rpx; white-space: nowrap; }.thread-row { height: 96rpx; display: inline-flex; align-items: center; gap: 12rpx; }.thread-chip,.thread-create { max-width: 260rpx; height: 58rpx; padding: 0 16rpx; border-radius: 999rpx; background: var(--surface-container); color: var(--muted); font-size: 20rpx; line-height: 58rpx; }.thread-chip { display: flex; align-items: center; gap: 8rpx; }.thread-chip>text:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.thread-chip.active { background: rgba(0,94,161,.12); color: var(--primary); font-weight: 750; }.thread-remove { flex: 0 0 auto; font-size: 26rpx; }.thread-create { background: transparent; color: var(--primary); border: 2rpx solid rgba(0,94,161,.35); }.messages { flex: 1; min-height: 0; }.message { display: flex; margin: 16rpx 0; }.user-message { justify-content: flex-end; }.assistant-message { justify-content: flex-start; }.bubble { max-width: 84%; padding: 22rpx; border-radius: 26rpx; }.user-message .bubble { background: var(--primary); color: #fff; border-bottom-right-radius: 8rpx; }.assistant-message .bubble { background: var(--card); color: var(--text); border: 1rpx solid rgba(193,199,210,.3); border-bottom-left-radius: 8rpx; }.message-content { display: block; font-size: 26rpx; line-height: 1.65; white-space: pre-wrap; }.tool-status { margin-top: 14rpx; padding-top: 12rpx; border-top: 1rpx solid rgba(193,199,210,.35); color: var(--muted); font-size: 19rpx; }.citation-row { margin-top: 14rpx; display: flex; flex-wrap: wrap; gap: 8rpx; }.citation { max-width: 180rpx; overflow: hidden; padding: 5rpx 10rpx; border-radius: 999rpx; background: rgba(0,94,161,.1); color: var(--primary); font-size: 17rpx; text-overflow: ellipsis; white-space: nowrap; }.welcome-card { margin-top: 24rpx; padding: 36rpx 30rpx; }.welcome-title,.welcome-copy { display: block; }.welcome-title { color: var(--text); font-size: 30rpx; font-weight: 850; }.welcome-copy { margin-top: 12rpx; color: var(--muted); font-size: 22rpx; line-height: 1.6; }.quick-list { margin-top: 28rpx; display: flex; flex-wrap: wrap; gap: 12rpx; }.quick-list button { height: 62rpx; padding: 0 18rpx; border-radius: 18rpx; background: rgba(0,94,161,.08); color: var(--primary); font-size: 20rpx; line-height: 62rpx; }.composer { position: fixed; z-index: 66; left: 0; right: 0; bottom: calc(128rpx + env(safe-area-inset-bottom)); padding: 14rpx 0; background: var(--surface); border-top: 1rpx solid rgba(193,199,210,.25); }.composer-inner { display: flex; align-items: flex-end; gap: 14rpx; padding: 0 24rpx; }.question-input { flex: 1; min-height: 76rpx; max-height: 160rpx; padding: 18rpx 22rpx; border-radius: 24rpx; background: var(--card); border: 2rpx solid rgba(193,199,210,.65); color: var(--text); font-size: 25rpx; line-height: 1.4; }.send-button { flex: 0 0 auto; width: 76rpx; height: 76rpx; padding: 0; border-radius: 50%; background: var(--primary); color: #fff; font-size: 34rpx; line-height: 76rpx; }.send-button[disabled] { opacity: .45; }.empty { margin-top: 24rpx; display: flex; flex-direction: column; align-items: center; }.empty-title { color: var(--text); font-size: 30rpx; font-weight: 800; }.empty-copy { max-width: 520rpx; margin-top: 14rpx; color: var(--muted); font-size: 22rpx; line-height: 1.6; text-align: center; }.empty-button { margin-top: 28rpx; }.loading-text { padding: 30rpx; color: var(--muted); text-align: center; }
</style>
