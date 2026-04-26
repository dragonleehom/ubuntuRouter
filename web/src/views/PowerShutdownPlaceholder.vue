<template>
  <div class="placeholder-page">
    <el-empty description="关机" />
    <el-button type="danger" @click="handleShutdown">确认关机</el-button>
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
onMounted(() => { document.title = route.meta?.title || '关机' })
const handleShutdown = () => {
  ElMessageBox.confirm('确定要关机吗？此操作不可撤销！', '警告', { confirmButtonText: '关机', type: 'warning' })
    .then(() => { /* TODO: 调用关机API */ })
    .catch(() => {})
}
</script>
<style scoped>
.placeholder-page { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 60vh; gap: 20px; }
</style>
