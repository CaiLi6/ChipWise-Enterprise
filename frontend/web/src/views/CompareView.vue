<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Close, Document, Download, MagicStick, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { compareChips, listChips } from '@/api/compare'
import type { ChipListItem, CompareCellValue, CompareResult } from '@/types/api'
import CitationCard from '@/components/CitationCard.vue'

// ── State ────────────────────────────────────────────────────────────
const allChips = ref<ChipListItem[]>([])
const searchKeyword = ref('')
const searching = ref(false)
const selectedChips = ref<string[]>([])
const result = ref<CompareResult | null>(null)
const loading = ref(false)
const highlightDiff = ref(true)
const groupByCategory = ref(true)

// Optional category filter sent to backend (drives `dimensions`).
const dimensionFilter = ref<string[]>([])
const KNOWN_CATEGORIES = [
  { value: 'electrical', label: '电气' },
  { value: 'timing', label: '时序' },
  { value: 'thermal', label: '温度' },
  { value: 'mechanical', label: '机械' },
  { value: 'environmental', label: '环境' },
]

// ── Chip search (remote) ─────────────────────────────────────────────
async function loadChips(q?: string) {
  searching.value = true
  try {
    const resp = await listChips(q, 50)
    allChips.value = resp.chips
  } catch (e: any) {
    ElMessage.error(`加载芯片列表失败：${e?.message || e}`)
  } finally {
    searching.value = false
  }
}

function handleRemoteSearch(query: string) {
  searchKeyword.value = query
  if (query) loadChips(query)
  else loadChips()
}

onMounted(() => loadChips())

// ── Compare action ───────────────────────────────────────────────────
async function handleCompare() {
  if (selectedChips.value.length < 2) {
    ElMessage.warning('至少选择 2 款芯片')
    return
  }
  loading.value = true
  try {
    result.value = await compareChips({
      chip_names: [...selectedChips.value],
      dimensions: dimensionFilter.value.length ? [...dimensionFilter.value] : undefined,
    })
  } catch (e: any) {
    ElMessage.error(`对比失败：${e?.response?.data?.detail || e?.message || e}`)
  } finally {
    loading.value = false
  }
}

function removeChip(chip: string) {
  selectedChips.value = selectedChips.value.filter((c) => c !== chip)
  if (!result.value) return
  result.value.chips = result.value.chips.filter((c) => c !== chip)
  for (const k of Object.keys(result.value.comparison_table)) {
    delete result.value.comparison_table[k][chip]
  }
  if (result.value.chips.length < 2) {
    result.value = null
  }
}

// ── Table data ───────────────────────────────────────────────────────
type Row = {
  param: string
  category: string
  values: Record<string, CompareCellValue | null>
}

function formatCell(v: CompareCellValue | null | undefined): string {
  if (!v) return '—'
  const typ = v.typ ?? v.max ?? v.min
  if (typ === null || typ === undefined || typ === '') return '—'
  return v.unit ? `${typ} ${v.unit}` : `${typ}`
}

const rows = computed<Row[]>(() => {
  if (!result.value) return []
  const tab = result.value.comparison_table || {}
  const out: Row[] = []
  for (const [param, perChip] of Object.entries(tab)) {
    // category from first non-null cell
    const cat =
      Object.values(perChip).find((c) => c && c.category)?.category ?? 'other'
    out.push({ param, category: cat || 'other', values: perChip })
  }
  return out.sort((a, b) =>
    a.category === b.category
      ? a.param.localeCompare(b.param)
      : a.category.localeCompare(b.category),
  )
})

const groupedRows = computed<Array<{ category: string; rows: Row[] }>>(() => {
  if (!groupByCategory.value) return [{ category: '', rows: rows.value }]
  const buckets: Record<string, Row[]> = {}
  for (const r of rows.value) {
    ;(buckets[r.category] ||= []).push(r)
  }
  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, rs]) => ({ category, rows: rs }))
})

function categoryLabel(c: string): string {
  return (
    KNOWN_CATEGORIES.find((k) => k.value === c)?.label ||
    (c === 'other' ? '其它' : c)
  )
}

function isDiffRow(row: Row): boolean {
  if (!result.value) return false
  const vals = result.value.chips.map((c) => formatCell(row.values[c]))
  return new Set(vals).size > 1
}

function rowClass({ row }: { row: Row }): string {
  return highlightDiff.value && isDiffRow(row) ? 'diff-row' : ''
}

// ── AI analysis rendering ─────────────────────────────────────────────
const analysisHtml = computed(() => {
  const md = result.value?.analysis?.trim()
  if (!md) return ''
  const html = marked.parse(md, { gfm: true, breaks: true }) as string
  return DOMPurify.sanitize(html)
})

// ── Export ───────────────────────────────────────────────────────────
function exportMarkdown() {
  if (!result.value) return
  const lines: string[] = []
  lines.push(`# 芯片对比报告\n`)
  lines.push(`**对比对象**: ${result.value.chips.join(' vs ')}\n`)
  if (result.value.analysis) {
    lines.push('## AI 智能解读\n')
    lines.push(result.value.analysis.trim() + '\n')
  }
  lines.push('## 参数对比\n')
  lines.push(`| 参数 | ${result.value.chips.join(' | ')} |`)
  lines.push(`|---${'|---'.repeat(result.value.chips.length)}|`)
  for (const g of groupedRows.value) {
    if (g.category) {
      lines.push(
        `| **${categoryLabel(g.category)}** ${'|'.repeat(result.value.chips.length + 1)}`,
      )
    }
    for (const r of g.rows) {
      lines.push(
        `| ${r.param} | ${result.value.chips.map((c) => formatCell(r.values[c])).join(' | ')} |`,
      )
    }
  }
  if (result.value.citations.length) {
    lines.push('\n## 引用来源\n')
    result.value.citations.forEach((c, i) => {
      lines.push(
        `${i + 1}. ${c.source || c.doc_id || '未知文档'}${c.page_number ? ` p.${c.page_number}` : ''}`,
      )
    })
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `chip-compare-${result.value.chips.join('-vs-')}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="compare-page">
    <header class="page-header">
      <div>
        <h2>芯片对比</h2>
        <p class="hint">从知识库选择 2–5 款芯片，按参数维度横向对比并获取 AI 智能解读。</p>
      </div>
      <div class="header-actions" v-if="result">
        <el-button :icon="Download" plain @click="exportMarkdown">导出 Markdown</el-button>
      </div>
    </header>

    <!-- Selector toolbar -->
    <section class="toolbar">
      <el-select
        v-model="selectedChips"
        multiple
        filterable
        remote
        :remote-method="handleRemoteSearch"
        :loading="searching"
        :max="5"
        placeholder="搜索 / 选择芯片型号"
        size="large"
        class="chip-select"
      >
        <el-option
          v-for="c in allChips"
          :key="c.chip_id"
          :label="c.part_number"
          :value="c.part_number"
        >
          <span>{{ c.part_number }}</span>
          <span class="chip-meta">
            {{ c.manufacturer || '—' }} · {{ c.param_count }} 参数
          </span>
        </el-option>
        <template #empty>
          <div class="empty-tip">
            {{ searching ? '搜索中…' : '未找到芯片，先在「文档管理」上传 datasheet。' }}
          </div>
        </template>
      </el-select>

      <el-select
        v-model="dimensionFilter"
        multiple
        collapse-tags
        collapse-tags-tooltip
        clearable
        placeholder="过滤参数类别（默认全部）"
        size="large"
        class="dim-select"
      >
        <el-option
          v-for="d in KNOWN_CATEGORIES"
          :key="d.value"
          :label="d.label"
          :value="d.value"
        />
      </el-select>

      <el-button
        type="primary"
        size="large"
        :loading="loading"
        :icon="MagicStick"
        :disabled="selectedChips.length < 2"
        @click="handleCompare"
      >
        开始对比
      </el-button>
    </section>

    <section class="view-options" v-if="result">
      <el-switch v-model="highlightDiff" /><span>高亮差异行</span>
      <el-switch v-model="groupByCategory" /><span>按类别分组</span>
    </section>

    <!-- AI analysis -->
    <section v-if="result && analysisHtml" class="analysis-card">
      <div class="analysis-header">
        <el-icon><MagicStick /></el-icon>
        <span>AI 智能解读</span>
      </div>
      <div class="analysis-body md" v-html="analysisHtml" />
    </section>

    <!-- Comparison table(s) -->
    <template v-if="result">
      <section
        v-for="grp in groupedRows"
        :key="grp.category || 'all'"
        class="table-section"
      >
        <h3 v-if="grp.category" class="cat-title">{{ categoryLabel(grp.category) }}</h3>
        <el-table
          :data="grp.rows"
          :row-class-name="rowClass"
          stripe
          border
          class="cmp-table"
        >
          <el-table-column prop="param" label="参数" fixed width="220" align="left" />
          <el-table-column
            v-for="chip in result.chips"
            :key="chip"
            min-width="160"
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
            <template #default="{ row }">
              <span class="cell-typ">{{ formatCell(row.values[chip]) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <!-- Citations -->
      <section v-if="result.citations.length" class="citations">
        <div class="cit-head"><el-icon><Document /></el-icon> 来源 · {{ result.citations.length }} 条</div>
        <div class="cit-list">
          <CitationCard
            v-for="(c, i) in result.citations"
            :key="i"
            :citation="c as any"
            :index="i + 1"
          />
        </div>
      </section>
    </template>

    <el-empty
      v-else
      :image-size="120"
      description="选择至少两款芯片，点击「开始对比」获取参数表 + AI 解读"
    >
      <template #image>
        <el-icon :size="64" color="#cbd5e1"><Plus /></el-icon>
      </template>
    </el-empty>
  </div>
</template>

<style scoped>
.compare-page {
  padding: 28px 32px;
  max-width: 1280px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 20px;
}
.page-header h2 { margin: 0; font-size: 22px; color: #111827; }
.hint { margin: 4px 0 0; color: #6b7280; font-size: 13px; }

.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 16px;
}
.chip-select { flex: 1 1 380px; min-width: 280px; }
.dim-select  { flex: 0 0 240px; }
.chip-meta {
  float: right;
  color: #9ca3af;
  font-size: 12px;
  margin-left: 12px;
}
.empty-tip {
  text-align: center;
  color: #9ca3af;
  padding: 16px;
  font-size: 13px;
}

.view-options {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  color: #4b5563;
  font-size: 13px;
}
.view-options span { margin-right: 16px; }

.analysis-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #6366f1;
  border-radius: 12px;
  padding: 18px 22px;
  margin-bottom: 20px;
}
.analysis-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #4338ca;
  margin-bottom: 10px;
  font-size: 14px;
}
.analysis-body {
  color: #374151;
  line-height: 1.7;
  font-size: 14px;
}
.analysis-body :deep(h3),
.analysis-body :deep(h4) { margin: 14px 0 6px; color: #1f2937; }
.analysis-body :deep(p)  { margin: 6px 0; }
.analysis-body :deep(ul) { margin: 6px 0; padding-left: 20px; }

.cat-title {
  margin: 22px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.cmp-table { border-radius: 10px; overflow: hidden; }
.chip-header {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
}
.chip-delete {
  font-size: 13px;
  color: #9ca3af;
  cursor: pointer;
  padding: 2px;
  border-radius: 50%;
}
.chip-delete:hover { background: rgba(245, 108, 108, 0.12); color: #f56c6c; }
.cell-typ { font-variant-numeric: tabular-nums; color: #1f2937; }

.citations {
  margin-top: 24px;
  padding: 16px 20px;
  background: #fafafa;
  border: 1px solid #f3f4f6;
  border-radius: 10px;
}
.cit-head {
  display: flex; align-items: center; gap: 6px;
  color: #9ca3af; font-size: 13px; margin-bottom: 10px;
}
.cit-list { display: flex; flex-wrap: wrap; gap: 8px; }
</style>

<style>
.diff-row > td.el-table__cell {
  background-color: #fffbeb !important;
}
.diff-row:hover > td.el-table__cell {
  background-color: #fef3c7 !important;
}
</style>
