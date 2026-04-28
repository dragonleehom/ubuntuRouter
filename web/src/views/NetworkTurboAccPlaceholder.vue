<template>
  <div class="page">
    <div class="page-header">
      <h2>Turbo ACC</h2>
    </div>

    <el-row :gutter="16">
      <!-- BBR -->
      <el-col :span="12">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>BBR 拥塞控制</span>
              <el-switch v-model="bbrEnabled" @change="toggleBBR" :loading="bbrLoading" />
            </div>
          </template>
          <el-form label-width="140px" size="small">
            <el-form-item label="当前拥塞算法">
              <el-tag>{{ congestionAlgo || '-' }}</el-tag>
            </el-form-item>
            <el-form-item label="BBR 版本">
              <el-select v-model="bbrVersion" :disabled="!bbrEnabled" style="width:200px">
                <el-option label="BBRv1" value="bbr" />
                <el-option label="BBRv3" value="bbr3" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-tag :type="bbrEnabled ? 'success' : 'info'">{{ bbrEnabled ? '已启用' : '已禁用' }}</el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 硬件加速 -->
      <el-col :span="12">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>Flow Offloading</span>
              <el-switch v-model="offloadEnabled" @change="toggleOffload" :loading="offloadLoading" />
            </div>
          </template>
          <el-form label-width="140px" size="small">
            <el-form-item label="模式">
              <el-select v-model="offloadMode" :disabled="!offloadEnabled" style="width:200px">
                <el-option label="软件加速 (software)" value="software" />
                <el-option label="硬件加速 (hardware)" value="hardware" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-tag :type="offloadEnabled ? 'success' : 'info'">{{ offloadEnabled ? '已启用' : '已禁用' }}</el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统信息 -->
    <el-card shadow="never" class="section-card" style="margin-top:16px">
      <template #header><span>系统信息</span></template>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="内核版本">{{ kernelVersion }}</el-descriptions-item>
        <el-descriptions-item label="TCP 可用算法">{{ availableAlgos }}</el-descriptions-item>
        <el-descriptions-item label="当前拥塞算法">{{ congestionAlgo }}</el-descriptions-item>
        <el-descriptions-item label="nf_conntrack 最大数">{{ conntrackMax }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/stores'

const bbrEnabled = ref(false)
const bbrVersion = ref('bbr')
const bbrLoading = ref(false)
const offloadEnabled = ref(false)
const offloadMode = ref('software')
const offloadLoading = ref(false)
const congestionAlgo = ref('')
const availableAlgos = ref('')
const kernelVersion = ref('')
const conntrackMax = ref('')

async function fetchStatus() {
  try {
    const res = await api.get('/firewall/stats')
    // 从系统读取
    const sysRes = await api.get('/system/info').catch(() => ({ data: {} }))
    kernelVersion.value = sysRes.data?.kernel || '-'
  } catch { /* ignore */ }

  // 直接从 VM 读取
  try {
    const r = await fetch('/api/v1/system/turbo-acc').catch(() => null)
    if (r) {
      const data = await r.json()
      bbrEnabled.value = data.bbr_enabled || false
      offloadEnabled.value = data.offload_enabled || false
      congestionAlgo.value = data.congestion_algo || ''
      availableAlgos.value = data.available_algos || ''
      conntrackMax.value = data.conntrack_max || ''
    }
  } catch { /* fallback to shell read */ }
}

// 直接 API 路径（通过 SSH 或系统命令的后端端点）
// 实际使用正式的 API: api.get('/system/turbo-acc/status')

async function toggleBBR(val) {
  bbrLoading.value = true
  try {
    await api.post('/system/turbo-acc/bbr', { enabled: val, version: bbrVersion.value })
    ElMessage.success(val ? 'BBR 已启用' : 'BBR 已禁用')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
    bbrEnabled.value = !val
  }
  bbrLoading.value = false
}

async function toggleOffload(val) {
  offloadLoading.value = true
  try {
    await api.post('/system/turbo-acc/offload', { enabled: val, mode: offloadMode.value })
    ElMessage.success(val ? 'Flow Offloading 已启用' : 'Flow Offloading 已禁用')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
    offloadEnabled.value = !val
  }
  offloadLoading.value = false
}

onMounted(fetchStatus)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { color: #e0e0e0; margin: 0; }
.section-card { background: #141414; border: 1px solid #222; }
.card-header { display: flex; justify-content: space-between; align-items: center; color: #ccc; }
</style>
