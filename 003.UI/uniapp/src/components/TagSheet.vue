<template>
  <view v-if="modelValue" class="modal-mask" @tap.self="close">
    <view class="modal-sheet">
      <view class="row-between title-row">
        <text class="section-title">{{ t('recorder.bookmark') }}</text>
        <text class="close" @tap="close">×</text>
      </view>
      <view class="tag-list">
        <view v-for="tag in tags" :key="tag.value" class="tag-option" @tap="select(tag.value)">
          <text class="tag-icon">{{ tag.icon }}</text>
          <view><text class="tag-name">{{ tag.label() }}</text><text class="tag-desc">{{ tag.desc() }}</text></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { t } from '../platform/i18n'
defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'select'])
const tags = [
  { value: 'important', label: () => t('tag.important'), icon: '⭐', desc: () => t('tag.importantHint') },
  { value: 'question', label: () => t('tag.question'), icon: '❓', desc: () => t('tag.questionHint') },
  { value: 'exam', label: () => t('tag.exam'), icon: '🎯', desc: () => t('tag.examHint') },
  { value: 'definition', label: () => t('tag.definition'), icon: '📘', desc: () => t('tag.definitionHint') },
]
function close() { emit('update:modelValue', false) }
function select(value) { emit('select', value); close() }
</script>

<style scoped>
.title-row { margin-bottom: 28rpx; }
.close { width: 64rpx; height: 64rpx; text-align: center; line-height: 58rpx; font-size: 48rpx; color: var(--muted); }
.tag-list { display: flex; flex-wrap: wrap; gap: 20rpx; }
.tag-option { width: calc(50% - 10rpx); min-height: 126rpx; padding: 24rpx; display: flex; align-items: center; gap: 20rpx; border-radius: 24rpx; background: var(--surface-low); }
.tag-icon { font-size: 38rpx; }
.tag-name, .tag-desc { display: block; }
.tag-name { font-weight: 700; color: var(--text); }
.tag-desc { margin-top: 6rpx; font-size: 20rpx; color: var(--muted); }
</style>
