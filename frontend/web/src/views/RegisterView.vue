<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { register as apiRegister } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  email: '',
  department: '',
})

const usernameError = computed(() => {
  if (!form.username) return ''
  if (form.username.length < 3) return '用户名至少 3 位'
  if (form.username.length > 50) return '用户名最多 50 位'
  if (!/^[A-Za-z0-9_.-]+$/.test(form.username)) return '仅允许字母 / 数字 / . _ -'
  return ''
})
const passwordError = computed(() => {
  if (!form.password) return ''
  if (form.password.length < 8) return '密码至少 8 位'
  return ''
})
const confirmError = computed(() => {
  if (!form.confirmPassword) return ''
  if (form.confirmPassword !== form.password) return '两次输入的密码不一致'
  return ''
})
const emailError = computed(() => {
  if (!form.email) return ''
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) return '请输入有效邮箱'
  return ''
})

const canSubmit = computed(() =>
  form.username && form.password && form.confirmPassword &&
  !usernameError.value && !passwordError.value && !confirmError.value && !emailError.value
)

async function handleRegister() {
  if (!canSubmit.value) {
    error.value = '请检查表单字段'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const resp = await apiRegister({
      username: form.username,
      password: form.password,
      email: form.email || undefined,
      department: form.department || undefined,
    })
    auth.token = resp.access_token
    auth.refreshToken = resp.refresh_token
    auth.username = form.username
    localStorage.setItem('chipwise_token', resp.access_token)
    localStorage.setItem('chipwise_refresh_token', resp.refresh_token)
    localStorage.setItem('chipwise_user', form.username)
    ElMessage.success('注册成功，已自动登录')
    router.push('/query')
  } catch (e: unknown) {
    let msg = '注册失败，请稍后重试'
    if (axios.isAxiosError(e)) {
      if (e.response) {
        const detail = e.response.data?.detail
        if (e.response.status === 409) msg = '用户名已存在'
        else if (e.response.status === 422) msg = typeof detail === 'string' ? detail : '输入格式不合规'
        else if (e.response.status === 503) msg = '后端数据库暂不可用，请稍后重试'
        else if (typeof detail === 'string') msg = detail
      } else if (e.request) {
        msg = `无法连接后端 (${import.meta.env.VITE_API_BASE_URL || ''})`
      }
    }
    error.value = msg
  } finally {
    loading.value = false
  }
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
            加入团队，
            <br/>
            <span class="hero-grad">让 datasheet 开口说话。</span>
          </h1>
          <p class="hero-sub">
            注册后即可使用 Agentic RAG 检索、芯片智能对比、BOM 物料审查、测试用例生成等全部功能。
            数据全程留在企业内网。
          </p>
        </div>

        <ul class="feature-list">
          <li><span class="feat-dot"></span><b>3 秒上手</b>·无需邮箱验证，部门信息可后补</li>
          <li><span class="feat-dot"></span><b>角色隔离</b>·viewer / user / admin 三级权限</li>
          <li><span class="feat-dot"></span><b>对话私有</b>·每个账号的会话历史完全隔离</li>
        </ul>

        <footer class="brand-foot">
          <span>© {{ new Date().getFullYear() }} ChipWise Enterprise</span>
          <span class="dot">·</span>
          <a href="https://github.com/CaiLi6/ChipWise-Enterprise" target="_blank">GitHub</a>
        </footer>
      </div>
    </aside>

    <!-- ────────── RIGHT — Form ────────── -->
    <main class="form-pane">
      <div class="form-card">
        <header class="form-head">
          <h2>创建账号</h2>
          <p>已有账号？<router-link to="/login">直接登录</router-link></p>
        </header>

        <form class="form" @submit.prevent="handleRegister">
          <label class="field">
            <span class="field-label">用户名 <em>*</em></span>
            <input v-model="form.username" type="text" autocomplete="username"
                   placeholder="字母 / 数字 / . _ -，3-50 位" spellcheck="false" />
            <span v-if="usernameError" class="hint err">{{ usernameError }}</span>
          </label>

          <label class="field">
            <span class="field-label">密码 <em>*</em></span>
            <input v-model="form.password" type="password" autocomplete="new-password" placeholder="至少 8 位" />
            <span v-if="passwordError" class="hint err">{{ passwordError }}</span>
          </label>

          <label class="field">
            <span class="field-label">确认密码 <em>*</em></span>
            <input v-model="form.confirmPassword" type="password" autocomplete="new-password" placeholder="再输一次密码" />
            <span v-if="confirmError" class="hint err">{{ confirmError }}</span>
          </label>

          <div class="row">
            <label class="field">
              <span class="field-label">邮箱<span class="opt">（可选）</span></span>
              <input v-model="form.email" type="email" autocomplete="email" placeholder="name@example.com" />
              <span v-if="emailError" class="hint err">{{ emailError }}</span>
            </label>
            <label class="field">
              <span class="field-label">部门<span class="opt">（可选）</span></span>
              <input v-model="form.department" type="text" placeholder="如：硬件部" />
            </label>
          </div>

          <transition name="fade">
            <div v-if="error" class="form-error" role="alert">{{ error }}</div>
          </transition>

          <button type="submit" class="primary-btn" :disabled="loading || !canSubmit">
            <span v-if="!loading">创建账号</span>
            <span v-else class="spinner" aria-hidden="true"></span>
          </button>
        </form>

        <p class="terms">
          点击「创建账号」即表示你同意遵守企业内部数据使用规范。
        </p>
      </div>
    </main>
  </div>
</template>

<style scoped>
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

.brand-pane {
  position: relative; overflow: hidden;
  background: radial-gradient(circle at 0% 0%, #1a1f3a 0%, #0a0d1f 50%, #050610 100%);
  color: #f5f5f7;
  padding: 56px 64px;
  display: flex; flex-direction: column;
}
.brand-mesh { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
.orb { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.55; animation: float 18s ease-in-out infinite; }
.orb-a { width: 480px; height: 480px; left: -120px; top: -100px; background: radial-gradient(circle, #6366f1 0%, transparent 70%); }
.orb-b { width: 380px; height: 380px; right: -80px; top: 35%; background: radial-gradient(circle, #8b5cf6 0%, transparent 70%); animation-delay: -6s; }
.orb-c { width: 420px; height: 420px; left: 30%; bottom: -120px; background: radial-gradient(circle, #06b6d4 0%, transparent 70%); animation-delay: -12s; }
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

.brand-content { position: relative; z-index: 1; display: flex; flex-direction: column; height: 100%; }
.brand-logo { display: flex; align-items: center; gap: 10px; font-size: 17px; font-weight: 600; letter-spacing: -0.01em; color: #fff; }
.brand-thin { color: rgba(255,255,255,0.55); font-weight: 400; }

.hero { margin-top: auto; padding-top: 60px; }
.hero-title { font-size: clamp(32px, 3.6vw, 48px); line-height: 1.08; letter-spacing: -0.025em; font-weight: 600; margin: 0 0 24px; color: #fff; }
.hero-grad {
  background: linear-gradient(135deg, #a5b4fc 0%, #c4b5fd 50%, #67e8f9 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero-sub { font-size: 15px; line-height: 1.65; color: rgba(245, 245, 247, 0.68); max-width: 460px; margin: 0; }

.feature-list { margin: 36px 0 0; padding: 0; list-style: none; display: grid; gap: 14px; }
.feature-list li { display: flex; align-items: flex-start; gap: 12px; font-size: 13.5px; color: rgba(245, 245, 247, 0.78); line-height: 1.55; }
.feature-list b { color: #fff; font-weight: 500; }
.feat-dot { flex: 0 0 6px; height: 6px; margin-top: 8px; border-radius: 50%; background: linear-gradient(135deg, #818cf8, #06b6d4); box-shadow: 0 0 12px rgba(129, 140, 248, 0.6); }

.brand-foot { margin-top: auto; padding-top: 40px; font-size: 12.5px; color: rgba(245, 245, 247, 0.45); display: flex; gap: 8px; align-items: center; }
.brand-foot a { color: inherit; text-decoration: none; transition: color .15s; }
.brand-foot a:hover { color: #fff; }
.brand-foot .dot { opacity: 0.5; }

.form-pane { display: flex; align-items: center; justify-content: center; padding: 48px 32px; background: #fafafa; }
.form-card { width: 100%; max-width: 440px; }

.form-head h2 { font-size: 28px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 8px; color: #0a0a0a; }
.form-head p { margin: 0 0 28px; color: #71717a; font-size: 14px; }
.form-head a { color: #0a0a0a; text-decoration: none; font-weight: 500; border-bottom: 1px solid transparent; transition: border-color .15s; }
.form-head a:hover { border-color: #0a0a0a; }

.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 7px; }
.field-label { font-size: 13px; color: #3f3f46; font-weight: 500; }
.field-label em { color: #ef4444; font-style: normal; margin-left: 2px; }
.opt { color: #a1a1aa; font-weight: 400; margin-left: 4px; }

.row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.field input {
  height: 42px; padding: 0 14px;
  border: 1px solid #e4e4e7; border-radius: 8px;
  font-size: 14px; color: #0a0a0a; background: #fff;
  outline: none; transition: border-color .15s, box-shadow .15s;
  font-family: inherit; width: 100%; box-sizing: border-box;
}
.field input::placeholder { color: #a1a1aa; }
.field input:hover:not(:focus) { border-color: #d4d4d8; }
.field input:focus { border-color: #0a0a0a; box-shadow: 0 0 0 3px rgba(10,10,10,0.06); }

.hint { font-size: 12px; color: #71717a; }
.hint.err { color: #b91c1c; }

.form-error { font-size: 13px; color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 9px 12px; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.primary-btn {
  height: 44px; background: #0a0a0a; color: #fff; border: none; border-radius: 8px;
  font-size: 14px; font-weight: 500; cursor: pointer;
  transition: background .15s, transform .05s; margin-top: 6px;
  display: inline-flex; align-items: center; justify-content: center;
}
.primary-btn:hover:not(:disabled) { background: #27272a; }
.primary-btn:active:not(:disabled) { transform: scale(0.98); }
.primary-btn:disabled { background: #d4d4d8; cursor: not-allowed; color: #fff; }

.spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.35); border-top-color: #fff; border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.terms { margin: 20px 0 0; text-align: center; font-size: 12px; color: #a1a1aa; line-height: 1.6; }
</style>
