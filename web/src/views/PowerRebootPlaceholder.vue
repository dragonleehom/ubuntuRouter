<template>
  <div class="placeholder-page">
    <el-empty description="重启系统" />
    <el-button type="danger" @click="handleReboot">确认重启</el-button>
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
onMounted(() => { document.title = route.meta?.title || '重启' })
const handleReboot = () => {
  ElMessageBox.confirm('确定要重启系统吗？', '警告', { confirmButtonText: '重启', type: 'warning' })
    .then(() => { /* TODO: 调用重启API */ })
    .catch(() => {})
}
</script>
<style scoped>
.placeholder-page { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 60vh; gap: 20px; }
</style>
