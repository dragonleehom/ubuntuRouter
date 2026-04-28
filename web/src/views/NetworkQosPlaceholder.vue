<template>
  <div class="page">
    <div class="page-header">
      <h2>SQM QoS</h2>
      <div class="header-actions">
        <el-button size="small" @click="fetchStatus">刷新</el-button>
        <el-button type="primary" size="small" @click="saveConfig" :loading="saving">保存并应用</el-button>
      </div>
    </div>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>队列管理设置</span>
          <el-switch v-model="enabled" @change="toggleQos" />
        </div>
      </template>
      <el-form label-width="120px" size="small">
        <el-form-item label="队列算法">
          <el-select v-model="algorithm" style="width:200px">
            <el-option label="fq_codel" value="fq_codel" />
            <el-option label="cake" value="cake" />
            <el-option label="htb" value="htb" />
          </el-select>
        </el-form-item>
        <el-form-item label="上行带宽">
          <el-input v-model="uploadSpeed" placeholder="如 100mbit" style="width:200px">
            <template #append>Mbps</template>
          </el-input>
        </el-form-item>
        <el-form-item label="下行带宽">
          <el-input v-model="downloadSpeed" placeholder="如 500mbit" style="width:200px">
            <template #append>Mbps</template>
          </el-input>
        </el-form-item>
        <el-form-item label="接口">
          <el-select v-model="interface" style="width:200px">
            <el-option v-for="iface in interfaces" :key="iface" :label="iface" :value="iface" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-tag :type="enabled ? 'success' : 'info'">{{ enabled ? '运行中' : '已停止' }}</el-tag>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/stores'

const enabled = ref(false)
const algorithm = ref('cake')
const uploadSpeed = ref(100)
const downloadSpeed = ref(500)
const interface = ref('eth0')
const interfaces = ref(['eth0', 'eth1', 'wan'])
const saving = ref(false)

async function fetchStatus() {
  try {
    const res = await api.get('/system/qos/status').catch(() => ({ data: {} }))
    if (res.data) {
      enabled.value = res.data.enabled || false
      algorithm.value = res.data.algorithm || 'cake'
      uploadSpeed.value = res.data.upload_speed || 100
      downloadSpeed.value = res.data.download_speed || 500
      interface.value = res.data.interface || 'eth0'
    }
  } catch { /* ignore */ }
}

async function saveConfig() {
  saving.value = true
  try {
    await api.post('/system/qos/config', {
      enabled: enabled.value,
      algorithm: algorithm.value,
      upload_speed: uploadSpeed.value,
      download_speed: downloadSpeed.value,
      interface: interface.value,
    })
    ElMessage.success('QoS 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
  saving.value = false
}

async function toggleQos(val) {
  try {
    if (val) {
      await api.post('/system/qos/start')
      ElMessage.success('QoS 已启动')
    } else {
      await api.post('/system/qos/stop')
      ElMessage.success('QoS 已停止')
    }
  } catch (e) {
    ElMessage.error('操作失败')
    enabled.value = !val
  }
}

onMounted(fetchStatus)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { color: #e0e0e0; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.section-card { background: #141414; border: 1px solid #222; }
.card-header { display: flex; justify-content: space-between; align-items: center; color: #ccc; }
</style>
