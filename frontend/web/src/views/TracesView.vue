<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Timer, View } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { listTraces, getTrace, type TraceSummary, type TraceDetail } from '@/api/traces'
import { getRecent, type EvaluationRecord, type MetricName } from '@/api/evaluations'

const router = useRouter()

const traces = ref<TraceSummary[]>([])
const loading = ref(false)
const queryFilter = ref('')
const statusFilter = ref<'all' | 'ok' | 'error'>('all')

const detail = ref<TraceDetail | null>(null)
const detailOpen = ref(false)
const detailLoading = ref(false)

// trace_id -> latest metrics map (enriched from /evaluations/recent)
const evalMap = ref<Record<string, Partial<Record<MetricName, number | null>>>>({})

async function load() {
  loading.value = true
  try {
    const params: { limit: number; q?: string; status?: 'ok' | 'error' } = { limit: 100 }
    if (queryFilter.value.trim()) params.q = queryFilter.value.trim()
    if (statusFilter.value !== 'all') params.status = statusFilter.value
    const resp = await listTraces(params)
    traces.value = resp.traces
    void loadEvalScores()
  } catch {
    ElMessage.error('加载 trace 列表失败')
  } finally {
    loading.value = false
  }
}

async function loadEvalScores() {
  try {
    const resp = await getRecent({ limit: 500 })
    const map: Record<string, Partial<Record<MetricName, number | null>>> = {}
    for (const r of resp.rows as EvaluationRecord[]) {
      if (!r.trace_id) continue
      if (!map[r.trace_id]) map[r.trace_id] = {}
      for (const [k, v] of Object.entries(r.metrics)) {
        if (v != null) (map[r.trace_id] as Record<string, number>)[k] = v as number
      }
    }
    evalMap.value = map
  } catch {
    // silent — eval is optional
  }
}

function scoreDotColor(v: number | null | undefined): string {
  if (v == null) return '#DCDFE6'
  if (v >= 0.8) return '#67C23A'
  if (v >= 0.6) return '#E6A23C'
  return '#F56C6C'
}

function scorePct(v: number | null | undefined): string {
  if (v == null) return '—'
  return (v * 100).toFixed(0)
}

function gotoEvaluations() {
  router.push('/evaluations')
}

async function openDetail(row: TraceSummary) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getTrace(row.trace_id)
  } catch {
    ElMessage.error('trace 加载失败（可能超出保留窗口）')
  } finally {
    detailLoading.value = false
  }
}

function formatTime(ts?: number) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
}

function formatMs(ms?: number | null) {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms.toFixed(0)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

function stageColor(stage: string): string {
  if (stage === 'request') return '#909399'
  if (stage === 'response') return '#67C23A'
  if (stage === 'error' || stage === 'max_iterations' || stage === 'budget_exhausted') return '#F56C6C'
  if (stage === 'iteration') return '#409EFF'
  if (stage === 'final_answer') return '#67C23A'
  if (stage === 'cache_hit') return '#E6A23C'
  return '#606266'
}

// Latency chart: percentage-width bars per stage.
const stageChart = computed(() => {
  if (!detail.value) return []
  const total = detail.value.stages.reduce((a, s) => a + (s.duration_ms || 0), 0) || 1
  return detail.value.stages
    .filter((s) => s.duration_ms != null && s.duration_ms > 0)
    .map((s) => ({
      stage: s.stage,
      ms: s.duration_ms as number,
      pct: ((s.duration_ms as number) / total) * 100,
      color: stageColor(s.stage),
    }))
})

onMounted(load)
</script>

<template>
  <div style="padding: 24px; height: 100vh; overflow-y: auto">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h2 style="margin: 0">Trace 查看器</h2>
      <div style="display: flex; gap: 8px">
        <el-input v-model="queryFilter" placeholder="按问题内容过滤" clearable style="width: 240px" @keyup.enter="load" />
        <el-select v-model="statusFilter" style="width: 120px" @change="load">
          <el-option label="全部" value="all" />
          <el-option label="成功" value="ok" />
          <el-option label="失败" value="error" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" plain @click="gotoEvaluations">评估仪表板</el-button>
      </div>
    </div>

    <el-table :data="traces" border stripe v-loading="loading" @row-click="openDetail">
      <el-table-column prop="started_at" label="时间" width="180">
        <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column prop="query" label="问题" min-width="280" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ok' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="citation_count" label="引用" width="80" />
      <el-table-column prop="iterations" label="轮次" width="80" />
      <el-table-column prop="stage_count" label="阶段" width="80" />
      <el-table-column label="评估" width="160">
        <template #default="{ row }">
          <div style="display: flex; gap: 8px; align-items: center">
            <el-tooltip :content="`忠实度 (faithfulness)：${scorePct(evalMap[row.trace_id]?.faithfulness)}${evalMap[row.trace_id]?.faithfulness != null ? '%' : ''}`" placement="top">
              <span style="display: inline-flex; align-items: center; gap: 4px">
                <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: scoreDotColor(evalMap[row.trace_id]?.faithfulness) }" />
                <span style="font-size: 12px; color: #606266">F {{ scorePct(evalMap[row.trace_id]?.faithfulness) }}</span>
              </span>
            </el-tooltip>
            <el-tooltip :content="`相关性 (answer_relevancy)：${scorePct(evalMap[row.trace_id]?.answer_relevancy)}${evalMap[row.trace_id]?.answer_relevancy != null ? '%' : ''}`" placement="top">
              <span style="display: inline-flex; align-items: center; gap: 4px">
                <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: scoreDotColor(evalMap[row.trace_id]?.answer_relevancy) }" />
                <span style="font-size: 12px; color: #606266">R {{ scorePct(evalMap[row.trace_id]?.answer_relevancy) }}</span>
              </span>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="100">
        <template #default="{ row }">
          <span :style="{ color: (row.duration_ms || 0) > 20000 ? '#F56C6C' : '#606266' }">
            {{ formatMs(row.duration_ms) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="user" label="用户" width="100" />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button :icon="View" text type="primary" size="small" @click.stop="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="detailOpen" size="800px" :title="detail ? `Trace ${detail.trace_id}` : 'Trace 详情'">
      <el-skeleton v-if="detailLoading" :rows="8" animated />
      <template v-else-if="detail">
        <!-- Summary header -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="状态" :span="1">
            <el-tag :type="detail.summary.status === 'ok' ? 'success' : 'danger'">{{ detail.summary.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="总耗时" :span="1">
            <el-icon><Timer /></el-icon> {{ formatMs(detail.duration_ms) }}
          </el-descriptions-item>
          <el-descriptions-item label="问题" :span="2">
            <div style="white-space: pre-wrap">{{ detail.summary.query }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="引用数">{{ detail.summary.citation_count }}</el-descriptions-item>
          <el-descriptions-item label="Agent 轮次">{{ detail.summary.iterations }}</el-descriptions-item>
        </el-descriptions>

        <!-- Latency chart -->
        <div style="margin-top: 20px" v-if="stageChart.length">
          <h4 style="margin: 0 0 8px">阶段耗时分布</h4>
          <div style="display: flex; height: 24px; border-radius: 4px; overflow: hidden; border: 1px solid #ebeef5">
            <el-tooltip v-for="(s, i) in stageChart" :key="i" :content="`${s.stage}: ${formatMs(s.ms)} (${s.pct.toFixed(1)}%)`" placement="top">
              <div :style="{ width: s.pct + '%', background: s.color, minWidth: '2px' }" />
            </el-tooltip>
          </div>
          <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px">
            <span v-for="(s, i) in stageChart" :key="i" style="display: inline-flex; align-items: center; gap: 4px">
              <span :style="{ display: 'inline-block', width: '10px', height: '10px', background: s.color, borderRadius: '2px' }" />
              {{ s.stage }} · {{ formatMs(s.ms) }}
            </span>
          </div>
        </div>

        <!-- Timeline -->
        <div style="margin-top: 20px">
          <h4 style="margin: 0 0 8px">阶段时间线</h4>
          <el-timeline>
            <el-timeline-item
              v-for="s in detail.stages"
              :key="s.index"
              :color="stageColor(s.stage)"
              :timestamp="formatTime(s.timestamp)"
              placement="top"
            >
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px">
                <el-tag :color="stageColor(s.stage)" style="color: #fff; border: none" size="small">{{ s.stage }}</el-tag>
                <span style="color: #909399; font-size: 12px" v-if="s.duration_ms != null">+{{ formatMs(s.duration_ms) }}</span>
              </div>
              <div v-if="s.stage === 'iteration'" class="meta-box">
                <div><strong>Thought:</strong> {{ (s.metadata as Record<string, string>).thought || '(no thought recorded)' }}</div>
                <div style="margin-top: 4px">
                  <strong>Tool calls:</strong>
                  <el-tag v-for="t in (s.metadata as Record<string, string[]>).tool_calls || []" :key="t" size="small" style="margin: 0 4px 0 0">
                    {{ t }}
                  </el-tag>
                </div>
                <div style="margin-top: 4px; color: #909399; font-size: 12px">
                  tokens so far: {{ (s.metadata as Record<string, number>).tokens }}
                </div>
              </div>
              <div v-else-if="s.stage === 'response'" class="meta-box">
                <div style="white-space: pre-wrap; margin-bottom: 8px">{{ (s.metadata as Record<string, string>).answer }}</div>
                <div style="color: #909399; font-size: 12px">
                  citations: {{ (s.metadata as Record<string, number>).citation_count }} ·
                  iterations: {{ (s.metadata as Record<string, number>).iterations }} ·
                  tokens: {{ (s.metadata as Record<string, number>).total_tokens }} ·
                  stopped: {{ (s.metadata as Record<string, string>).stopped_reason }}
                </div>
                <div v-if="((s.metadata as Record<string, unknown[]>).citations_preview || []).length" style="margin-top: 8px">
                  <div style="color: #606266; font-size: 12px; margin-bottom: 4px">引用 (top {{ ((s.metadata as Record<string, unknown[]>).citations_preview as unknown[]).length }})：</div>
                  <div v-for="(c, ci) in ((s.metadata as Record<string, Array<{chunk_id: string; source: string; page: number; score: number}>>).citations_preview)" :key="ci" style="font-size: 12px; color: #606266; margin: 2px 0">
                    [{{ (c.score || 0).toFixed(2) }}] {{ c.source || '?' }} p.{{ c.page || '?' }} · {{ c.chunk_id }}
                  </div>
                </div>
              </div>
              <div v-else-if="s.stage === 'error'" class="meta-box" style="color: #F56C6C">
                {{ (s.metadata as Record<string, string>).detail }}
              </div>
              <pre v-else class="meta-box" style="margin: 0; font-size: 11px; color: #606266">{{ JSON.stringify(s.metadata, null, 2) }}</pre>
            </el-timeline-item>
          </el-timeline>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.meta-box {
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  color: #303133;
  border-left: 3px solid #dcdfe6;
}
</style>
