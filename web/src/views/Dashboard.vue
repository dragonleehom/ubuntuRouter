<template>
  <div class="dashboard">
    <!-- 顶部：系统状态概览卡片行 -->
    <div class="stats-row">
      <div class="stat-card glass-card">
        <div class="stat-icon cpu"><Cpu /></div>
        <div class="stat-body">
          <div class="stat-value">{{ system.cpu_usage ?? '--' }}<span class="unit">%</span></div>
          <div class="stat-label">CPU</div>
        </div>
      </div>
      <div class="stat-card glass-card">
        <div class="stat-icon mem"><Coin /></div>
        <div class="stat-body">
          <div class="stat-value">{{ memUsed }}<span class="unit">/{{ memTotal }} MB</span></div>
          <div class="stat-label">内存</div>
        </div>
      </div>
      <div class="stat-card glass-card">
        <div class="stat-icon disk"><Folder /></div>
        <div class="stat-body">
          <div class="stat-value">{{ diskPercent }}<span class="unit">%</span></div>
          <div class="stat-label">磁盘</div>
        </div>
      </div>
      <div class="stat-card glass-card">
        <div class="stat-icon uptime"><Timer /></div>
        <div class="stat-body">
          <div class="stat-value uptime-text">{{ uptimeShort }}</div>
          <div class="stat-label">运行时间</div>
        </div>
      </div>
    </div>

    <!-- 快捷操作面板 -->
    <div class="quick-actions glass-card">
      <div class="section-title">快捷操作</div>
      <div class="action-buttons">
        <el-button class="action-btn" @click="handleAction('refresh')" :loading="actionLoading === 'refresh'">
          <el-icon><Refresh /></el-icon> 刷新服务
        </el-button>
        <el-button class="action-btn" @click="handleAction('check-updates')" :loading="actionLoading === 'check-updates'">
          <el-icon><Download /></el-icon> 检查更新
        </el-button>
        <el-button class="action-btn" type="success" @click="handleAction('apply-updates')" :loading="actionLoading === 'apply-updates'">
          <el-icon><Top /></el-icon> 更新系统
        </el-button>
        <el-button class="action-btn" type="warning" @click="handleAction('reboot')" :loading="actionLoading === 'reboot'">
          <el-icon><RefreshRight /></el-icon> 重启系统
        </el-button>
        <el-button class="action-btn" type="danger" @click="handleAction('shutdown')" :loading="actionLoading === 'shutdown'">
          <el-icon><SwitchButton /></el-icon> 关机
        </el-button>
      </div>
    </div>

    <!-- 中间行：实时流量 + 网络拓扑 2列布局 -->
    <div class="mid-row">
      <!-- 实时流量曲线 -->
      <div class="glass-card traffic-card">
        <div class="section-title">实时流量</div>
        <div class="traffic-rate-bar">
          <div class="rate-item">
            <span class="rate-dot down" />
            <span>下载</span>
            <span class="rate-value">{{ formatBps(currentTraffic.ens3?.rx_bps || 0) }}</span>
          </div>
          <div class="rate-item">
            <span class="rate-dot up" />
            <span>上传</span>
            <span class="rate-value">{{ formatBps(currentTraffic.ens3?.tx_bps || 0) }}</span>
          </div>
        </div>
        <v-chart ref="chartRef" :option="chartOption" autoresize class="traffic-chart" />
      </div>

      <!-- 网络拓扑 -->
      <div class="glass-card topo-card">
        <div class="section-title">网络拓扑</div>
        <NetTopo />
      </div>
    </div>

    <!-- 底行：网络状态 + 服务状态 2列 -->
    <div class="bottom-row">
      <!-- 网络状态 -->
      <div class="glass-card">
        <div class="section-title">网络状态</div>
        <div class="iface-list">
          <div v-for="iface in interfaces" :key="iface.name" class="iface-item">
            <div class="iface-left">
              <el-tag :type="iface.state === 'UP' ? 'success' : 'danger'" size="small" effect="plain" round>
                {{ iface.state }}
              </el-tag>
              <span class="iface-name">{{ iface.name }}</span>
            </div>
            <div class="iface-right">
              <span class="iface-ip">{{ iface.ipv4?.[0] || '无 IP' }}</span>
              <span v-if="iface.speed" class="iface-speed">{{ iface.speed }}M</span>
            </div>
          </div>
        </div>
        <div class="config-summary" v-if="config">
          <div class="config-row"><span>LAN 网关</span><span>192.168.21.1</span></div>
          <div class="config-row" v-if="config.dhcp"><span>DHCP</span><span>{{ config.dhcp.range }}</span></div>
          <div class="config-row"><span>接口数</span><span>{{ config.interfaces?.length || 0 }}</span></div>
        </div>
      </div>

      <!-- 服务状态 -->
      <div class="glass-card">
        <div class="section-title">服务状态</div>
        <div class="service-list">
          <div v-for="svc in services" :key="svc.name" class="service-item">
            <div class="service-left">
              <span class="status-dot" :class="svc.active ? 'alive' : 'dead'" />
              <span class="service-name">{{ svc.name }}</span>
            </div>
            <el-button
              size="small"
              :type="svc.active ? 'warning' : 'success'"
              round
              :loading="serviceLoading === svc.name"
              @click="toggleService(svc)"
            >
              {{ svc.active ? '停止' : '启动' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, useAuthStore } from '@/stores'
import {
  Cpu, Coin, Folder, Timer, Refresh, Download, Top,
  RefreshRight, SwitchButton,
} from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import 'echarts'
import NetTopo from '@/components/NetTopo.vue'

const route = useRoute()
const authStore = useAuthStore()

onMounted(() => { document.title = route.meta?.title || '仪表盘' })

// --- 系统状态 ---
const system = ref({})
const interfaces = ref([])
const services = ref([])
const config = ref(null)
const loading = ref(false)

async function fetchStatus() {
  loading.value = true
  try {
    const res = await api.get('/dashboard/status')
    const d = res.data
    system.value = d.system || {}
    interfaces.value = d.interfaces || []
    services.value = d.apps || []
    config.value = d.config || null
  } catch (e) {
    console.error('获取状态失败:', e)
  }
  loading.value = false
}

const memUsed = computed(() => system.value.memory?.used_mb ?? '--')
const memTotal = computed(() => system.value.memory?.total_mb ?? '')
const diskPercent = computed(() => {
  const d = system.value.disk?.usage_percent
  return d ? parseInt(d.replace('%', '')) : '--'
})
const uptimeShort = computed(() => {
  const sec = system.value.uptime_seconds || 0
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  if (d > 0) return `${d}d ${h}h`
  return `${h}h`
})

// --- 实时流量（WS）---
const chartRef = ref(null)
const trafficHistory = ref([])
const currentTraffic = ref({})
let ws = null
let wsTimer = null

function formatBps(bps) {
  if (bps >= 1e9) return (bps / 1e9).toFixed(2) + ' Gbps'
  if (bps >= 1e6) return (bps / 1e6).toFixed(2) + ' Mbps'
  if (bps >= 1e3) return (bps / 1e3).toFixed(1) + ' Kbps'
  return bps + ' bps'
}

function connectWS() {
  const token = localStorage.getItem('access_token')
  if (!token) return
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${location.host}/api/v1/ws/dashboard`

  try {
    ws = new WebSocket(url)
    ws.onopen = () => {
      ws.send(JSON.stringify({ token }))
    }
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'traffic') {
          currentTraffic.value = data.traffic || {}
          const rx = data.traffic?.ens3?.rx_bps || 0
          const tx = data.traffic?.ens3?.tx_bps || 0
          const now = Date.now()
          trafficHistory.value.push([now, rx, tx])
          if (trafficHistory.value.length > 60) {
            trafficHistory.value = trafficHistory.value.slice(-60)
          }
        }
      } catch {}
    }
    ws.onclose = () => {
      ws = null
    }
  } catch {}
}

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(255,255,255,0.9)',
    borderColor: 'rgba(0,0,0,0.06)',
    borderRadius: 12,
    padding: [10, 14],
    formatter: (params) => {
      const rx = params.find(p => p.seriesName === '下载')
      const tx = params.find(p => p.seriesName === '上传')
      return `<div style="font-size:13px;color:#1E293B;font-weight:600;margin-bottom:4px;">实时流量</div>
        <div style="display:flex;gap:16px;">
          <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#0052FF;margin-right:4px;"></span>下载 ${rx ? formatBps(rx.value[1]) : '--'}</span>
          <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#4ADE80;margin-right:4px;"></span>上传 ${tx ? formatBps(tx.value[2]) : '--'}</span>
        </div>`
    },
  },
  grid: { left: 50, right: 16, top: 24, bottom: 24 },
  xAxis: {
    type: 'time',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
    splitLine: { show: false },
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#94a3b8', fontSize: 11,
      formatter: (v) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v,
    },
    splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)', type: 'dashed' } },
  },
  series: [
    {
      name: '下载',
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#0052FF' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(0,82,255,0.25)' },
            { offset: 1, color: 'rgba(0,82,255,0.02)' },
          ],
        },
      },
      data: trafficHistory.value.map(d => [d[0], d[1]]),
    },
    {
      name: '上传',
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#4ADE80' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(74,222,128,0.2)' },
            { offset: 1, color: 'rgba(74,222,128,0.02)' },
          ],
        },
      },
      data: trafficHistory.value.map(d => [d[0], d[2]]),
    },
  ],
}))

// --- 快捷操作 ---
const actionLoading = ref('')

async function handleAction(action) {
  if (action === 'reboot' || action === 'shutdown') {
    try {
      await ElMessageBox.confirm(
        `确定要${action === 'reboot' ? '重启' : '关机'}系统吗？`,
        '警告',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
      )
    } catch { return }
  }

  actionLoading.value = action
  try {
    const res = await api.post(`/dashboard/action/${action}`)
    ElMessage.success(res.data.message || '操作成功')
    if (action === 'refresh') fetchStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
  actionLoading.value = ''
}

// --- 服务启停 ---
const serviceLoading = ref('')

async function toggleService(svc) {
  const action = svc.active ? 'stop' : 'start'
  serviceLoading.value = svc.name
  try {
    await api.post(`/dashboard/action/${action}-service/${svc.name}`)
    ElMessage.success(`${svc.name} ${action === 'start' ? '启动' : '停止'}成功`)
    fetchStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
  serviceLoading.value = ''
}

// --- 生命周期 ---
let statusTimer = null

onMounted(() => {
  fetchStatus()
  statusTimer = setInterval(fetchStatus, 15000)
  connectWS()
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
  if (ws) ws.close()
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 玻璃卡片复用 */
.glass-card {
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.4);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(31,38,135,0.07);
  padding: 20px;
  transition: all 0.25s ease;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
  margin-bottom: 16px;
}

/* 顶部统计行 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.stat-icon.cpu { background: rgba(0,82,255,0.1); color: #0052FF; }
.stat-icon.mem { background: rgba(74,222,128,0.1); color: #16a34a; }
.stat-icon.disk { background: rgba(245,158,11,0.1); color: #d97706; }
.stat-icon.uptime { background: rgba(139,92,246,0.1); color: #7c3aed; }

.stat-body { min-width: 0; }
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #1E293B;
  line-height: 1.2;
}
.stat-value .unit {
  font-size: 13px;
  font-weight: 400;
  color: #64748B;
  margin-left: 2px;
}
.uptime-text { font-size: 18px; }
.stat-label {
  font-size: 12px;
  color: #64748B;
  margin-top: 2px;
  font-weight: 500;
}

/* 快捷操作 */
.quick-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.quick-actions .section-title {
  margin-bottom: 0;
  white-space: nowrap;
}
.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.action-btn {
  border-radius: 12px !important;
  font-weight: 600 !important;
}

/* 中间行 */
.mid-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}

.traffic-card { display: flex; flex-direction: column; }
.traffic-rate-bar {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}
.rate-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748B;
}
.rate-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
}
.rate-dot.down { background: #0052FF; }
.rate-dot.up { background: #4ADE80; }
.rate-value {
  font-weight: 600;
  font-size: 14px;
  color: #1E293B;
  font-variant-numeric: tabular-nums;
}
.traffic-chart {
  flex: 1;
  min-height: 200px;
}

/* 底行 */
.bottom-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* 接口列表 */
.iface-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.iface-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(255,255,255,0.4);
  border-radius: 12px;
}
.iface-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.iface-name {
  font-weight: 500;
  color: #1E293B;
  font-size: 14px;
}
.iface-right {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748B;
  font-size: 13px;
}
.iface-speed {
  color: #0052FF;
  font-weight: 600;
  font-size: 12px;
}
.config-summary {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(0,0,0,0.04);
}
.config-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
  color: #64748B;
}
.config-row span:last-child {
  color: #1E293B;
  font-weight: 500;
}

/* 服务列表 */
.service-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.service-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(255,255,255,0.4);
  border-radius: 12px;
}
.service-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
}
.status-dot.alive { background: #4ADE80; box-shadow: 0 0 6px rgba(74,222,128,0.4); }
.status-dot.dead { background: #FF4D8D; }
.service-name {
  font-size: 14px;
  color: #1E293B;
}

/* 响应式 */
@media (max-width: 1024px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .mid-row, .bottom-row { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .stat-icon { width: 36px; height: 36px; font-size: 18px; }
  .stat-value { font-size: 18px; }
  .dashboard { gap: 12px; }
  .glass-card { padding: 14px; }
}
</style>
