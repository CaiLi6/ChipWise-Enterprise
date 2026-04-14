<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'

interface DocItem {
  id: string
  filename: string
  status: string
  uploadedAt: string
}

const documents = ref<DocItem[]>([
  { id: '1', filename: 'STM32F407_Datasheet.pdf', status: 'completed', uploadedAt: '2026-04-14' },
  { id: '2', filename: 'GD32F303_Manual.pdf', status: 'processing', uploadedAt: '2026-04-14' },
])

function handleUpload() {
  documents.value.unshift({
    id: String(Date.now()),
    filename: 'NewDocument.pdf',
    status: 'pending',
    uploadedAt: new Date().toISOString().slice(0, 10),
  })
}
</script>

<template>
  <div style="padding: 24px">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px">
      <h2 style="margin: 0">文档管理</h2>
      <el-upload action="#" :auto-upload="false" :show-file-list="false" @change="handleUpload">
        <el-button type="primary" size="large">
          <el-icon><UploadFilled /></el-icon>
          上传文档
        </el-button>
      </el-upload>
    </div>
    <el-table :data="documents" border stripe>
      <el-table-column prop="filename" label="文件名" />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'processing' ? 'warning' : 'info'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="uploadedAt" label="上传日期" width="150" />
    </el-table>
  </div>
</template>
