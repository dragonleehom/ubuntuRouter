<template>
  <div class="monitor-page">
    <h2>系统监控</h2>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="系统概览" name="overview">
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

        <!-- 进程列表 (Top 20) -->
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
      </el-tab-pane>

      <el-tab-pane label="进程列表" name="processes">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
              <span>共 <strong>{{ processCount }}</strong> 个进程</span>
              <div style="display: flex; align-items: center; gap: 8px">
                <el-input
                  v-model="processSearch"
                  placeholder="搜索进程名或 PID"
                  size="small"
                  clearable
                  style="width: 220px"
                  @input="filterProcesses"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>
                <el-button size="small" @click="fetchFullProcesses" :loading="fullProcLoading">
                  <el-icon><Refresh /></el-icon> 刷新
                </el-button>
              </div>
            </div>
          </template>
          <el-table
            :data="filteredProcesses"
            stripe
            size="small"
            max-height="600"
            v-loading="fullProcLoading"
            @expand-change="onProcessExpand"
            :row-class-name="tableRowClassName"
          >
            <el-table-column type="expand" width="1">
              <template #default="{ row }">
                <div class="process-detail">
                  <div class="detail-row">
                    <span class="detail-label">完整命令:</span>
                    <code class="detail-value">{{ row.command || row.cmdline || '--' }}</code>
                  </div>
                  <el-row :gutter="16" style="margin-top: 8px">
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">PID:</span>
                        <span class="detail-value">{{ row.pid }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">PPID:</span>
                        <span class="detail-value">{{ row.ppid ?? '--' }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">用户:</span>
                        <span class="detail-value">{{ row.user }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">状态:</span>
                        <el-tag :type="stateTagType(row.state)" size="small">{{ row.state }}</el-tag>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">CPU:</span>
                        <span class="detail-value">{{ row.cpu != null ? row.cpu + '%' : '--' }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">内存:</span>
                        <span class="detail-value">{{ row.memory != null ? row.memory + '%' : '--' }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">RSS:</span>
                        <span class="detail-value">{{ formatBytes(row.rss) }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">VSZ:</span>
                        <span class="detail-value">{{ formatBytes(row.vsz) }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="detail-row">
                        <span class="detail-label">优先级:</span>
                        <span class="detail-value">{{ row.nice ?? row.priority ?? '--' }}</span>
                      </div>
                    </el-col>
                  </el-row>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="pid" label="PID" width="80" sortable />
            <el-table-column prop="name" label="名称" min-width="120">
              <template #default="{ row }">
                <span class="proc-name">{{ row.name || truncateName(row.command) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="cpu" label="CPU%" width="80" sortable>
              <template #default="{ row }">
                <span :style="{ color: row.cpu > 50 ? '#e6a23c' : '#ccc' }">{{ row.cpu != null ? row.cpu + '%' : '--' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="memory" label="内存%" width="80" sortable>
              <template #default="{ row }">
                <span :style="{ color: row.memory > 50 ? '#f56c6c' : '#ccc' }">{{ row.memory != null ? row.memory + '%' : '--' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="state" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="stateTagType(row.state)" size="small" effect="dark">
                  {{ row.state || '--' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="user" label="用户" width="90" />
            <el-table-column prop="rss" label="RSS" width="90" sortable>
              <template #default="{ row }">
                <span>{{ formatBytes(row.rss) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="vsz" label="VSZ" width="90" sortable>
              <template #default="{ row }">
                <span>{{ formatBytes(row.vsz) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="command" label="命令行" min-width="200">
              <template #default="{ row }">
                <span class="cmd-text">{{ row.command || row.cmdline || '--' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { api } from '@/stores'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const activeTab = ref('overview')

const cpuChart = ref(null)
const memChart = ref(null)
const netChart = ref(null)
const tempChart = ref(null)
const realtime = ref(null)
const processes = ref([])
const procLoading = ref(false)

// Process list tab state
const fullProcesses = ref([])
const filteredProcesses = ref([])
const fullProcLoading = ref(false)
const processSearch = ref('')
const processCount = computed(() => fullProcesses.value.length)

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

function formatBytes(kb) {
  if (kb == null) return '--'
  if (kb < 1024) return kb + ' KB'
  if (kb < 1024 * 1024) return (kb / 1024).toFixed(1) + ' MB'
  return (kb / 1024 / 1024).toFixed(2) + ' GB'
}

function truncateName(cmd) {
  if (!cmd) return '--'
  return cmd.split(' ')[0].split('/').pop().substring(0, 30)
}

function stateTagType(state) {
  if (!state) return 'info'
  const s = state.toUpperCase()
  if (s === 'R') return 'success'
  if (s === 'S') return 'info'
  if (s === 'D') return 'warning'
  if (s === 'Z') return 'danger'
  if (s === 'T') return 'info'
  return 'info'
}

function tableRowClassName({ row }) {
  if (row.state === 'Z') return 'zombie-row'
  return ''
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

function filterProcesses() {
  const q = processSearch.value.trim().toLowerCase()
  if (!q) {
    filteredProcesses.value = [...fullProcesses.value]
    return
  }
  filteredProcesses.value = fullProcesses.value.filter(p => {
    const pidMatch = String(p.pid).includes(q)
    const nameMatch = (p.name || '').toLowerCase().includes(q)
    const cmdMatch = (p.command || p.cmdline || '').toLowerCase().includes(q)
    return pidMatch || nameMatch || cmdMatch
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

async function fetchFullProcesses() {
  fullProcLoading.value = true
  try {
    const res = await fetch('/api/v1/monitor/processes')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    fullProcesses.value = data.processes || []
    filteredProcesses.value = [...fullProcesses.value]
  } catch (e) {
    ElMessage.error('获取进程列表失败: ' + (e.message || e))
  }
  fullProcLoading.value = false
}

async function onProcessExpand(row, expanded) {
  if (!expanded) return
  // Optionally fetch single process detail
  try {
    const res = await fetch(`/api/v1/monitor/processes/${row.pid}`)
    if (res.ok) {
      const data = await res.json()
      Object.assign(row, data)
    }
  } catch (e) { /* ignore */ }
}

function onTabChange(tab) {
  if (tab === 'processes') {
    fetchFullProcesses()
  }
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
.proc-name {
  font-weight: 500;
  color: #e0e0e0;
}
.process-detail {
  padding: 12px 16px;
  background: rgba(255,255,255,0.02);
  border-radius: 6px;
}
.detail-row {
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.detail-label {
  font-size: 12px;
  color: #888;
  white-space: nowrap;
  min-width: 70px;
}
.detail-value {
  font-size: 13px;
  color: #ccc;
  word-break: break-all;
}
.detail-value code {
  font-size: 12px;
  background: rgba(255,255,255,0.06);
  padding: 2px 8px;
  border-radius: 4px;
  color: #a0c4ff;
}
:deep(.zombie-row) {
  background-color: rgba(245,108,108,0.08) !important;
}
:deep(.el-table__body tr.zombie-row:hover > td) {
  background-color: rgba(245,108,108,0.15) !important;
}
:deep(.el-tabs__item) {
  color: #888;
  font-size: 14px;
}
:deep(.el-tabs__item.is-active) {
  color: #409EFF;
  font-weight: 600;
}
:deep(.el-tabs__header) {
  margin-bottom: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
</style>
