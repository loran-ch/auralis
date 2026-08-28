<template>
  <view class="auth-page" :class="themeClass">
    <view class="auth-orb orb-one" /><view class="auth-orb orb-two" />
    <view class="auth-card">
      <view class="brand-mark">≋</view>
      <view class="locale-picker"><picker :range="localeNames" :value="localeIndex" @change="changeLocale"><text>{{ localeNames[localeIndex] }}⌄</text></picker></view>
      <text class="brand-title">Auralis</text>
      <text class="brand-subtitle">{{ t('auth.welcomeBack') }}</text>

      <view class="form">
        <view class="field">
          <text class="field-label">{{ t('auth.account') }}</text>
          <view class="input-wrap"><text class="prefix">♙</text><input v-model="account" class="auth-input" :placeholder="t('auth.accountPlaceholder')" autocomplete="username" /></view>
        </view>
        <view class="field">
          <view class="row-between"><text class="field-label">{{ t('auth.password') }}</text><text class="link">{{ t('auth.forgot') }}</text></view>
          <view class="input-wrap">
            <text class="prefix">⌑</text>
            <input v-model="password" class="auth-input" :password="!showPassword" :placeholder="t('auth.passwordPlaceholder')" autocomplete="current-password" @confirm="submit" />
            <text class="visibility" @tap="showPassword = !showPassword">{{ showPassword ? t('auth.hidePassword') : t('auth.showPassword') }}</text>
          </view>
        </view>
        <button class="btn btn-primary login-button" :disabled="submitting" @tap="submit">{{ submitting ? t('auth.loggingIn') : t('auth.login') }}</button>
      </view>

      <view class="register-hint"><text>{{ t('auth.noAccount') }}</text><text class="link strong" @tap="goRegister">{{ t('auth.registerNow') }}</text></view>
      <view class="divider-title"><view class="line" /><text>{{ t('auth.thirdParty') }}</text><view class="line" /></view>
      <view class="third-party"><button class="social">微</button><button class="social"></button><button class="social">G</button></view>
      <text class="agreement">{{ t('auth.agreement') }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { authApi } from '../../api'
import { saveAuth } from '../../api/session'
import { showError } from '../../platform/format'
import { useTheme } from '../../platform/theme'
import { setLocale, t, useLocale } from '../../platform/i18n'

const account = ref('')
const password = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const themeClass = useTheme()
const locale = useLocale()
const localeCodes = ['zh-Hans', 'zh-HK', 'en']
const localeNames = computed(() => [t('locale.simplified'), t('locale.cantonese'), t('locale.english')])
const localeIndex = computed(() => Math.max(0, localeCodes.indexOf(locale.value)))

function changeLocale(event) { setLocale(localeCodes[Number(event.detail.value)] || 'zh-Hans') }

async function submit() {
  if (!account.value.trim()) return uni.showToast({ title: '请输入用户名或手机号', icon: 'none' })
  if (password.value.length < 6) return uni.showToast({ title: '密码至少 6 位', icon: 'none' })
  submitting.value = true
  try {
    const result = await authApi.login(account.value.trim(), password.value)
    saveAuth(result)
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.reLaunch({ url: '/pages/recorder/index' }), 300)
  } catch (error) {
    showError(error, '登录失败')
  } finally {
    submitting.value = false
  }
}

function goRegister() { uni.navigateTo({ url: '/pages/register/index' }) }
</script>

<style scoped>
.auth-page { min-height: 100vh; padding: calc(80rpx + env(safe-area-inset-top)) 40rpx 60rpx; display: flex; align-items: center; justify-content: center; overflow: hidden; background: linear-gradient(155deg,#f6fbff 0%,#faf9fa 46%,#eef7ee 100%); position: relative; }
.auth-orb { position: absolute; border-radius: 50%; filter: blur(3rpx); opacity: .5; }
.orb-one { width: 430rpx; height: 430rpx; left: -180rpx; top: -100rpx; background: rgba(0,94,161,.12); }
.orb-two { width: 360rpx; height: 360rpx; right: -150rpx; bottom: -100rpx; background: rgba(0,110,28,.1); }
.auth-card { position: relative; z-index: 2; width: 100%; max-width: 680rpx; padding: 58rpx 44rpx 44rpx; background: rgba(255,255,255,.92); border: 1rpx solid rgba(193,199,210,.35); border-radius: 42rpx; box-shadow: 0 26rpx 70rpx rgba(0,56,98,.1); }
.locale-picker { display: flex; justify-content: flex-end; min-height: 30rpx; color: var(--primary); font-size: 21rpx; }.brand-mark { width: 96rpx; height: 96rpx; margin: 0 auto 20rpx; border-radius: 28rpx; display: flex; align-items: center; justify-content: center; background: var(--primary); color: #fff; font-size: 70rpx; font-weight: 900; line-height: 1; transform: rotate(90deg); }
.brand-title,.brand-subtitle { display: block; text-align: center; }
.brand-title { font-size: 42rpx; font-weight: 800; letter-spacing: -1rpx; color: var(--text); }
.brand-subtitle { margin-top: 10rpx; font-size: 26rpx; color: var(--muted); }
.form { margin-top: 52rpx; }
.input-wrap { min-height: 96rpx; padding: 0 22rpx; display: flex; align-items: center; gap: 16rpx; border: 2rpx solid #d9dde4; border-radius: 24rpx; background: #fff; }
.input-wrap:focus-within { border-color: var(--primary); box-shadow: 0 0 0 6rpx rgba(0,94,161,.08); }
.prefix { width: 38rpx; color: var(--primary); font-size: 34rpx; }
.auth-input { flex: 1; height: 92rpx; font-size: 28rpx; }
.visibility,.link { color: var(--primary); font-size: 23rpx; }
.strong { margin-left: 10rpx; font-weight: 800; }
.login-button { width: 100%; margin-top: 16rpx; }
.register-hint { margin-top: 34rpx; display: flex; justify-content: center; color: var(--muted); font-size: 24rpx; }
.divider-title { margin: 38rpx 0 26rpx; display: flex; align-items: center; gap: 18rpx; color: #8b9098; font-size: 22rpx; }
.line { flex: 1; height: 1rpx; background: #dfe3e8; }
.third-party { display: flex; justify-content: center; gap: 28rpx; }
.social { width: 80rpx; height: 80rpx; padding: 0; border-radius: 50%; background: #f4f5f7; color: #303438; font-size: 30rpx; line-height: 80rpx; }
.agreement { display: block; margin-top: 36rpx; text-align: center; color: #8b9098; font-size: 20rpx; line-height: 1.6; }
</style>
