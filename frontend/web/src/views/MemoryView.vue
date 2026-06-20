<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createMemory,
  deleteMemory,
  listEpisodes,
  listMemories,
  updateMemoryStatus,
  type MemoryEpisode,
  type MemoryRecord,
} from '@/api/memory'

const memories = ref<MemoryRecord[]>([])
const episodes = ref<MemoryEpisode[]>([])
const loading = ref(false)
const activeTab = ref('memories')
const statusFilter = ref<'candidate' | 'confirmed' | 'rejected'>('confirmed')

const form = ref({
  scope: 'user' as 'user' | 'project',
  kind: 'note',
  content: '',
  tagsText: '',
  status: 'confirmed' as 'candidate' | 'confirmed' | 'rejected',
})

function fmtTime(value?: string) {
  if (!value) return '—'
  const ts = Date.parse(value)
  return Number.isNaN(ts) ? value : new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

async function loadMemories() {
  loading.value = true
  try {
    const data = await listMemories({ status: statusFilter.value, limit: 200 })
    memories.value = data.memories
  } catch {
    ElMessage.error('加载记忆失败')
  } finally {
    loading.value = false
  }
}

async function loadEpisodes() {
  loading.value = true
  try {
    const data = await listEpisodes({ limit: 100 })
    episodes.value = data.episodes
  } catch {
    ElMessage.error('加载情节记忆失败')
  } finally {
    loading.value = false
  }
}

async function submitMemory() {
  const content = form.value.content.trim()
  if (!content) {
    ElMessage.warning('请输入记忆内容')
    return
  }
  const tags = form.value.tagsText
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
  await createMemory({
    scope: form.value.scope,
    kind: form.value.kind.trim() || 'note',
    content,
    tags,
    status: form.value.status,
  })
  ElMessage.success('记忆已创建')
  form.value.content = ''
  form.value.tagsText = ''
  await loadMemories()
}

async function changeStatus(row: MemoryRecord, status: 'candidate' | 'confirmed' | 'rejected') {
  await updateMemoryStatus(row.id, status)
  ElMessage.success(`已更新为 ${status}`)
  await loadMemories()
}

async function removeMemory(row: MemoryRecord) {
  await ElMessageBox.confirm('确认删除这条记忆？删除后不会再被检索或注入。', '删除记忆', {
    type: 'warning',
  })
  await deleteMemory(row.id)
  ElMessage.success('已删除')
  await loadMemories()
}

onMounted(async () => {
  await loadMemories()
  await loadEpisodes()
})
</script>

<template>
  <div class="memory-page">
    <header class="page-header">
      <div>
        <h1>记忆管理</h1>
        <p>管理 user/project 记忆，查看 query episode 和自动候选记忆。</p>
      </div>
      <el-button :loading="loading" @click="activeTab === 'memories' ? loadMemories() : loadEpisodes()">刷新</el-button>
    </header>

    <el-tabs v-model="activeTab" class="tabs">
      <el-tab-pane label="治理记忆" name="memories">
        <el-card class="create-card" shadow="never">
          <el-form :model="form" label-width="84px">
            <el-row :gutter="12">
              <el-col :span="6">
                <el-form-item label="范围">
                  <el-select v-model="form.scope">
                    <el-option label="User" value="user" />
                    <el-option label="Project" value="project" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="类型">
                  <el-input v-model="form.kind" placeholder="note / preference / procedure_hint" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="状态">
                  <el-select v-model="form.status">
                    <el-option label="confirmed" value="confirmed" />
                    <el-option label="candidate" value="candidate" />
                    <el-option label="rejected" value="rejected" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="标签">
                  <el-input v-model="form.tagsText" placeholder="逗号分隔" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="内容">
              <el-input v-model="form.content" type="textarea" :rows="3" placeholder="输入需要长期保留的偏好、事实或策略" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitMemory">创建记忆</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <div class="toolbar">
          <el-radio-group v-model="statusFilter" @change="loadMemories">
            <el-radio-button label="confirmed">confirmed</el-radio-button>
            <el-radio-button label="candidate">candidate</el-radio-button>
            <el-radio-button label="rejected">rejected</el-radio-button>
          </el-radio-group>
        </div>

        <el-table v-loading="loading" :data="memories" height="calc(100vh - 390px)" border>
          <el-table-column prop="scope" label="范围" width="90" />
          <el-table-column prop="kind" label="类型" width="140" />
          <el-table-column label="内容" min-width="360">
            <template #default="{ row }">
              <div class="content">{{ row.content }}</div>
              <div class="meta">{{ row.source }} · {{ row.tags?.join(', ') || 'no tags' }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column label="更新时间" width="180">
            <template #default="{ row }">{{ fmtTime(row.updated_at || row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="changeStatus(row, 'confirmed')">确认</el-button>
              <el-button size="small" @click="changeStatus(row, 'rejected')">拒绝</el-button>
              <el-button size="small" type="danger" @click="removeMemory(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="情节记忆" name="episodes">
        <el-table v-loading="loading" :data="episodes" height="calc(100vh - 210px)" border>
          <el-table-column prop="outcome" label="结果" width="120" />
          <el-table-column prop="session_id" label="Session" width="160" />
          <el-table-column label="问题" min-width="300">
            <template #default="{ row }">
              <div class="content">{{ row.query_text }}</div>
              <div v-if="row.rewritten_query" class="meta">改写：{{ row.rewritten_query }}</div>
            </template>
          </el-table-column>
          <el-table-column label="工具" width="200">
            <template #default="{ row }">{{ row.tools_used?.join(' → ') || '—' }}</template>
          </el-table-column>
          <el-table-column label="回答预览" min-width="300">
            <template #default="{ row }">{{ row.answer_preview || '—' }}</template>
          </el-table-column>
          <el-table-column label="时间" width="180">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.memory-page {
  height: 100%;
  padding: 24px;
  box-sizing: border-box;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
h1 {
  margin: 0;
  font-size: 28px;
}
p {
  margin: 6px 0 0;
  color: #606266;
}
.tabs {
  flex: 1;
  min-height: 0;
}
.create-card {
  margin-bottom: 12px;
}
.toolbar {
  margin: 8px 0 12px;
}
.content {
  white-space: pre-wrap;
  line-height: 1.45;
}
.meta {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}
</style>
