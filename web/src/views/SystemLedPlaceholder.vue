<template>
  <div class="placeholder-page">
    <el-empty description="LED 配置 — 开发中" />
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
onMounted(() => { document.title = route.meta?.title || 'LED 配置' })
</script>
<style scoped>
.placeholder-page { display: flex; justify-content: center; align-items: center; height: 60vh; }
</style>
