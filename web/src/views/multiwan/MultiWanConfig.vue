<template>
  <div class="multiwan-container">
    <el-tabs v-model="activeTab">
      <!-- 状态概览 -->
      <el-tab-pane label="线路状态" name="status">
        <div class="section-header">
          <h3>WAN 线路状态</h3>
          <div class="header-actions">
            <el-button
              :type="healthRunning ? 'danger' : 'success'"
              size="small"
              :icon="healthRunning ? VideoPause : VideoPlay"
              @click="toggleHealthCheck"
            >
              {{ healthRunning ? '停止检测' : '启动检测' }}
            </el-button>
          </div>
        </div>

        <el-table :data="wanStatus" stripe style="width: 100%" v-loading="loading.status">
          <el-table-column prop="name" label="线路" width="100" />
          <el-table-column prop="iface" label="接口" width="120" class="hide-mobile" />
          <el-table-column prop="gateway" label="网关" width="140" class="hide-mobile" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.online ? 'success' : 'danger'" size="small" effect="dark">
                {{ row.online ? '在线' : '离线' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="活跃" width="80" align="center" class="hide-mobile">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" type="primary" size="small" effect="dark">主用</el-tag>
              <span v-else style="color:#666">备用</span>
            </template>
          </el-table-column>
          <el-table-column prop="latency_ms" label="延迟(ms)" width="100" class="hide-mobile">
            <template #default="{ row }">
              <span :style="{ color: row.latency_ms > 100 ? '#E6A23C' : '#67C23A' }">
                {{ row.latency_ms }} ms
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="packet_loss" label="丢包率" width="90" class="hide-mobile">
            <template #default="{ row }">
              <span :style="{ color: row.packet_loss > 5 ? '#F56C6C' : '#67C23A' }">
                {{ row.packet_loss }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="failures" label="连续失败" width="100" class="hide-mobile" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                :disabled="!row.online || row.is_active"
                @click="switchToWan(row.name)"
              >
                切换
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 配置 -->
      <el-tab-pane label="策略配置" name="config">
        <el-form :model="form" label-width="140px" v-loading="loading.config">
          <el-divider content-position="left">WAN 线路</el-divider>

          <div v-for="(wan, idx) in form.wans" :key="idx" class="wan-row">
            <el-row :gutter="12" align="middle">
              <el-col :span="5">
                <el-form-item :label="`线路 ${idx + 1}`" label-width="60">
                  <el-input v-model="wan.name" placeholder="名称" size="small" />
                </el-form-item>
              </el-col>
              <el-col :span="5">
                <el-form-item label-width="0">
                  <el-input v-model="wan.iface" placeholder="接口(如 eth0)" size="small" />
                </el-form-item>
              </el-col>
              <el-col :span="5">
                <el-form-item label-width="0">
                  <el-input v-model="wan.gateway" placeholder="网关 IP" size="small" />
                </el-form-item>
              </el-col>
              <el-col :span="3">
                <el-form-item label-width="0">
                  <el-input-number v-model="wan.weight" :min="1" :max="100" size="small" />
                </el-form-item>
              </el-col>
              <el-col :span="3">
                <el-button type="danger" :icon="Delete" circle size="small" @click="removeWan(idx)" />
              </el-col>
            </el-row>
          </div>

          <el-button type="primary" plain size="small" @click="addWan">+ 添加线路</el-button>

          <el-divider content-position="left">检测参数</el-divider>

          <el-form-item label="检测间隔(秒)">
            <el-input-number v-model="form.check_interval" :min="1" :max="300" />
          </el-form-item>

          <el-form-item label="Ping 次数">
            <el-input-number v-model="form.ping_count" :min="1" :max="10" />
          </el-form-item>

          <el-form-item label="Ping 目标">
            <div v-for="(target, idx) in form.ping_targets" :key="idx" class="target-row">
              <el-input v-model="form.ping_targets[idx]" placeholder="IP 或域名" size="small" style="width:200px" />
              <el-button type="danger" :icon="Delete" circle size="small" @click="removeTarget(idx)" />
            </div>
            <el-button type="primary" plain size="small" @click="addTarget">+ 添加目标</el-button>
          </el-form-item>

          <el-divider content-position="left">故障转移</el-divider>

          <el-form-item label="失败阈值">
            <el-input-number v-model="form.failure_threshold" :min="1" :max="10" />
            <span class="form-hint">连续失败次数触发切换</span>
          </el-form-item>

          <el-form-item label="恢复阈值">
            <el-input-number v-model="form.recovery_threshold" :min="1" :max="10" />
            <span class="form-hint">连续成功次数触发恢复</span>
          </el-form-item>

          <el-form-item label="自动故障切换">
            <el-switch v-model="form.auto_failover" />
          </el-form-item>

          <el-form-item label="负载均衡">
            <el-switch v-model="form.load_balance" />
            <span class="form-hint">开启后流量按 weight 比例分配到各线路</span>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
            <el-button @click="loadConfig">重置</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { api } from '@/stores'

const activeTab = ref('status')
const healthRunning = ref(false)
const saving = ref(false)

const loading = reactive({
  status: false,
  config: false,
})

// ─── WAN 状态 ───────────────────────────────────────────────

const wanStatus = ref([])
let pollTimer = null

async function fetchStatus() {
  try {
    const res = await api.get('/multiwan/status')
    wanStatus.value = res.data.wans
  } catch {
    // ignore polling errors
  }
}

async function fetchHealth() {
  try {
    const res = await api.get('/multiwan/health')
    healthRunning.value = res.data.running
  } catch {
    healthRunning.value = false
  }
}

async function toggleHealthCheck() {
  try {
    if (healthRunning.value) {
      await api.post('/multiwan/stop')
      healthRunning.value = false
      ElMessage.success('健康检查已停止')
    } else {
      await api.post('/multiwan/start')
      healthRunning.value = true
      ElMessage.success('健康检查已启动')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function switchToWan(name) {
  try {
    await api.post(`/multiwan/switch?wan_name=${name}`)
    ElMessage.success(`已切换到 ${name}`)
    await fetchStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '切换失败')
  }
}

// ─── 配置表单 ───────────────────────────────────────────────

const form = reactive({
  wans: [],
  check_interval: 5,
  ping_targets: ['8.8.8.8', '114.114.114.114'],
  ping_count: 3,
  failure_threshold: 2,
  recovery_threshold: 3,
  auto_failover: true,
  load_balance: false,
})

async function loadConfig() {
  loading.config = true
  try {
    const res = await api.get('/multiwan/config')
    Object.assign(form, res.data)
  } catch (e) {
    ElMessage.error('加载配置失败')
  } finally {
    loading.config = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    await api.put('/multiwan/config', form)
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function addWan() {
  form.wans.push({ name: '', iface: '', gateway: '', weight: 1 })
}

function removeWan(idx) {
  form.wans.splice(idx, 1)
}

function addTarget() {
  form.ping_targets.push('')
}

function removeTarget(idx) {
  form.ping_targets.splice(idx, 1)
}

// ─── 生命周期 ──────────────────────────────────────────────

onMounted(async () => {
  loading.status = true
  await Promise.all([fetchStatus(), fetchHealth(), loadConfig()])
  loading.status = false

  // 每 5 秒轮询状态
  pollTimer = setInterval(fetchStatus, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.multiwan-container {
  padding: 0;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.section-header h3 {
  margin: 0;
  color: #ccc;
  font-size: 16px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.wan-row {
  margin-bottom: 8px;
}
.target-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.form-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #666;
}
</style>
