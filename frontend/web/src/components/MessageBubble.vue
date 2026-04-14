<script setup lang="ts">
import type { Citation } from '@/types/api'
import CitationCard from './CitationCard.vue'

defineProps<{
  role: 'user' | 'assistant' | 'system'
  content: string
  citations?: Citation[]
  loading?: boolean
}>()
</script>

<template>
  <div class="bubble-row" :class="role">
    <el-tag :type="role === 'user' ? 'primary' : role === 'system' ? 'danger' : 'success'" size="small" class="bubble-tag">
      {{ role === 'user' ? '我' : role === 'system' ? '系统' : 'ChipWise' }}
    </el-tag>
    <div class="bubble-body">
      <span style="white-space: pre-wrap">{{ content }}</span>
      <span v-if="loading" class="cursor">▌</span>
    </div>
    <div v-if="citations && citations.length" class="citations">
      <CitationCard v-for="c in citations" :key="c.chunk_id" :citation="c" />
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  margin-bottom: 16px;
}
.bubble-row.user {
  text-align: right;
}
.bubble-row.assistant,
.bubble-row.system {
  text-align: left;
}
.bubble-tag {
  margin-bottom: 4px;
}
.bubble-body {
  display: inline-block;
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 8px;
  text-align: left;
}
.user .bubble-body {
  background: #ecf5ff;
}
.assistant .bubble-body {
  background: #f0f9eb;
}
.system .bubble-body {
  background: #fef0f0;
  color: #f56c6c;
}
.citations {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cursor {
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>
