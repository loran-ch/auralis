<script>
export default {
  onLaunch() {
    // #ifdef APP-PLUS
    if (!uni.getStorageSync('livetrans_privacy_accepted')) {
      uni.showModal({
        title: '隐私保护说明',
        content: 'LiveTrans Voice 仅在你主动录音或更换头像时申请麦克风和相册权限。课堂音频会上传到你的账号用于回顾。',
        confirmText: '同意并继续',
        cancelText: '暂不使用',
        success: (result) => {
          if (result.confirm) uni.setStorageSync('livetrans_privacy_accepted', true)
        },
      })
    }
    // #endif
  },
}
</script>

<style>
page {
  --primary: #005ea1;
  --primary-container: #2b78bf;
  --secondary: #006e1c;
  --secondary-container: #91f78e;
  --tertiary: #874e00;
  --error: #ba1a1a;
  --surface: #faf9fa;
  --surface-low: #f4f3f4;
  --surface-container: #eeedee;
  --surface-high: #e9e8e9;
  --card: #ffffff;
  --text: #1a1c1d;
  --muted: #414751;
  --outline: #c1c7d2;
  min-height: 100%;
  background: var(--surface);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 28rpx;
}

view, text, input, textarea, button, image, scroll-view, picker, switch {
  box-sizing: border-box;
}

button::after { border: none; }

.theme-dark {
  --surface: #191c1e;
  --surface-low: #202427;
  --surface-container: #252a2d;
  --surface-high: #303538;
  --card: #252a2d;
  --text: #e2e2e5;
  --muted: #c1c7d2;
  --outline: #717782;
}

.page {
  min-height: 100vh;
  background: var(--surface);
  color: var(--text);
}

.page-with-nav { padding-bottom: calc(148rpx + env(safe-area-inset-bottom)); }
.content { padding: 32rpx 40rpx; }
.content-wide { width: 100%; max-width: 1240rpx; margin: 0 auto; }

.card {
  background: var(--card);
  border: 1rpx solid rgba(193, 199, 210, 0.25);
  border-radius: 32rpx;
  box-shadow: 0 8rpx 30rpx rgba(26, 28, 29, 0.05);
}

.section-title { font-size: 32rpx; font-weight: 700; color: var(--text); }
.section-subtitle { margin-top: 8rpx; color: var(--muted); font-size: 24rpx; }
.muted { color: var(--muted); }
.primary-text { color: var(--primary); }
.secondary-text { color: var(--secondary); }
.error-text { color: var(--error); }

.btn {
  min-height: 88rpx;
  padding: 0 32rpx;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  font-size: 28rpx;
  font-weight: 700;
  line-height: 1;
}

.btn-primary { background: var(--primary); color: #fff; }
.btn-outline { background: transparent; color: var(--primary); border: 2rpx solid var(--primary); }
.btn-soft { background: var(--surface-container); color: var(--text); }
.btn-danger { background: #ffdad6; color: #93000a; }
.btn[disabled] { opacity: 0.55; }
.icon-button { width: 80rpx; height: 80rpx; padding: 0; border-radius: 50%; font-size: 34rpx; }

.field { margin-bottom: 28rpx; }
.field-label { display: block; margin-bottom: 12rpx; color: var(--muted); font-size: 24rpx; font-weight: 600; }
.input, .picker-field, .textarea {
  width: 100%;
  min-height: 92rpx;
  padding: 0 28rpx;
  color: var(--text);
  background: var(--card);
  border: 2rpx solid rgba(193, 199, 210, 0.65);
  border-radius: 24rpx;
  font-size: 28rpx;
}
.textarea { height: 180rpx; padding-top: 24rpx; }
.picker-field { display: flex; align-items: center; justify-content: space-between; }
.input:focus, .textarea:focus { border-color: var(--primary); }

.row { display: flex; align-items: center; }
.row-between { display: flex; align-items: center; justify-content: space-between; }
.wrap { flex-wrap: wrap; }
.gap-sm { gap: 12rpx; }
.gap-md { gap: 24rpx; }
.stack-sm > view + view, .stack-sm > view + button { margin-top: 16rpx; }
.stack-md > view + view, .stack-md > view + button, .stack-md > section + section { margin-top: 28rpx; }

.pill {
  display: inline-flex;
  align-items: center;
  min-height: 52rpx;
  padding: 0 20rpx;
  border-radius: 999rpx;
  background: var(--surface-container);
  color: var(--muted);
  font-size: 22rpx;
}
.pill-active { background: rgba(0, 94, 161, 0.12); color: var(--primary); font-weight: 700; }

.divider { height: 1rpx; background: rgba(193, 199, 210, 0.35); }
.empty { padding: 100rpx 40rpx; text-align: center; color: var(--muted); }
.empty-icon { display: block; margin-bottom: 20rpx; font-size: 72rpx; opacity: 0.45; }

.modal-mask {
  position: fixed;
  z-index: 200;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.modal-sheet {
  width: 100%;
  max-width: 900rpx;
  padding: 40rpx;
  padding-bottom: calc(40rpx + env(safe-area-inset-bottom));
  background: var(--card);
  border-radius: 40rpx 40rpx 0 0;
}
.modal-card {
  width: calc(100% - 64rpx);
  max-width: 680rpx;
  margin: auto;
  padding: 40rpx;
  background: var(--card);
  border-radius: 32rpx;
}
.modal-mask.center { align-items: center; }

.toast-safe { bottom: calc(160rpx + env(safe-area-inset-bottom)); }

@media (min-width: 768px) {
  .content { padding-left: 64rpx; padding-right: 64rpx; }
  .modal-sheet { border-radius: 40rpx; margin-bottom: 40rpx; }
}
</style>
