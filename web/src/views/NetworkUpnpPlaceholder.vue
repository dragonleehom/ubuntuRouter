<template>
  <div class="upnp-page">
    <div class="page-header">
      <h2>UPnP 端口转发</h2>
      <div class="header-actions">
        <el-switch
          v-model="upnpEnabled"
          active-text="启用"
          inactive-text="禁用"
          @change="toggleUpnp"
          :loading="toggling"
        />
        <el-button size="small" @click="fetchRules" :loading="loading">
          <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 状态卡片 -->
    <el-row :gutter="16" class="status-row">
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" :class="serviceStatus.running ? 'green' : 'red'">
            {{ serviceStatus.running ? '运行中' : '已停止' }}
          </div>
          <div class="stat-label">UPnP 服务</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ rules.length }}</div>
          <div class="stat-label">转发规则</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" :class="serviceStatus.enabled ? 'green' : 'gray'">
            {{ serviceStatus.enabled ? '开机自启' : '手动启动' }}
          </div>
          <div class="stat-label">启动方式</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 规则列表 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>端口转发规则</span>
          <el-button type="primary" size="small" @click="showAddDialog = true">
            <el-icon style="margin-right:4px"><Plus /></el-icon>添加规则
          </el-button>
        </div>
      </template>
      <el-table :data="rules" stripe size="small" v-loading="loading">
        <el-table-column prop="external_port" label="外部端口" width="120" />
        <el-table-column prop="internal_ip" label="内网 IP" width="160" />
        <el-table-column prop="internal_port" label="内部端口" width="120" />
        <el-table-column prop="protocol" label="协议" width="80" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="deleteRule(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && rules.length === 0" description="暂无规则" />
    </el-card>

    <!-- 添加规则对话框 -->
    <el-dialog v-model="showAddDialog" title="添加端口转发" width="450px">
      <el-form :model="newRule" label-width="100px" size="small">
        <el-form-item label="外部端口" required>
          <el-input-number v-model="newRule.external_port" :min="1" :max="65535" style="width:100%" />
        </el-form-item>
        <el-form-item label="内网 IP" required>
          <el-input v-model="newRule.internal_ip" placeholder="如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="内部端口" required>
          <el-input-number v-model="newRule.internal_port" :min="1" :max="65535" style="width:100%" />
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="newRule.protocol" style="width:100%">
            <el-option label="TCP" value="TCP" />
            <el-option label="UDP" value="UDP" />
            <el-option label="TCP+UDP" value="BOTH" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newRule.description" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addRule" :loading="adding">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { api } from '@/stores'

const loading = ref(false)
const toggling = ref(false)
const adding = ref(false)
const rules = ref([])
const upnpEnabled = ref(false)
const showAddDialog = ref(false)
const serviceStatus = reactive({ running: false, enabled: false })
const newRule = reactive({
  external_port: 8080,
  internal_ip: '',
  internal_port: 80,
  protocol: 'TCP',
  description: '',
})

onMounted(fetchRules)

async function fetchRules() {
  loading.value = true
  try {
    const [statusRes, rulesRes] = await Promise.all([
      api.get('/upnp/status'),
      api.get('/upnp/rules'),
    ])
    Object.assign(serviceStatus, statusRes.data)
    upnpEnabled.value = statusRes.data.enabled
    rules.value = rulesRes.data.rules || []
  } catch {
    ElMessage.error('获取 UPnP 数据失败')
  }
  loading.value = false
}

async function toggleUpnp(val) {
  toggling.value = true
  try {
    if (val) {
      await api.post('/upnp/enable')
      ElMessage.success('UPnP 已启用')
    } else {
      await api.post('/upnp/disable')
      ElMessage.success('UPnP 已禁用')
    }
    await fetchRules()
  } catch (e) {
    upnpEnabled.value = !val
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
  toggling.value = false
}

async function addRule() {
  if (!newRule.internal_ip.trim()) { ElMessage.warning('请输入内网 IP'); return }
  adding.value = true
  try {
    const res = await api.post('/upnp/rules', { ...newRule })
    ElMessage.success(res.data.message)
    showAddDialog.value = false
    newRule.internal_ip = ''
    newRule.description = ''
    await fetchRules()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  }
  adding.value = false
}

async function deleteRule(row) {
  try {
    await ElMessageBox.confirm(`确定删除端口 ${row.external_port} 的转发规则？`, '确认')
    await api.delete(`/upnp/rules/${row.id}`)
    ElMessage.success('规则已删除')
    await fetchRules()
  } catch { /* cancelled */ }
}
</script>

<style scoped>
.upnp-page { padding: 0; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0; color: #e0e0e0; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.status-row { margin-bottom: 16px; }
.stat-card {
  background: #141414;
  border: 1px solid #222;
  text-align: center;
}
.stat-value { font-size: 22px; font-weight: 700; color: #409EFF; }
.stat-value.green { color: #67C23A; }
.stat-value.red { color: #F56C6C; }
.stat-value.gray { color: #909399; }
.stat-label { font-size: 13px; color: #888; margin-top: 4px; }
.section-card {
  background: #141414;
  border: 1px solid #222;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
