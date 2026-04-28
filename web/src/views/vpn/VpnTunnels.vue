<template>
  <div class="page">
    <div class="page-header">
      <h2>VPN 隧道</h2>
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
          <div class="stat-value">{{ stats.tunnels_count || 0 }}</div>
          <div class="stat-label">隧道数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value green">{{ stats.active_tunnels || 0 }}</div>
          <div class="stat-label">活跃隧道</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total_peers || 0 }}</div>
          <div class="stat-label">Peer 数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ formatBytes(stats.total_rx_bytes + stats.total_tx_bytes) }}</div>
          <div class="stat-label">总流量</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 协议标签页 -->
    <el-tabs v-model="activeTab">
      <!-- ─── WireGuard ─── -->
      <el-tab-pane label="WireGuard" name="wireguard">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span style="color:#ccc;">WireGuard 隧道</span>
              <el-button type="primary" size="small" @click="showAddTunnel = true">
                <el-icon style="margin-right:4px"><Plus /></el-icon>创建隧道
              </el-button>
            </div>
          </template>
          <el-table :data="tunnels" stripe size="small" v-loading="loading">
            <el-table-column prop="name" label="名称" width="100" />
            <el-table-column prop="public_key" label="公钥" min-width="200" class="hide-mobile">
              <template #default="{ row }">
                <code style="font-size:11px;color:#999;">{{ row.public_key ? row.public_key.substring(0, 32) + '...' : '-' }}</code>
              </template>
            </el-table-column>
            <el-table-column prop="listen_port" label="端口" width="80" class="hide-mobile" />
            <el-table-column prop="address" label="隧道 IP" width="140" class="hide-mobile" />
            <el-table-column prop="peers_count" label="Peer 数" width="80" align="right" class="hide-mobile" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.running ? 'success' : 'info'" size="small">{{ row.running ? '运行中' : '已停止' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button v-if="!row.running" size="small" type="success" text @click="startTunnel(row)">启动</el-button>
                <el-button v-else size="small" type="warning" text @click="stopTunnel(row)">停止</el-button>
                <el-button size="small" type="primary" text @click="showTunnelDetail(row)">详情</el-button>
                <el-button size="small" type="danger" text @click="deleteTunnel(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="tunnels.length === 0" description="暂无 VPN 隧道" />
        </el-card>
      </el-tab-pane>

      <!-- ─── PPTP ─── -->
      <el-tab-pane label="PPTP" name="pptp">
        <div class="toolbar">
          <el-tag :type="pptpStatus.running ? 'success' : 'info'" size="default" style="margin-right:12px">
            {{ pptpStatus.running ? '● 运行中' : '○ 已停止' }}
          </el-tag>
          <el-button size="small" @click="fetchPptpUsers">刷新</el-button>
          <el-button v-if="!pptpStatus.running" size="small" type="success" @click="pptpStart">启动服务</el-button>
          <el-button v-else size="small" type="warning" @click="pptpStop">停止服务</el-button>
          <el-button type="primary" size="small" @click="showAddPptpUser = true">
            <el-icon style="margin-right:4px"><Plus /></el-icon>添加用户
          </el-button>
        </div>
        <el-card shadow="never" class="section-card">
          <template #header><span style="color:#ccc;">PPTP 用户 ({{ pptpUsers.length }})</span></template>
          <el-table :data="pptpUsers" stripe size="small" v-loading="pptpLoading">
            <el-table-column prop="username" label="用户名" min-width="200" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="deletePptpUser(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="pptpUsers.length === 0 && !pptpLoading" description="暂无 PPTP 用户" />
        </el-card>
        <el-dialog v-model="showAddPptpUser" title="添加 PPTP 用户" width="400px">
          <el-form :model="newPptpUser" label-width="80px" size="small">
            <el-form-item label="用户名"><el-input v-model="newPptpUser.username" placeholder="输入用户名" /></el-form-item>
            <el-form-item label="密码"><el-input v-model="newPptpUser.password" type="password" show-password placeholder="输入密码" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showAddPptpUser = false">取消</el-button>
            <el-button type="primary" @click="addPptpUser">添加</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ─── IPSec ─── -->
      <el-tab-pane label="IPSec/IKEv2" name="ipsec">
        <div class="toolbar">
          <el-tag :type="ipsecStatus.running ? 'success' : 'info'" size="default" style="margin-right:12px">
            {{ ipsecStatus.running ? '● 运行中' : '○ 已停止' }}
          </el-tag>
          <el-button size="small" @click="fetchIpsecData">刷新</el-button>
          <el-button v-if="!ipsecStatus.running" size="small" type="success" @click="ipsecStart">启动服务</el-button>
          <el-button v-else size="small" type="warning" @click="ipsecStop">停止服务</el-button>
          <el-button size="small" type="primary" @click="ipsecGenerateCert" :loading="ipsecCertLoading">生成证书</el-button>
          <el-button type="primary" size="small" @click="showAddIpsecUser = true">
            <el-icon style="margin-right:4px"><Plus /></el-icon>添加用户
          </el-button>
        </div>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-card shadow="never" class="section-card">
              <template #header><span style="color:#ccc;">配置</span></template>
              <el-form :model="ipsecForm" label-width="100px" size="small">
                <el-form-item label="PSK"><el-input v-model="ipsecForm.psk" placeholder="预共享密钥" /></el-form-item>
                <el-form-item label="本地子网"><el-input v-model="ipsecForm.left_subnet" placeholder="如 192.168.1.0/24" /></el-form-item>
                <el-form-item label="端口"><el-input v-model.number="ipsecForm.ports" placeholder="500" /></el-form-item>
                <el-form-item label="DNS1"><el-input v-model="ipsecForm.dns1" placeholder="8.8.8.8" /></el-form-item>
                <el-form-item label="DNS2"><el-input v-model="ipsecForm.dns2" placeholder="8.8.4.4" /></el-form-item>
                <el-button type="primary" size="small" @click="ipsecSaveConfig" :loading="ipsecConfigLoading">保存配置</el-button>
              </el-form>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" class="section-card">
              <template #header><span style="color:#ccc;">用户 ({{ ipsecUsers.length }})</span></template>
              <el-table :data="ipsecUsers" stripe size="small" v-loading="ipsecUserLoading">
                <el-table-column prop="username" label="用户名" min-width="120" />
                <el-table-column label="导出" width="80">
                  <template #default="{ row }">
                    <el-button text type="primary" size="small" @click="ipsecExportConfig(row.username)">
                      导出
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column label="删除" width="60">
                  <template #default="{ row }">
                    <el-button text type="danger" size="small" @click="deleteIpsecUser(row)">×</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="ipsecUsers.length === 0 && !ipsecUserLoading" description="暂无用户" />
            </el-card>
          </el-col>
        </el-row>
        <el-dialog v-model="showAddIpsecUser" title="添加 IPSec 用户" width="400px">
          <el-form :model="newIpsecUser" label-width="80px" size="small">
            <el-form-item label="用户名"><el-input v-model="newIpsecUser.username" placeholder="输入用户名" /></el-form-item>
            <el-form-item label="密码"><el-input v-model="newIpsecUser.password" type="password" show-password placeholder="输入密码" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showAddIpsecUser = false">取消</el-button>
            <el-button type="primary" @click="addIpsecUser">添加</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ─── OpenVPN ─── -->
      <el-tab-pane label="OpenVPN" name="openvpn">
        <div class="toolbar">
          <el-tag :type="openvpnStatus.running ? 'success' : 'info'" size="default" style="margin-right:12px">
            {{ openvpnStatus.running ? '● 运行中' : '○ 已停止' }}
          </el-tag>
          <el-button size="small" @click="fetchOpenvpnData">刷新</el-button>
          <el-button v-if="!openvpnStatus.running" size="small" type="success" @click="openvpnStart">启动服务</el-button>
          <el-button v-else size="small" type="warning" @click="openvpnStop">停止服务</el-button>
          <el-button size="small" type="warning" @click="openvpnInitPki" :loading="openvpnPkiLoading">初始化 PKI</el-button>
          <el-button type="primary" size="small" @click="showAddOvpnClient = true">
            <el-icon style="margin-right:4px"><Plus /></el-icon>添加客户端
          </el-button>
        </div>
        <el-row :gutter="12">
          <el-col :span="10">
            <el-card shadow="never" class="section-card">
              <template #header><span style="color:#ccc;">配置</span></template>
              <el-form :model="openvpnForm" label-width="100px" size="small">
                <el-form-item label="协议"><el-select v-model="openvpnForm.proto"><el-option label="TCP" value="tcp" /><el-option label="UDP" value="udp" /></el-select></el-form-item>
                <el-form-item label="端口"><el-input-number v-model="openvpnForm.port" :min="1" :max="65535" /></el-form-item>
                <el-form-item label="加密"><el-input v-model="openvpnForm.cipher" placeholder="AES-256-GCM" /></el-form-item>
                <el-form-item label="认证"><el-input v-model="openvpnForm.auth" placeholder="SHA256" /></el-form-item>
                <el-button type="primary" size="small" @click="openvpnSaveConfig">保存配置</el-button>
              </el-form>
            </el-card>
          </el-col>
          <el-col :span="14">
            <el-card shadow="never" class="section-card">
              <template #header><span style="color:#ccc;">客户端 ({{ openvpnClients.length }})</span></template>
              <el-table :data="openvpnClients" stripe size="small" v-loading="openvpnClientLoading">
                <el-table-column prop="name" label="名称" min-width="100" />
                <el-table-column prop="valid_until" label="有效期" min-width="130" class="hide-mobile" />
                <el-table-column label="导出" width="70">
                  <template #default="{ row }">
                    <el-button text type="primary" size="small" @click="openvpnExportConfig(row.name)">
                      下载
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="70">
                  <template #default="{ row }">
                    <el-button text type="danger" size="small" @click="revokeOpenvpnClient(row)">撤销</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="openvpnClients.length === 0 && !openvpnClientLoading" description="暂无客户端" />
            </el-card>
          </el-col>
        </el-row>
        <el-dialog v-model="showAddOvpnClient" title="添加 OpenVPN 客户端" width="400px">
          <el-form :model="newOvpnClient" label-width="100px" size="small">
            <el-form-item label="客户端名称"><el-input v-model="newOvpnClient.name" placeholder="如 phone, laptop" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showAddOvpnClient = false">取消</el-button>
            <el-button type="primary" @click="addOpenvpnClient">添加</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建隧道对话框 -->
    <el-dialog v-model="showAddTunnel" title="创建 WireGuard 隧道" width="500px">
      <el-form :model="newTunnel" label-width="100px" size="small">
        <el-form-item label="名称">
          <el-input v-model="newTunnel.name" placeholder="如 wg0, office-vpn" />
        </el-form-item>
        <el-form-item label="监听端口">
          <el-input-number v-model="newTunnel.listen_port" :min="1024" :max="65535" />
        </el-form-item>
        <el-form-item label="隧道 IP">
          <el-input v-model="newTunnel.address" placeholder="如 10.0.0.1/24" />
        </el-form-item>
        <el-form-item label="DNS">
          <el-input v-model="newTunnel.dns" placeholder="可选，如 10.0.0.1" />
        </el-form-item>
        <el-form-item label="MTU">
          <el-input-number v-model="newTunnel.mtu" :min="1280" :max="1500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddTunnel = false">取消</el-button>
        <el-button type="primary" @click="addTunnel">创建</el-button>
      </template>
    </el-dialog>

    <!-- 隧道详情对话框 -->
    <el-dialog v-model="showDetail" :title="'隧道: ' + detail.name" width="700px">
      <el-descriptions :column="2" border size="small" v-if="detail.name">
        <el-descriptions-item label="名称">{{ detail.name }}</el-descriptions-item>
        <el-descriptions-item label="公钥"><code style="font-size:11px;">{{ detail.public_key }}</code></el-descriptions-item>
        <el-descriptions-item label="监听端口">{{ detail.listen_port }}</el-descriptions-item>
        <el-descriptions-item label="隧道 IP">{{ detail.address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="MTU">{{ detail.mtu }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="detail.running ? 'success' : 'info'" size="small">
            {{ detail.running ? '运行中' : '已停止' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <h4 style="color:#ccc;margin:20px 0 10px;">Peer 列表</h4>
      <div class="toolbar">
        <el-button size="small" type="primary" @click="showAddPeer = true">
          <el-icon style="margin-right:4px"><Plus /></el-icon>添加 Peer
        </el-button>
      </div>
      <el-table :data="detail.peers || []" stripe size="small">
        <el-table-column label="公钥" min-width="180">
          <template #default="{ row }">
            <code style="font-size:11px;">{{ row.public_key.substring(0, 32) + '...' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="endpoint" label="端点" width="160" class="hide-mobile" />
        <el-table-column label="AllowedIPs" width="160" class="hide-mobile">
          <template #default="{ row }">{{ (row.allowed_ips || []).join(', ') }}</template>
        </el-table-column>
        <el-table-column label="握手" width="80" class="hide-mobile">
          <template #default="{ row }">
            {{ row.latest_handshake > 0 ? formatTime(row.latest_handshake) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="下载" width="80" align="right" class="hide-mobile">
          <template #default="{ row }">{{ formatBytes(row.transfer_rx) }}</template>
        </el-table-column>
        <el-table-column label="上传" width="80" align="right" class="hide-mobile">
          <template #default="{ row }">{{ formatBytes(row.transfer_tx) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="60">
          <template #default="{ row, $index }">
            <el-button text type="danger" size="small" @click="removePeer($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!detail.peers || detail.peers.length === 0" description="暂无 Peer" />

      <!-- 添加 Peer 对话框 -->
      <el-dialog v-model="showAddPeer" title="添加 Peer" width="500px" append-to-body>
        <el-form :model="newPeer" label-width="120px" size="small">
          <el-form-item label="公钥">
            <el-input v-model="newPeer.public_key" placeholder="Peer 的公钥" />
          </el-form-item>
          <el-form-item label="端点">
            <el-input v-model="newPeer.endpoint" placeholder="如 1.2.3.4:51820" />
          </el-form-item>
          <el-form-item label="AllowedIPs">
            <el-input v-model="newPeer.allowed_ips" placeholder="如 10.0.0.2/32, 192.168.1.0/24" />
          </el-form-item>
          <el-form-item label="Keepalive">
            <el-input-number v-model="newPeer.persistent_keepalive" :min="0" :max="300" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showAddPeer = false">取消</el-button>
          <el-button type="primary" @click="addPeer">添加</el-button>
        </template>
      </el-dialog>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { api } from '@/stores'

const loading = ref(false)
const tunnels = ref([])
const stats = reactive({ tunnels_count: 0, active_tunnels: 0, total_peers: 0, total_rx_bytes: 0, total_tx_bytes: 0 })
const showAddTunnel = ref(false)
const showDetail = ref(false)
const showAddPeer = ref(false)
const detail = reactive({ name: '', peers: [] })
const selectedTunnelName = ref('')
const activeTab = ref('wireguard')

const newTunnel = reactive({ name: 'wg0', listen_port: 51820, address: '10.0.0.1/24', dns: '', mtu: 1420 })
const newPeer = reactive({ public_key: '', endpoint: '', allowed_ips: '', persistent_keepalive: 25 })

// ── PPTP ──
const pptpLoading = ref(false)
const pptpUsers = ref([])
const pptpStatus = reactive({ running: false })
const showAddPptpUser = ref(false)
const newPptpUser = reactive({ username: '', password: '' })

// ── IPSec ──
const ipsecLoading = ref(false)
const ipsecUserLoading = ref(false)
const ipsecConfigLoading = ref(false)
const ipsecCertLoading = ref(false)
const ipsecStatus = reactive({ running: false })
const ipsecUsers = ref([])
const ipsecForm = reactive({ psk: '', left_subnet: '', ports: 500, dns1: '', dns2: '' })
const showAddIpsecUser = ref(false)
const newIpsecUser = reactive({ username: '', password: '' })

// ── OpenVPN ──
const openvpnLoading = ref(false)
const openvpnClientLoading = ref(false)
const openvpnPkiLoading = ref(false)
const openvpnStatus = reactive({ running: false })
const openvpnClients = ref([])
const openvpnForm = reactive({ proto: 'udp', port: 1194, cipher: 'AES-256-GCM', auth: 'SHA256' })
const showAddOvpnClient = ref(false)
const newOvpnClient = reactive({ name: '' })

async function refreshData() {
  loading.value = true
  try {
    const [tunnelsRes, statsRes] = await Promise.all([
      api.get('/vpn/tunnels'),
      api.get('/vpn/stats'),
    ])
    tunnels.value = tunnelsRes.data.tunnels || []
    Object.assign(stats, statsRes.data)
  } catch (e) {
    ElMessage.error('获取 VPN 数据失败')
  }
  loading.value = false
}

async function addTunnel() {
  try {
    const res = await api.post('/vpn/tunnels', {
      name: newTunnel.name,
      listen_port: newTunnel.listen_port,
      address: newTunnel.address,
      dns: newTunnel.dns,
      mtu: newTunnel.mtu,
    })
    if (res.data.success) {
      ElMessage.success(res.data.message)
      ElMessage.info(`公钥: ${res.data.public_key}`)
      showAddTunnel.value = false
      await refreshData()
    }
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function startTunnel(row) {
  try {
    const res = await api.post(`/vpn/tunnels/${row.name}/start`)
    ElMessage.success(res.data.message)
    await refreshData()
  } catch (e) {
    ElMessage.error('启动失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function stopTunnel(row) {
  try {
    const res = await api.post(`/vpn/tunnels/${row.name}/stop`)
    ElMessage.success(res.data.message)
    await refreshData()
  } catch (e) {
    ElMessage.error('停止失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function showTunnelDetail(row) {
  try {
    const res = await api.get(`/vpn/tunnels/${row.name}`)
    Object.assign(detail, res.data)
    selectedTunnelName.value = row.name
    showDetail.value = true
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

async function deleteTunnel(row) {
  try {
    await ElMessageBox.confirm(`确定删除隧道 "${row.name}"？`, '确认')
    const res = await api.delete(`/vpn/tunnels/${row.name}`)
    ElMessage.success(res.data.message)
    await refreshData()
  } catch { /* cancelled */ }
}

async function addPeer() {
  if (!selectedTunnelName.value) return
  try {
    const allowedIPs = newPeer.allowed_ips
      ? newPeer.allowed_ips.split(',').map(s => s.trim()).filter(Boolean)
      : []
    const res = await api.post(`/vpn/tunnels/${selectedTunnelName.value}/peers`, {
      public_key: newPeer.public_key,
      endpoint: newPeer.endpoint,
      allowed_ips: allowedIPs,
      persistent_keepalive: newPeer.persistent_keepalive,
    })
    if (res.data.success) {
      ElMessage.success(res.data.message)
      showAddPeer.value = false
      // 刷新详情
      await showTunnelDetail({ name: selectedTunnelName.value })
    }
  } catch (e) {
    ElMessage.error('添加 Peer 失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function removePeer(index) {
  if (!detail.peers || !detail.peers[index]) return
  const pk = detail.peers[index].public_key
  try {
    await ElMessageBox.confirm('确定移除该 Peer？', '确认')
    const res = await api.delete(`/vpn/tunnels/${selectedTunnelName.value}/peers/${encodeURIComponent(pk)}`)
    ElMessage.success(res.data.message)
    await showTunnelDetail({ name: selectedTunnelName.value })
  } catch { /* cancelled */ }
}

onMounted(refreshData)

// ══════════════════════════════════════════════════════════
// PPTP Methods
// ══════════════════════════════════════════════════════════
async function fetchPptpUsers() {
  pptpLoading.value = true
  try {
    const [usersRes, statusRes] = await Promise.all([
      api.get('/vpn/pptp/users').catch(() => ({ data: { users: [] } })),
      api.get('/vpn/pptp/status').catch(() => ({ data: { running: false } })),
    ])
    pptpUsers.value = usersRes.data.users || []
    Object.assign(pptpStatus, statusRes.data)
  } catch (e) { /* ignore */ }
  pptpLoading.value = false
}
async function pptpStart() {
  try { await api.post('/vpn/pptp/start'); ElMessage.success('PPTP 已启动'); await fetchPptpUsers() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '启动失败') }
}
async function pptpStop() {
  try { await api.post('/vpn/pptp/stop'); ElMessage.success('PPTP 已停止'); await fetchPptpUsers() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '停止失败') }
}
async function addPptpUser() {
  try {
    const res = await api.post('/vpn/pptp/users', { username: newPptpUser.username, password: newPptpUser.password })
    ElMessage.success(res.data.message); showAddPptpUser.value = false; newPptpUser.username = ''; newPptpUser.password = ''; await fetchPptpUsers()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
}
async function deletePptpUser(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户 \"${row.username}\"？`, '确认')
    await api.delete(`/vpn/pptp/users/${encodeURIComponent(row.username)}`)
    ElMessage.success('用户已删除'); await fetchPptpUsers()
  } catch { /* cancelled */ }
}

// ══════════════════════════════════════════════════════════
// IPSec Methods
// ══════════════════════════════════════════════════════════
async function fetchIpsecData() {
  ipsecLoading.value = true
  try {
    const [statusRes, configRes, usersRes] = await Promise.all([
      api.get('/vpn/ipsec/status').catch(() => ({ data: { running: false } })),
      api.get('/vpn/ipsec/config').catch(() => ({ data: {} })),
      api.get('/vpn/ipsec/users').catch(() => ({ data: { users: [] } })),
    ])
    Object.assign(ipsecStatus, statusRes.data)
    if (configRes.data.psk) Object.assign(ipsecForm, configRes.data)
    ipsecUsers.value = usersRes.data.users || []
  } catch (e) { /* ignore */ }
  ipsecLoading.value = false
}
async function ipsecStart() {
  try { await api.post('/vpn/ipsec/start'); ElMessage.success('IPSec 已启动'); await fetchIpsecData() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '启动失败') }
}
async function ipsecStop() {
  try { await api.post('/vpn/ipsec/stop'); ElMessage.success('IPSec 已停止'); await fetchIpsecData() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '停止失败') }
}
async function ipsecGenerateCert() {
  ipsecCertLoading.value = true
  try { const res = await api.post('/vpn/ipsec/generate-cert'); ElMessage.success(res.data.message || '证书生成完成') }
  catch (e) { ElMessage.error(e.response?.data?.detail || '证书生成失败') }
  ipsecCertLoading.value = false
}
async function ipsecSaveConfig() {
  ipsecConfigLoading.value = true
  try { await api.put('/vpn/ipsec/config', ipsecForm); ElMessage.success('配置已保存') }
  catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  ipsecConfigLoading.value = false
}
async function addIpsecUser() {
  try {
    const res = await api.post('/vpn/ipsec/users', { username: newIpsecUser.username, password: newIpsecUser.password })
    ElMessage.success(res.data.message); showAddIpsecUser.value = false; newIpsecUser.username = ''; newIpsecUser.password = ''; await fetchIpsecData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
}
async function deleteIpsecUser(row) {
  try {
    await ElMessageBox.confirm(`确定删除用户 \"${row.username}\"？`, '确认')
    await api.delete(`/vpn/ipsec/users/${encodeURIComponent(row.username)}`)
    ElMessage.success('用户已删除'); await fetchIpsecData()
  } catch { /* cancelled */ }
}
async function ipsecExportConfig(username) {
  try {
    const res = await api.get(`/vpn/ipsec/export-config/${encodeURIComponent(username)}`, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'application/x-apple-aspen-config' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `${username}.mobileconfig`; a.click()
    URL.revokeObjectURL(url)
  } catch (e) { ElMessage.error('导出失败') }
}

// ══════════════════════════════════════════════════════════
// OpenVPN Methods
// ══════════════════════════════════════════════════════════
async function fetchOpenvpnData() {
  openvpnLoading.value = true
  try {
    const [statusRes, configRes, clientsRes] = await Promise.all([
      api.get('/vpn/openvpn/status').catch(() => ({ data: { running: false } })),
      api.get('/vpn/openvpn/config').catch(() => ({ data: {} })),
      api.get('/vpn/openvpn/clients').catch(() => ({ data: { clients: [] } })),
    ])
    Object.assign(openvpnStatus, statusRes.data)
    if (configRes.data.proto) Object.assign(openvpnForm, configRes.data)
    openvpnClients.value = clientsRes.data.clients || []
  } catch (e) { /* ignore */ }
  openvpnLoading.value = false
}
async function openvpnStart() {
  try { await api.post('/vpn/openvpn/start'); ElMessage.success('OpenVPN 已启动'); await fetchOpenvpnData() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '启动失败') }
}
async function openvpnStop() {
  try { await api.post('/vpn/openvpn/stop'); ElMessage.success('OpenVPN 已停止'); await fetchOpenvpnData() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '停止失败') }
}
async function openvpnInitPki() {
  openvpnPkiLoading.value = true
  try { const res = await api.post('/vpn/openvpn/init-pki'); ElMessage.success(res.data.message || 'PKI 初始化完成') }
  catch (e) { ElMessage.error(e.response?.data?.detail || 'PKI 初始化失败') }
  openvpnPkiLoading.value = false; await fetchOpenvpnData()
}
async function openvpnSaveConfig() {
  try { await api.put('/vpn/openvpn/config', openvpnForm); ElMessage.success('配置已保存') }
  catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') }
}
async function addOpenvpnClient() {
  try {
    const res = await api.post('/vpn/openvpn/clients', { name: newOvpnClient.name })
    ElMessage.success(res.data.message); showAddOvpnClient.value = false; newOvpnClient.name = ''; await fetchOpenvpnData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
}
async function revokeOpenvpnClient(row) {
  try {
    await ElMessageBox.confirm(`确定撤销客户端 \"${row.name}\" 的证书？`, '确认')
    const res = await api.delete(`/vpn/openvpn/clients/${encodeURIComponent(row.name)}`)
    ElMessage.success(res.data.message); await fetchOpenvpnData()
  } catch { /* cancelled */ }
}
async function openvpnExportConfig(name) {
  try {
    const res = await api.get(`/vpn/openvpn/export-config/${encodeURIComponent(name)}`, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `${name}.ovpn`; a.click()
    URL.revokeObjectURL(url)
  } catch (e) { ElMessage.error('导出失败') }
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatTime(ts) {
  if (!ts || ts === 0) return '-'
  const now = Math.floor(Date.now() / 1000)
  const diff = now - ts
  if (diff < 60) return diff + 's'
  if (diff < 3600) return Math.floor(diff / 60) + 'm'
  return Math.floor(diff / 3600) + 'h'
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
.stat-label {
  font-size: 13px;
  color: #888;
  margin-top: 4px;
}
.section-card {
  background: #141414;
  border: 1px solid #222;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar { margin-bottom: 12px; }
</style>
