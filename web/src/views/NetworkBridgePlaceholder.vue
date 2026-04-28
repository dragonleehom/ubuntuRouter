<template>
  <div class="page">
    <div class="page-header">
      <h2>桥接 & Bond</h2>
      <div class="header-actions">
        <el-button size="small" @click="fetchData">刷新</el-button>
        <el-button type="primary" size="small" @click="showAddBridge=true">
          <el-icon style="margin-right:4px"><Plus /></el-icon>创建桥接
        </el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <!-- Linux Bridge -->
      <el-tab-pane label="Linux Bridge" name="bridge">
        <el-card shadow="never" class="section-card">
          <template #header><span>桥接接口</span></template>
          <el-table :data="bridges" stripe size="small" v-loading="loading">
            <el-table-column prop="name" label="名称" width="120" />
            <el-table-column prop="ports" label="成员端口" min-width="200">
              <template #default="{ row }">{{ (row.ports || []).join(', ') || '-' }}</template>
            </el-table-column>
            <el-table-column prop="ip" label="IP 地址" width="160" class="hide-mobile" />
            <el-table-column prop="mac" label="MAC" width="160" class="hide-mobile" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.running ? 'success' : 'info'" size="small">{{ row.running ? 'UP' : 'DOWN' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="deleteBridge(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && bridges.length === 0" description="暂无桥接" />
        </el-card>
      </el-tab-pane>

      <!-- Bonding -->
      <el-tab-pane label="Bonding" name="bond">
        <el-card shadow="never" class="section-card">
          <template #header><span>Bond 接口</span></template>
          <el-table :data="bonds" stripe size="small" v-loading="loading">
            <el-table-column prop="name" label="名称" width="120" />
            <el-table-column prop="mode" label="模式" width="140">
              <template #default="{ row }">{{ bondModeLabel(row.mode) }}</template>
            </el-table-column>
            <el-table-column prop="slaves" label="成员" min-width="200">
              <template #default="{ row }">{{ (row.slaves || []).join(', ') || '-' }}</template>
            </el-table-column>
            <el-table-column prop="ip" label="IP" width="160" class="hide-mobile" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.running ? 'success' : 'info'" size="small">{{ row.running ? 'UP' : 'DOWN' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="deleteBond(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && bonds.length === 0" description="暂无 Bond" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建桥接 -->
    <el-dialog v-model="showAddBridge" title="创建桥接" width="450px">
      <el-form :model="newBridge" label-width="100px" size="small">
        <el-form-item label="名称"><el-input v-model="newBridge.name" placeholder="如 br0" /></el-form-item>
        <el-form-item label="成员端口">
          <el-select v-model="newBridge.ports" multiple placeholder="选择成员接口">
            <el-option v-for="iface in availableIfaces" :key="iface" :label="iface" :value="iface" />
          </el-select>
        </el-form-item>
        <el-form-item label="IP 地址"><el-input v-model="newBridge.ip" placeholder="如 192.168.10.1/24 (可选)" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddBridge=false">取消</el-button>
        <el-button type="primary" @click="createBridge">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { api } from '@/stores'

const activeTab = ref('bridge')
const loading = ref(false)
const bridges = ref([])
const bonds = ref([])
const availableIfaces = ref([])
const showAddBridge = ref(false)
const newBridge = reactive({ name: 'br0', ports: [], ip: '' })

function bondModeLabel(mode) {
  const modes = { '0': 'balance-rr', '1': 'active-backup', '2': 'balance-xor', '3': 'broadcast', '4': '802.3ad (LACP)', '5': 'balance-tlb', '6': 'balance-alb' }
  return modes[mode] || mode
}

async function fetchData() {
  loading.value = true
  try {
    const [bridgeRes, bondRes, ifaceRes] = await Promise.all([
      api.get('/system/bridge').catch(() => ({ data: { bridges: [] } })),
      api.get('/system/bond').catch(() => ({ data: { bonds: [] } })),
      api.get('/system/interfaces').catch(() => ({ data: { interfaces: [] } })),
    ])
    bridges.value = bridgeRes.data.bridges || []
    bonds.value = bondRes.data.bonds || []
    availableIfaces.value = (ifaceRes.data.interfaces || []).filter(i => !i.startsWith('br') && !i.startsWith('bond'))
  } catch { /* ignore */ }
  loading.value = false
}

async function createBridge() {
  try {
    await api.post('/system/bridge', newBridge)
    ElMessage.success('桥接已创建')
    showAddBridge.value = false
    await fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') }
}

async function deleteBridge(row) {
  try {
    await ElMessageBox.confirm(`确定删除桥接 ${row.name}？`, '确认')
    await api.delete(`/system/bridge/${row.name}`)
    ElMessage.success('已删除')
    await fetchData()
  } catch { /* cancelled */ }
}

async function deleteBond(row) {
  try {
    await ElMessageBox.confirm(`确定删除 Bond ${row.name}？`, '确认')
    await api.delete(`/system/bond/${row.name}`)
    ElMessage.success('已删除')
    await fetchData()
  } catch { /* cancelled */ }
}

onMounted(fetchData)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { color: #e0e0e0; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.section-card { background: #141414; border: 1px solid #222; }
</style>
