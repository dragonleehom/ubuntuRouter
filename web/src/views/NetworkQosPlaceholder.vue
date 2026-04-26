<template>
  <div class="placeholder-page">
    <el-empty description="SQM QoS — 开发中" />
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
onMounted(() => { document.title = route.meta?.title || 'SQM QoS' })
</script>
<style scoped>
.placeholder-page { display: flex; justify-content: center; align-items: center; height: 60vh; }
</style>
