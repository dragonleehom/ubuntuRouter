<template>
    <div class="dashboard">
    <!-- 拓扑图面板 (全宽) -->
    <div class="panel panel-topo">
      <div class="panel-header">
        <el-icon><Connection /></el-icon>
        <span>网络拓扑</span>
      </div>
      <div class="panel-body" style="padding:0;">
        <NetTopo />
      </div>
    </div>

    <div class="dashboard-grid">
      <!-- 面板一：网络拓扑 + 通道状态 + 流量仪表 -->
      <div class="panel panel-network">
        <div class="panel-header">
          <el-icon><Connection /></el-icon>
          <span>网络状态</span>
        </div>
        <div class="panel-body">
          <div v-if="loading" class="loading">
            <el-skeleton :rows="4" animated />
          </div>
          <div v-else-if="!status" class="empty">
            <el-empty description="无法获取网络状态" />
          </div>
          <div v-else>
            <!-- 接口列表 -->
            <div class="iface-list">
              <div
                v-for="iface in status.interfaces"
                :key="iface.name"
                class="iface-item"
              >
                <div class="iface-name">
                  <el-tag
                    :type="iface.state === 'UP' ? 'success' : 'danger'"
                    size="small"
                    effect="dark"
                  >
                    {{ iface.state }}
                  </el-tag>
                  <span>{{ iface.name }}</span>
                </div>
                <div class="iface-info">
                  <span v-if="iface.ipv4 && iface.ipv4.length">
                    {{ iface.ipv4[0] }}
                  </span>
                  <span v-else class="text-muted">无 IP</span>
                  <span v-if="iface.speed" class="speed">{{ iface.speed }}M</span>
                </div>
              </div>
            </div>

            <!-- 配置概览 -->
            <div v-if="status.config" class="config-summary">
              <div class="config-row">
                <span class="label">LAN 网关</span>
                <span class="value">192.168.21.1</span>
              </div>
              <div class="config-row" v-if="status.config.dhcp">
                <span class="label">DHCP</span>
                <span class="value">{{ status.config.dhcp.range }}</span>
              </div>
              <div class="config-row">
                <span class="label">接口数</span>
                <span class="value">{{ (status.config.interfaces || []).length }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 面板二：CPU/内存/磁盘/运行时间 -->
      <div class="panel panel-system">
        <div class="panel-header">
          <el-icon><Monitor /></el-icon>
          <span>系统资源</span>
        </div>
        <div class="panel-body">
          <div v-if="loading" class="loading">
            <el-skeleton :rows="4" animated />
          </div>
          <div v-else-if="!status?.system" class="empty">
            <el-empty description="无法获取系统信息" />
          </div>
          <div v-else class="system-stats">
            <!-- CPU -->
            <div class="stat-item">
              <div class="stat-label">
                <el-icon><Cpu /></el-icon>
                <span>CPU</span>
              </div>
              <div class="stat-bar">
                <el-progress
                  :percentage="Math.round(status.system.cpu_usage || 0)"
                  :stroke-width="12"
                  :format="() => `${Math.round(status.system.cpu_usage || 0)}%`"
                />
              </div>
            </div>

            <!-- 内存 -->
            <div class="stat-item" v-if="status.system.memory">
              <div class="stat-label">
                <el-icon><Coin /></el-icon>
                <span>内存</span>
              </div>
              <div class="stat-bar">
                <el-progress
                  :percentage="memPercent"
                  :stroke-width="12"
                  :format="() => `${status.system.memory.used_mb}MB / ${status.system.memory.total_mb}MB`"
                />
              </div>
            </div>

            <!-- 磁盘 -->
            <div class="stat-item" v-if="status.system.disk">
              <div class="stat-label">
                <el-icon><Folder /></el-icon>
                <span>磁盘</span>
              </div>
              <div class="stat-bar">
                <el-progress
                  :percentage="diskPercent"
                  :stroke-width="12"
                  :format="() => `${status.system.disk.usage_percent}`"
                />
              </div>
            </div>

            <!-- 运行时间 -->
            <div class="stat-item">
              <div class="stat-label">
                <el-icon><Timer /></el-icon>
                <span>运行时间</span>
              </div>
              <span class="stat-value">{{ uptimeText }}</span>
            </div>

            <!-- 温度 -->
            <div class="stat-item" v-if="status.system.temperature_c">
              <div class="stat-label">
                <el-icon><Sunny /></el-icon>
                <span>温度</span>
              </div>
              <span class="stat-value">{{ status.system.temperature_c }}°C</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 面板三：应用/服务状态 -->
      <div class="panel panel-apps">
        <div class="panel-header">
          <el-icon><Grid /></el-icon>
          <span>服务状态</span>
        </div>
        <div class="panel-body">
          <div v-if="loading" class="loading">
            <el-skeleton :rows="4" animated />
          </div>
          <div v-else-if="!status?.apps" class="empty">
            <el-empty description="无法获取服务状态" />
          </div>
          <div v-else class="app-list">
            <div
              v-for="app in status.apps"
              :key="app.name"
              class="app-card"
            >
              <div class="app-status">
                <el-tag
                  :type="app.active ? 'success' : 'danger'"
                  size="small"
                  effect="dark"
                  round
                >
                  {{ app.active ? '运行中' : '已停止' }}
                </el-tag>
              </div>
              <div class="app-name">{{ app.name }}</div>
              <div class="app-actions">
                <el-button
                  size="small"
                  :type="app.active ? 'warning' : 'success'"
                  @click="toggleService(app)"
                >
                  {{ app.active ? '停止' : '启动' }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDashboardStore } from '@/stores'
import {
  Connection, Monitor, Grid, Cpu, Coin, Folder, Timer, Sunny,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '@/stores'
import NetTopo from '@/components/NetTopo.vue'

const store = useDashboardStore()
const loading = ref(false)
const status = ref(null)
let timer = null

const memPercent = computed(() => {
  if (!status.value?.system?.memory) return 0
  const m = status.value.system.memory
  return Math.round((m.used_mb / m.total_mb) * 100)
})

const diskPercent = computed(() => {
  if (!status.value?.system?.disk) return 0
  const d = status.value.system.disk
  const pct = d.usage_percent?.replace('%', '')
  return parseInt(pct) || 0
})

const uptimeText = computed(() => {
  const sec = status.value?.system?.uptime_seconds || 0
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const parts = []
  if (d > 0) parts.push(`${d}天`)
  if (h > 0) parts.push(`${h}小时`)
  parts.push(`${m}分钟`)
  return parts.join(' ')
})

async function fetchData() {
  loading.value = true
  try {
    const res = await api.get('/dashboard/status')
    status.value = res.data
  } catch (e) {
    console.error('获取数据失败:', e)
  }
  loading.value = false
}

async function toggleService(app) {
  const action = app.active ? 'stop' : 'start'
  try {
    await api.post(`/system/service/${app.name}/${action}`)
    ElMessage.success(`${app.name} ${action === 'start' ? '启动' : '停止'}成功`)
    await fetchData()
  } catch (e) {
    ElMessage.error(`${app.name} 操作失败: ${e.response?.data?.detail || e.message}`)
  }
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
@media (max-width: 767px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
.panel {
  background: #141414;
  border-radius: 12px;
  border: 1px solid #222;
  overflow: hidden;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  border-bottom: 1px solid #222;
  font-size: 15px;
  color: #ccc;
}
@media (max-width: 767px) {
  .panel-header { padding: 12px 16px; font-size: 14px; }
}
.panel-body {
  padding: 16px 20px;
}
@media (max-width: 767px) {
  .panel-body { padding: 12px 14px; }
}
.panel-network {
  grid-row: span 1;
}
.panel-apps {
  grid-column: 1;
}
@media (max-width: 767px) {
  .panel-apps { grid-column: auto; }
}
.panel-topo {
  grid-column: 1 / -1;
  margin-bottom: 16px;
}
@media (max-width: 767px) {
  .panel-topo { margin-bottom: 12px; }
}
.panel-system {
  grid-row: span 2;
}
@media (max-width: 767px) {
  .panel-system { grid-row: auto; }
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
  padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}
.iface-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.iface-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #999;
  font-size: 13px;
}
.speed {
  color: #409EFF;
  font-size: 12px;
}

/* 系统统计 */
.system-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.stat-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #999;
}
.stat-value {
  font-size: 14px;
  color: #e0e0e0;
}

/* 应用卡片 */
.app-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.app-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}
.app-name {
  flex: 1;
  margin-left: 12px;
  font-size: 14px;
  color: #ccc;
}

.loading {
  padding: 20px;
}
.empty {
  padding: 20px;
}
.text-muted {
  color: #666;
}
.config-summary {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #222;
}
.config-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}
.config-row .label {
  color: #888;
}
.config-row .value {
  color: #ccc;
}
</style>
