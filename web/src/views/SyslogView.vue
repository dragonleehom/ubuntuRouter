<template>
  <div class="page">
    <div class="page-header">
      <h2>系统日志</h2>
    </div>

    <!-- 控制栏 -->
    <el-card class="controls-card">
      <div class="controls-row">
        <div class="control-group">
          <span class="control-label">日志来源</span>
          <el-select v-model="logSource" size="small" style="width: 180px" @change="fetchLogs">
            <el-option label="系统日志 (journalctl)" value="journal" />
            <el-option label="内核日志 (dmesg)" value="kernel" />
            <el-option label="防火墙日志" value="firewall" />
          </el-select>
        </div>

        <div class="control-group" v-if="logSource === 'journal'">
          <span class="control-label">服务</span>
          <el-select v-model="selectedService" size="small" style="width: 160px" @change="fetchLogs">
            <el-option label="ubunturouter" value="ubunturouter" />
            <el-option label="dnsmasq" value="dnsmasq" />
            <el-option label="nftables" value="nftables" />
            <el-option label="ssh" value="ssh" />
            <el-option label="systemd-networkd" value="systemd-networkd" />
            <el-option label="systemd-timesyncd" value="systemd-timesyncd" />
            <el-option label="全部日志" value="all" />
          </el-select>
        </div>

        <div class="control-group">
          <span class="control-label">行数</span>
          <el-select v-model="logLines" size="small" style="width: 100px" @change="fetchLogs">
            <el-option label="50" :value="50" />
            <el-option label="100" :value="100" />
            <el-option label="200" :value="200" />
            <el-option label="500" :value="500" />
          </el-select>
        </div>

        <div class="control-group">
          <span class="control-label">关键字</span>
          <el-input
            v-model="searchKeyword"
            size="small"
            style="width: 180px"
            placeholder="搜索高亮..."
            clearable
          />
        </div>

        <div class="control-group">
          <el-button size="small" type="primary" @click="fetchLogs" :icon="'Refresh'">
            刷新
          </el-button>
        </div>

        <div class="control-group">
          <el-switch
            v-model="autoRefresh"
            size="small"
            active-text="自动刷新"
            inactive-text=""
          />
          <span v-if="autoRefresh" class="auto-refresh-hint">每 5 秒</span>
        </div>
      </div>
    </el-card>

    <!-- 日志内容 -->
    <el-card class="log-card">
      <template #header>
        <div class="log-header">
          <span>日志输出 ({{ logLines }} 行)</span>
          <el-tag v-if="loading" type="warning" size="small">加载中...</el-tag>
          <el-tag v-else-if="logTimestamp" type="info" size="small">{{ logTimestamp }}</el-tag>
        </div>
      </template>

      <div class="log-container" ref="logContainerRef">
        <div v-if="loading" class="log-loading">
          <el-skeleton :rows="10" animated />
        </div>
        <div v-else-if="logLinesData.length === 0" class="log-empty">
          <el-empty description="暂无日志" />
        </div>
        <pre v-else class="log-content" v-html="highlightedLog"></pre>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { api } from '@/stores'

const logSource = ref('journal')
const selectedService = ref('ubunturouter')
const logLines = ref(50)
const searchKeyword = ref('')
const autoRefresh = ref(false)

const logLinesData = ref([])
const loading = ref(false)
const logTimestamp = ref('')
const logContainerRef = ref(null)

let refreshTimer = null

const highlightedLog = computed(() => {
  const lines = logLinesData.value
  const keyword = searchKeyword.value.trim()
  if (!keyword) return lines.map(l => escapeHtml(l)).join('\n')

  const escapedKeyword = escapeHtml(keyword)
  return lines.map(line => {
    const escaped = escapeHtml(line)
    return escaped.replace(
      new RegExp(`(${escapeRegex(escapedKeyword)})`, 'gi'),
      '<mark class="highlight">$1</mark>'
    )
  }).join('\n')
})

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

onMounted(async () => {
  await fetchLogs()
})

watch(autoRefresh, (val) => {
  if (val) {
    refreshTimer = setInterval(fetchLogs, 5000)
  } else {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})

async function fetchLogs() {
  loading.value = true
  logTimestamp.value = new Date().toLocaleTimeString()

  try {
    let res
    if (logSource.value === 'kernel') {
      res = await api.get('/system/logs/kernel', { params: { lines: logLines.value } })
    } else if (logSource.value === 'firewall') {
      res = await api.get('/system/logs/firewall', { params: { lines: logLines.value } })
    } else {
      // journal
      const params = { lines: logLines.value }
      if (selectedService.value !== 'all') {
        params.service = selectedService.value
      }
      res = await api.get('/system/logs', { params })
    }
    logLinesData.value = res.data.lines.filter(l => l.trim() !== '')
  } catch (e) {
    console.error('获取日志失败:', e)
    logLinesData.value = [`错误: ${e.response?.data?.detail || e.message}`]
  }

  loading.value = false
  await nextTick()
  // Scroll to bottom
  if (logContainerRef.value) {
    logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
  }
}
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; color: #e0e0e0; }
.controls-card { margin-bottom: 16px; }
.controls-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
}
.control-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.control-label {
  color: #888;
  font-size: 13px;
  white-space: nowrap;
}
.auto-refresh-hint {
  color: #666;
  font-size: 12px;
  margin-left: 4px;
}
.log-card { margin-bottom: 20px; }
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.log-container {
  max-height: 600px;
  overflow-y: auto;
  background: #1a1a2e;
  border-radius: 6px;
  padding: 0;
}
.log-content {
  margin: 0;
  padding: 12px 16px;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #c9d1d9;
  white-space: pre;
  overflow-x: auto;
}
.log-content :deep(.highlight) {
  background: rgba(255, 235, 59, 0.3);
  color: #ffd54f;
  border-radius: 2px;
  padding: 0 2px;
}
.log-loading { padding: 16px; }
.log-empty { padding: 40px; }
</style>
