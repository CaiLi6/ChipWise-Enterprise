<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useLayoutStore } from '@/stores/layout'
import { useQueryStore } from '@/stores/query'
import { Search, DataAnalysis, Document, Plus, Close, Histogram, TrendCharts } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const layout = useLayoutStore()
const query = useQueryStore()

function handleSelect(index: string) {
  router.push(index)
}

function handleNewSession() {
  query.newSession()
  if (route.path !== '/query') router.push('/query')
}

function handleSelectSession(id: string) {
  query.switchSession(id)
  if (route.path !== '/query') router.push('/query')
}

function handleDeleteSession(id: string) {
  query.deleteSession(id)
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside
      :width="layout.collapsed ? '64px' : '220px'"
      class="app-aside"
    >
      <!-- Logo -->
      <div class="logo-row">
        <span class="logo-text">
          {{ layout.collapsed ? 'CW' : 'ChipWise' }}
        </span>
      </div>

      <!-- 新建对话按钮 -->
      <div class="new-chat-wrap">
        <el-button
          v-if="!layout.collapsed"
          class="new-chat-btn"
          @click="handleNewSession"
        >
          <el-icon style="margin-right: 6px"><Plus /></el-icon>
          新建对话
        </el-button>
        <el-button
          v-else
          class="new-chat-btn-collapsed"
          circle
          @click="handleNewSession"
        >
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>

      <!-- 主菜单 -->
      <el-menu
        :default-active="route.path"
        :collapse="layout.collapsed"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        class="main-menu"
        @select="handleSelect"
      >
        <el-menu-item index="/query">
          <el-icon><Search /></el-icon>
          <template #title>智能查询</template>
        </el-menu-item>
        <el-menu-item index="/compare">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>芯片对比</template>
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>
          <template #title>文档管理</template>
        </el-menu-item>
        <el-menu-item index="/traces">
          <el-icon><Histogram /></el-icon>
          <template #title>Trace 查看器</template>
        </el-menu-item>
        <el-menu-item index="/evaluations">
          <el-icon><TrendCharts /></el-icon>
          <template #title>RAG 评估</template>
        </el-menu-item>
      </el-menu>

      <!-- 历史对话列表（折叠时隐藏） -->
      <div v-if="!layout.collapsed" class="history-section">
        <div class="history-label">历史对话</div>
        <div class="history-list">
          <div
            v-for="s in query.sortedSessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === query.currentSessionId }"
            @click="handleSelectSession(s.id)"
          >
            <span class="session-title">{{ s.title || '新对话' }}</span>
            <el-icon
              class="session-delete"
              @click.stop="handleDeleteSession(s.id)"
            >
              <Close />
            </el-icon>
          </div>
          <div v-if="query.sortedSessions.length === 0" class="history-empty">
            暂无历史对话
          </div>
        </div>
      </div>
    </el-aside>

    <el-main style="padding: 0; overflow: hidden">
      <router-view />
    </el-main>
  </el-container>
</template>

<style scoped>
.app-aside {
  background: #304156;
  transition: width 0.3s;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  position: relative;
  z-index: 10;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Logo */
.logo-row {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  height: 56px;
  border-bottom: 1px solid #3a4f66;
  overflow: hidden;
  padding: 0 12px;
  flex-shrink: 0;
}
.logo-text {
  font-size: 17px;
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 新建对话按钮 */
.new-chat-wrap {
  padding: 12px;
  flex-shrink: 0;
}
.new-chat-btn {
  width: 100%;
  background: rgba(64, 158, 255, 0.12);
  border: 1px solid rgba(64, 158, 255, 0.4);
  color: #fff;
  transition: background 0.15s, border-color 0.15s;
}
.new-chat-btn:hover {
  background: rgba(64, 158, 255, 0.25);
  border-color: #409eff;
  color: #fff;
}
.new-chat-btn-collapsed {
  background: rgba(64, 158, 255, 0.12);
  border: 1px solid rgba(64, 158, 255, 0.4);
  color: #fff;
}
.new-chat-btn-collapsed:hover {
  background: rgba(64, 158, 255, 0.25);
  border-color: #409eff;
  color: #fff;
}

.main-menu {
  border-right: none;
  flex-shrink: 0;
}

/* 历史对话区域 */
.history-section {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  border-top: 1px solid #3a4f66;
  padding-top: 8px;
}
.history-label {
  padding: 6px 16px 8px;
  color: #8492a6;
  font-size: 12px;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}
.history-empty {
  color: #667990;
  font-size: 12px;
  text-align: center;
  padding: 20px 8px;
}

/* 会话条目 */
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  margin: 2px 0;
  border-radius: 6px;
  color: #bfcbd9;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.session-item:hover {
  background: rgba(255, 255, 255, 0.08);
}
.session-item.active {
  background: rgba(64, 158, 255, 0.2);
  color: #fff;
}
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-delete {
  opacity: 0;
  font-size: 14px;
  color: #8492a6;
  flex-shrink: 0;
  margin-left: 6px;
  transition: opacity 0.15s, color 0.15s;
}
.session-item:hover .session-delete {
  opacity: 1;
}
.session-delete:hover {
  color: #f56c6c;
}

/* 历史列表滚动条 */
.history-list::-webkit-scrollbar {
  width: 6px;
}
.history-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
.history-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>

<style>
/* 侧边栏选中项：左侧蓝色竖线 + 半透明背景 */
.el-menu-item.is-active {
  background-color: rgba(64, 158, 255, 0.15) !important;
  border-radius: 6px;
  position: relative;
}
.el-menu-item.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  background: #409eff;
  border-radius: 0 3px 3px 0;
}
.el-menu-item:hover {
  background-color: rgba(255, 255, 255, 0.08) !important;
  border-radius: 6px;
}
</style>
