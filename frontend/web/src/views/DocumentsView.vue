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
  type DocumentChunk,
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

async function fetchDocuments() {
  try {
    const resp: DocumentListResponse = await listDocuments()
    documents.value = resp.documents
    error.value = null
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
  try {
    const resp = await listDocumentChunks(row.doc_id, 15)
    detailChunks.value = resp.chunks
    detailChipId.value = resp.chip_id
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
