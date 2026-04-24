<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { getSSOLoginURL } from '@/api/auth'

const router = useRouter()
const auth = useAuthStore()
const form = ref({ username: '', password: '' })
const rememberMe = ref(false)
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)

const ssoEnabled = import.meta.env.VITE_SSO_ENABLED !== 'false'

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(form.value)
    ElMessage.success('登录成功')
    const redirect = router.currentRoute.value.query.redirect as string
    router.push(redirect || '/query')
  } catch (e: unknown) {
    if (import.meta.env.DEV && !(axios.isAxiosError(e) && e.response)) {
      const mockUser = form.value.username || 'dev'
      auth.token = 'dev-mock-token'
      auth.username = mockUser
      localStorage.setItem('chipwise_token', 'dev-mock-token')
      localStorage.setItem('chipwise_user', mockUser)
      const redirect = router.currentRoute.value.query.redirect as string
      router.push(redirect || '/query')
      return
    }
    let msg = '登录失败，请检查用户名和密码'
    if (axios.isAxiosError(e)) {
      if (e.response) {
        const detail = e.response.data?.detail
        if (e.response.status === 401) msg = '用户名或密码错误'
        else if (e.response.status === 503) msg = '后端数据库暂不可用，请稍后重试'
        else if (typeof detail === 'string') msg = detail
      } else if (e.request) {
        msg = `无法连接后端 (${import.meta.env.VITE_API_BASE_URL || ''})，请确认服务已启动`
      }
    }
    error.value = msg
  } finally {
    loading.value = false
  }
}

function handleSSO(provider: string) {
  if (!ssoEnabled) {
    ElMessage.info('本地部署未配置 SSO，请使用账号密码登录')
    return
  }
  window.location.href = getSSOLoginURL(provider)
}
</script>

<template>
  <div class="auth-shell">
    <!-- ────────── LEFT — Brand / hero ────────── -->
    <aside class="brand-pane">
      <div class="brand-mesh" aria-hidden="true">
        <div class="orb orb-a"></div>
        <div class="orb orb-b"></div>
        <div class="orb orb-c"></div>
        <div class="grid-overlay"></div>
      </div>

      <div class="brand-content">
        <div class="brand-logo">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <rect x="6" y="6" width="12" height="12" rx="2.5" stroke="currentColor" stroke-width="1.6"/>
            <path d="M9 2v4M12 2v4M15 2v4M9 18v4M12 18v4M15 18v4M2 9h4M2 12h4M2 15h4M18 9h4M18 12h4M18 15h4"
                  stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            <rect x="9.5" y="9.5" width="5" height="5" rx="1" fill="currentColor" fill-opacity="0.32"/>
          </svg>
          <span>ChipWise<span class="brand-thin"> Enterprise</span></span>
        </div>

        <div class="hero">
          <h1 class="hero-title">
            把 datasheet
            <br/>
            <span class="hero-grad">变成可对话的知识。</span>
          </h1>
          <p class="hero-sub">
            为半导体硬件团队打造的本地化 Agentic RAG + Graph RAG 平台。
            参数检索、芯片对比、BOM 审查、测试用例生成 —— 一切运行在你自己的机器上。
          </p>
        </div>

        <ul class="feature-list">
          <li><span class="feat-dot"></span><b>100% 本地推理</b>·零数据外泄，符合芯片厂保密要求</li>
          <li><span class="feat-dot"></span><b>Graph + Vector 混合检索</b>·Kùzu 知识图谱 + Milvus BGE-M3</li>
          <li><span class="feat-dot"></span><b>10 类 ReAct 工具</b>·自然语言驱动选型、对比、报告导出</li>
        </ul>

        <footer class="brand-foot">
          <span>© {{ new Date().getFullYear() }} ChipWise Enterprise</span>
          <span class="dot">·</span>
          <a href="https://github.com/CaiLi6/ChipWise-Enterprise" target="_blank">GitHub</a>
          <span class="dot">·</span>
          <span>v1.0</span>
        </footer>
      </div>
    </aside>

    <!-- ────────── RIGHT — Form ────────── -->
    <main class="form-pane">
      <div class="form-card">
        <header class="form-head">
          <h2>欢迎回来</h2>
          <p>使用账号或单点登录继续。</p>
        </header>

        <form class="form" @submit.prevent="handleLogin">
          <label class="field">
            <span class="field-label">用户名</span>
            <input
              v-model="form.username"
              type="text"
              autocomplete="username"
              placeholder="your.name"
              spellcheck="false"
            />
          </label>

          <label class="field">
            <div class="field-row">
              <span class="field-label">密码</span>
              <a href="#" class="forget-link" @click.prevent>忘记密码？</a>
            </div>
            <div class="pwd-wrap">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                placeholder="••••••••"
              />
              <button
                type="button"
                class="pwd-toggle"
                tabindex="-1"
                :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
                <svg v-if="!showPassword" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M3 3l18 18M10.6 10.6a3 3 0 104.2 4.2"/><path d="M9.3 5.5C10.2 5.2 11.1 5 12 5c6.5 0 10 7 10 7a17 17 0 01-3.4 4.3M6.4 6.4A17 17 0 002 12s3.5 7 10 7c1.5 0 2.9-.4 4.2-1"/>
                </svg>
              </button>
            </div>
          </label>

          <div class="row-between">
            <label class="remember">
              <input v-model="rememberMe" type="checkbox" />
              <span>保持登录</span>
            </label>
          </div>

          <transition name="fade">
            <div v-if="error" class="form-error" role="alert">{{ error }}</div>
          </transition>

          <button type="submit" class="primary-btn" :disabled="loading">
            <span v-if="!loading">登录</span>
            <span v-else class="spinner" aria-hidden="true"></span>
          </button>
        </form>

        <div v-if="ssoEnabled" class="divider"><span>或使用单点登录</span></div>

        <div v-if="ssoEnabled" class="sso-row">
          <button class="sso-btn sso-dt" type="button" @click="handleSSO('dingtalk')">
            <svg viewBox="0 0 32 32" width="18" height="18">
              <rect width="32" height="32" rx="8" fill="#0091FF"/>
              <path d="M22.4 10.6c-.3-.7-1.1-.9-1.7-.5l-5.4 3.2-2.7-4.2c-.3-.5-1-.6-1.5-.3-.5.3-.6 1-.3 1.5l2.7 4.2-6.1 3.6c-.6.4-.7 1.1-.4 1.7.4.6 1.1.7 1.7.4l6.1-3.6 1.6 2.5-4.3 2.5c-.6.4-.7 1.1-.4 1.7.4.6 1.1.7 1.7.4l4.3-2.5.8 1.3c.4.6 1.1.7 1.7.4.6-.4.7-1.1.4-1.7l-.8-1.3 1.9-1.1c.6-.4.7-1.1.4-1.7-.4-.6-1.1-.7-1.7-.4l-1.9 1.1-1.6-2.5 5.4-3.2c.6-.4.8-1.2.5-1.8z" fill="#fff"/>
            </svg>
            <span>钉钉</span>
          </button>
          <button class="sso-btn" type="button" @click="handleSSO('feishu')">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M12 3C8 3 5 7 5 11c0 3 1.5 5.5 4 7l3 2 3-2c2.5-1.5 4-4 4-7 0-4-3-8-7-8z"/>
              <path d="M9 13l3-3 3 3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>飞书</span>
          </button>
          <button class="sso-btn" type="button" @click="handleSSO('keycloak')">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="12" cy="12" r="9"/>
              <path d="M12 7v5l3 3" stroke-linecap="round"/>
            </svg>
            <span>Keycloak</span>
          </button>
        </div>

        <p class="sign-up-hint">
          还没有账号？
          <router-link to="/register">创建一个</router-link>
        </p>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ───────────────────────────── shell ───────────────────────────── */
.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: #fafafa;
  color: #0a0a0a;
  font-family: ui-sans-serif, -apple-system, "SF Pro Text", "PingFang SC",
    "Helvetica Neue", Arial, sans-serif;
}

@media (max-width: 980px) {
  .auth-shell { grid-template-columns: 1fr; }
  .brand-pane { display: none; }
}

/* ───────────────────────────── brand pane ───────────────────────────── */
.brand-pane {
  position: relative;
  overflow: hidden;
  background: radial-gradient(circle at 0% 0%, #1a1f3a 0%, #0a0d1f 50%, #050610 100%);
  color: #f5f5f7;
  padding: 56px 64px;
  display: flex;
  flex-direction: column;
}

.brand-mesh {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  animation: float 18s ease-in-out infinite;
}
.orb-a {
  width: 480px; height: 480px; left: -120px; top: -100px;
  background: radial-gradient(circle, #6366f1 0%, transparent 70%);
}
.orb-b {
  width: 380px; height: 380px; right: -80px; top: 35%;
  background: radial-gradient(circle, #8b5cf6 0%, transparent 70%);
  animation-delay: -6s;
}
.orb-c {
  width: 420px; height: 420px; left: 30%; bottom: -120px;
  background: radial-gradient(circle, #06b6d4 0%, transparent 70%);
  animation-delay: -12s;
}
.grid-overlay {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse at 30% 40%, #000 30%, transparent 80%);
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, -30px) scale(1.05); }
  66% { transform: translate(-30px, 40px) scale(0.95); }
}

.brand-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.brand-logo {
  display: flex; align-items: center; gap: 10px;
  font-size: 17px; font-weight: 600;
  letter-spacing: -0.01em;
  color: #fff;
}
.brand-thin { color: rgba(255,255,255,0.55); font-weight: 400; }

.hero { margin-top: auto; padding-top: 80px; }
.hero-title {
  font-size: clamp(34px, 4vw, 52px);
  line-height: 1.08;
  letter-spacing: -0.025em;
  font-weight: 600;
  margin: 0 0 24px;
  color: #fff;
}
.hero-grad {
  background: linear-gradient(135deg, #a5b4fc 0%, #c4b5fd 50%, #67e8f9 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-sub {
  font-size: 15px;
  line-height: 1.65;
  color: rgba(245, 245, 247, 0.68);
  max-width: 460px;
  margin: 0;
}

.feature-list {
  margin: 40px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 14px;
}
.feature-list li {
  display: flex; align-items: flex-start; gap: 12px;
  font-size: 13.5px; color: rgba(245, 245, 247, 0.78);
  line-height: 1.55;
}
.feature-list b { color: #fff; font-weight: 500; }
.feat-dot {
  flex: 0 0 6px; height: 6px; margin-top: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #818cf8, #06b6d4);
  box-shadow: 0 0 12px rgba(129, 140, 248, 0.6);
}

.brand-foot {
  margin-top: auto;
  padding-top: 48px;
  font-size: 12.5px;
  color: rgba(245, 245, 247, 0.45);
  display: flex; gap: 8px; align-items: center;
}
.brand-foot a { color: inherit; text-decoration: none; transition: color .15s; }
.brand-foot a:hover { color: #fff; }
.brand-foot .dot { opacity: 0.5; }

/* ───────────────────────────── form pane ───────────────────────────── */
.form-pane {
  display: flex; align-items: center; justify-content: center;
  padding: 48px 32px;
  background: #fafafa;
}

.form-card {
  width: 100%;
  max-width: 380px;
}

.form-head h2 {
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0 0 8px;
  color: #0a0a0a;
}
.form-head p {
  margin: 0 0 32px;
  color: #71717a;
  font-size: 14px;
}

.form { display: flex; flex-direction: column; gap: 18px; }

.field { display: flex; flex-direction: column; gap: 7px; }
.field-row {
  display: flex; justify-content: space-between; align-items: baseline;
}
.field-label {
  font-size: 13px;
  color: #3f3f46;
  font-weight: 500;
}
.forget-link {
  font-size: 12.5px; color: #71717a;
  text-decoration: none;
  transition: color .15s;
}
.forget-link:hover { color: #0a0a0a; }

.field input {
  height: 42px;
  padding: 0 14px;
  border: 1px solid #e4e4e7;
  border-radius: 8px;
  font-size: 14px;
  color: #0a0a0a;
  background: #fff;
  outline: none;
  transition: border-color .15s, box-shadow .15s;
  font-family: inherit;
  width: 100%;
  box-sizing: border-box;
}
.field input::placeholder { color: #a1a1aa; }
.field input:hover:not(:focus) { border-color: #d4d4d8; }
.field input:focus {
  border-color: #0a0a0a;
  box-shadow: 0 0 0 3px rgba(10, 10, 10, 0.06);
}

.pwd-wrap { position: relative; }
.pwd-toggle {
  position: absolute; right: 10px; top: 50%;
  transform: translateY(-50%);
  background: none; border: none; cursor: pointer;
  color: #71717a;
  padding: 4px; line-height: 0;
  transition: color .15s;
}
.pwd-toggle:hover { color: #0a0a0a; }

.row-between {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: -4px;
}
.remember {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: #52525b; cursor: pointer;
  user-select: none;
}
.remember input {
  width: 15px; height: 15px;
  accent-color: #0a0a0a;
  cursor: pointer;
}

.form-error {
  font-size: 13px;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 9px 12px;
}
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.primary-btn {
  height: 44px;
  background: #0a0a0a;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background .15s, transform .05s;
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.primary-btn:hover { background: #27272a; }
.primary-btn:active { transform: scale(0.98); }
.primary-btn:disabled { background: #71717a; cursor: not-allowed; }

.spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.divider {
  display: flex; align-items: center; gap: 14px;
  margin: 28px 0 18px;
  color: #a1a1aa;
  font-size: 12px;
}
.divider::before, .divider::after {
  content: ""; flex: 1;
  height: 1px; background: #e4e4e7;
}

.sso-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.sso-btn {
  height: 42px;
  display: inline-flex;
  align-items: center; justify-content: center;
  gap: 7px;
  background: #fff;
  border: 1px solid #e4e4e7;
  border-radius: 8px;
  font-size: 13px; color: #3f3f46;
  cursor: pointer;
  transition: border-color .15s, color .15s, background .15s;
  font-family: inherit;
}
.sso-btn:hover {
  border-color: #0a0a0a;
  color: #0a0a0a;
  background: #fff;
}
.sso-dt:hover { border-color: #0091FF; color: #0091FF; }

.sign-up-hint {
  margin: 28px 0 0;
  text-align: center;
  font-size: 13px;
  color: #71717a;
}
.sign-up-hint a {
  color: #0a0a0a;
  text-decoration: none;
  font-weight: 500;
  border-bottom: 1px solid transparent;
  transition: border-color .15s;
}
.sign-up-hint a:hover { border-color: #0a0a0a; }
</style>
