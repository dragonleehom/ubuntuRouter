<template>
  <div class="traffic-realtime">
    <h2>实时流量监控</h2>

    <!-- 状态卡片行 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :xs="12" :sm="6" v-for="s in statCards" :key="s.label" style="margin-bottom: 12px">
        <el-card shadow="hover" :body-style="{ padding: '14px' }">
          <div class="stat-card">
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表行 -->
    <el-row :gutter="12">
      <el-col :xs="24" :sm="12" style="margin-bottom: 12px">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>网络流量 (bps)</span>
              <div class="header-actions">
                <el-switch
                  v-model="netChartUnit"
                  active-value="bps"
                  inactive-value="Bps"
                  active-text="bps"
                  inactive-text="B/s"
                  size="small"
                  style="margin-right: 8px"
                />
                <el-button size="small" :type="paused ? 'warning' : 'default'" @click="togglePause">
                  {{ paused ? '▶ 继续' : '⏸ 暂停' }}
                </el-button>
              </div>
            </div>
          </template>
          <div ref="netChart" style="height: 250px"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" style="margin-bottom: 12px">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>系统资源 (%)</span>
              <el-button size="small" :type="paused ? 'warning' : 'default'" @click="togglePause">
                {{ paused ? '▶ 继续' : '⏸ 暂停' }}
              </el-button>
            </div>
          </template>
          <div ref="sysChart" style="height: 250px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 当前接口流量明细 -->
    <el-card shadow="hover" style="margin-top: 4px">
      <template #header>
        <span>接口实时速率</span>
      </template>
      <el-table :data="interfaceRates" stripe size="small" max-height="300" v-loading="loading">
        <el-table-column prop="name" label="接口" width="120" />
        <el-table-column prop="rx" label="下载 (bps)" width="150">
          <template #default="{ row }">
            <span style="color: #409EFF">{{ formatBps(row.rx) }}/s</span>
          </template>
        </el-table-column>
        <el-table-column prop="tx" label="上传 (bps)" width="150">
          <template #default="{ row }">
            <span style="color: #67C23A">{{ formatBps(row.tx) }}/s</span>
          </template>
        </el-table-column>
        <el-table-column prop="rx_total" label="总接收" width="120">
          <template #default="{ row }">
            {{ formatBytes(row.rx_total) }}
          </template>
        </el-table-column>
        <el-table-column prop="tx_total" label="总发送" width="120">
          <template #default="{ row }">
            {{ formatBytes(row.tx_total) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { api } from '@/stores'
import { ElMessage } from 'element-plus'

const netChart = ref(null)
const sysChart = ref(null)
const loading = ref(false)
const paused = ref(false)
const netChartUnit = ref('bps') // 'bps' or 'Bps'

// 历史数据缓冲区
const MAX_POINTS = 60 // 60 points = 2 minutes at 2s interval
const netHistory = ref([]) // [{ time, upload, download }]
const sysHistory = ref([]) // [{ time, cpu, mem }]
const interfaceRates = ref([])

let charts = []
let timer = null
let echartsInstance = null

const currentData = ref({
  upload_bps: 0,
  download_bps: 0,
  cpu_percent: 0,
  memory_percent: 0,
  connections: 0,
})

const statCards = computed(() => {
  const d = currentData.value
  return [
    { label: '下载', value: formatBps(d.download_bps) + '/s', color: '#409EFF' },
    { label: '上传', value: formatBps(d.upload_bps) + '/s', color: '#67C23A' },
    { label: 'CPU', value: d.cpu_percent ? `${d.cpu_percent.toFixed(1)}%` : '--', color: '#e6a23c' },
    { label: '连接数', value: d.connections ?? '--', color: '#909399' },
  ]
})

function formatBps(val) {
  if (val == null || val === 0) return '0 b'
  // Convert to appropriate unit
  const useBits = netChartUnit.value === 'bps'
  const v = useBits ? val * 8 : val
  const unitBase = useBits ? 1000 : 1024
  const unitLabel = useBits ? ['b', 'Kb', 'Mb', 'Gb'] : ['B', 'KB', 'MB', 'GB']

  let idx = 0
  let scaled = v
  while (scaled >= unitBase && idx < unitLabel.length - 1) {
    scaled /= unitBase
    idx++
  }
  return `${scaled.toFixed(1)} ${unitLabel[idx]}`
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let idx = 0
  let val = bytes
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024
    idx++
  }
  return `${val.toFixed(1)} ${units[idx]}`
}

function initChart(el) {
  if (!el) return null
  try {
    // Try to import echarts from window first (loaded via vue-echarts or CDN)
    const echarts = window.echarts
    if (echarts) {
      echartsInstance = echarts
      const chart = echarts.init(el, 'dark')
      charts.push(chart)
      return chart
    }
  } catch (e) {
    console.warn('ECharts not available on window:', e)
  }
  return null
}

function getOrCreateChart(el) {
  if (!el) return null
  // Find existing chart instance
  const existing = charts.find(c => c && c.getDom() === el)
  if (existing) return existing

  try {
    const echarts = window.echarts
    if (!echarts) return null
    const chart = echarts.init(el, 'dark')
    charts.push(chart)
    return chart
  } catch (e) {
    console.warn('Failed to init chart:', e)
    return null
  }
}

function updateNetChart() {
  const chart = getOrCreateChart(netChart.value)
  if (!chart || netHistory.value.length < 2) return

  const useBits = netChartUnit.value === 'bps'
  const multiplier = useBits ? 8 : 1
  const unitLabel = useBits ? 'bps' : 'B/s'

  const times = netHistory.value.map(p => p.time)
  const uploadData = netHistory.value.map(p => [p.time, p.upload * multiplier])
  const downloadData = netHistory.value.map(p => [p.time, p.download * multiplier])

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => formatBps(v / multiplier) + '/s',
    },
    legend: { show: true, bottom: 0, textStyle: { fontSize: 10 } },
    grid: { top: 10, right: 10, bottom: 30, left: 55 },
    xAxis: {
      type: 'time',
      axisLabel: { fontSize: 10, formatter: { type: 'time', template: 'HH:mm:ss' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, formatter: (v) => formatBps(v / multiplier) },
      name: unitLabel,
      nameTextStyle: { fontSize: 10 },
    },
    series: [
      {
        name: '下载',
        type: 'line',
        smooth: true,
        data: downloadData,
        lineStyle: { color: '#409EFF', width: 2 },
        areaStyle: { color: 'rgba(64,158,255,0.15)' },
        showSymbol: false,
      },
      {
        name: '上传',
        type: 'line',
        smooth: true,
        data: uploadData,
        lineStyle: { color: '#67C23A', width: 2 },
        areaStyle: { color: 'rgba(103,194,58,0.15)' },
        showSymbol: false,
      },
    ],
  })
}

function updateSysChart() {
  const chart = getOrCreateChart(sysChart.value)
  if (!chart || sysHistory.value.length < 2) return

  const cpuData = sysHistory.value.map(p => [p.time, p.cpu])
  const memData = sysHistory.value.map(p => [p.time, p.mem])

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => v.toFixed(1) + '%',
    },
    legend: { show: true, bottom: 0, textStyle: { fontSize: 10 } },
    grid: { top: 10, right: 10, bottom: 30, left: 55 },
    xAxis: {
      type: 'time',
      axisLabel: { fontSize: 10, formatter: { type: 'time', template: 'HH:mm:ss' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { fontSize: 10, formatter: '{value}%' },
    },
    series: [
      {
        name: 'CPU',
        type: 'line',
        smooth: true,
        data: cpuData,
        lineStyle: { color: '#e6a23c', width: 2 },
        areaStyle: { color: 'rgba(230,162,60,0.15)' },
        showSymbol: false,
      },
      {
        name: '内存',
        type: 'line',
        smooth: true,
        data: memData,
        lineStyle: { color: '#67C23A', width: 2 },
        areaStyle: { color: 'rgba(103,194,58,0.15)' },
        showSymbol: false,
      },
    ],
  })
}

async function fetchData() {
  if (paused.value) return
  loading.value = true
  try {
    // Get aggregated real-time data
    const res = await api.get('/monitor/traffic-realtime')
    currentData.value = res.data

    const now = Date.now()
    // Add to history
    netHistory.value.push({
      time: now,
      upload: res.data.upload_bps || 0,
      download: res.data.download_bps || 0,
    })
    sysHistory.value.push({
      time: now,
      cpu: res.data.cpu_percent || 0,
      mem: res.data.memory_percent || 0,
    })

    // Trim to max points
    if (netHistory.value.length > MAX_POINTS) {
      netHistory.value = netHistory.value.slice(-MAX_POINTS)
    }
    if (sysHistory.value.length > MAX_POINTS) {
      sysHistory.value = sysHistory.value.slice(-MAX_POINTS)
    }

    // Update charts
    updateNetChart()
    updateSysChart()

    // Also fetch per-interface speeds
    const ifaceRes = await api.get('/monitor/network/traffic')
    const ifaceData = ifaceRes.data.interfaces || {}
    // Get raw byte counters for total
    const rawRes = await api.get('/monitor/realtime')
    const netInterfaces = rawRes.data.network || []

    interfaceRates.value = Object.entries(ifaceData).map(([name, data]) => {
      const rawIface = netInterfaces.find(i => i.name === name) || {}
      return {
        name,
        rx: data.rx_bytes_sec || 0,
        tx: data.tx_bytes_sec || 0,
        rx_total: rawIface.rx_bytes || 0,
        tx_total: rawIface.tx_bytes || 0,
      }
    }).sort((a, b) => (b.rx + b.tx) - (a.rx + a.tx))

  } catch (e) {
    // Silently handle polling errors
  }
  loading.value = false
}

function togglePause() {
  paused.value = !paused.value
}

function handleResize() {
  charts.forEach(c => c?.resize())
}

onMounted(async () => {
  await nextTick()
  // Ensure echarts is available
  try {
    if (!window.echarts) {
      const echarts = await import('echarts')
      window.echarts = echarts
    }
  } catch (e) {
    console.error('Failed to load ECharts:', e)
    ElMessage.error('图表库加载失败，请刷新页面重试')
    return
  }
  await fetchData()
  // Initialize charts
  updateNetChart()
  updateSysChart()
  // Start polling every 2 seconds
  timer = setInterval(fetchData, 2000)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  charts.forEach(c => c?.dispose())
  charts = []
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.traffic-realtime { padding: 0; }
.stat-card { text-align: center; }
.stat-label { font-size: 12px; color: #888; margin-bottom: 4px; }
.stat-value { font-size: 22px; font-weight: 600; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
