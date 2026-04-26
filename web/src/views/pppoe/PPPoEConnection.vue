<template>
  <div class="pppoe-page">
    <h2>PPPoE 拨号</h2>

    <!-- 状态卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">连接状态</div>
            <div class="stat-value">
              <el-tag :type="status.connected ? 'success' : 'danger'" size="large">
                {{ status.connected ? '已连接' : '未连接' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">IP 地址</div>
            <div class="stat-value small">{{ status.ip_address || '-' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">接收流量</div>
            <div class="stat-value small">{{ formatBytes(status.traffic?.rx_bytes || 0) }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">发送流量</div>
            <div class="stat-value small">{{ formatBytes(status.traffic?.tx_bytes || 0) }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作按钮 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header><span>连接控制</span></template>
          <div style="display: flex; gap: 12px; flex-wrap: wrap;">
            <el-button type="success" @click="connect" :disabled="status.connected" :loading="connecting">
              拨号
            </el-button>
            <el-button type="danger" @click="disconnect" :disabled="!status.connected" :loading="disconnecting">
              断开
            </el-button>
            <el-button @click="reconnect" :loading="reconnecting">
              重拨
            </el-button>
            <el-button @click="fetchStatus" :loading="loading">
              刷新
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 配置 -->
    <el-card shadow="hover">
      <template #header><span>拨号配置</span></template>
      <el-form :model="configForm" label-width="120px" style="max-width: 500px">
        <el-form-item label="用户名">
          <el-input v-model="configForm.username" placeholder="宽带账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="configForm.password" type="password" show-password placeholder="宽带密码" />
        </el-form-item>
        <el-form-item label="MTU">
          <el-input-number v-model="configForm.mtu" :min="576" :max="1500" />
        </el-form-item>
        <el-form-item label="自动重连">
          <el-switch v-model="configForm.auto_reconnect" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '@/stores'
import { ElMessage } from 'element-plus'

const status = ref({ connected: false, traffic: {}, config: {} })
const loading = ref(false)
const connecting = ref(false)
const disconnecting = ref(false)
const reconnecting = ref(false)
const saving = ref(false)

const configForm = reactive({
  username: '',
  password: '',
  mtu: 1492,
  auto_reconnect: true,
})

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(1)} ${units[i]}`
}

async function fetchStatus() {
  loading.value = true
  try {
    const res = await api.get('/pppoe/status')
    status.value = res.data
    if (res.data.config) {
      configForm.username = res.data.config.username || ''
      configForm.password = ''
      configForm.mtu = res.data.config.mtu || 1492
      configForm.auto_reconnect = res.data.config.auto_reconnect !== false
    }
  } catch (e) {
    ElMessage.error('获取状态失败')
  }
  loading.value = false
}

async function connect() {
  connecting.value = true
  try {
    const res = await api.post('/pppoe/connect')
    ElMessage.success(res.data.message || '拨号成功')
    setTimeout(fetchStatus, 2000)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '拨号失败')
  }
  connecting.value = false
}

async function disconnect() {
  disconnecting.value = true
  try {
    const res = await api.post('/pppoe/disconnect')
    ElMessage.success(res.data.message || '已断开')
    setTimeout(fetchStatus, 1000)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '断开失败')
  }
  disconnecting.value = false
}

async function reconnect() {
  reconnecting.value = true
  try {
    const res = await api.post('/pppoe/reconnect')
    ElMessage.success(res.data.message || '重拨成功')
    setTimeout(fetchStatus, 3000)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重拨失败')
  }
  reconnecting.value = false
}

async function saveConfig() {
  saving.value = true
  try {
    const res = await api.put('/pppoe/config', configForm)
    ElMessage.success(res.data.message || '配置已保存')
    await fetchStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
  saving.value = false
}

onMounted(fetchStatus)
</script>

<style scoped>
.pppoe-page { padding: 0; }
.stat-item { text-align: center; padding: 8px; }
.stat-label { font-size: 13px; color: #888; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #e0e0e0; }
.stat-value.small { font-size: 14px; }
</style>
