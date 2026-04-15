<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQueryStore } from '@/stores/query'
import { useAuthStore } from '@/stores/auth'
import { useLayoutStore } from '@/stores/layout'
import { streamQuery } from '@/api/query'
import { Promotion, Fold, Expand, User } from '@element-plus/icons-vue'
import MessageBubble from '@/components/MessageBubble.vue'

const router = useRouter()
const store = useQueryStore()
const auth = useAuthStore()
const layout = useLayoutStore()
const input = ref('')
const chatContainer = ref<HTMLElement>()

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

// Scroll to bottom whenever the user switches to a different session
watch(() => store.currentSessionId, () => scrollToBottom())

async function handleSend() {
  const text = input.value.trim()
  if (!text || store.isStreaming) return

  store.addMessage({ role: 'user', content: text })
  store.addMessage({ role: 'assistant', content: '' })
  store.isStreaming = true
  input.value = ''
  scrollToBottom()

  try {
    streamQuery(
      { query: text, session_id: store.currentSessionId },
      (chunk) => {
        store.appendToLast(chunk)
        scrollToBottom()
      },
      () => {
        store.isStreaming = false
      },
    )
  } catch (err: unknown) {
    store.isStreaming = false
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 503) {
      store.appendToLast('')
      const msgs = store.messages
      msgs[msgs.length - 1] = {
        ...msgs[msgs.length - 1],
        role: 'assistant',
        content: '⚠️ 后端 LLM 服务暂时不可用（503），请稍后重试',
      }
    } else {
      store.appendToLast('查询失败，请重试')
    }
    scrollToBottom()
  }
}
</script>

<template>
  <div style="display: flex; flex-direction: column; height: 100vh">
    <!-- 顶栏：折叠按钮（左）+ 标题 + 用户信息（右） -->
    <div
      style="height: 56px; display:flex; align-items:center; gap: 8px; padding: 0 16px;
             border-bottom: 1px solid #ebeef5; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
             flex-shrink:0; background: #fff"
    >
      <!-- 折叠按钮：常驻，不随侧边栏隐藏 -->
      <el-button
        text
        size="small"
        style="color: #606266; padding: 4px 6px"
        @click="layout.toggle()"
      >
        <el-icon size="18"><component :is="layout.collapsed ? Expand : Fold" /></el-icon>
      </el-button>

      <!-- 页面标题 -->
      <span style="font-weight:600; font-size:15px; color:#303133">智能查询</span>

      <!-- 右侧用户信息区 -->
      <div style="margin-left: auto; display:flex; align-items:center; gap: 10px">
        <el-avatar :size="28" style="background:#409EFF; font-size:12px; flex-shrink:0">
          {{ (auth.username || 'U')[0].toUpperCase() }}
        </el-avatar>
        <span style="font-size:13px; color:#606266; max-width:100px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">
          {{ auth.username || '用户' }}
        </span>
        <el-button text size="small" style="color:#909399" @click="handleLogout">
          <el-icon><User /></el-icon>
          退出
        </el-button>
      </div>
    </div>

    <!-- 聊天区域 -->
    <div ref="chatContainer" style="flex: 1; overflow-y: auto; padding: 16px">
      <div style="max-width: 860px; margin: 0 auto">
        <!-- 欢迎状态 -->
        <div
          v-if="store.messages.length === 0"
          style="text-align:center; color:#909399; padding-top: 80px"
        >
          <svg
            width="56" height="56" viewBox="0 0 24 24" fill="none"
            style="margin-bottom: 16px; opacity: 0.3"
          >
            <rect x="6" y="6" width="12" height="12" rx="2" stroke="#409EFF" stroke-width="1.5"/>
            <path
              d="M9 2v4M12 2v4M15 2v4M9 18v4M12 18v4M15 18v4M2 9h4M2 12h4M2 15h4M18 9h4M18 12h4M18 15h4"
              stroke="#409EFF" stroke-width="1.5" stroke-linecap="round"
            />
            <rect x="9" y="9" width="6" height="6" rx="1" fill="#409EFF" fill-opacity="0.15"/>
          </svg>
          <h3 style="font-size:18px; color:#606266; margin: 0 0 8px">
            欢迎使用 ChipWise 智能查询
          </h3>
          <p style="font-size:14px; margin: 0 0 24px">
            输入芯片相关问题，AI 将结合数据手册为您解答
          </p>
          <div style="display:flex; gap:8px; justify-content:center; flex-wrap:wrap">
            <span
              v-for="hint in ['STM32F407 最大主频是多少？', 'GD32 和 STM32 的区别？', '推荐一款低功耗 MCU']"
              :key="hint"
              class="hint-tag"
              @click="input = hint"
            >{{ hint }}</span>
          </div>
        </div>

        <MessageBubble
          v-for="(msg, i) in store.messages"
          :key="i"
          :role="msg.role"
          :content="msg.content"
          :citations="msg.citations"
          :loading="store.isStreaming && i === store.messages.length - 1 && msg.role === 'assistant'"
        />
      </div>
    </div>

    <!-- 输入区 -->
    <div style="padding: 12px 16px; border-top: 1px solid #ebeef5; flex-shrink:0">
      <div style="max-width: 860px; margin: 0 auto">
        <el-input
          v-model="input"
          placeholder="输入芯片查询问题..."
          size="large"
          @keydown.enter="handleSend"
        >
          <template #suffix>
            <el-button
              type="primary"
              :loading="store.isStreaming"
              circle
              size="small"
              style="margin-right: 4px"
              @click="handleSend"
            >
              <el-icon v-if="!store.isStreaming"><Promotion /></el-icon>
            </el-button>
          </template>
        </el-input>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 快捷提问气泡：明确的可点击样式 + hover 反馈 */
.hint-tag {
  display: inline-block;
  padding: 6px 14px;
  border-radius: 16px;
  border: 1px solid #dcdfe6;
  background: #f5f7fa;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.1s;
  user-select: none;
}
.hint-tag:hover {
  background: #ecf5ff;
  border-color: #409EFF;
  color: #409EFF;
  transform: translateY(-1px);
}
.hint-tag:active {
  transform: translateY(0);
  background: #d9ecff;
}
</style>
