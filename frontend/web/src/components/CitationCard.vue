<script setup lang="ts">
import { computed } from 'vue'
import type { Citation } from '@/types/api'

const props = defineProps<{ citation: Citation; index?: number }>()

const docLabel = computed(() => props.citation.source || props.citation.doc_id || '未知文档')

const preview = computed(() => {
  const text = (props.citation.content || '').replace(/\s+/g, ' ').trim()
  return text.length > 240 ? text.slice(0, 240) + '…' : text
})

const scoreTier = computed<'high' | 'mid' | 'low'>(() => {
  const s = props.citation.score ?? 0
  if (s >= 0.7) return 'high'
  if (s >= 0.4) return 'mid'
  return 'low'
})
</script>

<template>
  <el-tooltip placement="top" :show-after="200" popper-class="citation-tooltip">
    <template #content>
      <div class="tip-head">
        <strong>{{ docLabel }}</strong>
        <span v-if="citation.page_number"> · p.{{ citation.page_number }}</span>
        <span v-if="citation.score" class="tip-score">相关度 {{ (citation.score * 100).toFixed(0) }}%</span>
      </div>
      <div class="tip-body">{{ preview }}</div>
    </template>

    <span class="chip" :class="scoreTier">
      <span v-if="index != null" class="chip-idx">{{ index }}</span>
      <span class="chip-doc">{{ docLabel }}</span>
      <span v-if="citation.page_number" class="chip-page">p.{{ citation.page_number }}</span>
      <span class="chip-bar" :title="`相关度 ${((citation.score ?? 0) * 100).toFixed(0)}%`" />
    </span>
  </el-tooltip>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 4px 3px 8px;
  border: 1px solid #e4e7ed;
  border-radius: 999px;
  background: #fafbfc;
  font-size: 12px;
  line-height: 1.4;
  color: #606266;
  cursor: default;
  max-width: 240px;
  transition: background 0.15s, border-color 0.15s;
}
.chip:hover {
  background: #f0f7ff;
  border-color: #c6e2ff;
}
.chip-idx {
  flex-shrink: 0;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #e4e7ed;
  color: #303133;
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.chip-doc {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #409EFF;
  font-weight: 500;
}
.chip-page {
  color: #909399;
  font-size: 11px;
  flex-shrink: 0;
}
.chip-bar {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #c0c4cc;
}
.chip.high .chip-bar { background: #67C23A; }
.chip.mid .chip-bar  { background: #E6A23C; }
.chip.low .chip-bar  { background: #C0C4CC; }
</style>

<style>
.citation-tooltip {
  max-width: 420px !important;
}
.citation-tooltip .tip-head {
  margin-bottom: 6px;
  font-size: 12px;
}
.citation-tooltip .tip-score {
  margin-left: 8px;
  color: #a0cfff;
}
.citation-tooltip .tip-body {
  font-size: 12px;
  line-height: 1.6;
  color: #e5e7eb;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
