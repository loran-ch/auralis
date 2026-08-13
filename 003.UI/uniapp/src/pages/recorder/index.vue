<template>
  <view class="page recorder-page" :class="themeClass">
    <AppHeader :title="courseName" :subtitle="languagePair" menu @menu="menuOpen = true">
      <template #right><button class="account-button" @tap="navigate('/pages/profile/index')">♙</button></template>
    </AppHeader>

    <view class="status-strip">
      <view class="status-pill"><view class="status-dot" :class="{ active: recording && !paused, paused }" /><text>{{ statusText }}</text></view>
      <text v-if="elapsed" class="timer">{{ formatClock(elapsed) }}</text>
    </view>

    <view class="language-row">
      <picker :range="languageNames" :value="sourceIndex" :disabled="recording" @change="changeSource">
        <view class="language-picker">{{ sourceLabel }}⌄</view>
      </picker>
      <text class="arrow">→</text>
      <picker :range="languageNames" :value="targetIndex" :disabled="recording" @change="changeTarget">
        <view class="language-picker">{{ targetLabel }}⌄</view>
      </picker>
    </view>

    <view class="transcript-region">
      <scroll-view
        class="transcript-scroll"
        scroll-y
        :scroll-into-view="scrollTarget"
        :show-scrollbar="false"
        :lower-threshold="40"
        @scroll="handleTranscriptScroll"
        @scrolltolower="resumeTranscriptFollow"
        @touchstart="beginTranscriptTouch"
        @touchend="endTranscriptTouch"
        @touchcancel="endTranscriptTouch"
      >
        <view v-if="!transcripts.length && !liveTranscript" class="welcome-state">
          <view class="welcome-icon">◉</view>
          <text class="welcome-title">让课堂内容实时变成双语笔记</text>
          <text class="welcome-copy">点击下方录音按钮开始。系统会自动断句、翻译并保存到课堂记录。</text>
        </view>
        <view v-if="transcripts.length" class="transcript-history-heading">
          <view><text class="history-title">已确认内容</text><text class="history-count">{{ transcripts.length }} 句</text></view>
          <text class="history-hint">前文会持续保留</text>
        </view>
        <view v-for="(item, index) in transcripts" :id="`transcript-${item.id || item.client_id || index}`" :key="item.id || item.client_id || index" class="transcript-card confirmed" :class="{ 'latest-final': index === transcripts.length - 1 }">
          <view class="transcript-main">
            <view class="transcript-meta"><text>第 {{ index + 1 }} 句</text><text v-if="item.start_offset_ms != null">{{ formatTranscriptTime(item.start_offset_ms) }}</text><text v-if="item.pending" class="pending-label">处理中</text></view>
            <text class="source-text">{{ item.source_text }}</text>
            <text class="translated-text" :class="{ 'translation-error': item.translation_error }">{{ item.translation_error || item.translated_text || (item.pending ? '正在翻译…' : '暂无翻译') }}</text>
          </view>
          <button class="star-button" :class="{ bookmarked: item.is_bookmarked }" :disabled="!item.id" @tap="openTag(item)">★</button>
        </view>
        <view v-if="liveTranscript" id="live-transcript" class="transcript-card live-preview current">
          <view class="transcript-main">
            <view class="live-label"><view class="live-dot" /><text>正在更新</text></view>
            <text class="source-text">{{ liveTranscript }}</text>
            <text v-if="liveTranslation" class="translated-text live-translation">{{ liveTranslation }}</text>
            <text v-else class="recognizing-text">正在识别与理解上下文…</text>
          </view>
        </view>
        <view id="transcript-end" class="scroll-spacer" />
      </scroll-view>
      <button v-if="!followLatest && (transcripts.length || liveTranscript)" class="follow-latest-button" @tap="resumeTranscriptFollow">↓ {{ unseenTranscriptCount ? `${unseenTranscriptCount} 条新内容` : '回到最新' }}</button>
    </view>

    <view class="recorder-controls">
      <Waveform :active="recording && !paused" />
      <view class="control-row content-wide">
        <view class="side-action" @tap="markLatest"><view class="small-circle purple">◆</view><text>标记</text></view>
        <button class="round-action" :disabled="!recording || stopping" @tap="togglePause">{{ paused ? '▶' : 'Ⅱ' }}</button>
        <button class="record-button" :class="{ recording, stopping }" :disabled="stopping" @tap="toggleRecording"><text>{{ recording ? '■' : '●' }}</text></button>
        <button class="round-action" @tap="navigate('/pages/history/index')">◷</button>
        <view class="side-action" @tap="navigate('/pages/cards/index')"><view class="small-circle gold">★</view><text>收藏</text></view>
      </view>
    </view>

    <view v-if="menuOpen" class="menu-mask" @tap.self="menuOpen = false">
      <view class="side-menu">
        <view class="menu-brand"><text class="brand-icon">≋</text><view><text class="brand-name">LiveTrans Voice</text><text class="brand-caption">课堂翻译助手</text></view></view>
        <view v-for="item in menuItems" :key="item.url" class="menu-item" @tap="navigate(item.url)"><text class="menu-icon">{{ item.icon }}</text><text>{{ item.label }}</text></view>
        <view class="divider" />
        <view class="menu-item error-text" @tap="logout"><text class="menu-icon">↪</text><text>退出登录</text></view>
      </view>
    </view>

    <TagSheet v-model="tagOpen" @select="addBookmark" />

    <view v-if="nameModal" class="modal-mask center">
      <view class="modal-card">
        <text class="section-title">保存课堂记录</text>
        <text class="section-subtitle">共 {{ completedLecture?.sentence_count || transcripts.length }} 句话</text>
        <input v-model="renameValue" class="input rename-input" maxlength="80" placeholder="输入课程名称" />
        <view class="modal-actions"><button class="btn btn-soft" @tap="finishNaming(false)">稍后再说</button><button class="btn btn-primary" @tap="finishNaming(true)">保存</button></view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import AppHeader from '../../components/AppHeader.vue'
import Waveform from '../../components/Waveform.vue'
import TagSheet from '../../components/TagSheet.vue'
import { authApi, bookmarkApi, lectureApi, preferenceApi } from '../../api'
import { clearAuth, requireAuth } from '../../api/session'
import { ENABLE_DEMO_MODE } from '../../config/env'
import { finishCapture, pauseCapture, resumeCapture, startCapture, abortCapture } from '../../platform/recorder'
import { abortSpeechRecognition, isSpeechRecognitionSupported, resumeSpeechRecognition, startSpeechRecognition, stopSpeechRecognition } from '../../platform/speech-recognition'
import { abortRealtimeSpeech, isRealtimeSpeechSupported, startRealtimeSpeech, stopRealtimeSpeech } from '../../platform/realtime-speech'
import { formatClock, languageLabel, showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const lectureId = ref(null)
const recording = ref(false)
const paused = ref(false)
const stopping = ref(false)
const courseName = ref('课堂录音')
const statusText = ref('待机中')
const elapsed = ref(0)
const transcripts = ref([])
const liveTranscript = ref('')
const liveTranslation = ref('')
const browserRecognition = ref(false)
const realtimeRecognition = ref(false)
const languages = ref([])
const sourceLang = ref('en')
const targetLang = ref('zh-CN')
const menuOpen = ref(false)
const tagOpen = ref(false)
const selectedTranscript = ref(null)
const scrollTarget = ref('')
const followLatest = ref(true)
const unseenTranscriptCount = ref(0)
const nameModal = ref(false)
const renameValue = ref('课堂录音')
const completedLecture = ref(null)
const themeClass = useTheme()
let timer = null
let demoTimer = null
let segmentCount = 0
let uploadChain = Promise.resolve()
let asrAvailable = null
let pendingTextId = 0
const pendingTextJobs = new Set()
let speechErrorShown = false
let realtimeErrorShown = false
let liveRevision = 0
let liveUtteranceId = ''
let transcriptTouching = false
let lastTranscriptScrollTop = 0
let transcriptTouchTimer = null

const menuItems = [
  { label: '实时录音', icon: '●', url: '/pages/recorder/index' },
  { label: '课堂记录', icon: '◷', url: '/pages/history/index' },
  { label: '知识卡片', icon: '★', url: '/pages/cards/index' },
  { label: '个人中心', icon: '♙', url: '/pages/profile/index' },
]
const languageNames = computed(() => languages.value.map((item) => `${item.flag_emoji || '🌐'} ${item.name_native}`))
const sourceIndex = computed(() => Math.max(0, languages.value.findIndex((item) => item.code === sourceLang.value)))
const targetIndex = computed(() => Math.max(0, languages.value.findIndex((item) => item.code === targetLang.value)))
const sourceLabel = computed(() => languageLabel(sourceLang.value, languages.value))
const targetLabel = computed(() => languageLabel(targetLang.value, languages.value))
const languagePair = computed(() => `${sourceLabel.value} → ${targetLabel.value}`)

onLoad(async () => {
  if (!requireAuth()) return
  try {
    const [languageData, settings] = await Promise.all([preferenceApi.languages(), preferenceApi.settings()])
    languages.value = languageData
    sourceLang.value = settings.default_source_lang === 'auto' ? 'en' : settings.default_source_lang
    targetLang.value = settings.default_target_lang || 'zh-CN'
  } catch (error) { showError(error, '语言设置加载失败') }
})

onUnload(() => {
  clearTimers()
  clearTimeout(transcriptTouchTimer)
  abortSpeechRecognition()
  abortRealtimeSpeech()
  if (recording.value) abortCapture()
})

function changeSource(event) { sourceLang.value = languages.value[Number(event.detail.value)]?.code || 'en'; saveLanguageSettings() }
function changeTarget(event) { targetLang.value = languages.value[Number(event.detail.value)]?.code || 'zh-CN'; saveLanguageSettings() }
function saveLanguageSettings() { preferenceApi.saveSettings({ default_source_lang: sourceLang.value, default_target_lang: targetLang.value }).catch(() => {}) }

function beginTimers() {
  clearInterval(timer)
  timer = setInterval(() => { if (!paused.value) elapsed.value += 1 }, 1000)
  if (browserRecognition.value || realtimeRecognition.value) return
  if (ENABLE_DEMO_MODE && asrAvailable === false) startDemoMode()
  else if (ENABLE_DEMO_MODE && asrAvailable !== true && !demoTimer) {
    demoTimer = setTimeout(() => {
      demoTimer = null
      if (asrAvailable !== true) startDemoMode()
    }, 12000)
  }
}

function clearTimers() { clearInterval(timer); clearTimeout(demoTimer); clearInterval(demoTimer); timer = null; demoTimer = null }
function stopDemoMode() { clearTimeout(demoTimer); clearInterval(demoTimer); demoTimer = null }
function startDemoMode() { if (!demoTimer) demoTimer = setInterval(fetchDemoSentence, 4000) }

async function appendTranscript(sentence) {
  if (!sentence?.id || transcripts.value.some((item) => item.id === sentence.id)) return false
  transcripts.value.push(sentence)
  if (followLatest.value) await scrollToLatest()
  else unseenTranscriptCount.value += 1
  return true
}

async function setScrollTarget(id) {
  scrollTarget.value = ''
  await nextTick()
  scrollTarget.value = id
}

async function scrollToLatest(force = false) {
  if (!force && !followLatest.value) return
  await nextTick()
  await setScrollTarget(liveTranscript.value ? 'live-transcript' : 'transcript-end')
}

function pauseTranscriptFollow() {
  if (!followLatest.value) return
  followLatest.value = false
  unseenTranscriptCount.value = 0
}

function resumeTranscriptFollow() {
  followLatest.value = true
  unseenTranscriptCount.value = 0
  scrollToLatest(true)
}

function beginTranscriptTouch() {
  clearTimeout(transcriptTouchTimer)
  transcriptTouching = true
}

function endTranscriptTouch() {
  clearTimeout(transcriptTouchTimer)
  transcriptTouchTimer = setTimeout(() => { transcriptTouching = false }, 180)
}

function handleTranscriptScroll(event) {
  const currentTop = Number(event?.detail?.scrollTop || 0)
  if (transcriptTouching && currentTop < lastTranscriptScrollTop - 4) pauseTranscriptFollow()
  lastTranscriptScrollTop = currentTop
}

function formatTranscriptTime(offsetMs) {
  return formatClock(Math.max(0, Math.floor(Number(offsetMs || 0) / 1000)))
}

function showLiveTranscript(text) {
  liveTranscript.value = text
  if (text) scrollToLatest()
}

function applyRealtimeInterim(message) {
  const revision = Number(message?.revision || 0)
  if (revision < liveRevision) return
  liveRevision = revision
  liveUtteranceId = message.utterance_id || liveUtteranceId
  liveTranscript.value = message.source_text || ''
  if (message.type !== 'preview') liveTranslation.value = ''
  if (liveTranscript.value) scrollToLatest()
  statusText.value = '正在实时识别…'
}

function applyRealtimePreview(message) {
  const revision = Number(message?.revision || 0)
  if (revision < liveRevision) return
  liveRevision = revision
  liveUtteranceId = message.utterance_id || liveUtteranceId
  liveTranscript.value = message.source_text || liveTranscript.value
  liveTranslation.value = message.translated_text || ''
  if (liveTranscript.value) scrollToLatest()
}

async function applyRealtimeFinal(message) {
  const sentence = message?.transcription
  if (!sentence) return
  await appendTranscript(sentence)
  const revision = Number(message?.revision || 0)
  const finalizedCurrentDraft = revision >= liveRevision
  if (finalizedCurrentDraft) {
    liveTranscript.value = ''
    liveTranslation.value = ''
    liveRevision = 0
    liveUtteranceId = ''
  }
  if (followLatest.value) scrollToLatest()
  asrAvailable = true
  if (sentence.translation_success === false) {
    uni.showToast({ title: sentence.translation_warning || '翻译服务暂时不可用，已保留原文', icon: 'none' })
  }
  if (finalizedCurrentDraft && recording.value && !paused.value) statusText.value = '正在聆听…'
}

function realtimeCallbacks() {
  return {
    onReady: () => {
      realtimeRecognition.value = true
      asrAvailable = true
      stopDemoMode()
      statusText.value = '正在实时聆听…'
    },
    onInterim: applyRealtimeInterim,
    onPreview: applyRealtimePreview,
    onFinalizing: applyRealtimeInterim,
    onFinal: applyRealtimeFinal,
    onNoSpeech: () => {
      // 静音分片不应清掉可能已开始的下一句动态草稿。
      if (recording.value && !paused.value) statusText.value = '正在聆听…'
    },
    onError: (message) => {
      if (!message?.fallback || realtimeErrorShown) return
      realtimeErrorShown = true
      uni.showToast({ title: message.message || '实时识别已切换分片模式', icon: 'none' })
    },
    onFallback: (message) => {
      realtimeRecognition.value = false
      liveTranscript.value = ''
      liveTranslation.value = ''
      liveUtteranceId = ''
      statusText.value = '已切换分片语音识别'
      if (!realtimeErrorShown && message?.message) {
        realtimeErrorShown = true
        uni.showToast({ title: message.message, icon: 'none' })
      }
    },
  }
}

function translateAndSave(text) {
  const normalized = text.trim()
  if (!normalized || !lectureId.value) return Promise.resolve()
  const targetLectureId = lectureId.value
  const clientId = `pending-${++pendingTextId}`
  const item = {
    client_id: clientId,
    source_text: normalized,
    translated_text: '',
    pending: true,
    is_bookmarked: false,
  }
  liveTranscript.value = ''
  transcripts.value.push(item)
  if (followLatest.value) scrollToLatest()
  else unseenTranscriptCount.value += 1
  statusText.value = `正在翻译：${normalized.slice(0, 20)}`

  const job = (async () => {
    let translation
    try {
      translation = await lectureApi.translate({
        text: normalized,
        source: sourceLang.value,
        target: targetLang.value,
      })
    } catch (error) {
      translation = {
        translated_text: normalized,
        success: false,
        warning: error.message || '翻译失败，已保留原文',
      }
    }

    const translatedText = translation.translated_text || normalized
    item.translated_text = translatedText
    item.translation_error = translation.success === false
      ? (translation.warning || '翻译服务暂时不可用，已保留原文')
      : ''

    try {
      const saved = await lectureApi.saveText(targetLectureId, {
        source_text: normalized,
        translated_text: translatedText,
      })
      Object.assign(item, saved, {
        pending: false,
        translation_success: translation.success,
        translation_provider: translation.provider,
        translation_warning: translation.warning,
        translation_error: item.translation_error,
      })
    } catch (error) {
      item.pending = false
      item.translation_error = error.message || '内容保存失败，请重试'
    } finally {
      if (recording.value && !paused.value) statusText.value = '正在聆听…'
    }
  })()
  pendingTextJobs.add(job)
  job.then(() => pendingTextJobs.delete(job), () => pendingTextJobs.delete(job))
  return job
}

function speechOptions() {
  return {
    language: sourceLang.value,
    onStart: () => { if (recording.value && !paused.value) statusText.value = '正在聆听…' },
    onInterim: showLiveTranscript,
    onFinal: translateAndSave,
    onError: ({ code, fatal }) => {
      if (!fatal) return
      browserRecognition.value = false
      liveTranscript.value = ''
      statusText.value = '已切换服务端语音识别'
      if (!speechErrorShown) {
        speechErrorShown = true
        const messages = {
          'not-allowed': '浏览器语音识别权限被拒绝，已切换服务端识别',
          'service-not-allowed': '浏览器语音识别不可用，已切换服务端识别',
          'audio-capture': '浏览器未检测到麦克风，已切换服务端识别',
          network: '浏览器语音识别网络不可用，已切换服务端识别',
        }
        uni.showToast({ title: messages[code] || '实时识别不可用，已切换服务端识别', icon: 'none' })
      }
    },
  }
}

async function fetchDemoSentence() {
  if (!recording.value || paused.value || !lectureId.value) return
  statusText.value = '正在识别与翻译…'
  try {
    const sentence = await lectureApi.demoTranscribe(lectureId.value)
    await appendTranscript(sentence)
    statusText.value = '正在聆听…'
  } catch (error) {
    statusText.value = '识别服务暂时不可用'
  }
}

function releaseSegment(segment) {
  if (segment && typeof segment.cleanup === 'function') {
    try { segment.cleanup() } catch (_) {}
  }
}

function queueSegment(segment, forceAudioOnly = false) {
  const filePath = segment && typeof segment === 'object' && segment.filePath
    ? segment.filePath
    : segment
  if (!filePath || !lectureId.value) {
    releaseSegment(segment)
    return uploadChain
  }
  const id = lectureId.value
  // 在分片产生时就固定其处理方式。实时链路随后断开时，已经由流式 ASR
  // 覆盖的音频只做录音保存，避免整段重新识别造成重复字幕。
  const audioOnly = forceAudioOnly || browserRecognition.value || realtimeRecognition.value
  uploadChain = uploadChain
    .then(async () => {
      const append = segmentCount > 0
      segmentCount += 1
      try {
        if (audioOnly) {
          await lectureApi.uploadAudio(id, filePath, append)
          return
        }
        statusText.value = '正在识别与翻译…'
        const sentence = await lectureApi.transcribeAudio(id, filePath, append)
        asrAvailable = true
        stopDemoMode()
        if (!sentence) {
          // 静音或过短分片由服务端以 204 跳过，继续聆听且不弹错误。
          if (recording.value && !paused.value) statusText.value = '正在聆听…'
          return
        }
        await appendTranscript(sentence)
        if (sentence.translation_success === false) {
          uni.showToast({ title: sentence.translation_warning || '翻译服务暂时不可用，已保留原文', icon: 'none' })
        }
        if (recording.value && !paused.value) statusText.value = '正在聆听…'
      } catch (error) {
        if (error.statusCode === 503) {
          const firstFallback = asrAvailable !== false
          asrAvailable = false
          if (ENABLE_DEMO_MODE && recording.value && !paused.value) startDemoMode()
          statusText.value = ENABLE_DEMO_MODE ? '识别不可用，当前为演示模式' : '语音识别服务暂时不可用'
          if (firstFallback) {
            uni.showToast({
              title: ENABLE_DEMO_MODE ? '语音识别不可用，已切换演示模式' : '语音识别服务暂时不可用，录音仍会保存',
              icon: 'none',
            })
          }
        } else if (error.statusCode !== 409) {
          uni.showToast({ title: error.message || '语音识别失败', icon: 'none' })
        }
      } finally {
        releaseSegment(segment)
      }
    })
  return uploadChain
}

async function startRecording() {
  statusText.value = '正在启动…'
  try {
    const lecture = await lectureApi.start({ course_name: '课堂录音', source_lang: sourceLang.value, target_lang: targetLang.value })
    lectureId.value = lecture.id
    courseName.value = lecture.course_name
    transcripts.value = []
    liveTranscript.value = ''
    liveTranslation.value = ''
    followLatest.value = true
    unseenTranscriptCount.value = 0
    lastTranscriptScrollTop = 0
    elapsed.value = 0
    segmentCount = 0
    asrAvailable = null
    speechErrorShown = false
    realtimeErrorShown = false
    liveRevision = 0
    liveUtteranceId = ''
    uploadChain = Promise.resolve()
    await startCapture(queueSegment)
    recording.value = true
    paused.value = false
    realtimeRecognition.value = false
    if (isRealtimeSpeechSupported()) {
      try {
        realtimeRecognition.value = await startRealtimeSpeech(
          lecture.id, realtimeCallbacks(), { offsetMs: 0 },
        )
      }
      catch (_) { realtimeRecognition.value = false }
    }
    browserRecognition.value = !realtimeRecognition.value && isSpeechRecognitionSupported()
    if (browserRecognition.value) {
      try { browserRecognition.value = await startSpeechRecognition(speechOptions()) }
      catch (_) { browserRecognition.value = false }
    }
    statusText.value = '正在聆听…'
    beginTimers()
  } catch (error) {
    recording.value = false
    statusText.value = '待机中'
    showError(error, '课堂启动失败')
  }
}

async function stopRecording() {
  if (!lectureId.value) return
  stopping.value = true
  statusText.value = '正在保存录音与翻译…'
  clearTimers()
  try {
    const realtimeWasActive = realtimeRecognition.value
    const realtimeStop = realtimeWasActive ? stopRealtimeSpeech() : Promise.resolve(false)
    const speechStop = stopSpeechRecognition()
    const finalPath = await finishCapture()
    if (finalPath) await queueSegment(finalPath, realtimeWasActive)
    await realtimeStop
    realtimeRecognition.value = false
    await speechStop
    await Promise.allSettled(Array.from(pendingTextJobs))
    await uploadChain
    completedLecture.value = await lectureApi.stop(lectureId.value)
    recording.value = false
    paused.value = false
    renameValue.value = courseName.value
    nameModal.value = true
    statusText.value = '已保存'
  } catch (error) {
    showError(error, '停止课堂失败')
    statusText.value = '保存失败，请重试'
  } finally { stopping.value = false }
}

function toggleRecording() { recording.value ? stopRecording() : startRecording() }

async function togglePause() {
  if (!recording.value || stopping.value) return
  try {
    if (!paused.value) {
      // 先收取浏览器语音识别可能产生的最后一句；课堂仍处于 recording，
      // 最终原文和译文可以正常保存，再切换服务端暂停状态。
      await stopSpeechRecognition()
      const realtimeWasActive = realtimeRecognition.value
      if (realtimeWasActive) await stopRealtimeSpeech()
      realtimeRecognition.value = false
      await Promise.allSettled(Array.from(pendingTextJobs))
      await lectureApi.pause(lectureId.value)
      paused.value = true
      clearTimers()
      statusText.value = '已暂停'
      const filePath = await pauseCapture()
      if (filePath) await queueSegment(filePath, realtimeWasActive)
    } else {
      await lectureApi.resume(lectureId.value)
      await resumeCapture(queueSegment)
      if (isRealtimeSpeechSupported()) {
        try {
          realtimeRecognition.value = await startRealtimeSpeech(
            lectureId.value, realtimeCallbacks(), { offsetMs: elapsed.value * 1000 },
          )
        }
        catch (_) { realtimeRecognition.value = false }
      }
      browserRecognition.value = !realtimeRecognition.value && isSpeechRecognitionSupported()
      if (browserRecognition.value) await resumeSpeechRecognition(speechOptions())
      paused.value = false
      statusText.value = '正在聆听…'
      beginTimers()
    }
  } catch (error) { showError(error, paused.value ? '恢复失败' : '暂停失败') }
}

function openTag(item) { selectedTranscript.value = item; tagOpen.value = true }
function markLatest() {
  if (!transcripts.value.length) return uni.showToast({ title: '还没有可标记的内容', icon: 'none' })
  openTag(transcripts.value[transcripts.value.length - 1])
}

async function addBookmark(tag) {
  if (!selectedTranscript.value?.id) return
  try {
    await bookmarkApi.add({ transcription_id: selectedTranscript.value.id, tag })
    selectedTranscript.value.is_bookmarked = true
    selectedTranscript.value.bookmark_tag = tag
    uni.showToast({ title: '已收藏', icon: 'success' })
  } catch (error) { showError(error, '收藏失败') }
}

async function finishNaming(save) {
  if (save && renameValue.value.trim() && lectureId.value) {
    try { await lectureApi.rename(lectureId.value, renameValue.value.trim()) }
    catch (error) { return showError(error, '命名失败') }
  }
  nameModal.value = false
  lectureId.value = null
  courseName.value = '课堂录音'
  statusText.value = '待机中'
  uni.navigateTo({ url: `/pages/review/index?id=${completedLecture.value.id}` })
}

function navigate(url) {
  if (recording.value) return uni.showToast({ title: '请先结束当前录音', icon: 'none' })
  menuOpen.value = false
  uni.reLaunch({ url })
}

async function logout() {
  if (recording.value) return uni.showToast({ title: '请先结束当前录音', icon: 'none' })
  try { await authApi.logout() } catch (_) {}
  clearAuth()
  uni.reLaunch({ url: '/pages/login/index' })
}
</script>

<style scoped>
.recorder-page { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
.account-button { width: 76rpx; height: 76rpx; padding: 0; border-radius: 50%; background: transparent; color: var(--primary); font-size: 38rpx; line-height: 76rpx; }
.status-strip { min-height: 64rpx; padding: 10rpx 40rpx 0; display: flex; align-items: center; justify-content: space-between; }
.status-pill { display: flex; align-items: center; gap: 12rpx; color: var(--secondary); font-size: 22rpx; font-weight: 700; }
.status-dot { width: 16rpx; height: 16rpx; border-radius: 50%; background: #9ba1a9; }
.status-dot.active { background: var(--secondary); box-shadow: 0 0 0 8rpx rgba(0,110,28,.1); animation: pulse 1.2s infinite; }
.status-dot.paused { background: #aa6400; }
.timer { color: var(--muted); font-size: 24rpx; font-variant-numeric: tabular-nums; }
.language-row { padding: 12rpx 40rpx 20rpx; display: flex; align-items: center; justify-content: center; gap: 18rpx; }
.language-picker { min-height: 56rpx; padding: 0 20rpx; border-radius: 999rpx; background: var(--surface-low); color: var(--muted); font-size: 22rpx; line-height: 56rpx; }
.arrow { color: var(--primary); font-weight: 800; }
.transcript-region { position: relative; flex: 1; min-height: 0; }
.transcript-scroll { height: 100%; min-height: 0; box-sizing: border-box; padding: 0 40rpx; }
.welcome-state { min-height: 650rpx; padding: 120rpx 46rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.welcome-icon { width: 132rpx; height: 132rpx; border-radius: 42rpx; display: flex; align-items: center; justify-content: center; background: rgba(0,94,161,.1); color: var(--primary); font-size: 62rpx; }
.welcome-title { margin-top: 34rpx; font-size: 34rpx; line-height: 1.35; font-weight: 800; color: var(--text); }
.welcome-copy { margin-top: 18rpx; max-width: 560rpx; font-size: 24rpx; line-height: 1.65; color: var(--muted); }
.transcript-history-heading { position: sticky; z-index: 3; top: 0; margin: 0 -4rpx 20rpx; padding: 16rpx 4rpx 14rpx; display: flex; align-items: center; justify-content: space-between; background: var(--surface); }
.history-title { color: var(--text); font-size: 24rpx; font-weight: 800; }
.history-count { margin-left: 12rpx; padding: 4rpx 12rpx; border-radius: 999rpx; background: var(--surface-low); color: var(--muted); font-size: 19rpx; }
.history-hint { color: var(--muted); font-size: 19rpx; }
.transcript-card { margin-bottom: 20rpx; padding: 24rpx 20rpx 24rpx 24rpx; display: flex; align-items: flex-start; border: 1rpx solid rgba(0,94,161,.08); border-left: 5rpx solid rgba(0,94,161,.28); border-radius: 0 24rpx 24rpx 0; background: var(--card); box-shadow: 0 4rpx 16rpx rgba(26,28,29,.035); }
.transcript-card.confirmed { opacity: 1; }
.transcript-card.latest-final { border-left-color: rgba(0,110,28,.5); }
.transcript-card.current { border-left-color: var(--primary); opacity: 1; }
.transcript-main { flex: 1; min-width: 0; }
.transcript-meta { margin-bottom: 10rpx; display: flex; align-items: center; gap: 14rpx; color: var(--muted); font-size: 19rpx; }
.pending-label { color: var(--primary); }
.source-text,.translated-text { display: block; line-height: 1.55; }
.source-text { font-size: 30rpx; font-weight: 650; color: var(--text); }
.translated-text { margin-top: 10rpx; font-size: 29rpx; font-weight: 700; color: var(--secondary); }
.translation-error { color: var(--error); font-size: 23rpx; }
.recognizing-text { display: block; margin-top: 10rpx; color: var(--muted); font-size: 23rpx; }
.live-preview { border-color: rgba(0,94,161,.16); border-left-color: var(--primary); border-left-style: dashed; background: rgba(0,94,161,.045); }
.live-label { margin-bottom: 12rpx; display: flex; align-items: center; gap: 10rpx; color: var(--primary); font-size: 20rpx; font-weight: 800; }
.live-dot { width: 12rpx; height: 12rpx; border-radius: 50%; background: var(--primary); animation: pulse 1.2s infinite; }
.live-translation { opacity: .86; }
.star-button { width: 72rpx; height: 72rpx; margin-left: 16rpx; padding: 0; border-radius: 50%; background: #ffdcbe; color: var(--tertiary); font-size: 34rpx; line-height: 72rpx; }
.star-button[disabled] { opacity: .35; }
.star-button.bookmarked { background: #aa6400; color: #fff; }
.scroll-spacer { height: 36rpx; }
.follow-latest-button { position: absolute; z-index: 5; right: 30rpx; bottom: 22rpx; min-width: 174rpx; height: 64rpx; padding: 0 24rpx; border: 1rpx solid rgba(0,94,161,.15); border-radius: 999rpx; background: var(--primary); color: #fff; font-size: 21rpx; font-weight: 750; line-height: 64rpx; box-shadow: 0 8rpx 24rpx rgba(0,94,161,.24); }
.recorder-controls { flex-shrink: 0; padding: 8rpx 20rpx calc(18rpx + env(safe-area-inset-bottom)); background: var(--card); border-radius: 38rpx 38rpx 0 0; box-shadow: 0 -8rpx 30rpx rgba(26,28,29,.07); }
.control-row { height: 112rpx; display: flex; align-items: center; justify-content: space-around; }
.side-action { width: 100rpx; display: flex; flex-direction: column; align-items: center; gap: 7rpx; color: var(--muted); font-size: 19rpx; }
.small-circle { width: 64rpx; height: 64rpx; border-radius: 50%; text-align: center; line-height: 64rpx; font-size: 28rpx; }
.purple { color: #8b5cf6; background: rgba(139,92,246,.1); }.gold { color: #874e00; background: #ffdcbe; }
.round-action { width: 84rpx; height: 84rpx; padding: 0; border-radius: 50%; background: var(--surface-container); color: var(--muted); font-size: 30rpx; line-height: 84rpx; }
.record-button { width: 116rpx; height: 116rpx; padding: 0; border: 10rpx solid rgba(0,110,28,.15); border-radius: 50%; background: var(--secondary); color: #fff; font-size: 42rpx; line-height: 96rpx; box-shadow: 0 8rpx 22rpx rgba(0,110,28,.24); }
.record-button.recording { border-color: rgba(239,68,68,.18); background: #ef4444; box-shadow: 0 8rpx 22rpx rgba(239,68,68,.25); }
.record-button.stopping { opacity: .6; }
.menu-mask { position: fixed; z-index: 150; inset: 0; background: rgba(0,0,0,.28); }
.side-menu { width: 540rpx; max-width: 82vw; height: 100%; padding: calc(46rpx + env(safe-area-inset-top)) 26rpx 40rpx; background: var(--card); box-shadow: 16rpx 0 50rpx rgba(0,0,0,.12); }
.menu-brand { padding: 18rpx 20rpx 40rpx; display: flex; align-items: center; gap: 20rpx; }
.brand-icon { width: 74rpx; height: 74rpx; border-radius: 22rpx; text-align: center; line-height: 74rpx; background: var(--primary); color: #fff; font-size: 50rpx; transform: rotate(90deg); }
.brand-name,.brand-caption { display: block; }.brand-name { font-weight: 800; color: var(--text); }.brand-caption { margin-top: 4rpx; color: var(--muted); font-size: 20rpx; }
.menu-item { min-height: 94rpx; padding: 0 24rpx; display: flex; align-items: center; gap: 24rpx; border-radius: 22rpx; color: var(--text); font-weight: 650; }
.menu-item:active { background: var(--surface-low); }.menu-icon { width: 42rpx; color: var(--primary); font-size: 31rpx; text-align: center; }
.side-menu .divider { margin: 14rpx 20rpx; }
.rename-input { margin: 30rpx 0; }
.modal-actions { display: flex; justify-content: flex-end; gap: 18rpx; }.modal-actions .btn { flex: 1; }
@keyframes pulse { 0%,100% { opacity: .65; } 50% { opacity: 1; } }
</style>
