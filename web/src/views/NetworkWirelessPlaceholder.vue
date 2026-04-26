<template>
  <div class="wifi-page">
    <div class="page-header">
      <h2>WiFi 配置</h2>
      <p class="page-desc">管理无线网络连接和热点配置</p>
    </div>

      <!-- 无 WiFi 硬件 -->
    <el-empty v-if="!wifiAvailable && !loading" description="未检测到 WiFi 硬件">
      <template #image>
        <el-icon :size="64" color="#888"><Connection /></el-icon>
      </template>
      <p style="color: #666; font-size: 13px">当前系统没有检测到无线网卡，或有线虚拟机环境不支持 WiFi</p>
    </el-empty>

    <template v-if="wifiAvailable">
      <!-- 当前连接状态 -->
      <el-card shadow="never" style="margin-bottom: 20px">
        <template #header><span>当前连接</span></template>
        <div v-if="currentStatus.connected" class="connected-info">
          <div class="status-row">
            <el-tag type="success" size="large" effect="dark">
              已连接 {{ currentStatus.ssid }}
            </el-tag>
            <div class="signal-bars" :style="{ '--level': signalLevel }">
              <span v-for="i in 4" :key="i" class="bar"
                :class="{ active: i <= signalLevel }" />
            </div>
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="label">接口</span>
              <span class="value">{{ currentStatus.interface }}</span>
            </div>
            <div class="detail-item">
              <span class="label">IP 地址</span>
              <span class="value">{{ currentStatus.ip || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">频段</span>
              <span class="value">{{ currentStatus.frequency > 4000 ? '5GHz' : '2.4GHz' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">信号</span>
              <span class="value">{{ currentStatus.signal_dbm }} dBm</span>
            </div>
          </div>
          <el-button type="danger" @click="disconnectWiFi" :loading="disconnecting" style="margin-top: 12px">
            断开连接
          </el-button>
        </div>
        <el-empty v-else description="未连接任何 WiFi 网络" :image-size="60" />
      </el-card>

      <!-- 接口信息 -->
      <el-card shadow="never" style="margin-bottom: 20px">
        <template #header><span>检测到的无线接口</span></template>
        <div class="iface-list">
          <div v-for="iface in interfaces" :key="iface.name" class="iface-chip">
            <el-tag type="info">{{ iface.name }}</el-tag>
            <span class="iface-mac">{{ iface.mac || 'MAC 未知' }}</span>
            <span class="iface-type">{{ iface.type || 'station' }}</span>
          </div>
        </div>
      </el-card>

      <!-- 扫描网络 -->
      <el-card shadow="never" style="margin-bottom: 20px">
        <template #header>
          <div class="card-header">
            <span>扫描附近网络</span>
            <el-button size="small" @click="scanNetworks" :loading="scanning" text>
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </template>

        <el-table :data="networks" stripe v-loading="scanning" max-height="500" style="width: 100%">
          <el-table-column label="SSID" min-width="200">
            <template #default="{ row }">
              <div class="ssid-cell">
                <WifiIcon :encryption="row.encryption" />
                <span>{{ row.ssid }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="BSSID" width="180">
            <template #default="{ row }">
              <span class="bssid-text">{{ row.bssid }}</span>
            </template>
          </el-table-column>
          <el-table-column label="频段" width="80">
            <template #default="{ row }">
              <el-tag :type="row.band === '5GHz' ? 'primary' : 'default'" size="small">
                {{ row.band }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="加密" width="80">
            <template #default="{ row }">
              <el-tag :type="row.encryption === 'open' ? 'success' : 'warning'" size="small">
                {{ row.encryption === 'open' ? '开放' : row.encryption.toUpperCase() }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="信号" width="120">
            <template #default="{ row }">
              <div class="signal-cell">
                <div class="signal-bar-bg">
                  <div class="signal-bar-fill" :style="{ width: signalPercent(row.signal_dbm) + '%' }" />
                </div>
                <span class="signal-dbm">{{ row.signal_dbm }} dBm</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                @click="showConnectDialog(row)"
                :disabled="currentStatus.ssid === row.ssid"
              >
                {{ currentStatus.ssid === row.ssid ? '已连接' : '连接' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!scanning && networks.length === 0" description="未扫描到网络或扫描功能不可用" />
      </el-card>
    </template>

    <!-- 连接对话框 -->
    <el-dialog v-model="connectVisible" title="连接 WiFi" width="420px">
      <el-form label-width="80px">
        <el-form-item label="SSID">
          <el-input :model-value="selectedNetwork?.ssid" disabled />
        </el-form-item>
        <el-form-item v-if="selectedNetwork?.encryption !== 'open'" label="密码" required>
          <el-input v-model="password" type="password" show-password placeholder="输入 WiFi 密码" />
        </el-form-item>
        <el-form-item label="隐藏网络">
          <el-switch v-model="hidden" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="connectVisible = false">取消</el-button>
        <el-button type="primary" @click="doConnect" :loading="connecting">
          连接
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/stores'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const loading = ref(true)
const wifiAvailable = ref(false)
const scanning = ref(false)
const connecting = ref(false)
const disconnecting = ref(false)
const connectVisible = ref(false)
const password = ref('')
const hidden = ref(false)

const interfaces = ref([])
const networks = ref([])
const currentStatus = ref({ connected: false })
const selectedNetwork = ref(null)

const signalLevel = computed(() => {
  const dbm = currentStatus.value.signal_dbm
  if (!dbm) return 0
  if (dbm >= -50) return 4
  if (dbm >= -65) return 3
  if (dbm >= -80) return 2
  return 1
})

function signalPercent(dbm) {
  if (!dbm) return 0
  // -30 to -90 mapped to 100% to 0%
  return Math.max(0, Math.min(100, ((dbm + 90) / 60) * 100))
}

async function fetchStatus() {
  try {
    const res = await api.get('/wireless/interfaces')
    wifiAvailable.value = res.data.available
    interfaces.value = res.data.interfaces || []
  } catch {
    wifiAvailable.value = false
  }

  if (wifiAvailable.value) {
    try {
      const res = await api.get('/wireless/status')
      currentStatus.value = res.data.interfaces?.[0] || { connected: false }
    } catch { /* ignore */ }
  }
  loading.value = false
}

async function scanNetworks() {
  scanning.value = true
  try {
    const iface = interfaces.value[0]?.name || 'wlan0'
    const res = await api.get(`/wireless/scan?interface=${iface}`)
    networks.value = res.data.networks || []
    if (res.data.success) {
      ElMessage.success(`扫描到 ${res.data.count} 个网络`)
    }
  } catch (e) {
    ElMessage.error('扫描失败: ' + (e.response?.data?.detail || e.message))
  }
  scanning.value = false
}

function showConnectDialog(network) {
  selectedNetwork.value = network
  password.value = ''
  hidden.value = false
  connectVisible.value = true
}

async function doConnect() {
  if (selectedNetwork.value.encryption !== 'open' && !password.value.trim()) {
    ElMessage.warning('请输入 WiFi 密码')
    return
  }
  connecting.value = true
  try {
    const iface = interfaces.value[0]?.name || 'wlan0'
    await api.post(`/wireless/connect?interface=${iface}`, {
      ssid: selectedNetwork.value.ssid,
      password: selectedNetwork.value.encryption !== 'open' ? password.value : null,
      hidden: hidden.value,
    })
    ElMessage.success(`已连接到 ${selectedNetwork.value.ssid}`)
    connectVisible.value = false
    // Refresh status after a delay
    setTimeout(fetchStatus, 3000)
  } catch (e) {
    ElMessage.error('连接失败: ' + (e.response?.data?.detail || e.message))
  }
  connecting.value = false
}

async function disconnectWiFi() {
  disconnecting.value = true
  try {
    const iface = interfaces.value[0]?.name || 'wlan0'
    await api.post(`/wireless/disconnect?interface=${iface}`)
    ElMessage.success('已断开 WiFi 连接')
    currentStatus.value = { connected: false }
  } catch (e) {
    ElMessage.error('断开失败: ' + (e.response?.data?.detail || e.message))
  }
  disconnecting.value = false
}

onMounted(fetchStatus)
</script>

<style scoped>
.wifi-page { padding: 0; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px 0; color: #e0e0e0; }
.page-desc { margin: 0; font-size: 13px; color: #888; }

.connected-info { display: flex; flex-direction: column; gap: 12px; }
.status-row { display: flex; align-items: center; gap: 16px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.detail-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #2a2a3e; }
.detail-item .label { color: #888; font-size: 13px; }
.detail-item .value { color: #ccc; font-size: 13px; }

.iface-list { display: flex; gap: 12px; flex-wrap: wrap; }
.iface-chip { display: flex; align-items: center; gap: 8px; }
.iface-mac { color: #888; font-size: 12px; font-family: monospace; }
.iface-type { color: #666; font-size: 12px; }

.card-header { display: flex; justify-content: space-between; align-items: center; }

.ssid-cell { display: flex; align-items: center; gap: 8px; }
.bssid-text { font-family: monospace; font-size: 12px; color: #888; }

.signal-cell { display: flex; align-items: center; gap: 8px; }
.signal-bar-bg { width: 80px; height: 6px; background: #2a2a3e; border-radius: 3px; overflow: hidden; }
.signal-bar-fill { height: 100%; background: linear-gradient(90deg, #e6a23c, #67c23a); border-radius: 3px; transition: width 0.3s; }
.signal-dbm { font-size: 12px; color: #888; }

.signal-bars { display: flex; gap: 3px; align-items: end; height: 20px; --level: 0; }
.signal-bars .bar {
  width: 6px;
  background: #444;
  border-radius: 2px;
  transition: background 0.3s;
}
.signal-bars .bar:nth-child(1) { height: 6px; }
.signal-bars .bar:nth-child(2) { height: 10px; }
.signal-bars .bar:nth-child(3) { height: 14px; }
.signal-bars .bar:nth-child(4) { height: 18px; }
.signal-bars .bar.active { background: #67c23a; }
</style>
