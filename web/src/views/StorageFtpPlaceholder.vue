<template>
  <div class="page">
    <div class="page-header">
      <h2>FTP 服务</h2>
      <div class="header-actions">
        <el-button size="small" @click="fetchStatus">刷新</el-button>
        <el-button v-if="!enabled" type="success" size="small" @click="enableFtp">启用</el-button>
        <el-button v-else type="danger" size="small" @click="disableFtp">禁用</el-button>
      </div>
    </div>
    <el-card shadow="never" class="section-card">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="状态">
          <el-tag :type="enabled ? 'success' : 'info'">{{ enabled ? '运行中' : '已停止' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="端口">{{ port }}</el-descriptions-item>
        <el-descriptions-item label="模式">{{ mode }}</el-descriptions-item>
        <el-descriptions-item label="本地用户">{{ localEnable }}</el-descriptions-item>
        <el-descriptions-item label="匿名访问">{{ anonymousEnable }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/stores'
const enabled = ref(false); const port = ref(21); const mode = ref('')
const localEnable = ref('YES'); const anonymousEnable = ref('NO')
async function fetchStatus() {
  try {
    const res = await api.get('/system/ftp/status')
    enabled.value = res.data.enabled; port.value = res.data.port
    mode.value = res.data.mode; localEnable.value = res.data.local_enable
    anonymousEnable.value = res.data.anonymous_enable
  } catch { /* ignore */ }
}
async function enableFtp() { try { await api.post('/system/ftp/enable'); ElMessage.success('FTP 已启用'); await fetchStatus() } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') } }
async function disableFtp() { try { await api.post('/system/ftp/disable'); ElMessage.success('FTP 已禁用'); await fetchStatus() } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') } }
onMounted(fetchStatus)
</script>
<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { color: #e0e0e0; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.section-card { background: #141414; border: 1px solid #222; }
</style>
