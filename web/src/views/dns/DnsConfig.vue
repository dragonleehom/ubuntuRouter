<template>
  <div class="dns-page">
    <h2>DNS 管理</h2>

    <!-- 状态卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">服务状态</div>
            <div class="stat-value">
              <el-tag :type="status.running ? 'success' : 'danger'" size="large">
                {{ status.running ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">端口</div>
            <div class="stat-value small">{{ status.port || '-' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">缓存大小</div>
            <div class="stat-value small">{{ status.cache?.size || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">命中/未命中</div>
            <div class="stat-value small">{{ status.cache?.hits || 0 }} / {{ status.cache?.misses || 0 }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div class="toolbar">
      <el-button @click="flushCache" :loading="flushing">
        <el-icon><Refresh /></el-icon> 刷新缓存
      </el-button>
      <el-button @click="fetchAll" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 转发规则 -->
      <el-tab-pane label="转发规则" name="forwards">
        <div style="margin-bottom: 12px">
          <el-button type="primary" size="small" @click="showForwardDialog = true">
            <el-icon><Plus /></el-icon> 添加转发
          </el-button>
        </div>
        <el-table :data="forwards" stripe v-loading="loading">
          <el-table-column prop="domain" label="域名" min-width="250" />
          <el-table-column prop="target" label="目标 DNS" min-width="200" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="removeForward(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && forwards.length === 0" description="暂无转发规则" />
      </el-tab-pane>

      <!-- 重写规则 -->
      <el-tab-pane label="重写规则" name="rewrites">
        <div style="margin-bottom: 12px">
          <el-button type="primary" size="small" @click="showRewriteDialog = true">
            <el-icon><Plus /></el-icon> 添加重写
          </el-button>
        </div>
        <el-table :data="rewrites" stripe v-loading="loading">
          <el-table-column prop="domain" label="域名" min-width="250" />
          <el-table-column prop="ip" label="返回 IP" min-width="200" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="removeRewrite(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && rewrites.length === 0" description="暂无重写规则" />
      </el-tab-pane>

      <!-- /etc/hosts -->
      <el-tab-pane label="Hosts" name="hosts">
        <div style="margin-bottom: 12px">
          <el-button type="primary" size="small" @click="showHostDialog = true">
            <el-icon><Plus /></el-icon> 添加 Host
          </el-button>
        </div>
        <el-table :data="hosts" stripe v-loading="loading">
          <el-table-column prop="ip" label="IP" width="160" />
          <el-table-column prop="hostnames" label="主机名" min-width="300">
            <template #default="{ row }">
              <el-tag v-for="h in row.hostnames" :key="h" size="small" style="margin-right: 4px">{{ h }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="removeHost(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && hosts.length === 0" description="仅显示自定义 hosts" />
      </el-tab-pane>

      <!-- 查询日志 -->
      <el-tab-pane label="查询日志" name="logs">
        <div style="margin-bottom: 12px">
          <el-select v-model="logLines" style="width: 120px; margin-right: 12px">
            <el-option :value="50" label="50 条" />
            <el-option :value="100" label="100 条" />
            <el-option :value="200" label="200 条" />
          </el-select>
          <el-button @click="fetchLogs">刷新日志</el-button>
        </div>
        <div class="log-container">
          <div v-for="(line, i) in logs" :key="i" class="log-line">{{ line }}</div>
          <el-empty v-if="logs.length === 0" description="无 DNS 日志" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加转发对话框 -->
    <el-dialog v-model="showForwardDialog" title="添加 DNS 转发" width="450px">
      <el-form label-width="100px">
        <el-form-item label="域名" required>
          <el-input v-model="forwardForm.domain" placeholder="example.com" />
        </el-form-item>
        <el-form-item label="目标 DNS" required>
          <el-input v-model="forwardForm.target" placeholder="8.8.8.8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForwardDialog = false">取消</el-button>
        <el-button type="primary" @click="addForward" :loading="saving">添加</el-button>
      </template>
    </el-dialog>

    <!-- 添加重写对话框 -->
    <el-dialog v-model="showRewriteDialog" title="添加 DNS 重写" width="450px">
      <el-form label-width="100px">
        <el-form-item label="域名" required>
          <el-input v-model="rewriteForm.domain" placeholder="example.com" />
        </el-form-item>
        <el-form-item label="返回 IP" required>
          <el-input v-model="rewriteForm.ip" placeholder="127.0.0.1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRewriteDialog = false">取消</el-button>
        <el-button type="primary" @click="addRewrite" :loading="saving">添加</el-button>
      </template>
    </el-dialog>

    <!-- 添加 Host 对话框 -->
    <el-dialog v-model="showHostDialog" title="添加 Host" width="450px">
      <el-form label-width="100px">
        <el-form-item label="IP" required>
          <el-input v-model="hostForm.ip" placeholder="192.168.1.100" />
        </el-form-item>
        <el-form-item label="主机名" required>
          <el-input v-model="hostForm.hostname" placeholder="myhost.local" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showHostDialog = false">取消</el-button>
        <el-button type="primary" @click="addHost" :loading="saving">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const flushing = ref(false)
const saving = ref(false)
const activeTab = ref('forwards')
const status = ref({ running: false, cache: {} })
const forwards = ref([])
const rewrites = ref([])
const hosts = ref([])
const logs = ref([])
const logLines = ref(50)

const showForwardDialog = ref(false)
const showRewriteDialog = ref(false)
const showHostDialog = ref(false)
const forwardForm = ref({ domain: '', target: '' })
const rewriteForm = ref({ domain: '', ip: '' })
const hostForm = ref({ ip: '', hostname: '' })

async function fetchStatus() {
  try {
    const res = await api.get('/dns/status')
    status.value = res.data
  } catch { /* ignore */ }
}
async function fetchForwards() {
  try {
    const res = await api.get('/dns/forwards')
    forwards.value = res.data.forwards || []
  } catch { ElMessage.error('获取转发规则失败') }
}
async function fetchRewrites() {
  try {
    const res = await api.get('/dns/rewrites')
    rewrites.value = res.data.rewrites || []
  } catch { ElMessage.error('获取重写规则失败') }
}
async function fetchHosts() {
  try {
    const res = await api.get('/dns/hosts')
    hosts.value = res.data.hosts || []
  } catch { ElMessage.error('获取 hosts 失败') }
}
async function fetchLogs() {
  try {
    const res = await api.get('/dns/logs', { params: { lines: logLines.value } })
    logs.value = res.data.logs || []
  } catch { ElMessage.error('获取日志失败') }
}
async function fetchAll() {
  loading.value = true
  await Promise.all([fetchStatus(), fetchForwards(), fetchRewrites(), fetchHosts()])
  await fetchLogs()
  loading.value = false
}

async function flushCache() {
  flushing.value = true
  try {
    const res = await api.post('/dns/flush-cache')
    ElMessage.success(res.data.message || '缓存已刷新')
    await fetchStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '刷新失败')
  }
  flushing.value = false
}

async function addForward() {
  if (!forwardForm.value.domain || !forwardForm.value.target) { ElMessage.warning('请填写完整'); return }
  saving.value = true
  try {
    const res = await api.post('/dns/forwards', forwardForm.value)
    ElMessage.success(res.data.message || '添加成功')
    showForwardDialog.value = false
    forwardForm.value = { domain: '', target: '' }
    await fetchForwards()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
  saving.value = false
}

async function removeForward(row) {
  try {
    await ElMessageBox.confirm(`确认删除转发规则 "${row.domain} → ${row.target}"？`, '确认')
    await api.delete('/dns/forwards', { data: { domain: row.domain, target: row.target } })
    ElMessage.success('已删除')
    await fetchForwards()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

async function addRewrite() {
  if (!rewriteForm.value.domain || !rewriteForm.value.ip) { ElMessage.warning('请填写完整'); return }
  saving.value = true
  try {
    const res = await api.post('/dns/rewrites', rewriteForm.value)
    ElMessage.success(res.data.message || '添加成功')
    showRewriteDialog.value = false
    rewriteForm.value = { domain: '', ip: '' }
    await fetchRewrites()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
  saving.value = false
}

async function removeRewrite(row) {
  try {
    await ElMessageBox.confirm(`确认删除重写规则 "${row.domain} → ${row.ip}"？`, '确认')
    await api.delete('/dns/rewrites', { data: { domain: row.domain, ip: row.ip } })
    ElMessage.success('已删除')
    await fetchRewrites()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

async function addHost() {
  if (!hostForm.value.ip || !hostForm.value.hostname) { ElMessage.warning('请填写完整'); return }
  saving.value = true
  try {
    const res = await api.post('/dns/hosts', hostForm.value)
    ElMessage.success(res.data.message || '添加成功')
    showHostDialog.value = false
    hostForm.value = { ip: '', hostname: '' }
    await fetchHosts()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
  saving.value = false
}

async function removeHost(row) {
  try {
    await ElMessageBox.confirm(`确认删除 Host "${row.ip} → ${row.hostnames?.join(', ')}"？`, '确认')
    const hostname = row.hostnames?.[0] || ''
    await api.delete('/dns/hosts', { data: { ip: row.ip, hostname } })
    ElMessage.success('已删除')
    await fetchHosts()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

onMounted(fetchAll)
</script>

<style scoped>
.dns-page { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.stat-item { text-align: center; padding: 8px; }
.stat-label { font-size: 13px; color: #888; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #e0e0e0; }
.stat-value.small { font-size: 14px; }
.log-container { max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px; background: #111; padding: 12px; border-radius: 4px; }
.log-line { padding: 2px 0; color: #aaa; border-bottom: 1px solid #1a1a1a; white-space: pre-wrap; word-break: break-all; }
.log-line:hover { color: #e0e0e0; background: #1a1a1a; }
</style>
