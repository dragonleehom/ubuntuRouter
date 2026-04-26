<template>
  <div class="orchestrator-page">
    <div class="page-header">
      <h2>流量编排</h2>
      <div class="header-actions">
        <el-button size="small" @click="refreshAll">
          <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="section-card">
      <el-tabs v-model="activeTab">
        <!-- Tab 1: 设备列表 -->
        <el-tab-pane label="设备列表" name="devices">
          <div class="tab-loading" v-if="deviceLoading">
            <el-icon class="is-loading" :size="24"><Refresh /></el-icon>
            <span>加载中...</span>
          </div>
          <template v-else>
            <div class="toolbar">
              <el-input
                v-model="deviceSearch"
                placeholder="搜索设备名/IP/MAC..."
                size="small"
                clearable
                style="width: 300px"
                :prefix-icon="Search"
              />
            </div>
            <div class="device-grid" v-loading="deviceLoading">
              <el-card
                v-for="dev in filteredDevices"
                :key="dev.mac || dev.ip || dev.name"
                shadow="never"
                class="device-card"
                :class="{ 'device-online': dev.online, 'device-offline': !dev.online }"
              >
                <div class="device-header">
                  <span
                    class="device-name"
                    @click="startRename(dev)"
                    :title="'点击重命名'"
                  >{{ dev.name || dev.hostname || '未知设备' }}</span>
                  <el-tag
                    :type="dev.online ? 'success' : 'info'"
                    size="small"
                    effect="dark"
                  >{{ dev.online ? '在线' : '离线' }}</el-tag>
                </div>
                <div class="device-info">
                  <div class="info-row">
                    <span class="info-label">IP</span>
                    <span class="info-value">{{ dev.ip || '-' }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">MAC</span>
                    <span class="info-value">{{ dev.mac || '-' }}</span>
                  </div>
                  <div class="info-row" v-if="dev.vendor">
                    <span class="info-label">厂商</span>
                    <span class="info-value">{{ dev.vendor }}</span>
                  </div>
                  <div class="info-row" v-if="dev.apps && dev.apps.length">
                    <span class="info-label">应用</span>
                    <span class="info-value app-tags">
                      <el-tag
                        v-for="app in dev.apps.slice(0, 3)"
                        :key="app"
                        size="small"
                        type="warning"
                        style="margin-right:4px; margin-bottom:2px"
                      >{{ app }}</el-tag>
                      <el-tag v-if="dev.apps.length > 3" size="small" type="info">+{{ dev.apps.length - 3 }}</el-tag>
                    </span>
                  </div>
                </div>
              </el-card>
              <el-empty v-if="filteredDevices.length === 0" description="暂无设备" />
            </div>
          </template>
        </el-tab-pane>

        <!-- Tab 2: 编排规则 -->
        <el-tab-pane label="编排规则" name="rules">
          <div class="tab-loading" v-if="ruleLoading">
            <el-icon class="is-loading" :size="24"><Refresh /></el-icon>
            <span>加载中...</span>
          </div>
          <template v-else>
            <div class="toolbar">
              <el-button type="primary" size="small" @click="showAddRule = true">
                <el-icon style="margin-right:4px"><Plus /></el-icon>添加规则
              </el-button>
            </div>
            <el-table :data="rules" stripe size="small" v-loading="ruleLoading" style="width:100%">
              <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
              <el-table-column label="匹配条件" min-width="200">
                <template #default="{ row }">
                  <span style="color:#999;font-size:12px">
                    {{ row.match_device || '任意设备' }}
                    <span v-if="row.match_app"> / {{ row.match_app }}</span>
                    <span v-if="row.port"> / :{{ row.port }}</span>
                    <span v-if="row.protocol && row.protocol !== 'any'"> / {{ row.protocol }}</span>
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="动作(出口通道)" width="130">
                <template #default="{ row }">
                  <el-tag :type="actionTagType(row.action)" size="small">{{ row.action || '-' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="priority" label="优先级" width="80" align="center" />
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-switch
                    :model-value="row.enabled"
                    size="small"
                    @change="toggleRule(row)"
                  />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="{ row }">
                  <el-button text size="small" @click="editRule(row)">编辑</el-button>
                  <el-button text type="danger" size="small" @click="deleteRule(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>

        <!-- Tab 3: 流量统计 -->
        <el-tab-pane label="流量统计" name="stats">
          <div class="tab-loading" v-if="statsLoading">
            <el-icon class="is-loading" :size="24"><Refresh /></el-icon>
            <span>加载中...</span>
          </div>
          <template v-else>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-card shadow="never" class="chart-card">
                  <div class="chart-title">设备流量排行 (Top 10)</div>
                  <v-chart :option="deviceStatsOption" autoresize style="height:300px" />
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card shadow="never" class="chart-card">
                  <div class="chart-title">应用流量分布</div>
                  <v-chart :option="appStatsOption" autoresize style="height:300px" />
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card shadow="never" class="chart-card">
                  <div class="chart-title">通道流量对比</div>
                  <v-chart :option="channelStatsOption" autoresize style="height:300px" />
                </el-card>
              </el-col>
            </el-row>
          </template>
        </el-tab-pane>

        <!-- Tab 4: 预置模板 -->
        <el-tab-pane label="预置模板" name="templates">
          <div class="tab-loading" v-if="templateLoading">
            <el-icon class="is-loading" :size="24"><Refresh /></el-icon>
            <span>加载中...</span>
          </div>
          <template v-else>
            <div class="template-grid">
              <el-card
                v-for="tpl in templates"
                :key="tpl.id"
                shadow="never"
                class="template-card"
              >
                <div class="template-icon">
                  <el-icon :size="32" color="#409EFF"><SetUp /></el-icon>
                </div>
                <div class="template-name">{{ tpl.name }}</div>
                <div class="template-desc">{{ tpl.description }}</div>
                <div class="template-meta">
                  <span class="rule-count">{{ tpl.rule_count || 0 }} 条规则</span>
                </div>
                <el-button
                  type="primary"
                  size="small"
                  plain
                  style="margin-top:12px;width:100%"
                  @click="applyTemplate(tpl)"
                >应用</el-button>
              </el-card>
              <el-empty v-if="templates.length === 0" description="暂无预置模板" />
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 设备重命名对话框 -->
    <el-dialog v-model="showRename" title="重命名设备" width="400px">
      <el-form :model="renameForm" label-width="80px" size="small">
        <el-form-item label="设备">
          <span style="color:#ccc">{{ renameForm.mac || renameForm.ip }}</span>
        </el-form-item>
        <el-form-item label="新名称">
          <el-input v-model="renameForm.name" placeholder="输入设备名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRename = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确认</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑规则对话框 -->
    <el-dialog
      v-model="showAddRule"
      :title="editingRule ? '编辑规则' : '添加规则'"
      width="500px"
    >
      <el-form :model="ruleForm" label-width="110px" size="small">
        <el-form-item label="规则名称">
          <el-input v-model="ruleForm.name" placeholder="如 视频流量走WAN1" />
        </el-form-item>
        <el-form-item label="匹配设备">
          <el-select v-model="ruleForm.match_device" clearable placeholder="选择设备(可选)" style="width:100%">
            <el-option
              v-for="dev in devices"
              :key="dev.mac || dev.ip || dev.name"
              :label="dev.name || dev.hostname || dev.ip"
              :value="dev.name || dev.hostname || dev.ip"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配应用">
          <el-select v-model="ruleForm.match_app" clearable placeholder="选择应用(可选)" style="width:100%">
            <el-option
              v-for="app in knownApps"
              :key="app"
              :label="app"
              :value="app"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="ruleForm.port" :min="1" :max="65535" :step="1" style="width:120px" :disabled="!ruleForm.port" />
          <el-checkbox v-model="noPort" style="margin-left:8px" @change="ruleForm.port = noPort ? null : 80">不限制</el-checkbox>
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="ruleForm.protocol" style="width:140px">
            <el-option label="TCP" value="tcp" />
            <el-option label="UDP" value="udp" />
            <el-option label="ANY" value="any" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作(出口通道)">
          <el-select v-model="ruleForm.action" style="width:100%">
            <el-option label="路由到 WAN1" value="WAN1" />
            <el-option label="路由到 WAN2" value="WAN2" />
            <el-option label="路由到 VPN" value="VPN" />
            <el-option label="跳过/直连" value="skip" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="ruleForm.priority" :min="1" :max="1000" style="width:120px" />
          <span class="form-hint">数值越小优先级越高</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddRule = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus, Search, SetUp } from '@element-plus/icons-vue'
import { api } from '@/stores'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

// ── 状态 ──────────────────────────────────────────────────
const activeTab = ref('devices')

// 各 Tab 独立加载状态
const deviceLoading = ref(false)
const ruleLoading = ref(false)
const statsLoading = ref(false)
const templateLoading = ref(false)

// ── Tab 1: 设备列表 ───────────────────────────────────────
const devices = ref([])
const deviceSearch = ref('')

const filteredDevices = computed(() => {
  const q = deviceSearch.value.toLowerCase().trim()
  if (!q) return devices.value
  return devices.value.filter(d =>
    (d.name && d.name.toLowerCase().includes(q)) ||
    (d.hostname && d.hostname.toLowerCase().includes(q)) ||
    (d.ip && d.ip.includes(q)) ||
    (d.mac && d.mac.toLowerCase().includes(q))
  )
})

async function fetchDevices() {
  deviceLoading.value = true
  try {
    const res = await api.get('/orchestrator/devices')
    devices.value = res.data.devices || res.data || []
  } catch (e) {
    ElMessage.error('获取设备列表失败')
    devices.value = []
  } finally {
    deviceLoading.value = false
  }
}

// ── 设备重命名 ────────────────────────────────────────────
const showRename = ref(false)
const renameForm = reactive({ mac: '', ip: '', name: '' })
let renameTarget = null

function startRename(dev) {
  renameTarget = dev
  renameForm.mac = dev.mac || ''
  renameForm.ip = dev.ip || ''
  renameForm.name = dev.name || dev.hostname || ''
  showRename.value = true
}

async function confirmRename() {
  if (!renameTarget) return
  try {
    const payload = { name: renameForm.name }
    const mac = renameTarget.mac
    if (mac) {
      await api.put(`/orchestrator/devices/${mac}`, payload)
    } else {
      await api.put(`/orchestrator/devices/${encodeURIComponent(renameTarget.ip)}`, payload)
    }
    ElMessage.success('设备已重命名')
    showRename.value = false
    await fetchDevices()
  } catch (e) {
    ElMessage.error('重命名失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ── Tab 2: 编排规则 ───────────────────────────────────────
const rules = ref([])
const showAddRule = ref(false)
const editingRule = ref(null)
const noPort = ref(false)

const ruleForm = reactive({
  name: '',
  match_device: '',
  match_app: '',
  port: null,
  protocol: 'any',
  action: 'WAN1',
  priority: 100,
  enabled: true,
})

// 已知应用列表（从已有规则和设备中提取）
const knownApps = computed(() => {
  const appSet = new Set()
  // 从设备的应用中收集
  devices.value.forEach(d => {
    if (d.apps && Array.isArray(d.apps)) {
      d.apps.forEach(a => appSet.add(a))
    }
  })
  return Array.from(appSet).sort()
})

async function fetchRules() {
  ruleLoading.value = true
  try {
    const res = await api.get('/orchestrator/rules')
    rules.value = res.data.rules || res.data || []
  } catch (e) {
    ElMessage.error('获取规则列表失败')
    rules.value = []
  } finally {
    ruleLoading.value = false
  }
}

async function toggleRule(row) {
  try {
    const res = await api.post(`/orchestrator/rules/${row.id}/toggle`)
    row.enabled = res.data.enabled !== undefined ? res.data.enabled : !row.enabled
    ElMessage.success(row.enabled ? '规则已启用' : '规则已禁用')
  } catch (e) {
    ElMessage.error('切换状态失败: ' + (e.response?.data?.detail || e.message))
    // 回滚
    await fetchRules()
  }
}

function editRule(row) {
  editingRule.value = row
  ruleForm.name = row.name
  ruleForm.match_device = row.match_device || ''
  ruleForm.match_app = row.match_app || ''
  ruleForm.port = row.port || null
  noPort.value = !row.port
  ruleForm.protocol = row.protocol || 'any'
  ruleForm.action = row.action || 'WAN1'
  ruleForm.priority = row.priority || 100
  ruleForm.enabled = row.enabled !== undefined ? row.enabled : true
  showAddRule.value = true
}

async function deleteRule(row) {
  try {
    await ElMessageBox.confirm(`确定删除规则"${row.name}"？`, '确认')
    await api.delete(`/orchestrator/rules/${row.id}`)
    ElMessage.success('规则已删除')
    await fetchRules()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

async function saveRule() {
  const payload = {
    name: ruleForm.name,
    match_device: ruleForm.match_device || null,
    match_app: ruleForm.match_app || null,
    port: noPort.value ? null : (ruleForm.port || null),
    protocol: ruleForm.protocol,
    action: ruleForm.action,
    priority: ruleForm.priority,
    enabled: ruleForm.enabled,
  }
  try {
    if (editingRule.value) {
      await api.put(`/orchestrator/rules/${editingRule.value.id}`, payload)
      ElMessage.success('规则已更新')
    } else {
      await api.post('/orchestrator/rules', payload)
      ElMessage.success('规则已添加')
    }
    showAddRule.value = false
    editingRule.value = null
    resetRuleForm()
    await fetchRules()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}

function resetRuleForm() {
  ruleForm.name = ''
  ruleForm.match_device = ''
  ruleForm.match_app = ''
  ruleForm.port = null
  noPort.value = false
  ruleForm.protocol = 'any'
  ruleForm.action = 'WAN1'
  ruleForm.priority = 100
  ruleForm.enabled = true
}

function actionTagType(action) {
  if (!action) return 'info'
  const map = { WAN1: 'primary', WAN2: 'success', VPN: 'warning', skip: 'info' }
  return map[action] || 'info'
}

// ── Tab 3: 流量统计 ──────────────────────────────────────
const deviceStatsData = ref([])
const appStatsData = ref([])
const channelStatsData = ref([])

const deviceStatsOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} MB ({d}%)' },
  legend: { textStyle: { color: '#999' }, type: 'scroll', bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['30%', '60%'],
    center: ['50%', '45%'],
    data: deviceStatsData.value.length > 0
      ? deviceStatsData.value.slice(0, 10).map(d => ({
          name: d.name || d.device || '未知',
          value: d.traffic || d.bytes || d.mb || 0,
        }))
      : [{ name: '无数据', value: 1 }],
    label: { color: '#ccc', fontSize: 11, formatter: '{b}' },
    itemStyle: { borderRadius: 4 },
  }],
}))

const appStatsOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} MB ({d}%)' },
  legend: { textStyle: { color: '#999' }, type: 'scroll', bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['30%', '60%'],
    center: ['50%', '45%'],
    data: appStatsData.value.length > 0
      ? appStatsData.value.map(d => ({
          name: d.name || d.app || '未知',
          value: d.traffic || d.bytes || d.mb || 0,
        }))
      : [{ name: '无数据', value: 1 }],
    label: { color: '#ccc', fontSize: 11, formatter: '{b}' },
    itemStyle: { borderRadius: 4 },
  }],
}))

const channelStatsOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} MB ({d}%)' },
  legend: { textStyle: { color: '#999' }, bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['30%', '60%'],
    center: ['50%', '45%'],
    data: channelStatsData.value.length > 0
      ? channelStatsData.value.map(d => ({
          name: d.name || d.channel || '未知',
          value: d.traffic || d.bytes || d.mb || 0,
        }))
      : [{ name: '无数据', value: 1 }],
    label: { color: '#ccc', fontSize: 11, formatter: '{b}' },
    itemStyle: { borderRadius: 4 },
  }],
}))

async function fetchStats() {
  statsLoading.value = true
  try {
    const [devRes, appRes, chRes] = await Promise.all([
      api.get('/orchestrator/stats/devices'),
      api.get('/orchestrator/stats/apps'),
      api.get('/orchestrator/stats/channels'),
    ])
    deviceStatsData.value = devRes.data.devices || devRes.data || []
    appStatsData.value = appRes.data.apps || appRes.data || []
    channelStatsData.value = chRes.data.channels || chRes.data || []
  } catch (e) {
    ElMessage.error('获取流量统计失败')
    deviceStatsData.value = []
    appStatsData.value = []
    channelStatsData.value = []
  } finally {
    statsLoading.value = false
  }
}

// ── Tab 4: 预置模板 ───────────────────────────────────────
const templates = ref([])

async function fetchTemplates() {
  templateLoading.value = true
  try {
    const res = await api.get('/orchestrator/templates')
    templates.value = res.data.templates || res.data || []
  } catch (e) {
    ElMessage.error('获取模板列表失败')
    templates.value = []
  } finally {
    templateLoading.value = false
  }
}

async function applyTemplate(tpl) {
  try {
    await ElMessageBox.confirm(
      `确定应用模板"${tpl.name}"？这将添加 ${tpl.rule_count || 0} 条编排规则。`,
      '应用模板',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
    )
    await api.post(`/orchestrator/templates/${tpl.id}/apply`)
    ElMessage.success(`模板"${tpl.name}"已应用`)
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('应用模板失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

async function refreshAll() {
  await Promise.all([fetchDevices(), fetchRules(), fetchStats(), fetchTemplates()])
}

// ── Tab 切换时按需加载 ───────────────────────────────────
watch(activeTab, (tab) => {
  if (tab === 'devices' && devices.value.length === 0 && !deviceLoading.value) fetchDevices()
  if (tab === 'rules' && rules.value.length === 0 && !ruleLoading.value) fetchRules()
  if (tab === 'stats' && deviceStatsData.value.length === 0 && !statsLoading.value) fetchStats()
  if (tab === 'templates' && templates.value.length === 0 && !templateLoading.value) fetchTemplates()
})

// ── 生命周期 ─────────────────────────────────────────────
onMounted(() => {
  fetchDevices()
})
</script>

<style scoped>
.orchestrator-page {
  padding: 0;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  color: #e0e0e0;
  margin: 0;
  font-size: 18px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.section-card {
  background: #1a1a1a;
  border: 1px solid #333;
}
.toolbar {
  margin-bottom: 12px;
}

/* Tab 加载状态 */
.tab-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  color: #888;
  font-size: 14px;
}
.tab-loading .is-loading {
  animation: rotating 1.5s linear infinite;
}
@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 设备卡片网格 */
.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.device-card {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  transition: border-color 0.2s;
}
.device-card:hover {
  border-color: #555;
}
.device-online {
  border-left: 3px solid #67C23A;
}
.device-offline {
  border-left: 3px solid #555;
  opacity: 0.7;
}
.device-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.device-name {
  font-size: 15px;
  font-weight: 600;
  color: #e0e0e0;
  cursor: pointer;
  border-bottom: 1px dashed transparent;
  transition: border-color 0.2s;
}
.device-name:hover {
  border-bottom-color: #409EFF;
  color: #409EFF;
}
.device-info {
  font-size: 13px;
}
.info-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 5px;
  line-height: 1.6;
}
.info-label {
  color: #666;
  width: 48px;
  flex-shrink: 0;
}
.info-value {
  color: #ccc;
  word-break: break-all;
}
.app-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

/* 图表卡片 */
.chart-card {
  background: #1a1a1a;
  border: 1px solid #333;
}
.chart-title {
  color: #ccc;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  text-align: center;
}

/* 模板卡片网格 */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.template-card {
  background: #1a1a1a;
  border: 1px solid #333;
  text-align: center;
  padding: 8px 0;
  transition: border-color 0.2s;
}
.template-card:hover {
  border-color: #409EFF;
}
.template-icon {
  margin-bottom: 8px;
}
.template-name {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 6px;
}
.template-desc {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
  line-height: 1.5;
}
.template-meta {
  font-size: 12px;
  color: #666;
}
.rule-count {
  display: inline-block;
  background: #2a2a2a;
  padding: 2px 10px;
  border-radius: 10px;
  color: #999;
}

/* 表单辅助文字 */
.form-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #666;
}

/* 覆盖 Element Plus 暗色主题 */
:deep(.el-card) {
  background: #1a1a1a;
  border-color: #333;
  color: #ccc;
}
:deep(.el-table) {
  --el-table-bg-color: #1a1a1a;
  --el-table-tr-bg-color: #1a1a1a;
  --el-table-header-bg-color: #222;
  --el-table-row-hover-bg-color: #2a2a2a;
  --el-table-border-color: #333;
  --el-table-text-color: #ccc;
  --el-table-header-text-color: #999;
}
:deep(.el-tabs__item) {
  color: #888;
}
:deep(.el-tabs__item.is-active) {
  color: #409EFF;
}
:deep(.el-tabs__header) {
  border-bottom-color: #333;
}
:deep(.el-dialog) {
  background: #1a1a1a;
  border: 1px solid #333;
}
:deep(.el-dialog__title) {
  color: #e0e0e0;
}
:deep(.el-form-item__label) {
  color: #999;
}
:deep(.el-input__wrapper) {
  background: #2a2a2a;
  box-shadow: 0 0 0 1px #333 inset;
}
:deep(.el-input__inner) {
  color: #ccc;
}
:deep(.el-select .el-input__wrapper) {
  background: #2a2a2a;
}
:deep(.el-checkbox__label) {
  color: #999;
}
:deep(.el-empty__description) {
  color: #666;
}
</style>
