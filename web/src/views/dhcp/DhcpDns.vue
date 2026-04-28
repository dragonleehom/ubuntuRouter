<template>
  <div class="page">
    <div class="page-header">
      <h2>DHCP / DNS</h2>
      <div class="header-actions">
        <el-button size="small" @click="refreshData">
          <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 状态概览 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" :class="status.active ? 'green' : 'red'">
            {{ status.active ? '运行中' : '已停止' }}
          </div>
          <div class="stat-label">服务状态</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ status.active_leases }}</div>
          <div class="stat-label">活跃租约</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ status.total_leases }}</div>
          <div class="stat-label">总租约</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ status.cached_entries || 'N/A' }}</div>
          <div class="stat-label">DNS 缓存</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tabs -->
    <el-card shadow="never" class="section-card">
      <el-tabs v-model="activeTab">
        <!-- DHCP 租约 -->
        <el-tab-pane label="DHCP 租约" name="leases">
          <el-table :data="leases" stripe size="small" v-loading="loading" max-height="500">
            <el-table-column prop="mac" label="MAC 地址" width="160" />
            <el-table-column prop="ip" label="IP 地址" width="140" />
            <el-table-column prop="hostname" label="主机名" min-width="150" />
            <el-table-column prop="expires" label="到期时间" width="180" class="hide-mobile" />
            <el-table-column label="状态" width="80" class="hide-mobile">
              <template #default="{ row }">
                <el-tag :type="row.remaining_seconds > 0 ? 'success' : 'info'" size="small">
                  {{ row.remaining_seconds > 0 ? '活跃' : '过期' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="releaseLease(row)">释放</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 静态绑定 -->
        <el-tab-pane label="静态绑定" name="static">
          <div class="toolbar">
            <el-button type="primary" size="small" @click="showAddStatic = true">
              <el-icon style="margin-right:4px"><Plus /></el-icon>添加静态绑定
            </el-button>
          </div>
          <el-table :data="staticLeases" stripe size="small" v-loading="loading" max-height="500">
            <el-table-column prop="mac" label="MAC 地址" width="160" />
            <el-table-column prop="ip" label="IP 地址" width="140" />
            <el-table-column prop="hostname" label="主机名" min-width="150" />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="deleteStaticLease(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="staticLeases.length === 0" description="暂无静态绑定" />
        </el-tab-pane>

        <!-- DHCP 池配置（多池） -->
        <el-tab-pane label="DHCP 池" name="pool">
          <div class="toolbar">
            <el-button type="primary" size="small" @click="openAddPoolDialog">
              <el-icon style="margin-right:4px"><Plus /></el-icon>添加 DHCP 池
            </el-button>
          </div>
          <el-table :data="pools" stripe size="small" v-loading="loading" max-height="500">
            <el-table-column label="启用" width="60">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" width="120" />
            <el-table-column label="IP 范围" min-width="200">
              <template #default="{ row }">
                {{ row.range_start }} - {{ row.range_end }}
              </template>
            </el-table-column>
            <el-table-column prop="subnet_mask" label="子网掩码" width="130" />
            <el-table-column prop="gateway" label="网关" width="140" />
            <el-table-column label="租约时间" width="100">
              <template #default="{ row }">
                {{ (row.lease_time / 3600).toFixed(0) }} 小时
              </template>
            </el-table-column>
            <el-table-column label="DNS" min-width="180">
              <template #default="{ row }">
                {{ (row.dns_servers || []).join(', ') }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="openEditPoolDialog(row)">编辑</el-button>
                <el-button text type="danger" size="small" @click="deletePool(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="pools.length === 0" description="暂无 DHCP 池" />
        </el-tab-pane>

        <!-- DNS -->
        <el-tab-pane label="DNS" name="dns">
          <div class="toolbar">
            <el-button size="small" type="warning" @click="flushDns">
              <el-icon style="margin-right:4px"><Delete /></el-icon>刷新 DNS 缓存
            </el-button>
          </div>

          <h4 style="color:#ccc;margin:16px 0 8px;">上游 DNS 服务器</h4>
          <div style="display:flex;gap:8px;margin-bottom:8px;">
            <el-input v-model="newUpstreamDns" placeholder="如 8.8.8.8" size="small" style="width:200px" />
            <el-button size="small" type="primary" @click="addUpstreamDns">添加上游</el-button>
          </div>
          <el-table :data="dnsConfig.upstream || []" stripe size="small">
            <el-table-column label="服务器">
              <template #default="{ row, $index }">
                <span>{{ row }}</span>
                <el-button text type="danger" size="small" style="margin-left:8px" @click="removeUpstreamDns($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <h4 style="color:#ccc;margin:16px 0 8px;">DNS 重写</h4>
          <div style="display:flex;gap:8px;margin-bottom:8px;">
            <el-input v-model="newRewrite.domain" placeholder="域名" size="small" style="width:200px" />
            <el-input v-model="newRewrite.ip" placeholder="IP 地址" size="small" style="width:150px" />
            <el-button size="small" type="primary" @click="addRewrite">添加重写</el-button>
          </div>
          <el-table :data="dnsConfig.rewrites || []" stripe size="small">
            <el-table-column label="重写规则">
              <template #default="{ row, $index }">
                <span>{{ row }}</span>
                <el-button text type="danger" size="small" style="margin-left:8px" @click="removeRewrite($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <h4 style="color:#ccc;margin:16px 0 8px;">DNS 查询</h4>
          <div style="display:flex;gap:8px;align-items:center;">
            <el-input v-model="dnsQuery" placeholder="输入域名" size="small" style="width:300px" />
            <el-button size="small" type="primary" @click="resolveDns">查询</el-button>
          </div>
          <div v-if="dnsResult" style="margin-top:8px;padding:8px 12px;background:rgba(255,255,255,0.03);border-radius:6px;">
            <code>{{ dnsResult }}</code>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 添加静态绑定对话框 -->
    <el-dialog v-model="showAddStatic" title="添加静态绑定" width="450px">
      <el-form :model="newStaticLease" label-width="100px" size="small">
        <el-form-item label="MAC 地址">
          <el-input v-model="newStaticLease.mac" placeholder="如 00:11:22:33:44:55" />
        </el-form-item>
        <el-form-item label="IP 地址">
          <el-input v-model="newStaticLease.ip" placeholder="如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="主机名">
          <el-input v-model="newStaticLease.hostname" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddStatic = false">取消</el-button>
        <el-button type="primary" @click="addStaticLease">添加</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑 DHCP 池对话框 -->
    <el-dialog v-model="showPoolDialog" :title="isEditingPool ? '编辑 DHCP 池' : '添加 DHCP 池'" width="550px">
      <el-form :model="poolForm" label-width="120px" size="small">
        <el-form-item label="名称">
          <el-input v-model="poolForm.name" placeholder="如 LAN 池" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="poolForm.enabled" />
        </el-form-item>
        <el-form-item label="起始 IP">
          <el-input v-model="poolForm.range_start" placeholder="如 192.168.21.50" />
        </el-form-item>
        <el-form-item label="结束 IP">
          <el-input v-model="poolForm.range_end" placeholder="如 192.168.21.200" />
        </el-form-item>
        <el-form-item label="子网掩码">
          <el-input v-model="poolForm.subnet_mask" placeholder="如 255.255.255.0" />
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="poolForm.gateway" placeholder="如 192.168.21.1" />
        </el-form-item>
        <el-form-item label="DNS 服务器">
          <el-select v-model="poolForm.dns_servers" multiple allow-create filterable
            default-first-option placeholder="输入 DNS 地址后回车" style="width:100%">
            <el-option v-for="dns in poolForm.dns_servers" :key="dns" :label="dns" :value="dns" />
          </el-select>
          <div style="font-size:12px;color:#888;margin-top:4px;">输入后回车添加，点击标签可删除</div>
        </el-form-item>
        <el-form-item label="租约时间">
          <el-input-number v-model="leaseHours" :min="1" :max="8760" size="small" style="width:160px" />
          <span style="margin-left:8px;color:#888;">小时</span>
        </el-form-item>
        <el-form-item label="域名">
          <el-input v-model="poolForm.domain" placeholder="可选，如 lan" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPoolDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingPool" @click="savePool">
          {{ isEditingPool ? '保存修改' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete, Plus } from '@element-plus/icons-vue'
import { api } from '@/stores'

const loading = ref(false)
const activeTab = ref('leases')
const showAddStatic = ref(false)
const savingPool = ref(false)

const leases = ref([])
const staticLeases = ref([])
const pools = ref([])
const pool = reactive({ configured: false })
const status = reactive({ active: false, enabled: false, active_leases: 0, total_leases: 0, cached_entries: 0 })
const dnsConfig = reactive({ upstream: [], rewrites: [], forwards: [] })
const dnsQuery = ref('')
const dnsResult = ref('')
const newUpstreamDns = ref('')
const newRewrite = reactive({ domain: '', ip: '' })
const newStaticLease = reactive({ mac: '', ip: '', hostname: '' })

// Pool dialog state
const showPoolDialog = ref(false)
const isEditingPool = ref(false)
const editingPoolId = ref('')
const poolForm = reactive({
  name: '',
  enabled: true,
  range_start: '',
  range_end: '',
  subnet_mask: '255.255.255.0',
  gateway: '',
  dns_servers: ['192.168.21.1'],
  lease_time: 86400,
  domain: '',
})
const leaseHours = computed({
  get: () => Math.round(poolForm.lease_time / 3600),
  set: (val) => { poolForm.lease_time = val * 3600 },
})

async function refreshData() {
  loading.value = true
  try {
    const [leasesRes, staticRes, poolRes, statusRes, dnsRes, poolsRes] = await Promise.all([
      api.get('/dhcp/leases'),
      api.get('/dhcp/static-leases'),
      api.get('/dhcp/pool'),
      api.get('/dhcp/status'),
      api.get('/dhcp/dns/config'),
      api.get('/dhcp/pools'),
    ])
    leases.value = leasesRes.data.leases || []
    staticLeases.value = staticRes.data.leases || []
    Object.assign(pool, poolRes.data)
    Object.assign(status, statusRes.data)
    Object.assign(dnsConfig, dnsRes.data)
    pools.value = poolsRes.data.pools || []
  } catch (e) {
    ElMessage.error('获取 DHCP/DNS 数据失败')
  }
  loading.value = false
}

async function releaseLease(row) {
  try {
    await api.post('/dhcp/leases/release', null, { params: { mac: row.mac } })
    ElMessage.success(`已释放 ${row.ip} 的租约`)
    await refreshData()
  } catch (e) {
    ElMessage.error('释放失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function addStaticLease() {
  try {
    await api.post('/dhcp/static-leases', newStaticLease)
    ElMessage.success('静态绑定已添加')
    showAddStatic.value = false
    newStaticLease.mac = ''
    newStaticLease.ip = ''
    newStaticLease.hostname = ''
    await refreshData()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteStaticLease(row) {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.mac} 的静态绑定？`, '确认')
    await api.delete('/dhcp/static-leases', { data: { mac: row.mac, ip: row.ip } })
    ElMessage.success('静态绑定已删除')
    await refreshData()
  } catch { /* cancelled */ }
}

// ─── Pool CRUD ──────────────────────────────────────────────

function openAddPoolDialog() {
  isEditingPool.value = false
  editingPoolId.value = ''
  poolForm.name = ''
  poolForm.enabled = true
  poolForm.range_start = ''
  poolForm.range_end = ''
  poolForm.subnet_mask = '255.255.255.0'
  poolForm.gateway = ''
  poolForm.dns_servers = ['192.168.21.1']
  poolForm.lease_time = 86400
  poolForm.domain = ''
  showPoolDialog.value = true
}

function openEditPoolDialog(row) {
  isEditingPool.value = true
  editingPoolId.value = row.id
  poolForm.name = row.name
  poolForm.enabled = row.enabled
  poolForm.range_start = row.range_start
  poolForm.range_end = row.range_end
  poolForm.subnet_mask = row.subnet_mask || '255.255.255.0'
  poolForm.gateway = row.gateway
  poolForm.dns_servers = [...(row.dns_servers || ['192.168.21.1'])]
  poolForm.lease_time = row.lease_time || 86400
  poolForm.domain = row.domain || ''
  showPoolDialog.value = true
}

async function savePool() {
  if (!poolForm.range_start || !poolForm.range_end || !poolForm.gateway) {
    ElMessage.warning('请填写起始IP、结束IP和网关')
    return
  }
  savingPool.value = true
  try {
    const payload = {
      name: poolForm.name,
      enabled: poolForm.enabled,
      range_start: poolForm.range_start,
      range_end: poolForm.range_end,
      subnet_mask: poolForm.subnet_mask,
      gateway: poolForm.gateway,
      dns_servers: poolForm.dns_servers.length > 0 ? poolForm.dns_servers : ['192.168.21.1'],
      lease_time: poolForm.lease_time,
      domain: poolForm.domain,
    }
    if (isEditingPool.value) {
      await api.put(`/dhcp/pool/${editingPoolId.value}`, payload)
      ElMessage.success('DHCP 池已更新')
    } else {
      await api.post('/dhcp/pool', payload)
      ElMessage.success('DHCP 池已添加')
    }
    showPoolDialog.value = false
    await refreshData()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
  savingPool.value = false
}

async function deletePool(row) {
  try {
    await ElMessageBox.confirm(`确定删除 DHCP 池「${row.name || row.id}」？\n删除后该池分配的 IP 租约将会受到影响。`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await api.delete(`/dhcp/pool/${row.id}`)
    ElMessage.success('DHCP 池已删除')
    await refreshData()
  } catch { /* cancelled */ }
}

// ─── DNS ─────────────────────────────────────────────────────

async function flushDns() {
  try {
    await api.post('/dhcp/dns/flush')
    ElMessage.success('DNS 缓存已刷新')
  } catch (e) {
    ElMessage.error('刷新失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function resolveDns() {
  if (!dnsQuery.value) return
  try {
    const res = await api.get('/dhcp/dns/resolve', { params: { domain: dnsQuery.value } })
    dnsResult.value = res.data.result
  } catch (e) {
    dnsResult.value = '查询失败'
  }
}

async function addUpstreamDns() {
  if (!newUpstreamDns.value) return
  try {
    await api.post('/dhcp/dns/upstream', { server: newUpstreamDns.value })
    ElMessage.success('上游 DNS 已添加')
    newUpstreamDns.value = ''
    await refreshData()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function removeUpstreamDns(index) {
  try {
    const server = dnsConfig.upstream[index]
    await api.delete('/dhcp/dns/upstream', { data: { server } })
    ElMessage.success('上游 DNS 已删除')
    await refreshData()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function addRewrite() {
  if (!newRewrite.domain || !newRewrite.ip) return
  try {
    await api.post('/dhcp/dns/rewrite', { domain: newRewrite.domain, ip: newRewrite.ip })
    ElMessage.success('DNS 重写已添加')
    newRewrite.domain = ''
    newRewrite.ip = ''
    await refreshData()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function removeRewrite(index) {
  try {
    const rule = dnsConfig.rewrites[index]
    await api.delete('/dhcp/dns/rewrite', { data: { rule } })
    ElMessage.success('DNS 重写已删除')
    await refreshData()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(refreshData)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { color: #e0e0e0; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.stat-cards { margin-bottom: 16px; }
.stat-card {
  background: #141414;
  border: 1px solid #222;
  text-align: center;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #409EFF;
}
.stat-value.green { color: #67C23A; }
.stat-value.red { color: #F56C6C; }
.stat-label {
  font-size: 13px;
  color: #888;
  margin-top: 4px;
}
.section-card {
  background: #141414;
  border: 1px solid #222;
}
.toolbar { margin-bottom: 12px; }
</style>
