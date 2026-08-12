export function shareText(title, content) {
  // #ifdef APP-PLUS
  uni.share({
    provider: 'system',
    type: 0,
    title,
    summary: content,
    success: () => {},
    fail: () => copyText(content),
  })
  // #endif
  // #ifndef APP-PLUS
  copyText(content)
  // #endif
}

export function copyText(content) {
  uni.setClipboardData({
    data: content,
    success: () => uni.showToast({ title: '已复制到剪贴板', icon: 'success' }),
  })
}
