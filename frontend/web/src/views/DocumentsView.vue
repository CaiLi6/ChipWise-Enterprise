<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, MagicStick, Delete } from '@element-plus/icons-vue'
import {
  uploadDocument,
  listDocuments,
  ingestDocument,
  ingestAllDocuments,
  deleteDocument,
  listDocumentChunks,
  getGraphStats,
  type DocumentChunk,
  type GraphStats,
} from '@/api/documents'
import LoadingError from '@/components/LoadingError.vue'
import type { DocumentMeta, DocumentListResponse } from '@/types/api'
import type { UploadFile } from 'element-plus'

const documents = ref<DocumentMeta[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const ingestingIds = ref<Set<number>>(new Set())
const ingestingAll = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const detailOpen = ref(false)
const detailLoading = ref(false)
const detailDoc = ref<DocumentMeta | null>(null)
const detailChunks = ref<DocumentChunk[]>([])
const detailChipId = ref<number | null>(null)
const detailGraph = ref<GraphStats | null>(null)
const graphStatsCache = ref<Record<number, GraphStats>>({})

async function loadGraphStats(docId: number) {
  try {
    const stats = await getGraphStats(docId)
    graphStatsCache.value[docId] = stats
    return stats
  } catch {
    return null
  }
}

async function fetchDocuments() {
  try {
    const resp: DocumentListResponse = await listDocuments()
    documents.value = resp.documents
    error.value = null
    // Fetch graph stats in parallel for completed docs (best-effort)
    const completed = resp.documents.filter(d => d.status === 'completed' && d.doc_id)
    await Promise.all(completed.map(d => loadGraphStats(d.doc_id as number)))
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    if (status === 503) {
      error.value = '后端服务暂时不可用（503）'
    } else {
      error.value = '获取文档列表失败'
    }
  }
}

async function handleUpload(uploadFile: UploadFile) {
  if (!uploadFile.raw) return
  try {
    const resp = await uploadDocument(uploadFile.raw)
    ElMessage.success(`上传成功：${resp.filename}`)
    await fetchDocuments()
  } catch {
    ElMessage.error('上传失败，请重试')
  }
}

async function handleIngestOne(row: DocumentMeta) {
  if (!row.doc_id) return
  const id = row.doc_id
  ingestingIds.value.add(id)
  row.status = 'processing'
  try {
    const result = await ingestDocument(id)
    ElMessage.success(`Ingestion 完成：${result.pages} 页 / ${result.chunks} 块`)
    await fetchDocuments()
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(`Ingestion 失败：${detail || '未知错误'}`)
    await fetchDocuments()
  } finally {
    ingestingIds.value.delete(id)
  }
}

async function handleIngestAll() {
  ingestingAll.value = true
  try {
    const result = await ingestAllDocuments()
    if (result.total === 0) {
      ElMessage.info('没有待处理的文档')
    } else if (result.failed === 0) {
      ElMessage.success(`全部完成：成功 ${result.succeeded} / ${result.total}`)
    } else {
      ElMessage.warning(`完成：成功 ${result.succeeded}，失败 ${result.failed}`)
    }
    await fetchDocuments()
  } catch {
    ElMessage.error('批量 Ingestion 失败')
  } finally {
    ingestingAll.value = false
  }
}

async function handleDelete(row: DocumentMeta) {
  if (!row.doc_id) return
  try {
    await ElMessageBox.confirm(
      `确认删除 "${row.filename}" 及其所有向量数据？此操作不可恢复。`,
      '删除文档',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteDocument(row.doc_id)
    ElMessage.success(`已删除：${row.filename}`)
    await fetchDocuments()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function handleDetail(row: DocumentMeta) {
  if (!row.doc_id) return
  detailDoc.value = row
  detailOpen.value = true
  detailLoading.value = true
  detailChunks.value = []
  detailChipId.value = null
  detailGraph.value = null
  try {
    const [chunksResp, graph] = await Promise.all([
      listDocumentChunks(row.doc_id, 15),
      loadGraphStats(row.doc_id),
    ])
    detailChunks.value = chunksResp.chunks
    detailChipId.value = chunksResp.chip_id
    detailGraph.value = graph
  } catch {
    ElMessage.warning('块信息加载失败（文档可能尚未 ingestion）')
  } finally {
    detailLoading.value = false
  }
}

function formatBytes(n: number | null | undefined): string {
  if (!n) return '-'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

function statusType(status: string) {
  switch (status) {
    case 'completed': return 'success'
    case 'processing': return 'warning'
    case 'failed': return 'danger'
    default: return 'info'
  }
}

onMounted(async () => {
  loading.value = true
  await fetchDocuments()
  loading.value = false
  pollTimer = setInterval(fetchDocuments, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div style="padding: 24px; height: 100vh; overflow-y: auto">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px">
      <h2 style="margin: 0">文档管理</h2>
      <div style="display: flex; gap: 12px">
        <el-button
          type="success"
          size="large"
          :loading="ingestingAll"
          @click="handleIngestAll"
        >
          <el-icon><MagicStick /></el-icon>
          一键 Ingestion
        </el-button>
        <el-upload action="#" :auto-upload="false" :show-file-list="false" accept=".pdf,.xlsx" @change="handleUpload">
          <el-button type="primary" size="large">
            <el-icon><UploadFilled /></el-icon>
            上传文档
          </el-button>
        </el-upload>
      </div>
    </div>
    <LoadingError :loading="loading" :error="error" :empty="documents.length === 0" empty-text="暂无文档，请上传" @retry="fetchDocuments">
      <el-table :data="documents" border stripe>
        <el-table-column prop="filename" label="文件名" min-width="240">
          <template #default="{ row }">{{ row.filename || row.title || '-' }}</template>
        </el-table-column>
        <el-table-column prop="doc_type" label="类型" width="110" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="块数 / 页数" width="110">
          <template #default="{ row }">
            <span v-if="row.metadata?.chunk_count">
              {{ row.metadata.chunk_count }} / {{ row.metadata.page_count || '-' }}
            </span>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="知识图谱" min-width="220">
          <template #default="{ row }">
            <div v-if="row.doc_id && graphStatsCache[row.doc_id]" class="kg-badge">
              <span class="kg-pill kg-param" :title="`${graphStatsCache[row.doc_id].pg.params} 个参数`">
                📊 {{ graphStatsCache[row.doc_id].pg.params }}
              </span>
              <span class="kg-pill kg-rule" :title="`${graphStatsCache[row.doc_id].pg.rules} 条设计规则`">
                📐 {{ graphStatsCache[row.doc_id].pg.rules }}
              </span>
              <span class="kg-pill kg-errata" :title="`${graphStatsCache[row.doc_id].pg.errata} 条勘误`">
                ⚠️ {{ graphStatsCache[row.doc_id].pg.errata }}
              </span>
              <span class="kg-pill kg-alt" :title="`${graphStatsCache[row.doc_id].pg.alternatives} 个替代芯片`">
                ↔️ {{ graphStatsCache[row.doc_id].pg.alternatives }}
              </span>
              <span class="kg-pill kg-graph" :title="`Kùzu: ${graphStatsCache[row.doc_id].kuzu.nodes} 节点 / ${graphStatsCache[row.doc_id].kuzu.edges} 边`">
                🕸️ {{ graphStatsCache[row.doc_id].kuzu.nodes }}n·{{ graphStatsCache[row.doc_id].kuzu.edges }}e
              </span>
            </div>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button
              text
              type="success"
              size="small"
              :loading="ingestingIds.has(row.doc_id)"
              :disabled="row.status === 'processing'"
              @click="handleIngestOne(row)"
            >
              <el-icon><MagicStick /></el-icon>
              Ingestion
            </el-button>
            <el-button text type="primary" size="small" @click="handleDetail(row)">详情</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </LoadingError>

    <el-drawer v-model="detailOpen" size="640px" :title="detailDoc?.filename || '文档详情'">
      <template v-if="detailDoc">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detailDoc.status)">{{ detailDoc.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="类型">{{ detailDoc.doc_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="磁盘路径">
            <code style="font-size: 12px">{{ detailDoc.file_path || '-' }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="大小">{{ formatBytes(detailDoc.metadata?.file_size as number) }}</el-descriptions-item>
          <el-descriptions-item label="页数 / 块数">
            {{ detailDoc.metadata?.page_count || '-' }} / {{ detailDoc.metadata?.chunk_count || 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="Collection">{{ detailDoc.metadata?.collection || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Milvus chip_id" v-if="detailChipId !== null">{{ detailChipId }}</el-descriptions-item>
          <el-descriptions-item label="处理时间">{{ detailDoc.metadata?.processed_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detailGraph" style="margin-top: 18px">
          <h4 style="margin: 0 0 10px 0">知识图谱统计</h4>
          <div class="kg-grid">
            <div class="kg-cell"><span>参数</span><b>{{ detailGraph.pg.params }}</b></div>
            <div class="kg-cell"><span>设计规则</span><b>{{ detailGraph.pg.rules }}</b></div>
            <div class="kg-cell"><span>勘误</span><b>{{ detailGraph.pg.errata }}</b></div>
            <div class="kg-cell"><span>替代芯片</span><b>{{ detailGraph.pg.alternatives }}</b></div>
            <div class="kg-cell"><span>Kùzu 节点</span><b>{{ detailGraph.kuzu.nodes }}</b></div>
            <div class="kg-cell"><span>Kùzu 边</span><b>{{ detailGraph.kuzu.edges }}</b></div>
          </div>
        </div>

        <div style="margin-top: 20px">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px">
            <h4 style="margin: 0">索引块预览 <span style="color:#909399;font-weight:normal;font-size:12px">（前 {{ detailChunks.length }} 条）</span></h4>
          </div>
          <el-skeleton v-if="detailLoading" :rows="4" animated />
          <div v-else-if="detailChunks.length === 0" style="color:#909399;padding:16px 0">
            没有索引块 — 请先点击 Ingestion 按钮入库。
          </div>
          <el-collapse v-else accordion>
            <el-collapse-item v-for="c in detailChunks" :key="c.chunk_id" :name="c.chunk_id">
              <template #title>
                <span style="color:#409EFF;font-weight:600;font-size:12px">p.{{ c.page }}</span>
                <span style="color:#909399;font-size:12px;margin-left:8px">{{ c.chunk_id }}</span>
              </template>
              <div style="font-size:13px;line-height:1.6;color:#303133;white-space:pre-wrap">{{ c.content }}</div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.kg-badge {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.kg-pill {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
  line-height: 1.4;
}
.kg-param  { background: #eff6ff; color: #1d4ed8; border-color: #dbeafe; }
.kg-rule   { background: #f0fdf4; color: #15803d; border-color: #dcfce7; }
.kg-errata { background: #fef3c7; color: #92400e; border-color: #fde68a; }
.kg-alt    { background: #fdf4ff; color: #a21caf; border-color: #f5d0fe; }
.kg-graph  { background: #f3f4f6; color: #374151; border-color: #e5e7eb; }

.kg-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.kg-cell {
  background: #f9fafb;
  border: 1px solid #f3f4f6;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
}
.kg-cell span { font-size: 12px; color: #6b7280; }
.kg-cell b { font-size: 18px; color: #111827; margin-top: 2px; }
</style>
