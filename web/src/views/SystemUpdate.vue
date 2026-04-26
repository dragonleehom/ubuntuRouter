<template>
  <div class="ota-page">
    <div class="page-header">
      <h2>系统升级</h2>
      <p class="page-desc">检查系统更新、升级软件包和管理系统版本</p>
    </div>

    <!-- 当前版本卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card shadow="never" class="version-card">
          <div class="version-label">当前版本</div>
          <div class="version-value">{{ currentVersion }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="version-card">
          <div class="version-label">可升级包</div>
          <div class="version-value upgrade-count" :class="{ 'has-updates': checkResult.count > 0 }">
            {{ checkResult.count }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="version-card">
          <div class="version-label">最后检查</div>
          <div class="version-value last-check">{{ lastCheckTime || '尚未检查' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作区 -->
    <el-card shadow="never" style="margin-bottom: 20px">
      <div class="action-bar">
        <el-button type="primary" @click="checkUpdates" :loading="checking" :disabled="upgrading">
          <el-icon><Refresh /></el-icon> 检查更新
        </el-button>
        <el-button @click="runAptUpdate" :loading="updating" :disabled="checking || upgrading">
          <el-icon><Refresh /></el-icon> 刷新包索引
        </el-button>
        <el-button
          type="warning"
          @click="runUpgrade"
          :loading="upgrading"
          :disabled="checking || updating || checkResult.count === 0"
        >
          <el-icon><Top /></el-icon> 升级全部 ({{ checkResult.count }})
        </el-button>
      </div>
    </el-card>

    <!-- 升级输出日志 -->
    <el-card v-if="upgradeOutput.length" shadow="never" style="margin-bottom: 20px">
      <template #header>
        <div class="card-header">
          <span>升级输出</span>
          <el-button size="small" text @click="upgradeOutput = []">清空</el-button>
        </div>
      </template>
      <div class="log-viewer" ref="logViewer">
        <div v-for="(line, i) in upgradeOutput" :key="i" class="log-line"
          :class="{ 'log-error': line.startsWith('E:'), 'log-warn': line.startsWith('W:') }">
          {{ line }}
        </div>
      </div>
    </el-card>

    <!-- 可升级包列表 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>可升级软件包</span>
          <el-tag v-if="checkResult.count" type="warning" size="small">{{ checkResult.count }} 个</el-tag>
        </div>
      </template>

      <el-table
        :data="checkResult.upgradable"
        stripe
        v-loading="checking"
        max-height="400"
        style="width: 100%"
      >
        <el-table-column prop="package" label="软件包" min-width="300" />
        <el-table-column prop="version" label="可用版本" width="200" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="upgradeSingle(row.package)">
              升级
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!checking && checkResult.count === 0" description="系统已是最新" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { api } from '@/stores'
import { Refresh, Top } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const currentVersion = ref('0.1.0')
const checkResult = ref({ upgradable: [], count: 0 })
const checking = ref(false)
const updating = ref(false)
const upgrading = ref(false)
const lastCheckTime = ref('')
const upgradeOutput = ref([])
const logViewer = ref(null)

onMounted(() => {
  // 从 /system/status 获取版本号
  api.get('/system/status').then(res => {
    currentVersion.value = res.data.os?.version || '0.1.0'
  }).catch(() => {})
})

function appendLog(lines) {
  if (Array.isArray(lines)) {
    upgradeOutput.value.push(...lines)
  }
  nextTick(() => {
    if (logViewer.value) {
      logViewer.value.scrollTop = logViewer.value.scrollHeight
    }
  })
}

async function checkUpdates() {
  checking.value = true
  try {
    const res = await api.get('/system/upgrade/check')
    checkResult.value = res.data
    currentVersion.value = res.data.current_version || currentVersion.value
    lastCheckTime.value = new Date().toLocaleString('zh-CN')
    if (res.data.count > 0) {
      ElMessage.info(`发现 ${res.data.count} 个可升级包`)
    } else {
      ElMessage.success('系统已是最新')
    }
  } catch (e) {
    ElMessage.error('检查更新失败: ' + (e.response?.data?.detail || e.message))
  }
  checking.value = false
}

async function runAptUpdate() {
  updating.value = true
  appendLog(['>>> apt update 开始...'])
  try {
    const res = await api.post('/system/upgrade/apt-update')
    if (res.data.stdout) appendLog(res.data.stdout)
    if (res.data.stderr) appendLog(res.data.stderr)
    if (res.data.success) {
      ElMessage.success('包索引刷新完成')
    } else {
      ElMessage.warning('apt update 返回非零状态码')
    }
  } catch (e) {
    ElMessage.error('刷新失败: ' + (e.response?.data?.detail || e.message))
    appendLog([`错误: ${e.message}`])
  }
  updating.value = false
  appendLog(['>>> apt update 完成'])
  // 自动检查可升级包
  await checkUpdates()
}

async function runUpgrade() {
  if (checkResult.value.count === 0) {
    ElMessage.info('没有可升级的包')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将升级 ${checkResult.value.count} 个软件包，此操作可能需要几分钟，是否继续？`,
      '确认升级',
      { confirmButtonText: '升级', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  upgrading.value = true
  appendLog([`>>> 开始升级 ${checkResult.value.count} 个软件包...`])
  try {
    const res = await api.post('/system/upgrade/run')
    if (res.data.stdout) appendLog(res.data.stdout)
    if (res.data.stderr) appendLog(res.data.stderr)
    if (res.data.success) {
      ElMessage.success('升级完成')
    } else {
      ElMessage.warning('升级返回非零状态码，请查看输出日志')
    }
  } catch (e) {
    ElMessage.error('升级失败: ' + (e.response?.data?.detail || e.message))
    appendLog([`错误: ${e.message}`])
  }
  upgrading.value = false
  appendLog(['>>> 升级完成'])

  // 重新检查
  await checkUpdates()
}

async function upgradeSingle(pkg) {
  try {
    await ElMessageBox.confirm(`确认升级 ${pkg}？`, '确认')
  } catch {
    return
  }
  appendLog([`>>> 升级 ${pkg}...`])
  try {
    const res = await api.post('/apt/install', { packages: [pkg] })
    if (res.data.stdout) appendLog(res.data.stdout)
    ElMessage.success(`${pkg} 升级完成`)
  } catch (e) {
    ElMessage.error(`${pkg} 升级失败`)
    appendLog([`${pkg} 错误: ${e.message}`])
  }
  await checkUpdates()
}
</script>

<style scoped>
.ota-page { padding: 0; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px 0; color: #e0e0e0; }
.page-desc { margin: 0; font-size: 13px; color: #888; }

.version-card { text-align: center; padding: 8px; }
.version-label { font-size: 13px; color: #888; margin-bottom: 8px; }
.version-value { font-size: 28px; font-weight: 700; color: #e0e0e0; }
.upgrade-count { color: #409EFF; }
.upgrade-count.has-updates { color: #E6A23C; }
.last-check { font-size: 14px; font-weight: 400; color: #999; }

.action-bar { display: flex; gap: 12px; flex-wrap: wrap; }

.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header span { font-weight: 500; }

.log-viewer {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 16px;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.log-line { color: #a0a0b0; white-space: pre-wrap; word-break: break-all; }
.log-error { color: #f56c6c; }
.log-warn { color: #e6a23c; }
</style>
