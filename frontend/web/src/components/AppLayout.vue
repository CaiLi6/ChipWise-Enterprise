<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Search, DataAnalysis, Document, User, Fold, Expand } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const collapsed = ref(false)

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
    <el-aside :width="collapsed ? '64px' : '200px'" style="background: #304156; transition: width 0.3s">
      <div style="color: #fff; padding: 20px 0; font-size: 18px; font-weight: bold; text-align: center; white-space: nowrap; overflow: hidden">
        {{ collapsed ? 'CW' : 'ChipWise' }}
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="collapsed"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
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
      </el-menu>
      <div style="position: absolute; bottom: 60px; left: 0; right: 0; text-align: center">
        <el-button text style="color: #bfcbd9" @click="collapsed = !collapsed">
          <el-icon><component :is="collapsed ? Expand : Fold" /></el-icon>
        </el-button>
      </div>
      <div style="position: absolute; bottom: 16px; left: 0; right: 0; text-align: center">
        <el-tooltip :content="auth.username || 'User'" placement="right">
          <el-button type="info" text @click="handleLogout" style="color: #bfcbd9">
            <el-icon><User /></el-icon>
            <span v-if="!collapsed" style="margin-left: 4px">退出</span>
          </el-button>
        </el-tooltip>
      </div>
    </el-aside>
    <el-main style="padding: 0; overflow: hidden">
      <router-view />
    </el-main>
  </el-container>
</template>
