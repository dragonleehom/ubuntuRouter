<template>
  <div class="page">
    <div class="page-header">
      <h2>系统指示灯</h2>
      <div class="header-actions">
        <el-button size="small" @click="fetchLeds">刷新</el-button>
      </div>
    </div>
    <el-card shadow="never" class="section-card">
      <el-table :data="leds" stripe size="small" v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '亮' : '灭' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="亮度" width="100" class="hide-mobile">
          <template #default="{ row }">{{ row.brightness }} / {{ row.max_brightness }}</template>
        </el-table-column>
        <el-table-column label="触发模式" min-width="200" class="hide-mobile">
          <template #default="{ row }">
            <el-tag size="small">{{ row.trigger || 'none' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" text type="success" @click="ledOn(row.name)">点亮</el-button>
            <el-button size="small" text type="danger" @click="ledOff(row.name)">熄灭</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && leds.length === 0" description="无可用 LED" />
    </el-card>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/stores'
const loading = ref(false); const leds = ref([])
async function fetchLeds() {
  loading.value = true
  try { const res = await api.get('/system/led'); leds.value = res.data.leds || [] }
  catch { /* ignore */ }
  loading.value = false
}
async function ledOn(name) { try { await api.post(`/system/led/${name}/on`); ElMessage.success(`${name} 已点亮`); await fetchLeds() } catch { ElMessage.error('操作失败') } }
async function ledOff(name) { try { await api.post(`/system/led/${name}/off`); ElMessage.success(`${name} 已熄灭`); await fetchLeds() } catch { ElMessage.error('操作失败') } }
onMounted(fetchLeds)
</script>
<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { color: #e0e0e0; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.section-card { background: #141414; border: 1px solid #222; }
</style>
