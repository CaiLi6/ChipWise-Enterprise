<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadDocument, listDocuments } from '@/api/documents'
import LoadingError from '@/components/LoadingError.vue'
import type { DocumentMeta, DocumentListResponse } from '@/types/api'
import type { UploadFile } from 'element-plus'

const documents = ref<DocumentMeta[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

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
    ElMessage.success(`上传成功：${resp.filename}（任务 ${resp.task_id}）`)
    await fetchDocuments()
  } catch {
    ElMessage.error('上传失败，请重试')
  }
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
      <el-upload action="#" :auto-upload="false" :show-file-list="false" accept=".pdf,.xlsx" @change="handleUpload">
        <el-button type="primary" size="large">
          <el-icon><UploadFilled /></el-icon>
          上传文档
        </el-button>
      </el-upload>
    </div>
    <LoadingError :loading="loading" :error="error" :empty="documents.length === 0" empty-text="暂无文档，请上传" @retry="fetchDocuments">
      <el-table :data="documents" border stripe>
        <el-table-column prop="filename" label="文件名" min-width="200">
          <template #default="{ row }">{{ row.filename || row.title || '-' }}</template>
        </el-table-column>
        <el-table-column prop="doc_type" label="类型" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="console.log('detail', row.doc_id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </LoadingError>
  </div>
</template>
