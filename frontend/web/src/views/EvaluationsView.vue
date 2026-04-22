<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, TrendCharts, DataLine, Histogram, ScaleToOriginal, Warning, Collection, Document, Plus, Delete } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, BoxplotChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent,
  TitleComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import {
  METRICS, type MetricName,
  getSummary, getAggregate, getDistribution, getCompare, getOutliers, getRecent, listRuns, getRun, triggerRun,
  type EvaluationSummary, type AggregateResponse, type DistributionResponse, type CompareResponse,
  type EvaluationRecord, type BatchRun,
} from '@/api/evaluations'
import {
  listGolden, addGolden, deleteGolden, runGolden, type GoldenQA,
} from '@/api/golden'

echarts.use([
  LineChart, BarChart, BoxplotChart,
  GridComponent, TooltipComponent, LegendComponent, TitleComponent,
  DataZoomComponent, MarkLineComponent, MarkAreaComponent,
  CanvasRenderer,
])

// ---------------- Display helpers -------------------------------------------

const METRIC_LABELS: Record<MetricName, string> = {
  faithfulness: '忠实度',
  answer_relevancy: '相关性',
  context_precision: '检索精度',
  context_recall: '检索召回',
  citation_coverage: '引用覆盖',
  latency_score: '延迟分',
  citation_diversity: '引用多样',
  agent_efficiency: 'Agent效率',
}

const METRIC_COLORS: Record<MetricName, string> = {
  faithfulness: '#409EFF',
  answer_relevancy: '#67C23A',
  context_precision: '#E6A23C',
  context_recall: '#9B59B6',
  citation_coverage: '#F56C6C',
  latency_score: '#14B8A6',
  citation_diversity: '#FB923C',
  agent_efficiency: '#64748B',
}

const scoreColor = (v: number | null | undefined) => {
  if (v == null) return '#909399'
  if (v >= 0.8) return '#67C23A'
  if (v >= 0.6) return '#E6A23C'
  return '#F56C6C'
}
const formatScore = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(3))
const formatPct = (v: number | null | undefined) =>
  v == null ? '—' : (v * 100).toFixed(1) + '%'
const formatDelta = (v: number | null | undefined) => {
  if (v == null) return '—'
  const sign = v > 0 ? '+' : ''
  return sign + v.toFixed(3)
}
const fmtTime = (ts: number) =>
  ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : '—'
const fmtMs = (ms: number | null | undefined) => {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms.toFixed(0)} ms` : `${(ms / 1000).toFixed(1)} s`
}

// ---------------- Global state ----------------------------------------------

const activeTab = ref('overview')
const globalMode = ref<'' | 'online_sampled' | 'offline_batch' | 'golden'>('')
const globalWindow = ref<number>(7 * 86400)

const WINDOW_OPTS = [
  { label: '1小时', value: 3600 },
  { label: '6小时', value: 6 * 3600 },
  { label: '24小时', value: 86400 },
  { label: '7天', value: 7 * 86400 },
  { label: '30天', value: 30 * 86400 },
  { label: '90天', value: 90 * 86400 },
]

// ---------------- Overview tab ----------------------------------------------

const summary = ref<EvaluationSummary | null>(null)
const summaryLoading = ref(false)

async function loadSummary() {
  summaryLoading.value = true
  try {
    summary.value = await getSummary()
  } catch (e) {
    ElMessage.error('summary 加载失败')
  } finally {
    summaryLoading.value = false
  }
}

const sparklineRaw = ref<AggregateResponse | null>(null)
async function loadSparkline() {
  try {
    sparklineRaw.value = await getAggregate({
      bucket_sec: Math.max(3600, Math.floor(globalWindow.value / 48)),
      window_sec: globalWindow.value,
      mode: globalMode.value || undefined,
    })
  } catch {}
}

function sparkOption(metric: MetricName) {
  const series = (sparklineRaw.value?.series?.[metric] || [])
  return {
    grid: { top: 4, right: 4, bottom: 4, left: 4 },
    xAxis: { type: 'time', show: false },
    yAxis: { type: 'value', show: false, min: 0, max: 1 },
    tooltip: {
      trigger: 'axis',
      formatter: (p: any) => `${new Date(p[0].value[0]).toLocaleString('zh-CN')}<br/>${p[0].value[1].toFixed(3)}`,
    },
    series: [{
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { color: METRIC_COLORS[metric], width: 2 },
      areaStyle: { color: METRIC_COLORS[metric], opacity: 0.15 },
      data: series.map((p) => [p.ts * 1000, p.value]),
    }],
  }
}

const kpiMetrics = computed<MetricName[]>(() => [
  'faithfulness', 'answer_relevancy', 'context_precision', 'citation_coverage',
])

const kpiCards = computed(() => {
  const w = summary.value?.windows?.['7d']
  const delta = summary.value?.trend_7d_delta
  if (!w || !delta) return []
  return kpiMetrics.value.map((m) => {
    const s = w[m]
    return {
      metric: m,
      label: METRIC_LABELS[m],
      mean: s.mean,
      count: s.count,
      delta: delta[m] || 0,
      color: scoreColor(s.mean),
    }
  })
})

// ---------------- Time-series tab -------------------------------------------

const tsRaw = ref<AggregateResponse | null>(null)
const tsLoading = ref(false)
const tsSelectedMetrics = ref<MetricName[]>(['faithfulness', 'answer_relevancy', 'context_precision', 'citation_coverage'])
const tsBucketSec = ref(3600)

async function loadTs() {
  tsLoading.value = true
  try {
    tsRaw.value = await getAggregate({
      bucket_sec: tsBucketSec.value,
      window_sec: globalWindow.value,
      mode: globalMode.value || undefined,
    })
  } catch {
    ElMessage.error('时序加载失败')
  } finally {
    tsLoading.value = false
  }
}

const tsOption = computed(() => {
  const series = tsSelectedMetrics.value.map((m) => ({
    name: METRIC_LABELS[m],
    type: 'line' as const,
    smooth: true,
    showSymbol: false,
    itemStyle: { color: METRIC_COLORS[m] },
    data: (tsRaw.value?.series?.[m] || []).map((p) => [p.ts * 1000, p.value]),
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { top: 40, right: 20, bottom: 50, left: 50 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', min: 0, max: 1, name: '分数' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20 }],
    series,
  }
})

// ---------------- Distribution tab ------------------------------------------

const distMetric = ref<MetricName>('faithfulness')
const distBins = ref(20)
const distRaw = ref<DistributionResponse | null>(null)
const distLoading = ref(false)

async function loadDist() {
  distLoading.value = true
  try {
    distRaw.value = await getDistribution({
      metric: distMetric.value,
      window_sec: globalWindow.value,
      bins: distBins.value,
      mode: globalMode.value || undefined,
    })
  } catch {
    ElMessage.error('分布加载失败')
  } finally {
    distLoading.value = false
  }
}

const distOption = computed(() => {
  const d = distRaw.value
  if (!d) return {}
  const categories = d.bin_edges.slice(0, -1).map(
    (lo, i) => `${lo.toFixed(2)}–${d.bin_edges[i + 1].toFixed(2)}`,
  )
  return {
    tooltip: { trigger: 'axis' },
    grid: { top: 40, right: 20, bottom: 80, left: 60 },
    xAxis: { type: 'category', data: categories, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', name: '样本数' },
    series: [{
      type: 'bar',
      data: d.counts,
      itemStyle: { color: METRIC_COLORS[distMetric.value] },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#F56C6C', type: 'dashed' },
        data: [
          { xAxis: categories.findIndex((c) => parseFloat(c) >= d.mean), name: `均值 ${d.mean.toFixed(3)}` },
        ],
      },
    }],
  }
})

// ---------------- Compare tab -----------------------------------------------

const compareState = ref<{ a_from: number; a_to: number; b_from: number; b_to: number } | null>(null)
const compareRaw = ref<CompareResponse | null>(null)
const compareLoading = ref(false)

function initCompareDefaults() {
  const now = Math.floor(Date.now() / 1000)
  compareState.value = {
    a_from: now - 14 * 86400,
    a_to: now - 7 * 86400,
    b_from: now - 7 * 86400,
    b_to: now,
  }
}

async function loadCompare() {
  if (!compareState.value) return
  compareLoading.value = true
  try {
    compareRaw.value = await getCompare({
      ...compareState.value,
      mode: globalMode.value || undefined,
    })
  } catch {
    ElMessage.error('对比加载失败')
  } finally {
    compareLoading.value = false
  }
}

const compareRows = computed(() => {
  const m = compareRaw.value?.metrics
  if (!m) return []
  return (Object.keys(m) as MetricName[]).map((k) => ({
    metric: k,
    label: METRIC_LABELS[k],
    ...m[k],
  }))
})

// ---------------- Outliers tab ----------------------------------------------

const outlierMetric = ref<MetricName>('faithfulness')
const outlierLt = ref<number>(0.5)
const outlierRows = ref<EvaluationRecord[]>([])
const outlierLoading = ref(false)

async function loadOutliers() {
  outlierLoading.value = true
  try {
    const r = await getOutliers({
      metric: outlierMetric.value,
      lt: outlierLt.value,
      window_sec: globalWindow.value,
      limit: 100,
    })
    outlierRows.value = r.rows
  } catch {
    ElMessage.error('离群加载失败')
  } finally {
    outlierLoading.value = false
  }
}

function openTraceFromOutlier(row: EvaluationRecord) {
  if (!row.trace_id) return
  window.open(`/traces?trace=${row.trace_id}`, '_blank')
}

// ---------------- Recent tab (全部评估记录 ∈ 离群 tab 的姐妹) -----------------

const recentRows = ref<EvaluationRecord[]>([])
const recentLoading = ref(false)
async function loadRecent() {
  recentLoading.value = true
  try {
    const r = await getRecent({ limit: 100, mode: globalMode.value || undefined })
    recentRows.value = r.rows
  } catch {
    ElMessage.error('最近记录加载失败')
  } finally {
    recentLoading.value = false
  }
}

// ---------------- Batches tab -----------------------------------------------

const runs = ref<BatchRun[]>([])
const runsLoading = ref(false)
async function loadRuns() {
  runsLoading.value = true
  try {
    runs.value = (await listRuns(100)).runs
  } catch {
    ElMessage.error('批次加载失败')
  } finally {
    runsLoading.value = false
  }
}

const runForm = ref({
  kind: 'traces' as 'traces' | 'golden',
  judge: 'router' as 'primary' | 'router',
  limit: 20,
  concurrency: 2,
})
const runBusy = ref(false)
async function onTriggerRun() {
  runBusy.value = true
  try {
    const r = await triggerRun(runForm.value)
    ElMessage.success(`已启动批次 ${r.batch_id?.slice(0, 8)}`)
    await loadRuns()
  } catch {
    ElMessage.error('批次启动失败')
  } finally {
    runBusy.value = false
  }
}

const runDetail = ref<{ batch: BatchRun; samples: EvaluationRecord[] } | null>(null)
const runDetailOpen = ref(false)
async function openRun(r: BatchRun) {
  runDetailOpen.value = true
  try {
    const d = await getRun(r.batch_id)
    runDetail.value = { batch: d.batch, samples: d.samples }
  } catch {
    ElMessage.error('批次详情加载失败')
  }
}

// ---------------- Golden tab ------------------------------------------------

const goldenRows = ref<GoldenQA[]>([])
const goldenLoading = ref(false)
const goldenFormOpen = ref(false)
const goldenForm = ref({
  question: '',
  ground_truth_answer: '',
  chip_ids: '' as string,
  tags: '' as string,
})

async function loadGolden() {
  goldenLoading.value = true
  try {
    goldenRows.value = (await listGolden()).rows
  } catch {
    ElMessage.error('金标加载失败')
  } finally {
    goldenLoading.value = false
  }
}

async function onAddGolden() {
  if (!goldenForm.value.question || !goldenForm.value.ground_truth_answer) {
    ElMessage.warning('问题和标准答案都必填')
    return
  }
  await addGolden({
    question: goldenForm.value.question,
    ground_truth_answer: goldenForm.value.ground_truth_answer,
    chip_ids: goldenForm.value.chip_ids.split(',').map((s) => s.trim()).filter(Boolean),
    tags: goldenForm.value.tags.split(',').map((s) => s.trim()).filter(Boolean),
  })
  goldenFormOpen.value = false
  goldenForm.value = { question: '', ground_truth_answer: '', chip_ids: '', tags: '' }
  await loadGolden()
  ElMessage.success('已新增')
}

async function onDeleteGolden(row: GoldenQA) {
  try {
    await ElMessageBox.confirm(`删除金标「${row.question}」？`, '确认', { type: 'warning' })
    await deleteGolden(row.id)
    await loadGolden()
    ElMessage.success('已删除')
  } catch {}
}

async function onRunGolden(judge: 'primary' | 'router') {
  try {
    const r = await runGolden(judge)
    ElMessage.success(`已启动金标跑 ${r.batch_id?.slice(0, 8)}`)
    activeTab.value = 'batches'
    await loadRuns()
  } catch {
    ElMessage.error('启动金标跑失败')
  }
}

// ---------------- Lifecycle -------------------------------------------------

async function reloadAll() {
  await Promise.all([loadSummary(), loadSparkline()])
  if (activeTab.value === 'timeseries') loadTs()
  if (activeTab.value === 'distribution') loadDist()
  if (activeTab.value === 'compare') loadCompare()
  if (activeTab.value === 'outliers') loadOutliers()
  if (activeTab.value === 'recent') loadRecent()
  if (activeTab.value === 'batches') loadRuns()
  if (activeTab.value === 'golden') loadGolden()
}

watch(activeTab, (v) => {
  if (v === 'timeseries') loadTs()
  else if (v === 'distribution') loadDist()
  else if (v === 'compare') {
    if (!compareState.value) initCompareDefaults()
    loadCompare()
  }
  else if (v === 'outliers') loadOutliers()
  else if (v === 'recent') loadRecent()
  else if (v === 'batches') loadRuns()
  else if (v === 'golden') loadGolden()
})

watch(globalWindow, reloadAll)
watch(globalMode, reloadAll)

onMounted(async () => {
  initCompareDefaults()
  await reloadAll()
})
</script>

<template>
  <div class="eval-root">
    <!-- Header -->
    <div class="eval-header">
      <div>
        <h2 style="margin: 0">RAG 可视化评估</h2>
        <div style="color: #909399; font-size: 12px; margin-top: 4px">
          总记录 {{ summary?.total ?? '—' }} · 最近评估 {{ fmtTime(summary?.last_evaluated_at || 0) }}
        </div>
      </div>
      <div class="eval-controls">
        <el-select v-model="globalWindow" size="default" style="width: 120px">
          <el-option v-for="o in WINDOW_OPTS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="globalMode" size="default" style="width: 140px" placeholder="全部模式">
          <el-option label="全部模式" value="" />
          <el-option label="在线采样" value="online_sampled" />
          <el-option label="离线批" value="offline_batch" />
          <el-option label="金标" value="golden" />
        </el-select>
        <el-button :icon="Refresh" @click="reloadAll">刷新</el-button>
      </div>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" type="border-card" class="eval-tabs">
      <!-- 概览 -->
      <el-tab-pane name="overview">
        <template #label><el-icon><ScaleToOriginal /></el-icon> 概览</template>
        <div v-loading="summaryLoading">
          <div class="kpi-grid">
            <div v-for="card in kpiCards" :key="card.metric" class="kpi-card">
              <div class="kpi-label">{{ card.label }}</div>
              <div class="kpi-value" :style="{ color: card.color }">
                {{ formatPct(card.mean) }}
              </div>
              <div class="kpi-meta">
                <span>n={{ card.count }}</span>
                <span :style="{ color: card.delta >= 0 ? '#67C23A' : '#F56C6C' }">
                  {{ card.delta > 0 ? '▲' : card.delta < 0 ? '▼' : '·' }} {{ formatDelta(card.delta) }}
                </span>
              </div>
              <div class="kpi-spark">
                <VChart :option="sparkOption(card.metric)" autoresize style="height: 50px" />
              </div>
            </div>
          </div>
          <div class="overview-subtext">
            窗口: 7d vs 前 7d · 点击"时序"看完整曲线 · 点击"分布"看分数分布尾部
          </div>
        </div>
      </el-tab-pane>

      <!-- 时序 -->
      <el-tab-pane name="timeseries">
        <template #label><el-icon><DataLine /></el-icon> 时序</template>
        <div v-loading="tsLoading">
          <div class="ts-controls">
            <el-checkbox-group v-model="tsSelectedMetrics">
              <el-checkbox v-for="m in METRICS" :key="m" :label="m">
                <span :style="{ color: METRIC_COLORS[m] }">●</span> {{ METRIC_LABELS[m] }}
              </el-checkbox>
            </el-checkbox-group>
            <el-select v-model="tsBucketSec" size="small" style="width: 110px" @change="loadTs">
              <el-option label="每 10 分钟" :value="600" />
              <el-option label="每小时" :value="3600" />
              <el-option label="每 4 小时" :value="14400" />
              <el-option label="每天" :value="86400" />
            </el-select>
          </div>
          <VChart :option="tsOption" autoresize style="height: 480px" />
        </div>
      </el-tab-pane>

      <!-- 分布 -->
      <el-tab-pane name="distribution">
        <template #label><el-icon><Histogram /></el-icon> 分布</template>
        <div v-loading="distLoading">
          <div class="dist-controls">
            <el-select v-model="distMetric" style="width: 160px" @change="loadDist">
              <el-option v-for="m in METRICS" :key="m" :label="METRIC_LABELS[m]" :value="m" />
            </el-select>
            <el-input-number v-model="distBins" :min="5" :max="50" @change="loadDist" />
            <span v-if="distRaw" style="color: #606266; font-size: 13px">
              n={{ distRaw.n }} · 均值 {{ distRaw.mean.toFixed(3) }} · 中位 {{ distRaw.median.toFixed(3) }}
            </span>
          </div>
          <VChart :option="distOption" autoresize style="height: 480px" />
        </div>
      </el-tab-pane>

      <!-- 对比 -->
      <el-tab-pane name="compare">
        <template #label><el-icon><TrendCharts /></el-icon> A/B 对比</template>
        <div v-loading="compareLoading" v-if="compareState">
          <div class="compare-inputs">
            <div>
              <div class="compare-label" style="color: #909399">窗口 A (基线)</div>
              <el-date-picker v-model="compareState.a_from" type="datetime" value-format="x"
                style="width: 180px" @change="loadCompare" />
              <span style="margin: 0 6px">→</span>
              <el-date-picker v-model="compareState.a_to" type="datetime" value-format="x"
                style="width: 180px" @change="loadCompare" />
            </div>
            <div>
              <div class="compare-label" style="color: #409EFF">窗口 B (对比)</div>
              <el-date-picker v-model="compareState.b_from" type="datetime" value-format="x"
                style="width: 180px" @change="loadCompare" />
              <span style="margin: 0 6px">→</span>
              <el-date-picker v-model="compareState.b_to" type="datetime" value-format="x"
                style="width: 180px" @change="loadCompare" />
            </div>
            <el-button @click="loadCompare" :icon="Refresh">对比</el-button>
          </div>
          <el-alert v-if="compareRaw" type="info" :closable="false" style="margin-bottom: 12px">
            A 组 n={{ compareRaw.window_a.n }} · B 组 n={{ compareRaw.window_b.n }} · 正 Δ 表示 B 优于 A
          </el-alert>
          <el-table :data="compareRows" border stripe size="small">
            <el-table-column prop="label" label="指标" width="120" />
            <el-table-column label="A 均值" width="100">
              <template #default="{ row }">{{ formatScore(row.mean_a) }}</template>
            </el-table-column>
            <el-table-column label="B 均值" width="100">
              <template #default="{ row }">{{ formatScore(row.mean_b) }}</template>
            </el-table-column>
            <el-table-column label="Δ (B−A)" width="110">
              <template #default="{ row }">
                <span :style="{ color: row.delta >= 0 ? '#67C23A' : '#F56C6C', fontWeight: 600 }">
                  {{ formatDelta(row.delta) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="n_a" label="n(A)" width="70" />
            <el-table-column prop="n_b" label="n(B)" width="70" />
            <el-table-column label="t 统计量" width="100">
              <template #default="{ row }">{{ row.t.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="p ≈" width="90">
              <template #default="{ row }">
                <el-tag :type="row.p_approx < 0.05 ? 'success' : 'info'" size="small">
                  {{ row.p_approx.toFixed(3) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="显著">
              <template #default="{ row }">
                <span v-if="row.p_approx < 0.05 && Math.abs(row.t) > 1.96">
                  {{ row.delta > 0 ? '✅ B 显著优于 A' : '⚠ B 显著差于 A' }}
                </span>
                <span v-else style="color: #909399">无显著差异</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 离群 -->
      <el-tab-pane name="outliers">
        <template #label><el-icon><Warning /></el-icon> 离群</template>
        <div v-loading="outlierLoading">
          <div class="outlier-controls">
            <el-select v-model="outlierMetric" style="width: 160px" @change="loadOutliers">
              <el-option v-for="m in METRICS" :key="m" :label="METRIC_LABELS[m]" :value="m" />
            </el-select>
            <span>阈值 &lt;</span>
            <el-input-number v-model="outlierLt" :min="0" :max="1" :step="0.05" :precision="2"
              style="width: 120px" @change="loadOutliers" />
            <span style="color: #909399">{{ outlierRows.length }} 条</span>
          </div>
          <el-table :data="outlierRows" border stripe size="small" @row-click="openTraceFromOutlier">
            <el-table-column prop="evaluated_at" label="时间" width="160">
              <template #default="{ row }">{{ fmtTime(row.evaluated_at) }}</template>
            </el-table-column>
            <el-table-column prop="query" label="问题" min-width="220" show-overflow-tooltip />
            <el-table-column label="分数" width="100">
              <template #default="{ row }">
                <el-tag :color="scoreColor(row.metrics[outlierMetric])" style="color: #fff; border: none">
                  {{ formatScore(row.metrics[outlierMetric]) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="judge_model" label="judge" width="140" />
            <el-table-column prop="mode" label="模式" width="120" />
            <el-table-column label="trace" width="120">
              <template #default="{ row }">
                <el-link type="primary" @click.stop="openTraceFromOutlier(row)">
                  {{ (row.trace_id || '').slice(0, 8) }}
                </el-link>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 最近记录 -->
      <el-tab-pane name="recent">
        <template #label><el-icon><Document /></el-icon> 最近记录</template>
        <div v-loading="recentLoading">
          <el-table :data="recentRows" border stripe size="small" max-height="600">
            <el-table-column prop="evaluated_at" label="时间" width="160">
              <template #default="{ row }">{{ fmtTime(row.evaluated_at) }}</template>
            </el-table-column>
            <el-table-column prop="query" label="问题" min-width="240" show-overflow-tooltip />
            <el-table-column v-for="m in ['faithfulness','answer_relevancy','context_precision','citation_coverage'] as MetricName[]"
              :key="m" :label="METRIC_LABELS[m]" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.metrics[m] != null" :color="scoreColor(row.metrics[m])"
                  style="color: #fff; border: none" size="small">
                  {{ formatScore(row.metrics[m]) }}
                </el-tag>
                <span v-else style="color: #909399">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="mode" label="模式" width="120" />
            <el-table-column prop="judge_model" label="judge" width="140" />
            <el-table-column label="trace" width="100">
              <template #default="{ row }">
                <el-link type="primary" @click.stop="openTraceFromOutlier(row)">
                  {{ (row.trace_id || '').slice(0, 8) }}
                </el-link>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 批处理 -->
      <el-tab-pane name="batches">
        <template #label><el-icon><Collection /></el-icon> 批处理</template>
        <div class="batch-form">
          <el-form inline :model="runForm">
            <el-form-item label="类型">
              <el-select v-model="runForm.kind" style="width: 120px">
                <el-option label="trace 回放" value="traces" />
                <el-option label="金标跑" value="golden" />
              </el-select>
            </el-form-item>
            <el-form-item label="Judge">
              <el-select v-model="runForm.judge" style="width: 140px">
                <el-option label="router 1.7B (快)" value="router" />
                <el-option label="primary 35B (准)" value="primary" />
              </el-select>
            </el-form-item>
            <el-form-item label="limit" v-if="runForm.kind === 'traces'">
              <el-input-number v-model="runForm.limit" :min="1" :max="500" />
            </el-form-item>
            <el-form-item label="并发">
              <el-input-number v-model="runForm.concurrency" :min="1" :max="4" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="runBusy" @click="onTriggerRun">启动批次</el-button>
              <el-button :icon="Refresh" @click="loadRuns">刷新</el-button>
            </el-form-item>
          </el-form>
        </div>

        <el-table :data="runs" border stripe size="small" v-loading="runsLoading" @row-click="openRun">
          <el-table-column prop="started_at" label="开始" width="160">
            <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column prop="mode" label="模式" width="130" />
          <el-table-column prop="judge_model" label="judge" width="160" />
          <el-table-column label="进度" width="120">
            <template #default="{ row }">
              <el-progress :percentage="row.n_total ? Math.round(row.n_done / row.n_total * 100) : 0"
                :status="row.status === 'failed' ? 'exception' : row.status === 'succeeded' ? 'success' : ''" />
            </template>
          </el-table-column>
          <el-table-column label="完成/失败/总" width="120">
            <template #default="{ row }">{{ row.n_done }}/{{ row.n_failed }}/{{ row.n_total }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="100">
            <template #default="{ row }">
              {{ row.completed_at ? fmtMs((row.completed_at - row.started_at) * 1000) : '…' }}
            </template>
          </el-table-column>
          <el-table-column label="忠实度" width="100">
            <template #default="{ row }">
              <span v-if="row.aggregate?.faithfulness_mean != null"
                :style="{ color: scoreColor(row.aggregate.faithfulness_mean), fontWeight: 600 }">
                {{ formatScore(row.aggregate.faithfulness_mean) }}
              </span>
              <span v-else style="color: #909399">—</span>
            </template>
          </el-table-column>
          <el-table-column label="相关性" width="100">
            <template #default="{ row }">
              <span v-if="row.aggregate?.answer_relevancy_mean != null"
                :style="{ color: scoreColor(row.aggregate.answer_relevancy_mean), fontWeight: 600 }">
                {{ formatScore(row.aggregate.answer_relevancy_mean) }}
              </span>
              <span v-else style="color: #909399">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'succeeded' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'running' ? 'warning' : ''" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <el-drawer v-model="runDetailOpen" size="900px" :title="runDetail ? `批次 ${runDetail.batch.batch_id.slice(0,8)}` : '批次详情'">
          <template v-if="runDetail">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="批次">{{ runDetail.batch.batch_id }}</el-descriptions-item>
              <el-descriptions-item label="judge">{{ runDetail.batch.judge_model }}</el-descriptions-item>
              <el-descriptions-item label="模式">{{ runDetail.batch.mode }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="runDetail.batch.status === 'succeeded' ? 'success' : 'info'">
                  {{ runDetail.batch.status }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="总样本">{{ runDetail.batch.n_total }}</el-descriptions-item>
              <el-descriptions-item label="完成 / 失败">
                {{ runDetail.batch.n_done }} / {{ runDetail.batch.n_failed }}
              </el-descriptions-item>
              <el-descriptions-item label="聚合" :span="2">
                <div v-if="runDetail.batch.aggregate" class="aggregate-box">
                  <div v-for="(v, k) in runDetail.batch.aggregate" :key="k" class="aggregate-item">
                    <span style="color: #909399">{{ k }}:</span> <strong>{{ typeof v === 'number' ? v.toFixed(3) : v }}</strong>
                  </div>
                </div>
              </el-descriptions-item>
            </el-descriptions>
            <div style="margin-top: 16px">
              <h4 style="margin: 0 0 8px">样本 ({{ runDetail.samples.length }})</h4>
              <el-table :data="runDetail.samples" border stripe size="small" max-height="400">
                <el-table-column prop="query" label="问题" min-width="200" show-overflow-tooltip />
                <el-table-column v-for="m in ['faithfulness','answer_relevancy','context_precision','citation_coverage'] as MetricName[]"
                  :key="m" :label="METRIC_LABELS[m]" width="90">
                  <template #default="{ row }">
                    <span :style="{ color: scoreColor(row.metrics[m]), fontWeight: 600 }">
                      {{ formatScore(row.metrics[m]) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="trace" width="100">
                  <template #default="{ row }">
                    <el-link type="primary" @click="openTraceFromOutlier(row)">
                      {{ (row.trace_id || '').slice(0, 8) }}
                    </el-link>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-drawer>
      </el-tab-pane>

      <!-- 金标 -->
      <el-tab-pane name="golden">
        <template #label><el-icon><Document /></el-icon> 金标</template>
        <div class="golden-toolbar">
          <el-button type="primary" :icon="Plus" @click="goldenFormOpen = true">新增</el-button>
          <el-button type="warning" @click="onRunGolden('router')">一键跑 (router)</el-button>
          <el-button type="success" @click="onRunGolden('primary')">一键跑 (primary 35B)</el-button>
          <span style="color: #909399">共 {{ goldenRows.length }} 条</span>
        </div>
        <el-table :data="goldenRows" border stripe size="small" v-loading="goldenLoading" max-height="540">
          <el-table-column prop="id" label="ID" width="120" />
          <el-table-column prop="question" label="问题" min-width="250" show-overflow-tooltip />
          <el-table-column prop="ground_truth_answer" label="标准答案" min-width="250" show-overflow-tooltip />
          <el-table-column label="芯片" width="180">
            <template #default="{ row }">
              <el-tag v-for="c in row.chip_ids" :key="c" size="small" style="margin-right: 4px">
                {{ c }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="标签" width="160">
            <template #default="{ row }">
              <el-tag v-for="t in row.tags" :key="t" size="small" type="info" style="margin-right: 4px">
                {{ t }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button :icon="Delete" text type="danger" size="small" @click="onDeleteGolden(row)" />
            </template>
          </el-table-column>
        </el-table>
        <el-dialog v-model="goldenFormOpen" title="新增金标" width="600px">
          <el-form :model="goldenForm" label-width="90">
            <el-form-item label="问题">
              <el-input v-model="goldenForm.question" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="标准答案">
              <el-input v-model="goldenForm.ground_truth_answer" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="芯片(逗号)">
              <el-input v-model="goldenForm.chip_ids" placeholder="PH2A106FLG900, XCKU5PFFVD900" />
            </el-form-item>
            <el-form-item label="标签(逗号)">
              <el-input v-model="goldenForm.tags" placeholder="pcie, bandwidth" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="goldenFormOpen = false">取消</el-button>
            <el-button type="primary" @click="onAddGolden">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.eval-root {
  padding: 20px;
  height: 100vh;
  overflow-y: auto;
  background: #f5f7fa;
}
.eval-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}
.eval-controls {
  display: flex;
  gap: 8px;
}
.eval-tabs {
  background: #fff;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.kpi-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px 16px 10px;
  display: flex;
  flex-direction: column;
}
.kpi-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 4px;
}
.kpi-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
  margin-bottom: 4px;
}
.kpi-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}
.kpi-spark {
  margin-top: 8px;
}
.overview-subtext {
  margin-top: 12px;
  color: #909399;
  font-size: 12px;
}
.ts-controls {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
}
.dist-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.compare-inputs {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.compare-label {
  font-size: 12px;
  margin-bottom: 4px;
}
.outlier-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.batch-form {
  background: #fafbfc;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 12px;
}
.aggregate-box {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.aggregate-item {
  font-size: 12px;
}
.golden-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
</style>
