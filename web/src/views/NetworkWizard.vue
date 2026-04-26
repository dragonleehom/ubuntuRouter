<template>
  <div class="wizard-page">
    <div class="page-header">
      <h2>联网向导</h2>
      <p class="page-desc">快速设置网络连接方式</p>
    </div>

    <el-card shadow="never" style="margin-bottom: 20px">
      <template #header><span>选择上网方式</span></template>

      <!-- 步骤条 -->
      <el-steps :active="step" align-center style="margin: 24px 0 32px">
        <el-step title="选择模式" />
        <el-step title="配置参数" />
        <el-step title="确认结果" />
      </el-steps>

      <!-- Step 0: 选择模式 -->
      <div v-if="step === 0" class="mode-select">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-card
              shadow="hover"
              :class="['mode-card', { selected: mode === 'pppoe' }]"
              @click="mode = 'pppoe'"
            >
              <el-icon :size="48" color="#409EFF"><Connection /></el-icon>
              <h3>PPPoE 拨号</h3>
              <p>输入宽带账号密码拨号上网</p>
              <ul>
                <li>宽带拨号 (ADSL/光纤)</li>
                <li>输入账号密码即可</li>
                <li>支持自动重连</li>
              </ul>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card
              shadow="hover"
              :class="['mode-card', { selected: mode === 'dhcp' }]"
              @click="mode = 'dhcp'"
            >
              <el-icon :size="48" color="#67c23a"><Connection /></el-icon>
              <h3>自动 DHCP</h3>
              <p>上级路由自动分配 IP 地址</p>
              <ul>
                <li>光猫路由模式</li>
                <li>自动获取 IP 地址</li>
                <li>即插即用</li>
              </ul>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card
              shadow="hover"
              :class="['mode-card', { selected: mode === 'bridge' }]"
              @click="mode = 'bridge'"
            >
              <el-icon :size="48" color="#e6a23c"><Connection /></el-icon>
              <h3>旁路由模式</h3>
              <p>作为旁路由/透明网关使用</p>
              <ul>
                <li>仅修改网关和 DNS</li>
                <li>主路由 DHCP 不变</li>
                <li>适合透明代理场景</li>
              </ul>
            </el-card>
          </el-col>
        </el-row>

        <div class="step-actions">
          <el-button type="primary" size="large" @click="step = 1" :disabled="!mode">
            下一步 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- Step 1: 配置参数 -->
      <div v-if="step === 1" class="config-form">
        <!-- PPPoE -->
        <el-form v-if="mode === 'pppoe'" :model="pppoeForm" label-width="120px" style="max-width: 500px; margin: 0 auto">
          <el-form-item label="宽带账号" required>
            <el-input v-model="pppoeForm.username" placeholder="输入宽带账号" />
          </el-form-item>
          <el-form-item label="宽带密码" required>
            <el-input v-model="pppoeForm.password" type="password" show-password placeholder="输入宽带密码" />
          </el-form-item>
          <el-form-item label="MTU">
            <el-input-number v-model="pppoeForm.mtu" :min="576" :max="1500" />
          </el-form-item>
          <el-form-item label="WAN 接口">
            <el-select v-model="pppoeForm.interface" style="width: 100%">
              <el-option v-for="iface in wanInterfaces" :key="iface" :label="iface" :value="iface" />
            </el-select>
            <div class="form-hint">选择连接光猫的物理端口</div>
          </el-form-item>
          <el-form-item label="自动重连">
            <el-switch v-model="pppoeForm.auto_reconnect" />
          </el-form-item>
        </el-form>

        <!-- DHCP -->
        <el-form v-else-if="mode === 'dhcp'" :model="dhcpForm" label-width="120px" style="max-width: 500px; margin: 0 auto">
          <el-form-item label="WAN 接口" required>
            <el-select v-model="dhcpForm.interface" style="width: 100%">
              <el-option v-for="iface in wanInterfaces" :key="iface" :label="iface" :value="iface" />
            </el-select>
            <div class="form-hint">选择连接上级路由的物理端口</div>
          </el-form-item>
          <el-form-item label="DNS 服务器">
            <el-input v-model="dhcpForm.dns" placeholder="可选，多个用逗号分隔" />
          </el-form-item>
          <el-form-item label="主机名">
            <el-input v-model="dhcpForm.hostname" placeholder="可选" />
          </el-form-item>
        </el-form>

        <!-- 旁路由 -->
        <el-form v-else-if="mode === 'bridge'" :model="bridgeForm" label-width="130px" style="max-width: 500px; margin: 0 auto">
          <el-form-item label="LAN 接口" required>
            <el-select v-model="bridgeForm.interface" style="width: 100%">
              <el-option v-for="iface in lanInterfaces" :key="iface" :label="iface" :value="iface" />
            </el-select>
          </el-form-item>
          <el-form-item label="本机 IP 地址" required>
            <el-input v-model="bridgeForm.ip" placeholder="例如 192.168.1.2" />
          </el-form-item>
          <el-form-item label="子网掩码">
            <el-input-number v-model="bridgeForm.mask" :min="8" :max="30" />
          </el-form-item>
          <el-form-item label="主路由网关" required>
            <el-input v-model="bridgeForm.gateway" placeholder="例如 192.168.1.1" />
          </el-form-item>
          <el-form-item label="DNS 服务器" required>
            <el-input v-model="bridgeForm.dns" placeholder="例如 8.8.8.8,114.114.114.114" />
          </el-form-item>
          <el-form-item label="DHCP 关闭">
            <el-switch v-model="bridgeForm.disable_dhcp" />
            <div class="form-hint">旁路由模式建议关闭内置 DHCP</div>
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button @click="step = 0"><el-icon><ArrowLeft /></el-icon> 上一步</el-button>
          <el-button type="primary" size="large" @click="handleApply" :loading="applying">
            {{ applying ? '正在应用...' : '应用配置' }}
          </el-button>
        </div>
      </div>

      <!-- Step 2: 结果 -->
      <div v-if="step === 2" class="result-view">
        <el-result
          :icon="applySuccess ? 'success' : 'error'"
          :title="applySuccess ? '配置已应用' : '配置失败'"
          :sub-title="applySuccess ? resultMessage : (resultError || '请检查参数后重试')"
        >
          <template #extra>
            <el-button v-if="!applySuccess" type="primary" @click="step = 1">返回修改</el-button>
            <el-button v-else @click="resetAll">重新设置</el-button>
          </template>
        </el-result>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { ArrowRight, ArrowLeft, Connection } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const step = ref(0)
const mode = ref('')

const pppoeForm = ref({ username: '', password: '', mtu: 1492, interface: 'ens3', auto_reconnect: true })
const dhcpForm = ref({ interface: 'ens3', dns: '', hostname: 'ubunturouter' })
const bridgeForm = ref({ interface: 'ens3', ip: '', mask: 24, gateway: '', dns: '114.114.114.114,8.8.8.8', disable_dhcp: true })

const wanInterfaces = ref([])
const lanInterfaces = ref([])
const applying = ref(false)
const applySuccess = ref(false)
const resultMessage = ref('')
const resultError = ref('')

onMounted(async () => {
  try {
    const res = await api.get('/interfaces')
    const allIfaces = res.data?.interfaces || []
    // Physical ports as WAN candidates
    wanInterfaces.value = allIfaces
      .filter(i => !i.name.startsWith('lo') && !i.name.startsWith('docker') && !i.name.startsWith('br') && !i.name.startsWith('veth'))
      .map(i => i.name)
    lanInterfaces.value = [...wanInterfaces.value]
  } catch { /* ignore */ }
})

async function handleApply() {
  applying.value = true
  try {
    let res
    if (mode.value === 'pppoe') {
      // Save PPPoE config and dial
      await api.put('/pppoe/config', {
        username: pppoeForm.value.username,
        password: pppoeForm.value.password,
        mtu: pppoeForm.value.mtu,
        auto_reconnect: pppoeForm.value.auto_reconnect,
      })
      await api.post('/pppoe/connect')
      resultMessage.value = `PPPoE 配置已保存，正在拨号至 ${pppoeForm.value.username}`
    } else if (mode.value === 'dhcp') {
      // Switch interface to DHCP
      await api.put('/interfaces/config', {
        name: dhcpForm.value.interface,
        method: 'dhcp',
        dns: dhcpForm.value.dns || undefined,
        hostname: dhcpForm.value.hostname || undefined,
      })
      await api.post('/config/apply')
      resultMessage.value = `${dhcpForm.value.interface} 已切换为 DHCP 自动获取 IP`
    } else if (mode.value === 'bridge') {
      // Set static IP for bridge mode
      const dnsList = bridgeForm.value.dns.split(',').map(s => s.trim()).filter(Boolean)
      await api.put('/interfaces/config', {
        name: bridgeForm.value.interface,
        method: 'static',
        address: bridgeForm.value.ip + '/' + bridgeForm.value.mask,
        gateway: bridgeForm.value.gateway,
        dns: dnsList.length ? dnsList.join(',') : undefined,
      })
      await api.post('/config/apply')
      resultMessage.value = `旁路由模式已配置：${bridgeForm.value.ip} → ${bridgeForm.value.gateway}`
    }
    applySuccess.value = true
    step.value = 2
  } catch (e) {
    applySuccess.value = false
    resultError.value = e.response?.data?.detail || e.message || '应用失败'
    step.value = 2
  }
  applying.value = false
}

function resetAll() {
  step.value = 0
  mode.value = ''
  applySuccess.value = false
  resultMessage.value = ''
}
</script>

<style scoped>
.wizard-page { padding: 0; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px 0; color: #e0e0e0; }
.page-desc { margin: 0; font-size: 13px; color: #888; }

.mode-select { max-width: 900px; margin: 0 auto; }

.mode-card {
  cursor: pointer;
  text-align: center;
  padding: 16px;
  transition: all 0.3s;
  border: 2px solid transparent;
}
.mode-card:hover { border-color: #409EFF; transform: translateY(-2px); }
.mode-card.selected { border-color: #409EFF; background: rgba(64, 158, 255, 0.08); }
.mode-card h3 { margin: 12px 0 8px; color: #e0e0e0; }
.mode-card > p { color: #888; font-size: 13px; margin-bottom: 12px; }
.mode-card ul { text-align: left; color: #999; font-size: 12px; padding-left: 16px; line-height: 1.8; }

.step-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #2a2a3e;
}

.config-form { max-width: 600px; margin: 0 auto; }
.form-hint { font-size: 12px; color: #888; margin-top: 4px; }

.result-view { max-width: 500px; margin: 0 auto; }
</style>
