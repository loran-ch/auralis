<template>
  <view class="register-page" :class="themeClass">
    <view class="topbar"><button class="back" @tap="goBack">‹</button><text>创建账户</text><view class="back" /></view>
    <view class="register-content">
      <view class="intro"><view class="logo">≋</view><text class="title">加入 LiveTrans Voice</text><text class="subtitle">保存每一堂课，收藏每一个知识点</text></view>
      <view class="form-card card">
        <view class="field"><text class="field-label">用户名</text><input v-model="form.username" class="input" placeholder="3-32 位字母、数字或下划线" maxlength="32" /></view>
        <view class="field"><text class="field-label">手机号码</text><input v-model="form.phone" class="input" type="number" placeholder="请输入手机号码" maxlength="11" /></view>
        <view class="field">
          <text class="field-label">验证码</text>
          <view class="code-row"><input v-model="form.code" class="input code-input" type="number" placeholder="6 位验证码" maxlength="6" /><button class="code-button" :disabled="countdown > 0 || sendingCode" @tap="sendCode">{{ countdown > 0 ? `${countdown}s` : (sendingCode ? '发送中' : '获取验证码') }}</button></view>
        </view>
        <view class="field"><text class="field-label">设置密码</text><input v-model="form.password" class="input" password placeholder="至少 6 位" maxlength="72" /></view>
        <view class="field"><text class="field-label">确认密码</text><input v-model="confirmPassword" class="input" password placeholder="请再次输入密码" maxlength="72" /></view>
        <view class="consent" @tap="agreed = !agreed"><view class="checkbox" :class="{ checked: agreed }">{{ agreed ? '✓' : '' }}</view><text>我已阅读并同意《服务协议》和《隐私政策》</text></view>
        <button class="btn btn-primary submit" :disabled="submitting" @tap="register">{{ submitting ? '正在创建…' : '注册并登录' }}</button>
      </view>
      <view class="login-hint"><text>已有账户？</text><text class="link" @tap="goBack">立即登录</text></view>
    </view>
  </view>
</template>

<script setup>
import { reactive, ref, onUnmounted } from 'vue'
import { authApi } from '../../api'
import { saveAuth } from '../../api/session'
import { showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'

const form = reactive({ username: '', phone: '', code: '', password: '' })
const confirmPassword = ref('')
const agreed = ref(false)
const sendingCode = ref(false)
const submitting = ref(false)
const countdown = ref(0)
const themeClass = useTheme()
let timer = null

function validPhone() { return /^1[3-9]\d{9}$/.test(form.phone) }

async function sendCode() {
  if (!validPhone()) return uni.showToast({ title: '请输入正确的手机号码', icon: 'none' })
  sendingCode.value = true
  try {
    const result = await authApi.sendCode(form.phone)
    uni.showToast({ title: result.message || '验证码已发送', icon: 'none' })
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (error) { showError(error, '验证码发送失败') }
  finally { sendingCode.value = false }
}

async function register() {
  if (!/^[a-zA-Z0-9_]{3,32}$/.test(form.username)) return uni.showToast({ title: '用户名格式不正确', icon: 'none' })
  if (!validPhone()) return uni.showToast({ title: '请输入正确的手机号码', icon: 'none' })
  if (form.code.length < 4) return uni.showToast({ title: '请输入验证码', icon: 'none' })
  if (form.password.length < 6) return uni.showToast({ title: '密码至少 6 位', icon: 'none' })
  if (form.password !== confirmPassword.value) return uni.showToast({ title: '两次输入的密码不一致', icon: 'none' })
  if (!agreed.value) return uni.showToast({ title: '请先同意服务协议与隐私政策', icon: 'none' })
  submitting.value = true
  try {
    const result = await authApi.register({ ...form, nickname: form.username })
    saveAuth(result)
    uni.showToast({ title: '注册成功', icon: 'success' })
    setTimeout(() => uni.reLaunch({ url: '/pages/recorder/index' }), 300)
  } catch (error) { showError(error, '注册失败') }
  finally { submitting.value = false }
}

function goBack() { uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/login/index' }) }) }
onUnmounted(() => clearInterval(timer))
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
.code-row { display: flex; gap: 16rpx; }
.code-input { flex: 1; }
.code-button { width: 210rpx; min-height: 92rpx; padding: 0 16rpx; border-radius: 24rpx; background: rgba(0,94,161,.1); color: var(--primary); font-size: 23rpx; font-weight: 700; line-height: 1; }
.consent { display: flex; align-items: center; gap: 14rpx; color: var(--muted); font-size: 21rpx; }
.checkbox { width: 36rpx; height: 36rpx; flex-shrink: 0; border: 2rpx solid var(--outline); border-radius: 9rpx; text-align: center; line-height: 32rpx; color: #fff; }
.checkbox.checked { border-color: var(--primary); background: var(--primary); }
.submit { width: 100%; margin-top: 30rpx; }
.login-hint { margin-top: 34rpx; text-align: center; color: var(--muted); font-size: 24rpx; }
.link { margin-left: 10rpx; color: var(--primary); font-weight: 800; }
</style>
