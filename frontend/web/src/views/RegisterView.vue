<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import axios from 'axios'
import { register as apiRegister } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  email: '',
  department: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度应在 3-50 之间', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_.-]+$/, message: '仅允许字母/数字/._-', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, max: 128, message: '密码至少 8 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_r: unknown, v: string, cb: (e?: Error) => void) =>
        v === form.password ? cb() : cb(new Error('两次输入的密码不一致')),
      trigger: 'blur',
    },
  ],
  email: [
    { type: 'email', message: '请输入有效邮箱', trigger: 'blur' },
  ],
}

async function handleRegister() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
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
        else if (e.response.status === 422) {
          msg = typeof detail === 'string' ? detail : '输入格式不合规'
        } else if (e.response.status === 503) msg = '后端数据库暂不可用，请稍后重试'
        else if (typeof detail === 'string') msg = detail
      } else if (e.request) {
        msg = `无法连接后端 (${import.meta.env.VITE_API_BASE_URL || ''})`
      }
    }
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-bg">
    <el-card style="width:440px; border:none; box-shadow: 0 8px 32px rgba(0,0,0,0.10)">
      <template #header>
        <div style="text-align:center; padding: 4px 0">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" style="margin-bottom:8px; display:block; margin-left:auto; margin-right:auto">
            <rect x="6" y="6" width="12" height="12" rx="2" stroke="#409EFF" stroke-width="1.5"/>
            <path d="M9 2v4M12 2v4M15 2v4M9 18v4M12 18v4M15 18v4M2 9h4M2 12h4M2 15h4M18 9h4M18 12h4M18 15h4"
                  stroke="#409EFF" stroke-width="1.5" stroke-linecap="round"/>
            <rect x="9" y="9" width="6" height="6" rx="1" fill="#409EFF" fill-opacity="0.2"/>
          </svg>
          <h2 style="margin:0; font-size:20px; color:#303133">注册 ChipWise 账号</h2>
          <p style="color:#909399; margin:6px 0 0; font-size:13px">创建账号即可使用芯片数据智能检索</p>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleRegister">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="字母/数字/._- 组合，3-50 位" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少 8 位" size="large" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="再输一次密码" size="large" show-password />
        </el-form-item>
        <el-form-item label="邮箱（可选）" prop="email">
          <el-input v-model="form.email" placeholder="name@example.com" size="large" />
        </el-form-item>
        <el-form-item label="部门（可选）" prop="department">
          <el-input v-model="form.department" placeholder="如：硬件部" size="large" />
        </el-form-item>

        <el-form-item style="margin-bottom:0">
          <el-button type="primary" native-type="submit" :loading="loading" style="width:100%" size="large">
            注 册
          </el-button>
        </el-form-item>
      </el-form>

      <div style="text-align:center; margin-top:16px; font-size:13px; color:#909399">
        已有账号？
        <router-link to="/login" style="color:#409EFF; text-decoration:none">返回登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.register-bg {
  min-height: 100vh;
  background-color: #f0f2f5;
  background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23409EFF' stroke-width='0.5' opacity='0.12'%3E%3Crect x='15' y='15' width='30' height='30' rx='4'/%3E%3Cline x1='22' y1='0' x2='22' y2='15'/%3E%3Cline x1='30' y1='0' x2='30' y2='15'/%3E%3Cline x1='38' y1='0' x2='38' y2='15'/%3E%3Cline x1='22' y1='45' x2='22' y2='60'/%3E%3Cline x1='30' y1='45' x2='30' y2='60'/%3E%3Cline x1='38' y1='45' x2='38' y2='60'/%3E%3Cline x1='0' y1='22' x2='15' y2='22'/%3E%3Cline x1='0' y1='30' x2='15' y2='30'/%3E%3Cline x1='0' y1='38' x2='15' y2='38'/%3E%3Cline x1='45' y1='22' x2='60' y2='22'/%3E%3Cline x1='45' y1='30' x2='60' y2='30'/%3E%3Cline x1='45' y1='38' x2='60' y2='38'/%3E%3C/g%3E%3C/svg%3E");
  background-repeat: repeat;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px 0;
}
</style>
