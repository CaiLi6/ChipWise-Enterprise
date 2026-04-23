<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useLayoutStore } from '@/stores/layout'
import { useQueryStore } from '@/stores/query'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const layout = useLayoutStore()
const query = useQueryStore()
const auth = useAuthStore()

const navItems = [
  { path: '/query',       label: '智能查询', icon: 'chat'  },
  { path: '/compare',     label: '芯片对比', icon: 'compare' },
  { path: '/documents',   label: '文档管理', icon: 'doc'   },
  { path: '/traces',      label: 'Trace 查看器', icon: 'trace' },
  { path: '/evaluations', label: 'RAG 评估',  icon: 'eval'  },
] as const

function navigate(path: string) { router.push(path) }
function newChat() {
  query.newSession()
  if (route.path !== '/query') router.push('/query')
}
function pickSession(id: string) {
  query.switchSession(id)
  if (route.path !== '/query') router.push('/query')
}
function delSession(id: string) { query.deleteSession(id) }
function logout() {
  auth.logout()
  router.push('/login')
}
function initial() { return (auth.username || 'U')[0].toUpperCase() }
</script>

<template>
  <div class="app-shell">
    <!-- ============== SIDEBAR ============== -->
    <aside class="side" :class="{ collapsed: layout.collapsed }">
      <!-- top: collapse + brand -->
      <div class="brand-row">
        <button class="icon-btn" :title="layout.collapsed ? '展开' : '收起'" @click="layout.toggle()">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 6h16M4 12h16M4 18h16" stroke-linecap="round"/>
          </svg>
        </button>
        <span v-if="!layout.collapsed" class="brand">
          <span class="brand-dot" />ChipWise
        </span>
      </div>

      <!-- new chat -->
      <button class="new-chat" :class="{ collapsed: layout.collapsed }" @click="newChat">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14" stroke-linecap="round"/>
        </svg>
        <span v-if="!layout.collapsed">新建对话</span>
      </button>

      <!-- recent (collapsed = hide section) -->
      <div v-if="!layout.collapsed" class="section">
        <div class="section-label">最近对话</div>
        <div class="session-list">
          <div
            v-for="s in query.sortedSessions.slice(0, 12)" :key="s.id"
            class="session" :class="{ active: s.id === query.currentSessionId }"
            @click="pickSession(s.id)"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" class="session-icon">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="session-title">{{ s.title || '新对话' }}</span>
            <button class="session-x" title="删除" @click.stop="delSession(s.id)">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2">
                <path d="M6 6l12 12M18 6L6 18" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div v-if="query.sortedSessions.length === 0" class="empty-hint">暂无历史对话</div>
        </div>
      </div>

      <!-- main nav -->
      <nav class="nav" :class="{ collapsed: layout.collapsed }">
        <button
          v-for="n in navItems" :key="n.path"
          class="nav-item" :class="{ active: route.path === n.path }"
          :title="n.label" @click="navigate(n.path)"
        >
          <span class="nav-icon">
            <svg v-if="n.icon === 'chat'"    viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z"/></svg>
            <svg v-if="n.icon === 'compare'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6h7v15H3zM14 3h7v18h-7z"/></svg>
            <svg v-if="n.icon === 'doc'"     viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></svg>
            <svg v-if="n.icon === 'trace'"   viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 12h4l3-9 4 18 3-9h4"/></svg>
            <svg v-if="n.icon === 'eval'"    viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 3v18h18M7 14l4-4 4 4 5-7"/></svg>
          </span>
          <span v-if="!layout.collapsed" class="nav-label">{{ n.label }}</span>
        </button>
      </nav>

      <!-- footer: user -->
      <div class="user-row" :class="{ collapsed: layout.collapsed }" @click="logout">
        <div class="avatar">{{ initial() }}</div>
        <div v-if="!layout.collapsed" class="user-meta">
          <div class="user-name">{{ auth.username || '用户' }}</div>
          <div class="user-action">退出登录</div>
        </div>
      </div>
    </aside>

    <!-- ============== MAIN ============== -->
    <main class="content"><router-view /></main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex; height: 100vh; width: 100vw;
  background: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  color: #1f1f1f;
}

/* ============== SIDE ============== */
.side {
  width: 260px;
  background: #f0f4f9;            /* Gemini signature warm-cool gray */
  border-right: 1px solid transparent;
  display: flex; flex-direction: column;
  transition: width .25s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
  flex-shrink: 0;
}
.side.collapsed { width: 72px; }

.brand-row {
  height: 56px;
  padding: 8px 12px;
  display: flex; align-items: center; gap: 8px;
  flex-shrink: 0;
}
.brand {
  font-size: 15px; font-weight: 500; color: #1f1f1f;
  letter-spacing: -0.01em;
  display: inline-flex; align-items: center; gap: 8px;
  white-space: nowrap;
}
.brand-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: linear-gradient(135deg, #4f8cff 0%, #a16bff 50%, #ff6cab 100%);
  box-shadow: 0 0 12px rgba(122, 132, 255, 0.45);
}
.icon-btn {
  width: 40px; height: 40px;
  border: none; background: transparent;
  border-radius: 50%;
  color: #444746;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: background .15s;
}
.icon-btn:hover { background: rgba(0,0,0,0.06); }

/* new-chat pill */
.new-chat {
  margin: 4px 12px 12px;
  height: 44px; padding: 0 18px;
  border: none; border-radius: 22px;
  background: #c2e7ff;             /* Gemini blue tint */
  color: #001d35; font-size: 14px; font-weight: 500;
  display: inline-flex; align-items: center; gap: 8px;
  cursor: pointer;
  transition: background .15s, box-shadow .15s, transform .05s;
  align-self: flex-start;
}
.new-chat:hover { background: #b1ddff; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.new-chat:active { transform: translateY(1px); }
.new-chat.collapsed {
  width: 44px; padding: 0;
  justify-content: center;
  margin-left: 14px; margin-right: 14px;
}

/* Sections */
.section { padding: 8px 0 0; flex-shrink: 0; }
.section-label {
  padding: 12px 24px 8px;
  font-size: 12px; color: #5e6368; font-weight: 500;
  letter-spacing: 0.02em;
}
.session-list {
  padding: 0 8px;
  max-height: 220px;
  overflow-y: auto;
}

.session {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 14px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 13.5px; color: #1f1f1f;
  transition: background .15s;
  margin-bottom: 1px;
}
.session:hover { background: rgba(60, 64, 67, 0.08); }
.session.active { background: #d3e3fd; color: #001d35; font-weight: 500; }
.session-icon { color: #5e6368; flex-shrink: 0; }
.session.active .session-icon { color: #001d35; }
.session-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-x {
  border: none; background: transparent;
  color: #5e6368; opacity: 0;
  width: 22px; height: 22px;
  border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
  transition: background .15s, color .15s, opacity .15s;
}
.session:hover .session-x { opacity: 1; }
.session-x:hover { background: rgba(217, 48, 37, 0.12); color: #d93025; }
.empty-hint {
  padding: 8px 16px;
  font-size: 12px; color: #80868b; text-align: center;
}

/* nav */
.nav {
  margin-top: 8px;
  padding: 4px 8px 12px;
  flex: 1; min-height: 0;
  overflow-y: auto;
  border-top: 1px solid rgba(0,0,0,0.06);
  padding-top: 12px;
}
.nav.collapsed { padding: 12px 14px; }
.nav-item {
  width: 100%;
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  margin-bottom: 2px;
  border: none; background: transparent;
  border-radius: 999px;
  font-size: 14px; color: #1f1f1f; text-align: left;
  cursor: pointer;
  transition: background .15s, color .15s;
}
.nav.collapsed .nav-item {
  padding: 10px;
  justify-content: center;
  width: 44px; height: 44px;
  margin-left: auto; margin-right: auto;
  border-radius: 50%;
}
.nav-item:hover { background: rgba(60, 64, 67, 0.08); }
.nav-item.active {
  background: #d3e3fd;
  color: #001d35;
  font-weight: 500;
}
.nav-icon { display: inline-flex; color: #444746; flex-shrink: 0; }
.nav-item.active .nav-icon { color: #0b57d0; }
.nav-label { flex: 1; }

/* user footer */
.user-row {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  margin: 0 8px 8px;
  border-radius: 999px;
  cursor: pointer;
  transition: background .15s;
  flex-shrink: 0;
}
.user-row:hover { background: rgba(60, 64, 67, 0.08); }
.user-row.collapsed { justify-content: center; padding: 8px; }
.avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f8cff 0%, #a16bff 100%);
  color: #fff; font-size: 13px; font-weight: 600;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  letter-spacing: 0;
}
.user-meta { flex: 1; min-width: 0; }
.user-name {
  font-size: 13px; color: #1f1f1f; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.user-action { font-size: 11.5px; color: #5e6368; }

/* main content */
.content { flex: 1; min-width: 0; overflow: hidden; background: #ffffff; }

/* scrollbar */
.session-list::-webkit-scrollbar, .nav::-webkit-scrollbar { width: 6px; }
.session-list::-webkit-scrollbar-thumb,
.nav::-webkit-scrollbar-thumb {
  background: rgba(0,0,0,0.10); border-radius: 3px;
}
</style>
