<template>
  <view class="register-page" :class="themeClass">
    <view class="topbar"><button class="back" @tap="goBack">‹</button><text>创建账户</text><view class="back" /></view>
    <view class="register-content">
      <view class="intro"><view class="logo">≋</view><text class="title">加入 LiveTrans Voice</text><text class="subtitle">保存每一堂课，收藏每一个知识点</text></view>
      <view v-if="statusLoading" class="registration-notice card"><text>正在确认注册状态…</text></view>
      <view v-else-if="!registrationEnabled" class="registration-notice paused card"><text class="notice-title">新用户注册已暂停</text><text class="notice-copy">{{ registrationMessage }}，请稍后再试或联系管理员。</text></view>
      <view class="form-card card">
        <view class="field"><text class="field-label">用户名</text><input v-model="form.username" class="input" placeholder="3-32 位字母、数字或下划线" maxlength="32" /></view>
        <view class="field"><text class="field-label">设置密码</text><input v-model="form.password" class="input" password placeholder="至少 6 位" maxlength="72" /></view>
        <view class="field"><text class="field-label">确认密码</text><input v-model="confirmPassword" class="input" password placeholder="请再次输入密码" maxlength="72" /></view>
        <view class="field">
          <text class="field-label">验证码</text>
          <view class="captcha-row"><input v-model="form.captcha_code" class="input captcha-input" placeholder="输入图中字符" maxlength="4" :disabled="!registrationEnabled" /><view class="captcha-image-wrap" @tap="loadCaptcha"><image v-if="captchaImage" class="captcha-image" :src="captchaImage" mode="aspectFit" /><text v-else>{{ captchaLoading ? '加载中…' : '点击刷新' }}</text></view></view>
          <text class="captcha-hint" @tap="loadCaptcha">看不清？点击图片换一张</text>
        </view>
        <view class="consent" @tap="agreed = !agreed"><view class="checkbox" :class="{ checked: agreed }">{{ agreed ? '✓' : '' }}</view><text>我已阅读并同意《服务协议》和《隐私政策》</text></view>
        <button class="btn btn-primary submit" :disabled="statusLoading || !registrationEnabled || submitting" @tap="register">{{ registrationEnabled ? (submitting ? '正在创建…' : '注册并登录') : '注册已暂停' }}</button>
      </view>
      <view class="login-hint"><text>已有账户？</text><text class="link" @tap="goBack">立即登录</text></view>
    </view>
  </view>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { authApi } from '../../api'
import { saveAuth } from '../../api/session'
import { showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const form = reactive({ username: '', password: '', captcha_code: '', captcha_token: '' })
const confirmPassword = ref('')
const agreed = ref(false)
const submitting = ref(false)
const statusLoading = ref(true)
const registrationEnabled = ref(true)
const registrationMessage = ref('管理员已暂停新用户注册')
const captchaImage = ref('')
const captchaLoading = ref(false)
const themeClass = useTheme()

onLoad(loadRegistrationStatus)

async function loadRegistrationStatus() {
  statusLoading.value = true
  try {
    const status = await authApi.registrationStatus()
    registrationEnabled.value = status.enabled !== false
    registrationMessage.value = status.message || registrationMessage.value
    if (registrationEnabled.value) await loadCaptcha()
  } catch (error) {
    registrationEnabled.value = false
    registrationMessage.value = '暂时无法确认注册状态'
    showError(error, '注册状态加载失败')
  } finally { statusLoading.value = false }
}

async function loadCaptcha() {
  if (!registrationEnabled.value || captchaLoading.value) return
  captchaLoading.value = true
  try {
    const result = await authApi.captcha()
    form.captcha_token = result.captcha_token
    form.captcha_code = ''
    captchaImage.value = result.image
  } catch (error) { showError(error, '验证码加载失败') }
  finally { captchaLoading.value = false }
}

async function register() {
  if (!registrationEnabled.value) return uni.showToast({ title: registrationMessage.value, icon: 'none' })
  if (!/^[a-zA-Z0-9_]{3,32}$/.test(form.username)) return uni.showToast({ title: '用户名格式不正确', icon: 'none' })
  if (form.password.length < 6) return uni.showToast({ title: '密码至少 6 位', icon: 'none' })
  if (form.password !== confirmPassword.value) return uni.showToast({ title: '两次输入的密码不一致', icon: 'none' })
  if (!form.captcha_token || form.captcha_code.trim().length !== 4) return uni.showToast({ title: '请输入图片验证码', icon: 'none' })
  if (!agreed.value) return uni.showToast({ title: '请先同意服务协议与隐私政策', icon: 'none' })
  submitting.value = true
  try {
    const result = await authApi.register({ ...form, confirm_password: confirmPassword.value, nickname: form.username })
    saveAuth(result)
    uni.showToast({ title: '注册成功', icon: 'success' })
    setTimeout(() => uni.reLaunch({ url: '/pages/recorder/index' }), 300)
  } catch (error) { showError(error, '注册失败'); loadCaptcha() }
  finally { submitting.value = false }
}

function goBack() { uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/login/index' }) }) }
</script>

<style scoped>
.register-page { min-height: 100vh; background: linear-gradient(160deg,#f5faff,#faf9fa 48%,#f0f8f0); }
.topbar { height: calc(112rpx + env(safe-area-inset-top)); padding: env(safe-area-inset-top) 24rpx 0; display: flex; align-items: center; justify-content: space-between; font-size: 32rpx; font-weight: 800; }
.back { width: 80rpx; height: 80rpx; padding: 0; background: transparent; color: var(--primary); font-size: 52rpx; line-height: 76rpx; }
.register-content { width: 100%; max-width: 680rpx; margin: auto; padding: 32rpx 40rpx 70rpx; }
.intro { text-align: center; }
.logo { width: 84rpx; height: 84rpx; margin: auto; border-radius: 24rpx; background: var(--primary); color: #fff; font-size: 60rpx; line-height: 84rpx; transform: rotate(90deg); }
.title,.subtitle { display: block; }
.title { margin-top: 20rpx; font-size: 38rpx; font-weight: 800; }
.subtitle { margin-top: 10rpx; font-size: 23rpx; color: var(--muted); }
.form-card { margin-top: 34rpx; padding: 40rpx; }
.registration-notice { margin-top: 28rpx; padding: 24rpx 28rpx; color: var(--muted); font-size: 22rpx; text-align: center; }
.registration-notice.paused { border: 1rpx solid rgba(186,26,26,.2); background: #fff4f2; text-align: left; }
.notice-title,.notice-copy { display: block; }.notice-title { color: var(--error); font-size: 25rpx; font-weight: 800; }.notice-copy { margin-top: 8rpx; color: var(--muted); line-height: 1.55; }
.captcha-row { display: flex; align-items: stretch; gap: 16rpx; }.captcha-input { flex: 1; min-width: 0; }.captcha-image-wrap { flex: 0 0 220rpx; height: 92rpx; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1rpx solid rgba(0,94,161,.14); border-radius: 24rpx; background: var(--surface-low); color: var(--muted); font-size: 20rpx; }.captcha-image { width: 100%; height: 100%; }.captcha-hint { display: block; margin-top: 10rpx; color: var(--primary); font-size: 19rpx; text-align: right; }
.consent { display: flex; align-items: center; gap: 14rpx; color: var(--muted); font-size: 21rpx; }
.checkbox { width: 36rpx; height: 36rpx; flex-shrink: 0; border: 2rpx solid var(--outline); border-radius: 9rpx; text-align: center; line-height: 32rpx; color: #fff; }
.checkbox.checked { border-color: var(--primary); background: var(--primary); }
.submit { width: 100%; margin-top: 30rpx; }
.login-hint { margin-top: 34rpx; text-align: center; color: var(--muted); font-size: 24rpx; }
.link { margin-left: 10rpx; color: var(--primary); font-weight: 800; }
</style>
