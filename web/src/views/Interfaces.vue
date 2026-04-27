<template>
  <div class="interfaces-page">
    <!-- 页面标题 -->
    <div class="page-header glass-card">
      <div class="header-left">
        <h2><el-icon :size="22"><Connection /></el-icon> 网络接口</h2>
        <span class="header-subtitle">配置、管理网络端口和连接协议</span>
      </div>
      <div class="header-actions">
        <el-button type="success" @click="showCreateDialog = true" round>
          <el-icon><Plus /></el-icon> 新建接口
        </el-button>
        <el-button :type="refreshing ? 'default' : 'primary'" :loading="refreshing" @click="refreshAll" round>
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- ─────────────── 物理端口面板 ─────────────── -->
    <div class="section-title">
      <el-icon :size="18"><Monitor /></el-icon> 物理端口
      <span class="section-count">{{ physicalPorts.length }}</span>
    </div>
    <div class="port-grid">
      <div
        v-for="p in physicalPorts"
        :key="p.name"
        class="port-card glass-card"
        :class="{ 'is-up': p.state === 'UP', 'is-down': p.state !== 'UP' }"
      >
        <!-- 端口头部 -->
        <div class="port-header">
          <span class="port-name">{{ p.name }}</span>
          <div class="port-header-right">
            <el-tag
              v-if="p.role === 'wan'"
              type="warning"
              size="small"
              effect="dark"
              class="role-tag"
            >WAN</el-tag>
            <el-tag
              v-else-if="p.role === 'lan'"
              type="primary"
              size="small"
              effect="dark"
              class="role-tag"
            >LAN</el-tag>
            <el-tag
              v-else
              type="info"
              size="small"
              effect="plain"
              class="role-tag"
            >{{ p.role.toUpperCase() }}</el-tag>
            <el-tag
              :type="p.state === 'UP' ? 'success' : 'danger'"
              size="small"
              effect="dark"
              class="port-state-tag"
            >
              {{ p.state === 'UP' ? '已连接' : '未连接' }}
            </el-tag>
          </div>
        </div>

        <!-- 端口速率指示 -->
        <div class="port-speed-indicator">
          <div class="speed-ring" :class="{ active: p.state === 'UP', flashing: isFlashing(p.name) }">
            <template v-if="p.speed">
              <span class="speed-value">{{ p.speed }}</span>
              <span class="speed-unit">Mbps</span>
            </template>
            <template v-else>
              <span class="speed-icon"><el-icon :size="28"><Monitor /></el-icon></span>
              <span class="speed-unit">物理端口</span>
            </template>
          </div>
        </div>

        <!-- 端口详情 -->
        <div class="port-details">
          <div class="detail-row" v-if="p.mac">
            <span class="detail-label">MAC</span>
            <span class="detail-value mono">{{ p.mac }}</span>
          </div>
          <div class="detail-row" v-if="p.portInfo">
            <span class="detail-label">驱动</span>
            <span class="detail-value">{{ p.portInfo.driver || '-' }}</span>
          </div>
          <div class="detail-row" v-if="p.portInfo">
            <span class="detail-label">固件</span>
            <span class="detail-value">{{ p.portInfo.firmware || '-' }}</span>
          </div>
          <div class="detail-row" v-if="p.portInfo">
            <span class="detail-label">双工</span>
            <span class="detail-value">{{ p.portInfo.duplex || '-' }}</span>
          </div>
          <div class="detail-row" v-if="p.portInfo">
            <span class="detail-label">自动协商</span>
            <span class="detail-value">{{ p.portInfo.auto_negotiation || '-' }}</span>
          </div>
          <div class="detail-row" v-if="p.portInfo">
            <span class="detail-label">Wake-on-LAN</span>
            <span class="detail-value">{{ p.portInfo.wol || '-' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">IP 地址</span>
            <span class="detail-value" :class="{ 'text-muted': !p.ipv4 || !p.ipv4.length }">
              {{ p.ipv4 && p.ipv4.length ? p.ipv4.join(', ') : '未配置' }}
            </span>
          </div>
          <div class="detail-row" v-if="p.rx_bytes !== undefined">
            <span class="detail-label">接收</span>
            <span class="detail-value mono">{{ formatBytes(p.rx_bytes) }}</span>
          </div>
          <div class="detail-row" v-if="p.tx_bytes !== undefined">
            <span class="detail-label">发送</span>
            <span class="detail-value mono">{{ formatBytes(p.tx_bytes) }}</span>
          </div>
        </div>

        <!-- 端口操作 -->
        <div class="port-actions">
          <el-button text type="primary" size="small" @click="showEditDialog(p)">
            <el-icon><Edit /></el-icon> 编辑配置
          </el-button>
          <el-button
            v-if="p.portInfo"
            text
            type="info"
            size="small"
            @click="showPortDetail(p)"
          >
            <el-icon><InfoFilled /></el-icon> 详情
          </el-button>
        </div>
      </div>

      <!-- 无物理端口时的占位 -->
      <div v-if="physicalPorts.length === 0" class="empty-card glass-card">
        <el-icon :size="48"><Monitor /></el-icon>
        <span class="empty-text">未检测到物理端口</span>
      </div>
    </div>

    <!-- ─────────────── 虚拟接口面板 ─────────────── -->
    <div class="section-title">
      <el-icon :size="18"><Connection /></el-icon> 虚拟接口
      <span class="section-count">{{ virtualPorts.length }}</span>
    </div>
    <div class="port-grid">
      <div
        v-for="p in virtualPorts"
        :key="p.name"
        class="port-card glass-card virtual"
        :class="{ 'is-up': p.state === 'UP', 'is-down': p.state !== 'UP' }"
      >
        <!-- 端口头部 -->
        <div class="port-header">
          <span class="port-name">{{ p.name }}</span>
          <div class="port-header-right">
            <el-tag
              v-if="p.role === 'wan'"
              type="warning"
              size="small"
              effect="dark"
              class="role-tag"
            >WAN</el-tag>
            <el-tag
              v-else-if="p.role === 'lan'"
              type="primary"
              size="small"
              effect="dark"
              class="role-tag"
            >LAN</el-tag>
            <el-tag
              v-else
              type="info"
              size="small"
              effect="plain"
              class="role-tag"
            >{{ p.role.toUpperCase() }}</el-tag>
            <el-tag
              :type="p.state === 'UP' ? 'success' : 'danger'"
              size="small"
              effect="dark"
              class="port-state-tag"
            >
              {{ p.state === 'UP' ? '运行中' : '已停止' }}
            </el-tag>
          </div>
        </div>

        <!-- 速率指示（虚拟接口不显示速率环，显示类型图标） -->
        <div class="port-speed-indicator">
          <div class="speed-ring virtual-ring" :class="{ active: p.state === 'UP', flashing: isFlashing(p.name) }">
            <span class="speed-icon">
              <el-icon :size="26">
                <component :is="getVirtualIcon(p)" />
              </el-icon>
            </span>
            <span class="speed-unit">{{ p.type }}</span>
          </div>
        </div>

        <!-- 接口详情 -->
        <div class="port-details">
          <div class="detail-row" v-if="p.mac">
            <span class="detail-label">MAC</span>
            <span class="detail-value mono">{{ p.mac }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">IP 地址</span>
            <span class="detail-value" :class="{ 'text-muted': !p.ipv4 || !p.ipv4.length }">
              {{ p.ipv4 && p.ipv4.length ? p.ipv4.join(', ') : '未配置' }}
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">MTU</span>
            <span class="detail-value">{{ p.mtu }}</span>
          </div>
        </div>

        <!-- 端口操作 -->
        <div class="port-actions">
          <el-button text type="primary" size="small" @click="showEditDialog(p)">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
        </div>
      </div>

      <!-- 无虚拟接口时的占位 -->
      <div v-if="virtualPorts.length === 0" class="empty-card glass-card">
        <el-icon :size="48"><Connection /></el-icon>
        <span class="empty-text">暂无虚拟接口</span>
      </div>
    </div>

    <!-- ─────────────── 编辑对话框 ─────────────── -->
    <el-dialog
      v-model="showEdit"
      :title="'编辑接口 — ' + editForm.iface"
      width="600px"
      :close-on-click-modal="false"
      class="edit-dialog"
    >
      <el-form :model="editForm" label-width="110px" size="small" @submit.prevent>
        <!-- 当前状态 -->
        <el-form-item label="当前状态">
          <el-tag :type="editForm.currentState === 'UP' ? 'success' : 'danger'" size="small">
            {{ editForm.currentState === 'UP' ? '已连接' : '未连接' }}
          </el-tag>
          <span class="form-hint" v-if="editForm.currentMac">MAC: {{ editForm.currentMac }}</span>
        </el-form-item>

        <el-divider />

        <!-- 连接协议 -->
        <el-form-item label="连接协议" required>
          <el-radio-group v-model="editForm.protocol" class="protocol-group">
            <el-radio-button value="dhcp">
              <el-icon :size="14"><Refresh /></el-icon> DHCP
            </el-radio-button>
            <el-radio-button value="static">
              <el-icon :size="14"><Link /></el-icon> 静态IP
            </el-radio-button>
            <el-radio-button value="pppoe">
              <el-icon :size="14"><Connection /></el-icon> PPPoE拨号
            </el-radio-button>
            <el-radio-button value="disabled">
              <el-icon :size="14"><Remove /></el-icon> 禁用
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 静态IP配置 -->
        <template v-if="editForm.protocol === 'static'">
          <el-form-item label="IP 地址" required>
            <el-input v-model="editForm.address" placeholder="如 192.168.1.1/24" />
          </el-form-item>
          <el-form-item label="网关">
            <el-input v-model="editForm.gateway" placeholder="如 192.168.1.254" />
          </el-form-item>
        </template>

        <!-- PPPoE 配置 -->
        <template v-if="editForm.protocol === 'pppoe'">
          <el-form-item label="宽带账号" required>
            <el-input v-model="editForm.pppoeUsername" placeholder="宽带服务商提供的账号" />
          </el-form-item>
          <el-form-item label="宽带密码" required>
            <el-input v-model="editForm.pppoePassword" type="password" show-password placeholder="宽带密码" />
          </el-form-item>
        </template>

        <!-- DHCP 提示 -->
        <el-form-item v-if="editForm.protocol === 'dhcp'" label="说明">
          <div class="form-hint-block">
            <el-icon :size="14"><InfoFilled /></el-icon>
            接口将通过 DHCP 自动获取 IP 地址、网关和 DNS
          </div>
        </el-form-item>

        <!-- 禁用提示 -->
        <el-form-item v-if="editForm.protocol === 'disabled'" label="说明">
          <div class="form-hint-block warning">
            <el-icon :size="14"><WarningFilled /></el-icon>
            禁用后该接口将无法通信，如果这是您的管理接口，请谨慎操作！
          </div>
        </el-form-item>

        <el-divider />

        <!-- DNS -->
        <el-form-item label="DNS 服务器">
          <div class="dns-list">
            <div v-for="(dns, i) in editForm.dns" :key="i" class="dns-row">
              <el-input
                v-model="editForm.dns[i]"
                placeholder="如 223.5.5.5"
                size="small"
                style="width: 200px"
              />
              <el-button
                v-if="editForm.dns.length > 1"
                type="danger"
                :icon="Remove"
                size="small"
                circle
                @click="removeDns(i)"
              />
            </div>
            <el-button type="primary" link size="small" @click="addDns" :icon="Plus">
              添加 DNS
            </el-button>
          </div>
        </el-form-item>

        <!-- MTU -->
        <el-form-item label="MTU">
          <el-input-number
            v-model="editForm.mtu"
            :min="576"
            :max="9000"
            :step="100"
            size="small"
          />
          <span class="form-hint" style="margin-left: 10px">
            {{ editForm.protocol === 'pppoe' ? 'PPPoE 通常为 1492' : '以太网默认 1500' }}
          </span>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showEdit = false">取消</el-button>
          <el-button
            type="primary"
            @click="saveConfig"
            :loading="saving"
            :icon="Select"
          >
            保存并应用
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- ─────────────── 端口详情抽屉 ─────────────── -->
    <el-drawer
      v-model="showPortDrawer"
      :title="'端口详情 — ' + (portDetail?.name || '')"
      size="450px"
    >
      <div v-if="portDetail" class="port-detail-content">
        <div class="detail-section glass-card">
          <h4>基本信息</h4>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">接口名</span>
              <span class="info-value">{{ portDetail.name }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">驱动</span>
              <span class="info-value mono">{{ portDetail.portInfo?.driver || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">固件版本</span>
              <span class="info-value">{{ portDetail.portInfo?.firmware || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">总线</span>
              <span class="info-value">{{ portDetail.portInfo?.bus_info || '-' }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section glass-card">
          <h4>连接状态</h4>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">连接状态</span>
              <el-tag :type="portDetail.state === 'UP' ? 'success' : 'danger'" size="small">
                {{ portDetail.state === 'UP' ? '已连接' : '未连接' }}
              </el-tag>
            </div>
            <div class="info-item">
              <span class="info-label">速率</span>
              <span class="info-value">{{ portDetail.speed ? portDetail.speed + ' Mbps' : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">双工模式</span>
              <span class="info-value">{{ portDetail.portInfo?.duplex || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">自动协商</span>
              <span class="info-value">{{ portDetail.portInfo?.auto_negotiation || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Wake-on-LAN</span>
              <span class="info-value">{{ portDetail.portInfo?.wol || '-' }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section glass-card">
          <h4>Offload 功能</h4>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">RX Checksum</span>
              <span class="info-value">{{ portDetail.portInfo?.rx_checksum || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">TX Checksum</span>
              <span class="info-value">{{ portDetail.portInfo?.tx_checksum || '-' }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section glass-card">
          <h4>支持的连接模式</h4>
          <div class="link-modes">
            <el-tag
              v-for="mode in (portDetail.portInfo?.supported_links || [])"
              :key="mode"
              size="small"
              type="info"
              style="margin: 2px"
            >
              {{ mode }}
            </el-tag>
            <span v-if="!portDetail.portInfo?.supported_links?.length" class="text-muted">无数据</span>
          </div>
        </div>

        <div class="detail-section glass-card">
          <h4>MAC 地址</h4>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">MAC</span>
              <span class="info-value mono">{{ portDetail.mac }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- ─────────────── 新建接口对话框 ─────────────── -->
    <el-dialog v-model="showCreateDialog" title="新建虚拟接口" width="520px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="接口类型" required>
          <el-select v-model="createForm.type" style="width: 100%">
            <el-option label="Bridge 桥接" value="bridge" />
            <el-option label="VLAN" value="vlan" />
            <el-option label="Dummy 虚拟" value="dummy" />
            <el-option label="MACVLAN" value="macvlan" />
            <el-option label="Bond 绑定" value="bond" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口名称" required>
          <el-input v-model="createForm.name" placeholder="如: br0, vlan10" />
        </el-form-item>
        <el-form-item v-if="createForm.type === 'vlan' || createForm.type === 'macvlan'" label="父接口" required>
          <el-input v-model="createForm.parent" placeholder="如: eth0, ens3" />
        </el-form-item>
        <el-form-item v-if="createForm.type === 'vlan'" label="VLAN ID" required>
          <el-input-number v-model="createForm.vid" :min="1" :max="4094" />
        </el-form-item>
        <el-form-item label="IP 分配">
          <el-select v-model="createForm.ipv4_method" style="width: 100%">
            <el-option label="DHCP 自动获取" value="dhcp" />
            <el-option label="静态 IP" value="static" />
            <el-option label="不分配" value="disabled" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="createForm.ipv4_method === 'static'" label="IP 地址">
          <el-input v-model="createForm.address" placeholder="如: 192.168.10.1/24" />
        </el-form-item>
        <el-form-item v-if="createForm.ipv4_method === 'static'" label="网关">
          <el-input v-model="createForm.gateway" placeholder="如: 192.168.10.254" />
        </el-form-item>
        <el-form-item label="MTU">
          <el-input-number v-model="createForm.mtu" :min="68" :max="9000" :step="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="success" @click="doCreateInterface" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/stores'
import {
  Refresh, Connection, Monitor, Edit, InfoFilled,
  List, Plus, Remove, Select, Link, WarningFilled,
} from '@element-plus/icons-vue'

const interfaces = ref([])
const loading = ref(false)
const refreshing = ref(false)
const showEdit = ref(false)
const saving = ref(false)
const showPortDrawer = ref(false)
const portDetail = ref(null)
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = reactive({
  type: 'bridge',
  name: '',
  parent: '',
  vid: 1,
  ipv4_method: 'dhcp',
  address: '',
  gateway: '',
  dns: [],
  mtu: 1500,
})
const trafficData = ref({})      // 流量缓存 { ifname: { rx_bytes, tx_bytes } }
const flashingIfaces = ref({})   // 闪烁状态 { ifname: true/false }
let trafficTimer = null          // setInterval 句柄

const editForm = reactive({
  iface: '',
  currentState: '',
  currentMac: '',
  protocol: 'dhcp',
  address: '',
  gateway: '',
  dns: [''],
  mtu: 1500,
  pppoeUsername: '',
  pppoePassword: '',
})

// 物理端口列表
const physicalPorts = computed(() => {
  return interfaces.value.filter(i => i.type === 'physical')
})

// 虚拟接口列表
const virtualPorts = computed(() => {
  return interfaces.value.filter(i => i.type !== 'physical')
})

// 虚拟接口图标
function getVirtualIcon(p) {
  if (p.role === 'docker' || p.name.startsWith('docker')) return 'Wallet'
  if (p.role === 'container' || p.name.startsWith('veth')) return 'Connection'
  if (p.role === 'wan' || p.name.startsWith('ppp')) return 'Link'
  return 'FolderOpened'
}

// 判断接口是否有数据流闪烁
function isFlashing(ifname) {
  return flashingIfaces.value[ifname] || false
}

function formatBytes(bytes) {
  if (bytes === undefined || bytes === null) return '--'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

// 轮询流量
async function pollTraffic() {
  try {
    const res = await api.get('/interfaces/traffic')
    const current = res.data.traffic || {}
    const changed = {}

    for (const [name, stats] of Object.entries(current)) {
      const prev = trafficData.value[name]
      if (prev) {
        const rxDiff = stats.rx_packets - (prev.rx_packets || 0)
        const txDiff = stats.tx_packets - (prev.tx_packets || 0)
        changed[name] = rxDiff > 0 || txDiff > 0
      }
    }

    trafficData.value = current
    flashingIfaces.value = changed
  } catch {
    // 静默
  }
}

async function refreshAll() {
  refreshing.value = true
  await Promise.all([fetchInterfaces()])
  refreshing.value = false
}

async function fetchInterfaces() {
  loading.value = true
  try {
    const res = await api.get('/interfaces/list')
    interfaces.value = res.data.interfaces
    // 并发获取物理端口详情
    for (const iface of physicalPorts.value) {
      try {
        const portRes = await api.get(`/interfaces/port/${iface.name}`)
        iface.portInfo = portRes.data.port
      } catch {
        // ethtool 可能不支持
      }
    }
  } catch (e) {
    console.error('获取接口列表失败:', e)
    ElMessage.error('获取接口列表失败')
  }
  loading.value = false
}

function showEditDialog(row) {
  editForm.iface = row.name
  editForm.currentState = row.state
  editForm.currentMac = row.mac

  // 猜测当前协议
  if (row.ipv4 && row.ipv4.length) {
    editForm.address = row.ipv4[0]
    editForm.protocol = 'static'
  } else {
    // 默认 DHCP
    editForm.protocol = 'dhcp'
    editForm.address = ''
  }
  editForm.gateway = ''
  editForm.dns = ['']
  editForm.mtu = row.mtu || 1500
  editForm.pppoeUsername = ''
  editForm.pppoePassword = ''

  showEdit.value = true
}

function addDns() {
  editForm.dns.push('')
}

function removeDns(index) {
  editForm.dns.splice(index, 1)
}

async function showPortDetail(row) {
  try {
    let info = row.portInfo
    if (!info) {
      const res = await api.get(`/interfaces/port/${row.name}`)
      info = res.data.port
    }
    portDetail.value = {
      ...row,
      portInfo: info,
    }
    showPortDrawer.value = true
  } catch (e) {
    ElMessage.error('获取端口详情失败')
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const warningMsg = {
      dhcp: `将 ${editForm.iface} 切换为 DHCP 自动获取 IP，网络可能短暂中断`,
      static: `将 ${editForm.iface} 的 IP 设为 ${editForm.address}，可能影响当前连接`,
      pppoe: `在 ${editForm.iface} 上启动 PPPoE 拨号，将切换为拨号上网模式`,
      disabled: `禁用 ${editForm.iface}，该接口将无法通信！\n如果是当前管理接口，你将失去连接！`,
    }[editForm.protocol] || `修改 ${editForm.iface} 的配置`

    await ElMessageBox.confirm(
      warningMsg + '\n\n⚠️ netplan 将在 120 秒后自动回滚，配置正确后请点击确认。',
      '确认修改',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: false,
      }
    )

    const payload = {
      name: editForm.iface,
      protocol: editForm.protocol,
      address: editForm.protocol === 'static' ? editForm.address : undefined,
      gateway: editForm.protocol === 'static' ? (editForm.gateway || undefined) : undefined,
      dns: editForm.dns.filter(d => d.trim()) || undefined,
      mtu: editForm.mtu || undefined,
      pppoe_username: editForm.protocol === 'pppoe' ? editForm.pppoeUsername : undefined,
      pppoe_password: editForm.protocol === 'pppoe' ? editForm.pppoePassword : undefined,
    }

    const res = await api.put('/interfaces/config', payload)
    if (res.data.success) {
      ElMessage.success(res.data.message || '配置已应用')
      showEdit.value = false

      // 弹出确认对话框
      try {
        await ElMessageBox.confirm(
          '配置已通过 netplan try 应用。如果网络正常工作，请点击"确认"持久化配置。\n\n' +
          '如果不操作，120 秒后 netplan 将自动回滚到之前的状态。',
          '确认 netplan 配置',
          {
            confirmButtonText: '确认并持久化',
            cancelButtonText: '取消（等待自动回滚）',
            type: 'info',
            distinguishCancelAndClose: true,
          }
        )
        const confirmRes = await api.post('/interfaces/confirm')
        if (confirmRes.data.success) {
          ElMessage.success('netplan 配置已确认并持久化')
        } else {
          ElMessage.error(confirmRes.data.message || '确认失败')
        }
      } catch {
        // 用户取消，netplan 将自动回滚
        ElMessage.info('未确认，netplan 将在 120 秒后自动回滚')
      }

      await fetchInterfaces()
    } else {
      ElMessage.error(res.data.message || '配置失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
    }
  }
  saving.value = false
}

onMounted(() => {
  fetchInterfaces()
  // 启动流量轮询（1秒间隔，纯读 /proc/net/dev 无资源开销）
  trafficTimer = setInterval(pollTraffic, 1000)
})

async function doCreateInterface() {
  if (!createForm.name.trim()) { ElMessage.warning('请输入接口名称'); return }
  creating.value = true
  try {
    const payload = { ...createForm }
    // 清理不需要的字段
    if (payload.type !== 'vlan') delete payload.vid
    if (payload.type !== 'vlan' && payload.type !== 'macvlan') delete payload.parent
    if (payload.ipv4_method !== 'static') { delete payload.address; delete payload.gateway }

    const res = await api.post('/interfaces/create', payload)
    ElMessage.success(res.data.message || '接口创建成功')
    showCreateDialog.value = false
    await fetchInterfaces()
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  }
  creating.value = false
}

onUnmounted(() => {
  if (trafficTimer) clearInterval(trafficTimer)
})

</script>

<style scoped>
.interfaces-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

/* 页面标题 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}
.page-header.glass-card {
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: 16px;
  padding: 20px 28px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-left h2 {
  margin: 0;
  font-size: 22px;
  color: #1a1a2e;
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-subtitle {
  color: #888;
  font-size: 13px;
}

/* 分区标题 */
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 16px;
  margin-top: 32px;
}
.section-count {
  font-size: 12px;
  color: #aaa;
  font-weight: 400;
  background: rgba(0,0,0,0.04);
  padding: 0 8px;
  border-radius: 10px;
  line-height: 20px;
}

/* 端口网格 */
.port-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.port-card {
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  transition: box-shadow 0.2s, border-color 0.2s;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.port-card:hover {
  box-shadow: 0 4px 20px rgba(0,82,255,0.08);
  border-color: rgba(0,82,255,0.2);
}
.port-card.is-up {
  border-left: 3px solid #67c23a;
}
.port-card.is-down {
  border-left: 3px solid #f56c6c;
}
.port-card.virtual {
  border-left: 3px solid #909399;
  background: rgba(255,255,255,0.45);
}
.port-card.virtual:hover {
  border-color: rgba(0,82,255,0.3);
}
.port-card.virtual .port-name {
  color: #555;
  font-weight: 500;
}

/* 空卡片占位 */
.empty-card {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: #bbb;
  gap: 12px;
}
.empty-text {
  font-size: 14px;
  color: #aaa;
}

.port-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.port-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.port-name {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.port-state-tag {
  font-size: 11px;
}

.port-speed-indicator {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}
.speed-ring {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 3px solid #ddd;
  background: rgba(255,255,255,0.5);
  transition: all 0.3s;
}
.speed-ring.active {
  border-color: #0052FF;
  background: rgba(0,82,255,0.06);
  box-shadow: 0 0 16px rgba(0,82,255,0.15);
}
.speed-ring.flashing {
  animation: pulse-glow 0.6s ease-in-out;
}
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 8px rgba(0,82,255,0.1); }
  50% { box-shadow: 0 0 24px rgba(0,82,255,0.5), 0 0 40px rgba(0,82,255,0.2); }
}
.speed-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
  margin-top: -4px;
}
.speed-value {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  line-height: 1;
}
.speed-unit {
  font-size: 10px;
  color: #999;
  margin-top: 2px;
}

.port-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.detail-label {
  color: #888;
  font-weight: 500;
}
.detail-value {
  color: #333;
}
.detail-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
}
.text-muted { color: #aaa; }

.port-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid rgba(0,0,0,0.06);
}

/* 表格容器 */
.table-wrapper {
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: 16px;
  padding: 4px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

/* 编辑对话框 */
.edit-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(0,0,0,0.06);
  padding: 20px 24px 16px;
}
.edit-dialog :deep(.el-dialog__body) {
  padding: 24px;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.protocol-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.protocol-group :deep(.el-radio-button__inner) {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.form-hint {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}
.form-hint-block {
  color: #666;
  font-size: 12px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 12px;
  background: #f0f5ff;
  border-radius: 8px;
  line-height: 1.5;
}
.form-hint-block.warning {
  background: #fff7e6;
  color: #d46b08;
}

.dns-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.dns-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 抽屉详情 */
.port-detail-content {
  padding: 8px 4px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-section {
  padding: 16px;
  border-radius: 12px;
}
.detail-section.glass-card {
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.5);
  box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}
.detail-section h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #1a1a2e;
  font-weight: 600;
}
.info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.info-label {
  color: #888;
}
.info-value {
  color: #333;
  font-weight: 500;
}
.info-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
}

.link-modes {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}
</style>
