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

        <!-- DHCP 池配置 -->
        <el-tab-pane label="DHCP 池" name="pool">
          <el-form :model="pool" label-width="120px" size="small" v-if="pool.configured">
            <el-form-item label="接口">{{ pool.interface }}</el-form-item>
            <el-form-item label="IP 范围">{{ pool.range_start }} - {{ pool.range_end }}</el-form-item>
            <el-form-item label="网关">{{ pool.gateway }}</el-form-item>
            <el-form-item label="租约时间">{{ pool.lease_time }} 小时</el-form-item>
            <el-form-item label="域名">{{ pool.domain || '未设置' }}</el-form-item>
            <el-form-item label="活跃租约数">{{ pool.active_leases }}</el-form-item>
          </el-form>
          <el-empty v-else description="DHCP 池未配置" />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete, Plus } from '@element-plus/icons-vue'
import { api } from '@/stores'

const loading = ref(false)
const activeTab = ref('leases')
const showAddStatic = ref(false)

const leases = ref([])
const staticLeases = ref([])
const pool = reactive({ configured: false })
const status = reactive({ active: false, enabled: false, active_leases: 0, total_leases: 0, cached_entries: 0 })
const dnsConfig = reactive({ upstream: [], rewrites: [], forwards: [] })
const dnsQuery = ref('')
const dnsResult = ref('')
const newUpstreamDns = ref('')
const newRewrite = reactive({ domain: '', ip: '' })
const newStaticLease = reactive({ mac: '', ip: '', hostname: '' })

async function refreshData() {
  loading.value = true
  try {
    const [leasesRes, staticRes, poolRes, statusRes, dnsRes] = await Promise.all([
      api.get('/dhcp/leases'),
      api.get('/dhcp/static-leases'),
      api.get('/dhcp/pool'),
      api.get('/dhcp/status'),
      api.get('/dhcp/dns/config'),
    ])
    leases.value = leasesRes.data.leases || []
    staticLeases.value = staticRes.data.leases || []
    Object.assign(pool, poolRes.data)
    Object.assign(status, statusRes.data)
    Object.assign(dnsConfig, dnsRes.data)
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
