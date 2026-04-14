<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getSSOLoginURL } from '@/api/auth'

const router = useRouter()
const auth = useAuthStore()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(form.value)
    const redirect = router.currentRoute.value.query.redirect as string
    router.push(redirect || '/query')
  } catch (_e: unknown) {
    if (import.meta.env.DEV) {
      // Mock login in dev mode
      localStorage.setItem('chipwise_token', 'dev-mock-token')
      localStorage.setItem('chipwise_user', form.value.username || 'dev')
      const redirect = router.currentRoute.value.query.redirect as string
      router.push(redirect || '/query')
      return
    }
    error.value = '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}

function handleSSO(provider: string) {
  window.location.href = getSSOLoginURL(provider)
}
</script>

<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5">
    <el-card style="width: 400px">
      <template #header>
        <div style="text-align: center">
          <h2 style="margin: 0">ChipWise Enterprise</h2>
          <p style="color: #909399; margin: 8px 0 0">芯片数据智能检索平台</p>
        </div>
      </template>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" style="margin-bottom: 16px" />
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%" size="large">
            登录
          </el-button>
        </el-form-item>
      </el-form>
      <el-divider>SSO 登录</el-divider>
      <div style="display: flex; gap: 8px; justify-content: center">
        <el-button @click="handleSSO('keycloak')">Keycloak</el-button>
        <el-button @click="handleSSO('dingtalk')">钉钉</el-button>
        <el-button @click="handleSSO('feishu')">飞书</el-button>
      </div>
    </el-card>
  </div>
</template>
