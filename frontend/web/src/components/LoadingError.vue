<script setup lang="ts">
defineProps<{
  loading?: boolean
  error?: string | null
  empty?: boolean
  emptyText?: string
}>()
</script>

<template>
  <div v-if="loading" class="state-wrapper">
    <el-skeleton :rows="4" animated />
  </div>
  <div v-else-if="error" class="state-wrapper">
    <el-result icon="error" :title="error">
      <template #extra>
        <el-button type="primary" @click="$emit('retry')">重试</el-button>
      </template>
    </el-result>
  </div>
  <div v-else-if="empty" class="state-wrapper">
    <el-empty :description="emptyText || '暂无数据'" />
  </div>
  <slot v-else />
</template>

<style scoped>
.state-wrapper {
  padding: 40px 0;
  text-align: center;
}
</style>
