<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Search, DataAnalysis, Document, User } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

function handleSelect(index: string) {
  router.push(index)
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside v-if="route.path !== '/login'" width="200px" style="background: #304156">
      <div style="color: #fff; padding: 20px; font-size: 18px; font-weight: bold; text-align: center">
        ChipWise
      </div>
      <el-menu
        :default-active="route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        @select="handleSelect"
      >
        <el-menu-item index="/query">
          <el-icon><Search /></el-icon>
          <span>智能查询</span>
        </el-menu-item>
        <el-menu-item index="/compare">
          <el-icon><DataAnalysis /></el-icon>
          <span>芯片对比</span>
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>
          <span>文档管理</span>
        </el-menu-item>
      </el-menu>
      <div style="position: absolute; bottom: 20px; left: 0; right: 0; text-align: center">
        <el-button type="info" text @click="handleLogout">
          <el-icon><User /></el-icon>
          退出登录
        </el-button>
      </div>
    </el-aside>
    <el-main style="padding: 0">
      <router-view />
    </el-main>
  </el-container>
</template>

<style>
body { margin: 0; }
#app { font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', Arial, sans-serif; }
</style>
