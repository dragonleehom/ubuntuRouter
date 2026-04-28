<template>
  <div class="page">
    <div class="page-header">
      <h2>防火墙</h2>
      <div class="header-actions">
        <el-button type="primary" size="small" @click="refreshStats">
          <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 状态概览 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.rules_count || 0 }}</div>
          <div class="stat-label">规则数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ zones.length }}</div>
          <div class="stat-label">Zone</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ conntrack.total || 0 }}</div>
          <div class="stat-label">连接跟踪</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ portForwards.length }}</div>
          <div class="stat-label">端口转发</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tabs -->
    <el-card shadow="never" class="section-card">
      <el-tabs v-model="activeTab">
        <!-- Zone 管理 -->
        <el-tab-pane label="Zone 管理" name="zones">
          <div class="toolbar">
            <el-button type="primary" size="small" @click="showAddZone = true">
              <el-icon style="margin-right:4px"><Plus /></el-icon>创建 Zone
            </el-button>
          </div>
          <el-table :data="zones" stripe size="small" v-loading="loading">
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column label="类型" width="100" class="hide-mobile">
              <template #default="{ row }">
                <el-tag :type="row.type === 'builtin' ? 'info' : 'warning'" size="small">
                  {{ row.type === 'builtin' ? '内置' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="policy" label="默认策略" width="100" class="hide-mobile" />
            <el-table-column prop="rules_count" label="规则数" width="100" align="right" class="hide-mobile" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button v-if="row.type === 'custom'"
                  text type="danger" size="small" @click="deleteZone(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 防火墙规则 -->
        <el-tab-pane label="防火墙规则" name="rules">
          <div class="toolbar">
            <el-button type="primary" size="small" @click="showAddRule = true">
              <el-icon style="margin-right:4px"><Plus /></el-icon>添加规则
            </el-button>
          </div>
          <el-table :data="rules" stripe size="small" v-loading="loading" max-height="500">
            <el-table-column prop="handle" label="Handle" width="70" class="hide-mobile" />
            <el-table-column prop="chain" label="链" width="100" class="hide-mobile" />
            <el-table-column prop="rule" label="规则" min-width="300" show-overflow-tooltip />
            <el-table-column prop="packets" label="数据包" width="100" align="right" class="hide-mobile" />
            <el-table-column prop="bytes" label="字节" width="100" align="right" class="hide-mobile" />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="deleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 端口转发 -->
        <el-tab-pane label="端口转发" name="portfw">
          <div class="toolbar">
            <el-button type="primary" size="small" @click="showAddPortForward = true">
              <el-icon style="margin-right:4px"><Plus /></el-icon>添加转发
            </el-button>
          </div>
          <el-table :data="portForwards" stripe size="small" v-loading="loading" max-height="500">
            <el-table-column prop="handle" label="Handle" width="70" class="hide-mobile" />
            <el-table-column prop="chain" label="链" width="100" class="hide-mobile" />
            <el-table-column prop="rule" label="规则" min-width="350" show-overflow-tooltip />
            <el-table-column prop="packets" label="数据包" width="100" align="right" class="hide-mobile" />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="deletePortForward(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 连接跟踪 -->
        <el-tab-pane label="连接跟踪" name="conntrack">
          <div class="conntrack-header">
            <span class="conntrack-title">共 {{ conntrack.total || 0 }} 条连接</span>
            <div class="toolbar">
              <el-button size="small" @click="refreshConntrack">
                <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
              </el-button>
              <el-button type="danger" size="small" @click="flushConntrack">
                <el-icon style="margin-right:4px"><Delete /></el-icon>清空
              </el-button>
            </div>
          </div>
          <el-table :data="conntrack.entries || []" stripe size="small" v-loading="loading" max-height="500">
            <el-table-column prop="protocol" label="协议" width="80" />
            <el-table-column prop="src" label="源地址" min-width="180" />
            <el-table-column prop="dst" label="目标地址" min-width="180" />
            <el-table-column label="状态" width="140" class="hide-mobile">
              <template #default="{ row }">
                <el-tag :type="stateTagType(row.state)" size="small">
                  {{ row.state }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="timeout" label="超时(秒)" width="100" align="right" class="hide-mobile" />
            <el-table-column prop="bytes" label="流量" width="120" align="right" class="hide-mobile" />
          </el-table>
        </el-tab-pane>

        <!-- ipset / NFTables Set 管理 -->
        <el-tab-pane label="ipset / Set 管理" name="ipsets">
          <div class="toolbar">
            <el-button type="primary" size="small" @click="showAddSet = true">
              <el-icon style="margin-right:4px"><Plus /></el-icon>创建集合
            </el-button>
            <el-button size="small" @click="fetchSets">
              <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
            </el-button>
          </div>
          <el-table :data="sets" stripe size="small" v-loading="setLoading" max-height="500">
            <el-table-column prop="name" label="名称" width="180" />
            <el-table-column prop="type" label="类型" width="140" class="hide-mobile" />
            <el-table-column prop="flags" label="标志" width="120" class="hide-mobile" />
            <el-table-column label="元素" min-width="200" class="hide-mobile">
              <template #default="{ row }">
                <div class="set-elements-cell">
                  <span v-if="row.elements && row.elements.length">
                    {{ row.elements.join(', ') }}
                  </span>
                  <span v-else style="color:#666">(空)</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="showAddElement(row)">
                  <el-icon style="margin-right:2px"><Plus /></el-icon>元素
                </el-button>
                <el-button text type="danger" size="small" @click="deleteSet(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 创建 Zone 对话框 -->
    <el-dialog v-model="showAddZone" title="创建 Zone" width="450px">
      <el-form :model="newZone" label-width="100px" size="small">
        <el-form-item label="名称">
          <el-input v-model="newZone.name" placeholder="如 lan, wan, dmz" />
        </el-form-item>
        <el-form-item label="入站策略">
          <el-select v-model="newZone.input">
            <el-option label="accept (允许)" value="accept" />
            <el-option label="drop (丢弃)" value="drop" />
          </el-select>
        </el-form-item>
        <el-form-item label="转发策略">
          <el-select v-model="newZone.forward">
            <el-option label="accept (允许)" value="accept" />
            <el-option label="drop (丢弃)" value="drop" />
          </el-select>
        </el-form-item>
        <el-form-item label="出站策略">
          <el-select v-model="newZone.output">
            <el-option label="accept (允许)" value="accept" />
            <el-option label="drop (丢弃)" value="drop" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddZone = false">取消</el-button>
        <el-button type="primary" @click="createZone">创建</el-button>
      </template>
    </el-dialog>

    <!-- 添加端口转发对话框（含 NAT 回环） -->
    <el-dialog v-model="showAddPortForward" title="添加端口转发" width="500px">
      <el-form :model="newPortForward" label-width="120px" size="small">
        <el-form-item label="名称">
          <el-input v-model="newPortForward.name" placeholder="如 web-server" />
        </el-form-item>
        <el-form-item label="来源 Zone">
          <el-select v-model="newPortForward.from_zone">
            <el-option label="WAN" value="wan" />
            <el-option label="LAN" value="lan" />
            <el-option label="DMZ" value="dmz" />
          </el-select>
        </el-form-item>
        <el-form-item label="外部端口">
          <el-input-number v-model="newPortForward.from_port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="newPortForward.protocol">
            <el-option label="TCP" value="tcp" />
            <el-option label="UDP" value="udp" />
            <el-option label="TCP+UDP" value="tcp udp" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标 IP">
          <el-input v-model="newPortForward.to_ip" placeholder="如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="目标端口">
          <el-input-number v-model="newPortForward.to_port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="NAT 回环">
          <el-switch v-model="newPortForward.nat_loopback" />
          <span class="form-hint">允许内网通过公网IP访问映射服务</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddPortForward = false">取消</el-button>
        <el-button type="primary" @click="addPortForward">添加</el-button>
      </template>
    </el-dialog>

    <!-- 添加规则对话框（增强版 Sprint 1） -->
    <el-dialog v-model="showAddRule" title="添加防火墙规则" width="700px">
      <el-form :model="newRule" label-width="110px" size="small">
        <!-- 基础字段 -->
        <el-divider content-position="left">基础匹配</el-divider>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="方向">
              <el-select v-model="newRule.direction">
                <el-option label="input (入站)" value="input" />
                <el-option label="forward (转发)" value="forward" />
                <el-option label="output (出站)" value="output" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="动作">
              <el-select v-model="newRule.action">
                <el-option label="accept (允许)" value="accept" />
                <el-option label="drop (丢弃)" value="drop" />
                <el-option label="reject (拒绝)" value="reject" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="协议">
              <el-select v-model="newRule.protocol">
                <el-option label="TCP" value="tcp" />
                <el-option label="UDP" value="udp" />
                <el-option label="TCP+UDP" value="tcp udp" />
                <el-option label="ICMP" value="icmp" />
                <el-option label="ICMPv6" value="ipv6-icmp" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="源 IP">
              <el-input v-model="newRule.src_ip" placeholder="留空=任意" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标 IP">
              <el-input v-model="newRule.dst_ip" placeholder="留空=任意" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标端口">
              <el-input-number v-model="newRule.dst_port" :min="1" :max="65535"
                v-if="newRule.protocol !== 'icmp' && newRule.protocol !== 'ipv6-icmp'" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- Sprint 1 增强字段 -->
        <el-divider content-position="left">高级匹配 (Sprint 1)</el-divider>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="源 MAC">
              <el-input v-model="newRule.src_mac" placeholder="如 00:11:22:33:44:55" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="入接口">
              <el-input v-model="newRule.in_iface" placeholder="如 eth0, wan" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="出接口">
              <el-input v-model="newRule.out_iface" placeholder="如 eth1, lan" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="ICMP 类型" v-if="newRule.protocol === 'icmp' || newRule.protocol === 'ipv6-icmp'">
              <el-select v-model="newRule.icmp_type" filterable clearable placeholder="选择 ICMP 类型">
                <el-option
                  v-for="item in icmpTypes"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Conntrack 状态">
              <el-select v-model="newRule.ct_state" clearable placeholder="任意状态">
                <el-option label="new (新建)" value="new" />
                <el-option label="established (已建立)" value="established" />
                <el-option label="related (关联)" value="related" />
                <el-option label="invalid (无效)" value="invalid" />
                <el-option label="untracked (未跟踪)" value="untracked" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="速率限制">
              <el-input v-model="newRule.rate" placeholder="如 10/minute" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="突发">
              <el-input v-model="newRule.burst" placeholder="如 5 packets" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Mark">
              <el-input v-model="newRule.mark" placeholder="如 0x1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="DSCP">
              <el-input-number v-model="newRule.dscp" :min="0" :max="63" controls-position="right" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="跳转到">
              <el-input v-model="newRule.jump_to" placeholder="如 zone_lan" />
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="记录日志">
              <el-switch v-model="newRule.log" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showAddRule = false">取消</el-button>
        <el-button type="primary" @click="addRule">添加</el-button>
      </template>
    </el-dialog>

    <!-- 创建集合对话框 -->
    <el-dialog v-model="showAddSet" title="创建 NFTables 集合" width="450px">
      <el-form :model="newSet" label-width="100px" size="small">
        <el-form-item label="名称">
          <el-input v-model="newSet.name" placeholder="如 blacklist, allowed_ips" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="newSet.type">
            <el-option label="ipv4_addr" value="ipv4_addr" />
            <el-option label="ipv6_addr" value="ipv6_addr" />
            <el-option label="ether_addr" value="ether_addr" />
            <el-option label="inet_proto" value="inet_proto" />
            <el-option label="inet_service" value="inet_service" />
            <el-option label="mark" value="mark" />
          </el-select>
        </el-form-item>
        <el-form-item label="标志">
          <el-select v-model="newSet.flags" clearable>
            <el-option label="interval (区间)" value="interval" />
            <el-option label="timeout (超时)" value="timeout" />
            <el-option label="无" value="" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddSet = false">取消</el-button>
        <el-button type="primary" @click="createSet">创建</el-button>
      </template>
    </el-dialog>

    <!-- 添加集合元素对话框 -->
    <el-dialog v-model="showAddElementDialog" title="添加元素到集合" width="400px">
      <el-form :model="elementForm" label-width="80px" size="small">
        <el-form-item label="集合">
          <el-input :model-value="elementForm.setName" disabled />
        </el-form-item>
        <el-form-item label="元素">
          <el-input v-model="elementForm.element" placeholder="如 192.168.1.100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddElementDialog = false">取消</el-button>
        <el-button type="primary" @click="addSetElement">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus, Delete } from '@element-plus/icons-vue'
import { api } from '@/stores'

const loading = ref(false)
const setLoading = ref(false)
const activeTab = ref('zones')
const showAddZone = ref(false)
const showAddRule = ref(false)
const showAddPortForward = ref(false)
const showAddSet = ref(false)
const showAddElementDialog = ref(false)

const stats = reactive({ rules_count: 0, tables: [], chains: {} })
const conntrack = reactive({ total: 0, entries: [] })
const rules = ref([])
const zones = ref([])
const portForwards = ref([])
const sets = ref([])
const icmpTypes = ref([])

const newZone = reactive({
  name: '',
  input: 'accept',
  forward: 'accept',
  output: 'accept',
})

const newRule = reactive({
  direction: 'input',
  action: 'accept',
  src_ip: '',
  dst_ip: '',
  src_port: null,
  dst_port: 80,
  protocol: 'tcp',
  log: false,
  // Sprint 1 增强字段（默认空值）
  src_mac: '',
  in_iface: '',
  out_iface: '',
  icmp_type: '',
  ct_state: '',
  rate: '',
  burst: '',
  time_begin: '',
  time_end: '',
  time_days: '',
  log_prefix: '',
  mark: '',
  dscp: 0,
  jump_to: '',
  comment: '',
})

const newPortForward = reactive({
  name: '',
  from_zone: 'wan',
  from_port: 8080,
  protocol: 'tcp',
  to_ip: '',
  to_port: 80,
  nat_loopback: false,
})

const newSet = reactive({
  name: '',
  type: 'ipv4_addr',
  flags: 'interval',
})

const elementForm = reactive({
  setName: '',
  element: '',
})

async function loadIcmpTypes() {
  try {
    const res = await api.get('/firewall/icmp-types')
    // 合并 ICMP 和 ICMPv6 类型列表，用户根据选择的协议自动过滤
    icmpTypes.value = [
      ...(res.data.icmp || []),
      ...(res.data.icmpv6 || []),
    ]
  } catch (e) {
    // ICMP 类型加载失败不影响整体功能
    console.warn('加载 ICMP 类型失败:', e)
    icmpTypes.value = []
  }
}

async function refreshStats() {
  loading.value = true
  try {
    const [zonesRes, statsRes, conntrackRes, pfRes] = await Promise.all([
      api.get('/firewall/zones'),
      api.get('/firewall/stats/ubunturouter'),
      api.get('/firewall/conntrack?limit=100'),
      api.get('/firewall/port-forwards'),
    ])
    zones.value = zonesRes.data.zones || []
    Object.assign(stats, statsRes.data)
    rules.value = statsRes.data.rules || []
    Object.assign(conntrack, conntrackRes.data)
    portForwards.value = pfRes.data.port_forwards || []
  } catch (e) {
    ElMessage.error('获取防火墙数据失败')
  }
  loading.value = false
}

async function createZone() {
  try {
    const res = await api.post('/firewall/zones', newZone)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      showAddZone.value = false
      newZone.name = ''
      await refreshStats()
    } else {
      ElMessage.error(res.data.message)
    }
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteZone(row) {
  try {
    await ElMessageBox.confirm(`确定删除 Zone "${row.name}"？`, '确认')
    const res = await api.delete(`/firewall/zones/${row.name}`)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      await refreshStats()
    } else {
      ElMessage.error(res.data.message)
    }
  } catch { /* cancelled */ }
}

async function addPortForward() {
  try {
    const res = await api.post('/firewall/port-forwards', newPortForward)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      showAddPortForward.value = false
      await refreshStats()
    } else {
      ElMessage.error(res.data.message)
    }
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deletePortForward(row) {
  try {
    await ElMessageBox.confirm(`确定删除端口转发 #${row.handle}？`, '确认')
    const res = await api.delete(`/firewall/port-forwards/${row.handle}`)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      await refreshStats()
    } else {
      ElMessage.error(res.data.message)
    }
  } catch { /* cancelled */ }
}

async function deleteRule(row) {
  try {
    await ElMessageBox.confirm(`确定删除规则 #${row.handle}？`, '确认')
    await api.delete(`/firewall/rules/${row.handle}?chain=${row.chain}`)
    ElMessage.success('规则已删除')
    await refreshStats()
  } catch { /* cancelled */ }
}

async function addRule() {
  try {
    await api.post('/firewall/rules', newRule)
    ElMessage.success('规则已添加')
    showAddRule.value = false
    await refreshStats()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function refreshConntrack() {
  loading.value = true
  try {
    const res = await api.get('/firewall/conntrack?limit=10000')
    Object.assign(conntrack, res.data)
  } catch (e) {
    ElMessage.error('获取连接跟踪数据失败')
  }
  loading.value = false
}

function stateTagType(state) {
  if (!state) return 'info'
  const s = state.toUpperCase()
  if (s === 'ESTABLISHED') return 'success'
  if (s === 'TIME_WAIT') return 'warning'
  if (s === 'CLOSE' || s === 'CLOSED') return 'info'
  return 'info'
}

async function flushConntrack() {
  try {
    await ElMessageBox.confirm('确定清空所有连接跟踪？', '确认')
    await api.post('/firewall/conntrack/flush')
    ElMessage.success('连接跟踪已清空')
    await refreshStats()
  } catch { /* cancelled */ }
}

// ─── ipset / Set 管理 ────────────────────────────────────

async function fetchSets() {
  setLoading.value = true
  try {
    const res = await api.get('/firewall/sets')
    sets.value = res.data.sets || []
  } catch (e) {
    ElMessage.error('获取集合列表失败')
  }
  setLoading.value = false
}

async function createSet() {
  try {
    const res = await api.post('/firewall/sets', newSet)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      showAddSet.value = false
      newSet.name = ''
      await fetchSets()
    } else {
      ElMessage.error(res.data.message)
    }
  } catch (e) {
    ElMessage.error('创建集合失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteSet(row) {
  try {
    await ElMessageBox.confirm(`确定删除集合 "${row.name}"？`, '确认')
    const res = await api.delete(`/firewall/sets/${row.name}`)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      await fetchSets()
    } else {
      ElMessage.error(res.data.message)
    }
  } catch { /* cancelled */ }
}

function showAddElement(row) {
  elementForm.setName = row.name
  elementForm.element = ''
  showAddElementDialog.value = true
}

async function addSetElement() {
  if (!elementForm.element) {
    ElMessage.warning('请输入元素')
    return
  }
  try {
    const res = await api.post('/firewall/sets/elements', {
      name: elementForm.setName,
      element: elementForm.element,
    })
    if (res.data.success) {
      ElMessage.success(res.data.message)
      showAddElementDialog.value = false
      await fetchSets()
    } else {
      ElMessage.error(res.data.message)
    }
  } catch (e) {
    ElMessage.error('添加元素失败: ' + (e.response?.data?.detail || e.message))
  }
}

watch(activeTab, (tab) => {
  if (tab === 'conntrack') {
    refreshConntrack()
  } else if (tab === 'ipsets') {
    fetchSets()
  }
})

onMounted(() => {
  refreshStats()
  loadIcmpTypes()
})
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
  font-size: 28px;
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
.toolbar {
  margin-bottom: 12px;
}
.conntrack-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.conntrack-title {
  font-size: 14px;
  color: #aaa;
}
.set-elements-cell {
  font-size: 12px;
  color: #ccc;
  max-height: 48px;
  overflow-y: auto;
  line-height: 1.4;
}
.form-hint {
  font-size: 11px;
  color: #888;
  margin-left: 8px;
}
</style>
