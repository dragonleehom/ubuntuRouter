<template>
  <div class="diag-page">
    <h2>网络诊断</h2>

    <el-row :gutter="16">
      <!-- 诊断工具选择 -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><span>诊断工具</span></template>
          <el-menu :default-active="activeTool" @select="onToolSelect" style="border-right: none">
            <el-menu-item index="ping"><el-icon><Connection /></el-icon><span>Ping</span></el-menu-item>
            <el-menu-item index="traceroute"><el-icon><Connection /></el-icon><span>Traceroute</span></el-menu-item>
            <el-menu-item index="nslookup"><el-icon><Connection /></el-icon><span>DNS 查询</span></el-menu-item>
            <el-menu-item index="mtr"><el-icon><Connection /></el-icon><span>MTR</span></el-menu-item>
            <el-menu-item index="tcpcheck"><el-icon><Connection /></el-icon><span>TCP 端口检测</span></el-menu-item>
            <el-menu-item index="curl"><el-icon><Connection /></el-icon><span>HTTP 检测</span></el-menu-item>
          </el-menu>
        </el-card>
      </el-col>

      <!-- 输入参数 -->
      <el-col :span="16">
        <el-card shadow="hover" style="margin-bottom: 16px">
          <template #header><span>{{ toolTitle }}</span></template>
          <el-form :model="form" label-width="100px" inline>
            <el-form-item label="目标" required>
              <el-input v-model="form.target" :placeholder="targetPlaceholder" style="width: 300px" @keyup.enter="runDiagnostic" />
            </el-form-item>
            <el-form-item v-if="activeTool === 'ping'" label="次数">
              <el-input-number v-model="form.count" :min="1" :max="100" :step="1" />
            </el-form-item>
            <el-form-item v-if="activeTool === 'mtr'" label="次数">
              <el-input-number v-model="form.count" :min="3" :max="100" :step="1" />
            </el-form-item>
            <el-form-item v-if="activeTool === 'tcpcheck'" label="端口" required>
              <el-input-number v-model="form.port" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item v-if="activeTool === 'nslookup'" label="DNS 服务器">
              <el-input v-model="form.dnsServer" placeholder="留空=系统默认" style="width: 200px" />
            </el-form-item>
            <el-form-item v-if="activeTool === 'curl'" label="URL" style="width: 100%">
              <el-input v-model="form.target" placeholder="https://example.com" />
            </el-form-item>
          </el-form>
          <el-button type="primary" @click="runDiagnostic" :loading="running" :disabled="!form.target">
            执行
          </el-button>
        </el-card>

        <!-- 结果输出 -->
        <el-card shadow="hover">
          <template #header>
            <span>诊断结果</span>
            <el-button v-if="result" text size="small" @click="copyResult" style="float: right">
              复制
            </el-button>
          </template>
          <div class="result-container" ref="resultRef">
            <div v-if="!result" class="result-placeholder">选择工具并执行诊断...</div>
            <div v-for="(line, i) in resultLines" :key="i" class="result-line">{{ line }}</div>
            <div v-if="running" class="result-line running">执行中...</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { api } from '@/stores'
import { Connection } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const activeTool = ref('ping')
const running = ref(false)
const result = ref(null)
const resultLines = ref([])
const resultRef = ref(null)
let pollTimer = null

const form = ref({
  target: '',
  count: 4,
  port: 80,
  dnsServer: '',
})

const toolTitle = computed(() => {
  const map = {
    ping: 'Ping', traceroute: 'Traceroute', nslookup: 'DNS 查询',
    mtr: 'MTR', tcpcheck: 'TCP 端口检测', curl: 'HTTP 检测',
  }
  return map[activeTool.value] || '诊断工具'
})

const targetPlaceholder = computed(() => {
  const map = {
    ping: 'IP 或主机名 (如 8.8.8.8)',
    traceroute: 'IP 或主机名 (如 google.com)',
    nslookup: '域名 (如 google.com)',
    mtr: 'IP 或主机名 (如 google.com)',
    tcpcheck: 'IP 或主机名',
    curl: 'URL',
  }
  return map[activeTool.value] || '目标'
})

function onToolSelect(tool) {
  activeTool.value = tool
  result.value = null
  resultLines.value = []
  form.value.target = ''
  form.value.port = 80
  form.value.count = 4
  form.value.dnsServer = ''
  if (tool === 'curl') form.value.target = 'https://'
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function getEndpoint() {
  const map = { ping: '/diag/ping', traceroute: '/diag/traceroute', nslookup: '/diag/nslookup', mtr: '/diag/mtr', tcpcheck: '/diag/tcpcheck', curl: '/diag/curl' }
  return map[activeTool.value]
}

function getPayload() {
  const p = { target: form.value.target, timeout: 30 }
  if (activeTool.value === 'ping') p.count = form.value.count
  if (activeTool.value === 'mtr') { p.count = form.value.count; p.timeout = 60 }
  if (activeTool.value === 'tcpcheck') { p.host = form.value.target; p.port = form.value.port; delete p.target }
  if (activeTool.value === 'nslookup') { p.domain = form.value.target; p.dns_server = form.value.dnsServer || null; delete p.target }
  if (activeTool.value === 'curl') { p.url = form.value.target; delete p.target }
  return p
}

async function runDiagnostic() {
  if (!form.value.target) { ElMessage.warning('请输入目标'); return }
  if (activeTool.value === 'tcpcheck' && !form.value.port) { ElMessage.warning('请输入端口'); return }

  running.value = true
  resultLines.value = []
  result.value = null

  try {
    const res = await api.post(getEndpoint(), getPayload())
    const taskId = res.data.task_id

    // Poll for result
    pollTimer = setInterval(async () => {
      try {
        const r = await api.get(`/diag/result/${taskId}`)
        resultLines.value = r.data.lines || []
        if (!r.data.running) {
          clearInterval(pollTimer)
          pollTimer = null
          running.value = false
          result.value = r.data
        }
      } catch {
        clearInterval(pollTimer)
        pollTimer = null
        running.value = false
      }
    }, 1000)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '诊断失败')
    running.value = false
  }
}

function copyResult() {
  if (!resultLines.value.length) return
  const text = resultLines.value.join('\n')
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制')
  }).catch(() => {
    ElMessage.warning('复制失败')
  })
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.diag-page { padding: 0; }
.result-container { max-height: 500px; overflow-y: auto; background: #111; padding: 12px; border-radius: 4px; font-family: monospace; font-size: 12px; min-height: 200px; }
.result-placeholder { color: #555; font-family: sans-serif; font-size: 14px; text-align: center; padding: 40px; }
.result-line { padding: 1px 0; color: #ccc; white-space: pre-wrap; word-break: break-all; }
.result-line.running { color: #409EFF; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.3; } }
</style>
