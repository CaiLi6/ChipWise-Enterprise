<script setup lang="ts">
import { ref, computed } from 'vue'
import { compareChips } from '@/api/compare'
import type { CompareResult } from '@/types/api'
import { Close } from '@element-plus/icons-vue'

const MOCK_CHIPS = ['STM32F407', 'STM32F103', 'GD32F303', 'ESP32-S3', 'TPS65217']
const selectedChips = ref<string[]>(['STM32F407', 'STM32F103'])
const result = ref<CompareResult | null>(null)
const loading = ref(false)
const highlight = ref(true)

type Row = { param: string } & Record<string, string>

const tableData = computed<Row[]>(() => {
  if (!result.value) return []
  return Object.keys(result.value.parameters).map((k) => ({
    param: k,
    ...result.value!.parameters[k],
  }))
})

async function handleCompare() {
  if (selectedChips.value.length < 2) return
  loading.value = true
  try {
    // Strictly pass current selection — table reflects exactly these chips
    result.value = await compareChips({ chips: [...selectedChips.value] })
  } finally {
    loading.value = false
  }
}

function isDiffRow(row: Row): boolean {
  if (!result.value) return false
  const values = result.value.chips.map((c) => row[c])
  return new Set(values).size > 1
}

function rowClassName({ row }: { row: Row }): string {
  return highlight.value && isDiffRow(row) ? 'diff-row' : ''
}

function removeChip(chip: string) {
  selectedChips.value = selectedChips.value.filter((c) => c !== chip)
  if (!result.value) return
  result.value.chips = result.value.chips.filter((c) => c !== chip)
  for (const key of Object.keys(result.value.parameters)) {
    delete result.value.parameters[key][chip]
  }
  if (result.value.chips.length < 2) {
    result.value = null
  }
}
</script>

<template>
  <div style="padding: 24px; max-width: 1280px; margin: 0 auto">
    <h2 style="margin: 0 0 20px">芯片对比</h2>

    <div style="display: flex; gap: 16px; margin-bottom: 24px; align-items: center; flex-wrap: wrap">
      <el-select
        v-model="selectedChips"
        multiple
        placeholder="选择芯片型号"
        style="width: 420px"
        size="large"
      >
        <el-option v-for="chip in MOCK_CHIPS" :key="chip" :label="chip" :value="chip" />
      </el-select>

      <el-button type="primary" size="large" :loading="loading" @click="handleCompare">
        对比
      </el-button>

      <div style="display: flex; align-items: center; gap: 8px; margin-left: 4px">
        <el-switch v-model="highlight" />
        <span style="font-size: 14px; color: #606266">高亮差异</span>
      </div>
    </div>

    <el-table
      v-if="result"
      :data="tableData"
      :row-class-name="rowClassName"
      border
      stripe
      style="width: 100%"
    >
      <el-table-column prop="param" label="参数" fixed width="160" align="left" />
      <el-table-column
        v-for="chip in result.chips"
        :key="chip"
        :prop="chip"
        min-width="140"
        align="center"
      >
        <template #header>
          <div class="chip-header">
            <span>{{ chip }}</span>
            <el-icon class="chip-delete" @click.stop="removeChip(chip)">
              <Close />
            </el-icon>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else description="选择至少两款芯片并点击对比" />
  </div>
</template>

<style scoped>
.chip-header {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
}
.chip-delete {
  font-size: 14px;
  color: #909399;
  cursor: pointer;
  padding: 2px;
  border-radius: 50%;
  transition: background 0.15s, color 0.15s;
}
.chip-delete:hover {
  background: rgba(245, 108, 108, 0.12);
  color: #f56c6c;
}
</style>

<style>
/* 差异行：浅黄底，比 hover 稍亮，覆盖 stripe 的条纹 */
.el-table .diff-row > td.el-table__cell {
  background-color: #fffbe6 !important;
}
.el-table .diff-row:hover > td.el-table__cell {
  background-color: #fff4c2 !important;
}
/* 普通行 hover 加强 */
.el-table tbody tr:hover > td.el-table__cell {
  background-color: #f0f7ff !important;
}
</style>
