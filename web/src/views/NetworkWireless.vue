<template>
  <div class="wifi-page">
    <div class="page-header">
      <h2>无线设置</h2>
      <p class="page-desc">配置无线网卡工作模式 — AP 热点 或 Client 客户端</p>
    </div>

    <!-- 无硬件 -->
    <el-empty v-if="!available && !loading" description="未检测到无线网卡">
      <p style="color: #666; font-size: 13px">请插入 USB WiFi 无线网卡后刷新</p>
      <el-button @click="fetchStatus" :loading="loading">刷新检测</el-button>
    </el-empty>

    <template v-if="available">
      <!-- 硬件信息 -->
      <el-card shadow="never" class="info-card">
        <template #header><span>无线网卡</span></template>
        <div class="hw-info">
          <div class="hw-item">
            <span class="label">接口</span>
            <el-tag>{{ iface }}</el-tag>
          </div>
          <div class="hw-item">
            <span class="label">MAC</span>
            <code>{{ mac }}</code>
          </div>
          <div class="hw-item">
            <span class="label">当前模式</span>
            <el-tag :type="mode === 'ap' ? 'success' : mode === 'client' ? 'warning' : 'info'" effect="dark">
              {{ mode === 'ap' ? 'AP 热点' : mode === 'client' ? 'Client 客户端' : '空闲' }}
            </el-tag>
          </div>
        </div>
      </el-card>

      <!-- 模式切换选项卡 -->
      <el-card shadow="never" class="mode-card">
        <el-radio-group v-model="activeTab" class="mode-tabs" @change="onTabChange">
          <el-radio-button value="ap" :disabled="mode === 'client'">
            <el-icon><Connection /></el-icon> AP 热点
            <el-tag v-if="mode === 'ap'" type="success" size="small" effect="dark" style="margin-left: 6px">运行中</el-tag>
          </el-radio-button>
          <el-radio-button value="client" :disabled="mode === 'ap'">
            <el-icon><Connection /></el-icon> Client 客户端
            <el-tag v-if="mode === 'client'" type="warning" size="small" effect="dark" style="margin-left: 6px">已连接</el-tag>
          </el-radio-button>
        </el-radio-group>

        <!-- AP 模式面板 -->
        <div v-if="activeTab === 'ap'" class="tab-panel">
          <!-- AP 运行中 -->
          <div v-if="mode === 'ap'" class="running-section">
            <el-alert title="AP 热点运行中" type="success" show-icon :closable="false"
              :description="`SSID: ${ap.ssid}  |  频道: ${ap.channel}  |  已连接: ${ap.stations?.length || 0} 个设备`" />

            <div style="margin-top: 16px">
              <h4>已连接设备 ({{ ap.stations?.length || 0 }})</h4>
              <el-table :data="ap.stations || []" stripe max-height="240" style="width: 100%">
                <el-table-column prop="mac" label="MAC" width="200" />
                <el-table-column label="信号" width="100">
                  <template #default="{ row }">
                    <el-tag :type="(row.signal_dbm || -100) > -60 ? 'success' : (row.signal_dbm || -100) > -75 ? 'warning' : 'danger'" size="small">
                      {{ row.signal_dbm }} dBm
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="TX" width="100">
                  <template #default="{ row }">{{ row.tx_bitrate || '?' }} Mbps</template>
                </el-table-column>
                <el-table-column label="RX" width="100">
                  <template #default="{ row }">{{ row.rx_bitrate || '?' }} Mbps</template>
                </el-table-column>
                <el-table-column label="在线时长" min-width="120">
                  <template #default="{ row }">{{ formatDuration(row.connected_sec) }}</template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!ap.stations?.length" description="暂无设备连接" :image-size="60" />
            </div>

            <div class="action-bar" style="margin-top: 16px">
              <el-button type="danger" @click="stopAP" :loading="stopping">停止 AP</el-button>
              <el-button @click="configureAP">修改配置</el-button>
            </div>
          </div>

          <!-- AP 配置表单 -->
          <div v-else class="ap-form">
            <el-form :model="apForm" label-width="120px" style="max-width: 480px">
              <el-form-item label="SSID" required>
                <el-input v-model="apForm.ssid" placeholder="WiFi 名称" maxlength="32" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input v-model="apForm.password" type="password" show-password
                  placeholder="留空为开放网络 (不推荐)" maxlength="63" />
                <div class="form-hint">8-63 位字符，留空则创建开放热点</div>
              </el-form-item>
              <el-form-item label="频道">
                <el-select v-model="apForm.channel" style="width: 100%">
                  <el-option v-for="ch in channels" :key="ch" :label="`${ch} (${ch <= 13 ? '2.4GHz' : '5GHz'})`" :value="ch" />
                </el-select>
              </el-form-item>
              <el-form-item label="频段">
                <el-radio-group v-model="apForm.hw_mode">
                  <el-radio value="g">2.4GHz (802.11g)</el-radio>
                  <el-radio value="a">5GHz (802.11a)</el-radio>
                  <el-radio value="b">2.4GHz (802.11b)</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="隐藏 SSID">
                <el-switch v-model="apForm.hidden" />
              </el-form-item>
              <el-form-item label="最大客户端">
                <el-input-number v-model="apForm.max_num_sta" :min="1" :max="128" />
              </el-form-item>
              <el-form-item>
                <el-button type="success" @click="startAP" :loading="starting">
                  <el-icon><Connection /></el-icon> 启动 AP 热点
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>

        <!-- Client 模式面板 -->
        <div v-if="activeTab === 'client'" class="tab-panel">
          <!-- Client 运行中 -->
          <div v-if="mode === 'client'" class="running-section">
            <el-alert title="已连接到上级 AP" type="warning" show-icon :closable="false"
              :description="`SSID: ${client.ssid}  |  IP: ${client.ip || '获取中...'}  |  信号: ${client.signal_dbm || '?'} dBm`" />

            <div class="client-detail">
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="label">连接目标</span>
                  <span class="value">{{ client.ssid || '-' }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">IP 地址</span>
                  <span class="value">{{ client.ip || '-' }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">信号强度</span>
                  <span class="value">{{ client.signal_dbm ? client.signal_dbm + ' dBm' : '-' }}</span>
                </div>
              </div>
            </div>

            <div class="action-bar" style="margin-top: 16px">
              <el-button type="danger" @click="disconnectClient" :loading="disconnecting">断开连接</el-button>
              <el-button @click="activeTab = 'client-connect'">连接到其他网络</el-button>
            </div>
          </div>

          <!-- 扫描 & 连接 -->
          <div v-else class="client-scan">
            <div class="scan-toolbar">
              <span class="scan-title">附近 WiFi 网络</span>
              <el-button size="small" @click="scanNetworks" :loading="scanning">
                <el-icon><Refresh /></el-icon> 扫描
              </el-button>
            </div>

            <el-table :data="networks" stripe v-loading="scanning" max-height="500" style="width: 100%; margin-top: 12px">
              <el-table-column label="SSID" min-width="180">
                <template #default="{ row }">
                  <div class="ssid-cell">
                    <LockIcon :encrypted="row.encryption !== 'open'" />
                    <span>{{ row.ssid }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="频段" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.band === '5GHz' ? 'primary' : 'default'" size="small">{{ row.band }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="加密" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.encryption === 'open' ? 'success' : 'warning'" size="small">
                    {{ row.encryption === 'open' ? '开放' : '加密' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="信号" width="160">
                <template #default="{ row }">
                  <div class="signal-bar">
                    <div class="bar-bg"><div class="bar-fill" :style="{ width: signalPercent(row.signal_dbm) + '%' }" /></div>
                    <span class="dbm">{{ row.signal_dbm }} dBm</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" @click="showConnectDialog(row)">连接</el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-empty v-if="!scanning && networks.length === 0" description="未扫描到网络" :image-size="60" />
          </div>
        </div>
      </el-card>
    </template>

    <!-- 连接对话框 -->
    <el-dialog v-model="connectVisible" title="连接 WiFi" width="420px">
      <el-form label-width="80px">
        <el-form-item label="SSID">
          <el-input :model-value="selectedNet?.ssid" disabled />
        </el-form-item>
        <el-form-item v-if="selectedNet?.encryption !== 'open'" label="密码" required>
          <el-input v-model="clientPassword" type="password" show-password placeholder="输入 WiFi 密码" />
        </el-form-item>
        <el-form-item label="隐藏网络">
          <el-switch v-model="clientHidden" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="connectVisible = false">取消</el-button>
        <el-button type="primary" @click="doClientConnect" :loading="connecting">连接</el-button>
      </template>
    </el-dialog>

    <!-- 修改 AP 配置对话框 -->
    <el-dialog v-model="apConfigVisible" title="修改 AP 配置" width="480px">
      <el-form :model="apForm" label-width="100px">
        <el-form-item label="SSID">
          <el-input v-model="apForm.ssid" maxlength="32" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="apForm.password" type="password" show-password maxlength="63" />
        </el-form-item>
        <el-form-item label="频道">
          <el-select v-model="apForm.channel">
            <el-option v-for="ch in channels" :key="ch" :label="`${ch}`" :value="ch" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="apConfigVisible = false">取消</el-button>
        <el-button type="primary" @click="stopAPthenStart">保存并重启</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { api } from '@/stores'
import { Refresh, Connection } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ─── 状态 ──────────────────────────────────────────────────────────

const loading = ref(true)
const available = ref(false)
const iface = ref('')
const mac = ref('')
const mode = ref('idle')  // ap | client | idle
const ap = ref({ running: false, ssid: '', channel: 0, stations: [] })
const client = ref({ running: false, ssid: '', ip: null, signal_dbm: null })

const activeTab = ref('ap')
const networks = ref([])
const scanning = ref(false)
const starting = ref(false)
const stopping = ref(false)
const connecting = ref(false)
const disconnecting = ref(false)
const connectVisible = ref(false)
const apConfigVisible = ref(false)
const selectedNet = ref(null)
const clientPassword = ref('')
const clientHidden = ref(false)

const apForm = reactive({
  ssid: 'UbuntuRouter',
  password: '',
  channel: 6,
  hw_mode: 'g',
  hidden: false,
  max_num_sta: 32,
})

const channels = computed(() => {
  const ch = []
  for (let i = 1; i <= 13; i++) ch.push(i)
  for (let i = 36; i <= 48; i += 4) ch.push(i)
  return ch
})

let pollTimer = null

// ─── 工具函数 ──────────────────────────────────────────────────────

function formatDuration(sec) {
  if (!sec && sec !== 0) return '-'
  if (sec < 60) return `${sec}秒`
  if (sec < 3600) return `${Math.floor(sec / 60)}分${sec % 60}秒`
  return `${Math.floor(sec / 3600)}时${Math.floor((sec % 3600) / 60)}分`
}

function signalPercent(dbm) {
  if (!dbm) return 0
  return Math.max(0, Math.min(100, ((dbm + 90) / 60) * 100))
}

// ─── API 调用 ──────────────────────────────────────────────────────

async function fetchStatus() {
  loading.value = true
  try {
    const res = await api.get('/wireless/status')
    available.value = res.data.available
    if (!available.value) { loading.value = false; return }

    iface.value = res.data.interface || ''
    mac.value = res.data.mac || ''
    mode.value = res.data.mode || 'idle'
    ap.value = res.data.ap || { running: false, ssid: '', channel: 0, stations: [] }
    client.value = res.data.client || { running: false, ssid: '', ip: null }

    // 同步 tab
    if (mode.value === 'ap') activeTab.value = 'ap'
    else if (mode.value === 'client') activeTab.value = 'client'
  } catch (e) {
    available.value = false
  }
  loading.value = false
}

async function scanNetworks() {
  scanning.value = true
  try {
    const res = await api.get(`/wireless/scan?interface=${iface.value}`)
    networks.value = res.data.networks || []
    if (res.data.success) ElMessage.success(`扫描到 ${res.data.count} 个网络`)
    else ElMessage.warning('扫描失败: ' + (res.data.error || ''))
  } catch (e) {
    ElMessage.error('扫描失败: ' + (e.response?.data?.detail || e.message))
    networks.value = []
  }
  scanning.value = false
}

async function startAP() {
  if (!apForm.ssid.trim()) { ElMessage.warning('请输入 SSID'); return }
  starting.value = true
  try {
    const res = await api.post('/wireless/ap/start', { ...apForm })
    ElMessage.success(res.data.message || 'AP 启动成功')
    await fetchStatus()
  } catch (e) {
    ElMessage.error('启动失败: ' + (e.response?.data?.detail || e.message))
  }
  starting.value = false
}

async function stopAP() {
  try {
    await ElMessageBox.confirm('停止 AP 热点将断开所有已连接的 WiFi 设备，确认？', '确认', { type: 'warning' })
  } catch { return }
  stopping.value = true
  try {
    await api.post('/wireless/ap/stop')
    ElMessage.success('AP 已停止')
    mode.value = 'idle'
    ap.value = { running: false, ssid: '', channel: 0, stations: [] }
  } catch (e) {
    ElMessage.error('停止失败: ' + (e.response?.data?.detail || e.message))
  }
  stopping.value = false
}

function configureAP() {
  apForm.ssid = ap.value.ssid || 'UbuntuRouter'
  apForm.channel = ap.value.channel || 6
  apConfigVisible.value = true
}

async function stopAPthenStart() {
  apConfigVisible.value = false
  stopping.value = true
  try {
    await api.post('/wireless/ap/stop')
    await new Promise(r => setTimeout(r, 1000))
    await startAP()
  } catch (e) {
    ElMessage.error('重启失败: ' + e.message)
  }
  stopping.value = false
}

function showConnectDialog(net) {
  selectedNet.value = net
  clientPassword.value = ''
  clientHidden.value = false
  connectVisible.value = true
}

async function doClientConnect() {
  if (selectedNet.value.encryption !== 'open' && !clientPassword.value.trim()) {
    ElMessage.warning('请输入密码')
    return
  }
  connecting.value = true
  try {
    const res = await api.post('/wireless/client/connect', {
      ssid: selectedNet.value.ssid,
      password: selectedNet.value.encryption !== 'open' ? clientPassword.value : null,
      hidden: clientHidden.value,
    })
    ElMessage.success(res.data.message || '连接成功')
    connectVisible.value = false
    setTimeout(fetchStatus, 3000)
  } catch (e) {
    ElMessage.error('连接失败: ' + (e.response?.data?.detail || e.message))
  }
  connecting.value = false
}

async function disconnectClient() {
  try {
    await ElMessageBox.confirm('断开后将无法通过此 WiFi 访问网络，确认？', '确认', { type: 'warning' })
  } catch { return }
  disconnecting.value = true
  try {
    await api.post('/wireless/client/disconnect')
    ElMessage.success('已断开')
    mode.value = 'idle'
    client.value = { running: false, ssid: '', ip: null }
  } catch (e) {
    ElMessage.error('断开失败: ' + (e.response?.data?.detail || e.message))
  }
  disconnecting.value = false
}

function onTabChange(tab) {
  if (tab === 'client') {
    scanNetworks()
  }
}

// ─── 生命周期 ──────────────────────────────────────────────────────

onMounted(async () => {
  await fetchStatus()
  // 每 10s 轮询状态 (AP 连接设备数, Client 状态)
  if (available.value) {
    pollTimer = setInterval(fetchStatus, 10000)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.wifi-page { padding: 0; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px 0; color: #e0e0e0; }
.page-desc { margin: 0; font-size: 13px; color: #888; }

.info-card { margin-bottom: 20px; }
.hw-info { display: flex; gap: 24px; flex-wrap: wrap; align-items: center; }
.hw-item { display: flex; align-items: center; gap: 8px; }
.hw-item .label { color: #888; font-size: 13px; }
.hw-item code { font-size: 12px; color: #ccc; }

.mode-card { margin-bottom: 20px; }
.mode-tabs { display: flex; justify-content: center; margin-bottom: 24px; }

.tab-panel { padding: 8px 0; }

.running-section {  }
.client-detail { margin-top: 12px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
.detail-item { display: flex; justify-content: space-between; padding: 8px 12px; background: #1a1a2e; border-radius: 6px; }
.detail-item .label { color: #888; font-size: 13px; }
.detail-item .value { color: #ccc; font-size: 13px; font-weight: 500; }

.ap-form { max-width: 520px; margin: 0 auto; }

.client-scan {  }
.scan-toolbar { display: flex; justify-content: space-between; align-items: center; }
.scan-title { font-weight: 500; color: #ccc; }

.ssid-cell { display: flex; align-items: center; gap: 6px; }

.signal-bar { display: flex; align-items: center; gap: 8px; }
.bar-bg { width: 80px; height: 6px; background: #2a2a3e; border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, #e6a23c, #67c23a); border-radius: 3px; transition: width 0.3s; }
.dbm { font-size: 12px; color: #888; }

.action-bar { display: flex; gap: 12px; }

.form-hint { font-size: 12px; color: #888; margin-top: 4px; }
</style>
