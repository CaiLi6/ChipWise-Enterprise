<script setup lang="ts">
import { ref } from 'vue'
import { compareChips } from '@/api/compare'
import type { CompareResult } from '@/types/api'

const MOCK_CHIPS = ['STM32F407', 'STM32F103', 'GD32F303', 'ESP32-S3', 'TPS65217']
const selectedChips = ref<string[]>(['STM32F407', 'STM32F103'])
const result = ref<CompareResult | null>(null)
const loading = ref(false)

async function handleCompare() {
  if (selectedChips.value.length < 2) return
  loading.value = true
  try {
    result.value = await compareChips({ chips: selectedChips.value })
  } finally {
    loading.value = false
  }
}

function paramKeys(): string[] {
  if (!result.value) return []
  return Object.keys(result.value.parameters)
}
</script>

<template>
  <div style="padding: 24px">
    <h2>芯片对比</h2>
    <div style="display: flex; gap: 16px; margin-bottom: 24px; align-items: center">
      <el-select v-model="selectedChips" multiple placeholder="选择芯片型号" style="width: 400px" size="large">
        <el-option v-for="chip in MOCK_CHIPS" :key="chip" :label="chip" :value="chip" />
      </el-select>
      <el-button type="primary" size="large" :loading="loading" @click="handleCompare">
        对比
      </el-button>
    </div>
    <el-table v-if="result" :data="paramKeys().map(k => ({ param: k, ...result!.parameters[k] }))" border stripe>
      <el-table-column prop="param" label="参数" fixed width="150" />
      <el-table-column v-for="chip in result.chips" :key="chip" :prop="chip" :label="chip" min-width="120" />
    </el-table>
    <el-empty v-else description="选择至少两款芯片并点击对比" />
  </div>
</template>
