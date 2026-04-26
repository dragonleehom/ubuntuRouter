<template>
  <div class="module-layout">
    <div class="module-header">
      <h2 class="module-title">{{ moduleTitle }}</h2>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item v-if="parentTitle">{{ parentTitle }}</el-breadcrumb-item>
        <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>
    <div class="module-content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const moduleTitle = computed(() => {
  return route.meta?.title || ''
})

const parentTitle = computed(() => {
  // 如果有两级 meta，取父级标题
  const matched = route.matched
  if (matched.length >= 3) {
    return matched[matched.length - 2]?.meta?.title || ''
  }
  return ''
})

const currentTitle = computed(() => {
  return route.meta?.title || ''
})
</script>

<style scoped>
.module-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.module-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid #222;
  margin-bottom: 20px;
}
.module-title {
  font-size: 20px;
  font-weight: 600;
  color: #e0e0e0;
  margin: 0;
}
.module-content {
  flex: 1;
}
</style>
