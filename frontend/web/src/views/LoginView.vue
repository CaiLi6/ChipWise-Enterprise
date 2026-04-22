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

const ssoEnabled = import.meta.env.VITE_SSO_ENABLED !== 'false'

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    error.value = '请输入用户名和密码'
    ElMessage.warning('请输入用户名和密码')
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
        msg = `无法连接后端 (${import.meta.env.VITE_API_BASE_URL || ''})，请确认服务是否启动`
      }
    }
    error.value = msg
    ElMessage.error(msg)
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
  <div class="login-bg">
    <el-card style="width: 420px; border: none; box-shadow: 0 8px 32px rgba(0,0,0,0.10)">
      <template #header>
        <div style="text-align: center; padding: 4px 0">
          <!-- 小芯片图标 -->
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" style="margin-bottom: 8px; display:block; margin-left:auto; margin-right:auto">
            <rect x="6" y="6" width="12" height="12" rx="2" stroke="#409EFF" stroke-width="1.5"/>
            <path d="M9 2v4M12 2v4M15 2v4M9 18v4M12 18v4M15 18v4M2 9h4M2 12h4M2 15h4M18 9h4M18 12h4M18 15h4"
                  stroke="#409EFF" stroke-width="1.5" stroke-linecap="round"/>
            <rect x="9" y="9" width="6" height="6" rx="1" fill="#409EFF" fill-opacity="0.2"/>
          </svg>
          <h2 style="margin: 0; font-size: 20px; color: #303133">ChipWise Enterprise</h2>
          <p style="color: #909399; margin: 6px 0 0; font-size: 13px">芯片数据智能检索平台</p>
        </div>
      </template>

      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="请输入用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="请输入密码" prefix-icon="Lock" size="large" show-password />
        </el-form-item>

        <!-- 记住密码 + 忘记密码 -->
        <div style="display:flex; justify-content:space-between; align-items:center; margin: -4px 0 16px">
          <el-checkbox v-model="rememberMe" style="color:#606266; font-size:13px">记住密码</el-checkbox>
          <a href="#" style="font-size:13px; color:#409EFF; text-decoration:none" @click.prevent>忘记密码？</a>
        </div>

        <el-alert v-if="error" :title="error" type="error" :closable="false" style="margin-bottom: 16px" />

        <el-form-item style="margin-bottom: 0">
          <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%" size="large">
            登录
          </el-button>
        </el-form-item>

        <!-- 钉钉扫码授权登录 -->
        <el-button
          v-if="ssoEnabled"
          class="dingtalk-btn"
          size="large"
          @click="handleSSO('dingtalk')"
        >
          <svg width="16" height="16" viewBox="0 0 32 32" fill="none" style="margin-right:6px; flex-shrink:0">
            <rect width="32" height="32" rx="8" fill="#0091FF"/>
            <path d="M22.4 10.6c-.3-.7-1.1-.9-1.7-.5l-5.4 3.2-2.7-4.2c-.3-.5-1-.6-1.5-.3-.5.3-.6 1-.3 1.5l2.7 4.2-6.1 3.6c-.6.4-.7 1.1-.4 1.7.4.6 1.1.7 1.7.4l6.1-3.6 1.6 2.5-4.3 2.5c-.6.4-.7 1.1-.4 1.7.4.6 1.1.7 1.7.4l4.3-2.5.8 1.3c.4.6 1.1.7 1.7.4.6-.4.7-1.1.4-1.7l-.8-1.3 1.9-1.1c.6-.4.7-1.1.4-1.7-.4-.6-1.1-.7-1.7-.4l-1.9 1.1-1.6-2.5 5.4-3.2c.6-.4.8-1.2.5-1.8z" fill="white"/>
          </svg>
          钉钉扫码 / 授权登录
        </el-button>
      </el-form>

      <el-divider v-if="ssoEnabled" style="margin: 20px 0 16px">其他登录方式</el-divider>

      <!-- Keycloak + Feishu 胶囊按钮 -->
      <div v-if="ssoEnabled" style="display: flex; gap: 10px; justify-content: center">
        <button class="sso-pill sso-keycloak" @click="handleSSO('keycloak')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="margin-right:5px">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.8"/>
            <path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          Keycloak
        </button>
        <button class="sso-pill sso-feishu" @click="handleSSO('feishu')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="margin-right:5px">
            <path d="M12 3C8 3 5 7 5 11c0 3 1.5 5.5 4 7l3 2 3-2c2.5-1.5 4-4 4-7 0-4-3-8-7-8z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M9 13l3-3 3 3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          飞书
        </button>
      </div>

      <!-- 注册引导 -->
      <div style="text-align:center; margin-top: 20px; font-size: 13px; color: #909399">
        还没有账号？
        <router-link to="/register" style="color: #409EFF; text-decoration: none">立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.login-bg {
  min-height: 100vh;
  background-color: #f0f2f5;
  background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23409EFF' stroke-width='0.5' opacity='0.12'%3E%3Crect x='15' y='15' width='30' height='30' rx='4'/%3E%3Cline x1='22' y1='0' x2='22' y2='15'/%3E%3Cline x1='30' y1='0' x2='30' y2='15'/%3E%3Cline x1='38' y1='0' x2='38' y2='15'/%3E%3Cline x1='22' y1='45' x2='22' y2='60'/%3E%3Cline x1='30' y1='45' x2='30' y2='60'/%3E%3Cline x1='38' y1='45' x2='38' y2='60'/%3E%3Cline x1='0' y1='22' x2='15' y2='22'/%3E%3Cline x1='0' y1='30' x2='15' y2='30'/%3E%3Cline x1='0' y1='38' x2='15' y2='38'/%3E%3Cline x1='45' y1='22' x2='60' y2='22'/%3E%3Cline x1='45' y1='30' x2='60' y2='30'/%3E%3Cline x1='45' y1='38' x2='60' y2='38'/%3E%3C/g%3E%3C/svg%3E");
  background-repeat: repeat;
  display: flex;
  justify-content: center;
  align-items: center;
}

.dingtalk-btn {
  width: 100%;
  margin-top: 10px;
  background: #0091FF;
  border-color: #0091FF;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: background 0.2s, border-color 0.2s;
}
.dingtalk-btn:hover {
  background: #007ADB;
  border-color: #007ADB;
  color: #fff;
}
.dingtalk-btn:active {
  background: #0068BA;
  border-color: #0068BA;
  color: #fff;
}

.sso-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 18px;
  border-radius: 20px;
  border: 1px solid #dcdfe6;
  background: #fff;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
  line-height: 1.4;
}
.sso-pill:hover {
  background: #f5f7fa;
}

.sso-keycloak:hover {
  border-color: #0099D3;
  color: #0099D3;
}
.sso-feishu:hover {
  border-color: #0071E3;
  color: #0071E3;
}
</style>
