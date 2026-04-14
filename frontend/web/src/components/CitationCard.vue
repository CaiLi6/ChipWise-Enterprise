<script setup lang="ts">
import { computed } from 'vue'
import type { Citation } from '@/types/api'

const props = defineProps<{ citation: Citation }>()

const preview = computed(() => {
  const text = props.citation.content || ''
  return text.length > 150 ? text.slice(0, 150) + '…' : text
})
</script>

<template>
  <el-tooltip :content="citation.content" placement="top" :show-after="300">
    <el-card shadow="hover" class="citation-card" body-style="padding: 8px 12px">
      <div class="citation-header">
        <span class="doc-id">{{ citation.doc_id }}</span>
        <el-tag size="small" type="info" v-if="citation.score">{{ citation.score.toFixed(2) }}</el-tag>
      </div>
      <div class="citation-text">{{ preview }}</div>
    </el-card>
  </el-tooltip>
</template>

<style scoped>
.citation-card {
  max-width: 300px;
  cursor: pointer;
}
.citation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.doc-id {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}
.citation-text {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}
</style>
