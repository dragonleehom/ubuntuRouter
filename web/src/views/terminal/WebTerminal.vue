<template>
  <div class="terminal-page">
    <h2>Web 终端</h2>

    <!-- 状态 & 控制 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">服务状态</div>
            <div class="stat-value">
              <el-tag :type="info.running ? 'success' : 'danger'" size="large">
                {{ info.running ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">端口</div>
            <div class="stat-value small">{{ info.port || 7681 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">ttyd 状态</div>
            <div class="stat-value">
              <el-tag v-if="info.installed" type="success" size="small">已安装</el-tag>
              <el-tag v-else type="warning" size="small">未安装</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;">
      <el-button type="primary" @click="startTtyd" :disabled="info.running" :loading="starting">
        启动
      </el-button>
      <el-button type="danger" @click="stopTtyd" :disabled="!info.running" :loading="stopping">
        停止
      </el-button>
      <el-button @click="restartTtyd" :loading="restarting">重启</el-button>
      <el-button @click="fetchInfo" :loading="loading">刷新</el-button>
    </div>

    <!-- 未安装提示 -->
    <el-alert
      v-if="info.installed === false"
      title="ttyd 未安装"
      type="warning"
      description="请在终端中运行 apt install ttyd 安装后使用本功能"
      show-icon
      style="margin-bottom: 20px"
    />

    <!-- 终端 iframe -->
    <el-card v-if="info.running && info.url" shadow="hover" style="min-height: 500px">
      <template #header><span>终端</span></template>
      <iframe
        :src="info.url"
        style="width: 100%; height: 500px; border: none; border-radius: 4px;"
        title="Web Terminal"
        sandbox="allow-scripts allow-same-origin allow-forms"
      />
    </el-card>

    <el-card v-else shadow="hover">
      <el-empty description="终端未启动" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '@/stores'
import { ElMessage } from 'element-plus'

const info = reactive({
  installed: false,
  running: false,
  port: 7681,
  url: null,
})
const loading = ref(false)
const starting = ref(false)
const stopping = ref(false)
const restarting = ref(false)

async function fetchInfo() {
  loading.value = true
  try {
    const res = await api.get('/ttyd/info')
    Object.assign(info, res.data)
  } catch (e) {
    ElMessage.error('获取终端信息失败')
  }
  loading.value = false
}

async function startTtyd() {
  starting.value = true
  try {
    const res = await api.post('/ttyd/start')
    ElMessage.success(res.data.message || '启动成功')
    setTimeout(fetchInfo, 1500)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '启动失败')
  }
  starting.value = false
}

async function stopTtyd() {
  stopping.value = true
  try {
    const res = await api.post('/ttyd/stop')
    ElMessage.success(res.data.message || '已停止')
    setTimeout(fetchInfo, 1000)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '停止失败')
  }
  stopping.value = false
}

async function restartTtyd() {
  restarting.value = true
  try {
    const res = await api.post('/ttyd/restart')
    ElMessage.success(res.data.message || '重启成功')
    setTimeout(fetchInfo, 2000)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重启失败')
  }
  restarting.value = false
}

onMounted(fetchInfo)
</script>

<style scoped>
.terminal-page { padding: 0; }
.stat-item { text-align: center; padding: 8px; }
.stat-label { font-size: 13px; color: #888; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #e0e0e0; }
.stat-value.small { font-size: 14px; }
</style>
