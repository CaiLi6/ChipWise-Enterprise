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

// Build a deep link to the source PDF at the cited page when a doc_id is
// available. Browsers honour the `#page=N` PDF fragment for the built-in
// viewer, which is enough to drop the user on the right page.
const sourceUrl = computed<string | null>(() => {
  const did = props.citation.doc_id
  if (did === undefined || did === null) return null
  const base = (import.meta as any).env?.VITE_API_BASE_URL || ''
  const page = props.citation.page_number
  const frag = page ? `#page=${page}` : ''
  return `${base}/api/v1/documents/${did}/file${frag}`
})

function openSource() {
  if (sourceUrl.value) {
    window.open(sourceUrl.value, '_blank', 'noopener')
  }
}
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
      <div v-if="sourceUrl" class="tip-foot">点击打开原文档 ↗</div>
    </template>

    <span
      class="chip"
      :class="[scoreTier, { clickable: !!sourceUrl }]"
      :role="sourceUrl ? 'link' : undefined"
      :tabindex="sourceUrl ? 0 : undefined"
      @click="openSource"
      @keydown.enter="openSource"
    >
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
  padding: 3px 10px 3px 4px;
  border: 1px solid #f3f4f6;
  border-radius: 999px;
  background: #fafafa;
  font-size: 12px;
  line-height: 1.4;
  color: #6b7280;
  cursor: default;
  max-width: 240px;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.chip:hover {
  background: #ffffff;
  border-color: #e5e7eb;
  color: #374151;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
}
.chip-idx {
  flex-shrink: 0;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #ffffff;
  color: #6b7280;
  font-size: 10.5px;
  font-weight: 600;
  border: 1px solid #f3f4f6;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-variant-numeric: tabular-nums;
}
.chip-doc {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #374151;
  font-weight: 500;
}
.chip-page {
  color: #9ca3af;
  font-size: 11px;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.chip-bar {
  flex-shrink: 0;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #d1d5db;
}
.chip.high .chip-bar { background: #10b981; }
.chip.mid  .chip-bar { background: #f59e0b; }
.chip.low  .chip-bar { background: #d1d5db; }
.chip.clickable {
  cursor: pointer;
}
.chip.clickable:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 2px;
}
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
.citation-tooltip .tip-foot {
  margin-top: 6px;
  font-size: 11px;
  color: #93c5fd;
}
</style>
