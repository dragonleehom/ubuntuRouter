<template>
  <div class="docker-networks">
    <div class="toolbar">
      <el-button type="primary" size="small" @click="refreshNetworks" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
      <el-button size="small" type="success" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 创建网络
      </el-button>
      <el-button size="small" type="danger" text @click="pruneNetworks" :loading="pruning">
        清理未使用网络
      </el-button>
    </div>

    <el-table :data="networks" stripe style="width: 100%" v-loading="loading"
      highlight-current-row empty-text="暂无 Docker 网络">
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="driver" label="驱动" width="100" />
      <el-table-column label="子网" width="160" class="hide-mobile">
        <template #default="{ row }">
          {{ row.ipam?.subnet || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="网关" width="160" class="hide-mobile">
        <template #default="{ row }">
          {{ row.ipam?.gateway || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="内部" width="70" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.internal" type="warning" size="small">是</el-tag>
          <span v-else class="text-muted">否</span>
        </template>
      </el-table-column>
      <el-table-column prop="containers" label="容器数" width="80" align="center" />
      <el-table-column prop="scope" label="范围" width="80" class="hide-mobile" />
      <el-table-column label="创建时间" min-width="160" class="hide-mobile">
        <template #default="{ row }">
          {{ row.created ? formatTime(row.created) : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="danger" @click="removeNetwork(row)"
            :disabled="row.name === 'bridge' || row.name === 'host' || row.name === 'none'">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建网络弹窗 -->
    <el-dialog v-model="showCreateDialog" title="创建 Docker 网络" width="520px">
      <el-form :model="createForm" label-width="90px" size="small">
        <el-form-item label="网络名称" required>
          <el-input v-model="createForm.name" placeholder="my_network" />
        </el-form-item>
        <el-form-item label="驱动">
          <el-select v-model="createForm.driver" style="width:100%">
            <el-option label="bridge" value="bridge" />
            <el-option label="overlay" value="overlay" />
            <el-option label="macvlan" value="macvlan" />
            <el-option label="ipvlan" value="ipvlan" />
          </el-select>
        </el-form-item>
        <el-form-item label="子网">
          <el-input v-model="createForm.subnet" placeholder="172.20.0.0/24 (可选)" />
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="createForm.gateway" placeholder="172.20.0.1 (可选)" />
        </el-form-item>
        <el-form-item label="IP 范围">
          <el-input v-model="createForm.ip_range" placeholder="172.20.0.0/24 (可选)" />
        </el-form-item>
        <el-form-item label="内部网络">
          <el-switch v-model="createForm.internal" />
          <span class="form-hint">启用后容器无法访问外部网络</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="showCreateDialog = false">取消</el-button>
        <el-button size="small" type="primary" @click="doCreateNetwork" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const pruning = ref(false)
const networks = ref([])
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  driver: 'bridge',
  subnet: '',
  gateway: '',
  ip_range: '',
  internal: false,
})

onMounted(() => { refreshNetworks() })

async function refreshNetworks() {
  loading.value = true
  try {
    const res = await api.get('/containers/networks')
    networks.value = res.data.networks || []
  } catch (e) {
    ElMessage.error('获取网络列表失败')
  }
  loading.value = false
}

async function doCreateNetwork() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入网络名称')
    return
  }
  creating.value = true
  try {
    const payload = {
      name: createForm.value.name.trim(),
      driver: createForm.value.driver,
      internal: createForm.value.internal,
    }
    if (createForm.value.subnet) payload.subnet = createForm.value.subnet
    if (createForm.value.gateway) payload.gateway = createForm.value.gateway
    if (createForm.value.ip_range) payload.ip_range = createForm.value.ip_range
    await api.post('/containers/networks', payload)
    ElMessage.success(`网络 '${payload.name}' 创建成功`)
    showCreateDialog.value = false
    createForm.value = { name: '', driver: 'bridge', subnet: '', gateway: '', ip_range: '', internal: false }
    await refreshNetworks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建网络失败')
  }
  creating.value = false
}

async function removeNetwork(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除网络 "${row.name}"？\n如果有容器正在使用此网络，删除将失败。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete(`/containers/networks/${row.name}`)
    ElMessage.success(`网络 '${row.name}' 已删除`)
    await refreshNetworks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function pruneNetworks() {
  try {
    await ElMessageBox.confirm('确认清理所有未使用的 Docker 网络？', '确认', { type: 'warning' })
    pruning.value = true
    await api.post('/containers/networks/prune')
    ElMessage.success('未使用的网络已清理')
    await refreshNetworks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '清理失败')
  }
  pruning.value = false
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return ts
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.text-muted {
  color: #999;
}
.form-hint {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}
</style>
