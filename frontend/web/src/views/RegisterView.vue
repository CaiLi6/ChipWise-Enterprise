<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div style="display:flex; justify-content:center; align-items:center; height:100vh; background:#f0f2f5">
    <el-card style="width:400px; text-align:center; box-shadow: 0 8px 32px rgba(0,0,0,0.10); border:none">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" style="margin-bottom:12px">
        <rect x="6" y="6" width="12" height="12" rx="2" stroke="#409EFF" stroke-width="1.5"/>
        <path d="M9 2v4M12 2v4M15 2v4M9 18v4M12 18v4M15 18v4M2 9h4M2 12h4M2 15h4M18 9h4M18 12h4M18 15h4"
              stroke="#409EFF" stroke-width="1.5" stroke-linecap="round"/>
        <rect x="9" y="9" width="6" height="6" rx="1" fill="#409EFF" fill-opacity="0.2"/>
      </svg>
      <h2 style="margin: 0 0 12px; color:#303133">注册账号</h2>
      <p style="color:#909399; margin:0 0 24px; font-size:14px; line-height:1.6">
        账号注册功能正在建设中，<br>请联系管理员开通账号。
      </p>
      <el-button type="primary" size="large" style="width:100%" @click="router.push('/login')">
        返回登录
      </el-button>
    </el-card>
  </div>
</template>
