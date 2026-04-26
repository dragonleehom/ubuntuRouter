<template>
  <div class="placeholder-page">
    <el-empty description="SSH 密钥管理 — 开发中" />
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
onMounted(() => { document.title = route.meta?.title || 'SSH 密钥' })
</script>
<style scoped>
.placeholder-page { display: flex; justify-content: center; align-items: center; height: 60vh; }
</style>
