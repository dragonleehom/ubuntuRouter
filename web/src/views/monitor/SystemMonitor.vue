<template>
  <div class="monitor-page">
    <h2>系统监控</h2>

    <!-- 状态卡片 -->
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
          <template #header><span>CPU 使用率 (%)</span></template>
          <div ref="cpuChart" style="height: 200px"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" style="margin-bottom: 12px">
        <el-card shadow="hover">
          <template #header><span>内存使用率 (%)</span></template>
          <div ref="memChart" style="height: 200px"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" style="margin-bottom: 12px">
        <el-card shadow="hover">
          <template #header><span>网络流量 (KB/s)</span></template>
          <div ref="netChart" style="height: 200px"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" style="margin-bottom: 12px">
        <el-card shadow="hover">
          <template #header><span>温度 (°C)</span></template>
          <div ref="tempChart" style="height: 200px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 进程列表 -->
    <el-card shadow="hover" style="margin-top: 12px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>进程 (Top 20 by CPU)</span>
          <el-button size="small" @click="fetchProcesses" :loading="procLoading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-table :data="processes" stripe size="small" max-height="400" v-loading="procLoading">
        <el-table-column prop="pid" label="PID" width="70" class-name="hide-xs" />
        <el-table-column prop="user" label="用户" width="80" class-name="hide-mobile" />
        <el-table-column prop="cpu_pct" label="CPU%" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.cpu_pct > 50 ? '#e6a23c' : '#ccc' }">{{ row.cpu_pct }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="mem_pct" label="MEM%" width="80" class-name="hide-xs" />
        <el-table-column prop="rss_mb" label="RSS (MB)" width="100" class-name="hide-mobile" />
        <el-table-column prop="command" label="命令" min-width="200">
          <template #default="{ row }">
            <span class="cmd-text">{{ row.command }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { api } from '@/stores'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const cpuChart = ref(null)
const memChart = ref(null)
const netChart = ref(null)
const tempChart = ref(null)
const realtime = ref(null)
const processes = ref([])
const procLoading = ref(false)

let charts = []
let timer = null

const statCards = computed(() => {
  const s = realtime.value
  if (!s) return []
  return [
    { label: 'CPU', value: s.cpu ? `${s.cpu.usage_pct.toFixed(1)}%` : '--', color: '#409EFF' },
    { label: '内存', value: s.memory ? `${s.memory.usage_pct.toFixed(1)}%` : '--', color: '#67C23A' },
    { label: '温度', value: s.temperature?.[0] ? `${s.temperature[0].temp_c.toFixed(1)}°C` : '--', color: '#e6a23c' },
    { label: '运行时间', value: formatUptime(s.uptime_seconds), color: '#ccc' },
  ]
})

function formatUptime(sec) {
  if (!sec) return '--'
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  let s = ''
  if (d > 0) s += `${d}d `
  s += `${h}h ${m}m`
  return s
}

function initChart(el) {
  if (!el) return null
  const echarts = window.echarts
  if (!echarts) return null
  const chart = echarts.init(el, 'dark')
  charts.push(chart)
  return chart
}

function updateCpuChart(usage) {
  const chart = initChart(cpuChart.value)
  if (!chart) return
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', max: 100, axisLabel: { fontSize: 10, formatter: '{value}%' } },
    series: [{
      type: 'line', smooth: true, data: usage || [],
      lineStyle: { color: '#409EFF', width: 2 },
      areaStyle: { color: 'rgba(64,158,255,0.1)' },
      showSymbol: false,
    }],
  })
}

function updateMemChart(usage) {
  const chart = initChart(memChart.value)
  if (!chart) return
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', max: 100, axisLabel: { fontSize: 10, formatter: '{value}%' } },
    series: [{
      type: 'line', smooth: true, data: usage || [],
      lineStyle: { color: '#67C23A', width: 2 },
      areaStyle: { color: 'rgba(103,194,58,0.1)' },
      showSymbol: false,
    }],
  })
}

function updateNetChart(data) {
  const chart = initChart(netChart.value)
  if (!chart) return
  const series = Object.entries(data || {}).map(([name, vals], i) => ({
    name, type: 'line', smooth: true, data: vals.map(v => [v[0], v[1] / 1024]),
    lineStyle: { width: 1.5 }, showSymbol: false,
  }))
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { show: true, type: 'scroll', bottom: 0, textStyle: { fontSize: 10 } },
    grid: { top: 10, right: 10, bottom: 30, left: 45 },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: '{value} KB/s' } },
    series,
  })
}

function updateTempChart(data) {
  const chart = initChart(tempChart.value)
  if (!chart) return
  const series = Object.entries(data || {}).map(([name, vals], i) => ({
    name, type: 'line', smooth: true, data: vals,
    lineStyle: { width: 1.5 }, showSymbol: false,
  }))
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { show: true, bottom: 0, textStyle: { fontSize: 10 } },
    grid: { top: 10, right: 10, bottom: 30, left: 45 },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: '{value}°C' } },
    series,
  })
}

async function fetchRealtime() {
  try {
    const res = await api.get('/monitor/realtime')
    realtime.value = res.data
  } catch (e) { /* ignore polling errors */ }
}

async function fetchHistory() {
  try {
    const [cpuRes, memRes, netRes, tempRes] = await Promise.all([
      api.get('/monitor/history', { params: { metric: 'cpu', range: '1h' } }),
      api.get('/monitor/history', { params: { metric: 'memory', range: '1h' } }),
      api.get('/monitor/network/traffic'),
      api.get('/monitor/history', { params: { metric: 'temperature', range: '1h' } }),
    ])
    updateCpuChart(cpuRes.data.data)
    updateMemChart(memRes.data.data)
    updateNetChart(netRes.data)
    updateTempChart(tempRes.data)
  } catch (e) { /* ignore */ }
}

async function fetchProcesses() {
  procLoading.value = true
  try {
    const res = await api.get('/monitor/processes')
    processes.value = (res.data.processes || []).slice(0, 20)
  } catch (e) { ElMessage.error('获取进程列表失败') }
  procLoading.value = false
}

function handleResize() {
  charts.forEach(c => c?.resize())
}

onMounted(async () => {
  await nextTick()
  await fetchRealtime()
  await fetchHistory()
  await fetchProcesses()
  timer = setInterval(async () => {
    await fetchRealtime()
  }, 5000)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  charts.forEach(c => c?.dispose())
  charts = []
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.monitor-page { padding: 0; }
.stat-card { text-align: center; }
.stat-label { font-size: 12px; color: #888; margin-bottom: 4px; }
.stat-value { font-size: 22px; font-weight: 600; }
.cmd-text {
  display: inline-block;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
