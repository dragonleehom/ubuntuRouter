<template>
  <div class="storage-page">
    <h2>存储管理</h2>

    <el-tabs v-model="activeTab">
      <!-- 磁盘概览 -->
      <el-tab-pane label="磁盘" name="disks">
        <div class="toolbar">
          <el-button @click="fetchOverview" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>

        <el-row :gutter="16">
          <el-col v-for="disk in disks" :key="disk.name" :xs="24" :sm="12" :lg="8" style="margin-bottom: 16px">
            <el-card shadow="hover" class="disk-card" @click="showDiskDetail(disk)">
              <div class="disk-header">
                <el-icon :size="24" :color="disk.type === 'disk' ? '#409EFF' : '#67C23A'">
                  <Monitor />
                </el-icon>
                <span class="disk-name">/dev/{{ disk.name }}</span>
              </div>
              <div class="disk-body">
                <div class="disk-info">
                  <span class="label">类型</span>
                  <span>{{ disk.type }}</span>
                </div>
                <div class="disk-info">
                  <span class="label">容量</span>
                  <span>{{ formatBytes(disk.size_bytes) }}</span>
                </div>
                <div class="disk-info">
                  <span class="label">SSD</span>
                  <el-tag :type="disk.is_ssd ? 'success' : 'info'" size="small">
                    {{ disk.is_ssd ? '是' : '否' }}
                  </el-tag>
                </div>
                <div class="disk-info" v-if="disk.model">
                  <span class="label">型号</span>
                  <span>{{ disk.model }}</span>
                </div>
                <div class="disk-info" v-if="disk.vendor">
                  <span class="label">厂商</span>
                  <span>{{ disk.vendor }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-if="!loading && disks.length === 0" description="未检测到磁盘" />
      </el-tab-pane>

      <!-- 挂载点 -->
      <el-tab-pane label="挂载点" name="mounts">
        <el-table :data="mounts" stripe v-loading="loading">
          <el-table-column prop="target" label="挂载点" min-width="200" />
          <el-table-column prop="source" label="设备" width="200" />
          <el-table-column prop="fstype" label="文件系统" width="100" />
          <el-table-column label="容量" width="150">
            <template #default="{ row }">
              {{ formatBytes(row.size) }}
            </template>
          </el-table-column>
          <el-table-column label="已用" width="150">
            <template #default="{ row }">
              <el-progress :percentage="parseInt(row['use%']) || 0" :stroke-width="16" striped>
                <span>{{ formatBytes(row.used) }} / {{ formatBytes(row.size) }}</span>
              </el-progress>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 磁盘详情对话框 -->
    <el-dialog v-model="detailDialog.visible" :title="`/dev/${detailDialog.disk?.name} 详情`" width="850px">
      <template v-if="detailDialog.disk">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="设备">{{ detailDialog.disk.name }}</el-descriptions-item>
          <el-descriptions-item label="容量">{{ formatBytes(detailDialog.disk.size_bytes) }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ detailDialog.disk.type }}</el-descriptions-item>
          <el-descriptions-item label="SSD">
            <el-tag :type="detailDialog.disk.is_ssd ? 'success' : 'info'" size="small">
              {{ detailDialog.disk.is_ssd ? '是' : '否' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="型号" v-if="detailDialog.disk.model">{{ detailDialog.disk.model }}</el-descriptions-item>
          <el-descriptions-item label="序列号" v-if="detailDialog.disk.serial">{{ detailDialog.disk.serial }}</el-descriptions-item>
          <el-descriptions-item label="传输协议" v-if="detailDialog.disk.transport">{{ detailDialog.disk.transport }}</el-descriptions-item>
          <el-descriptions-item label="厂商" v-if="detailDialog.disk.vendor">{{ detailDialog.disk.vendor }}</el-descriptions-item>
        </el-descriptions>

        <!-- S.M.A.R.T 状态 -->
        <h4 style="margin: 20px 0 10px">S.M.A.R.T 状态</h4>
        <div v-if="smartInfo.error" class="smart-error">{{ smartInfo.error }}</div>
        <el-descriptions v-else :column="2" border size="small">
          <el-descriptions-item label="整体健康">
            <el-tag :type="smartInfo.overall_health === 'PASSED' ? 'success' : 'danger'">
              {{ smartInfo.overall_health || '未知' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="温度">{{ smartInfo.temperature || '-' }} °C</el-descriptions-item>
          <el-descriptions-item label="通电时间">{{ smartInfo.power_on_hours || '-' }} 小时</el-descriptions-item>
          <el-descriptions-item label="已重映射扇区">{{ smartInfo.reallocated_sector_count || '-' }}</el-descriptions-item>
          <el-descriptions-item label="待处理扇区">{{ smartInfo.pending_sectors || '-' }}</el-descriptions-item>
          <el-descriptions-item label="离线无法修正">{{ smartInfo.offline_uncorrectable || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- APM / 休眠管理 -->
        <h4 style="margin: 20px 0 10px">
          APM / 硬盘休眠管理
          <el-button size="small" @click="fetchApmStatus" :loading="apmLoading" style="margin-left: 12px">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </h4>

        <!-- APM 加载中 -->
        <div v-if="apmLoading && !apmData.device" style="padding: 20px; text-align: center; color: #888">加载 APM 信息中...</div>

        <!-- APM 错误 -->
        <div v-else-if="apmError" class="smart-error">{{ apmError }}</div>

        <!-- APM 数据展示 -->
        <template v-else-if="apmData.device">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="硬盘状态" :span="1">
              <el-tag :type="statusTagType" size="small">
                {{ statusLabel }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="APM 级别" :span="1">
              <template v-if="apmData.apm_enabled">
                {{ apmData.apm_level ?? '-' }}
                <span style="color: #888; font-size: 12px; margin-left: 4px">({{ apmData.apm_level_name || '未知' }})</span>
              </template>
              <span v-else style="color: #888">未启用</span>
            </el-descriptions-item>
            <el-descriptions-item label="休眠超时" :span="1">
              {{ apmData.spindown_timeout_name || '永不超时' }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- 修改按钮 -->
          <div style="margin-top: 12px; text-align: right">
            <el-button type="primary" size="small" @click="showApmForm = !showApmForm">
              {{ showApmForm ? '取消' : '修改设置' }}
            </el-button>
          </div>

          <!-- APM 设置表单 -->
          <el-form v-if="showApmForm" ref="apmFormRef" :model="apmForm" style="margin-top: 12px" label-width="140px">
            <el-form-item label="APM 级别 (1-255)">
              <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
                <el-slider
                  v-model="apmForm.apm_level"
                  :min="1"
                  :max="255"
                  :step="1"
                  show-input
                  style="width: 240px"
                />
                <span style="color: #888; font-size: 12px; margin-left: 4px">
                  {{ apmForm.apm_level_name }}
                </span>
              </div>
              <div style="margin-top: 4px; font-size: 12px; color: #666">
                1-127 = 性能优先 | 128-254 = 允许降速 | 255 = 禁用 APM
              </div>
            </el-form-item>

            <el-form-item label="休眠超时">
              <div style="display: flex; gap: 8px; align-items: center">
                <el-select v-model="apmForm.spindown_timeout" placeholder="选择超时时间" style="width: 240px">
                  <el-option label="永不超时（禁用）" :value="0" />
                  <el-option label="5 秒" :value="1" />
                  <el-option label="10 秒" :value="2" />
                  <el-option label="30 秒" :value="6" />
                  <el-option label="1 分钟" :value="12" />
                  <el-option label="2 分钟" :value="24" />
                  <el-option label="3 分钟" :value="36" />
                  <el-option label="5 分钟" :value="60" />
                  <el-option label="10 分钟" :value="120" />
                  <el-option label="15 分钟" :value="180" />
                  <el-option label="20 分钟" :value="240" />
                </el-select>
                <span style="color: #888; font-size: 12px">{{ apmForm.spindown_timeout_label }}</span>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveApmSettings" :loading="apmSaving">保存设置</el-button>
              <el-button @click="showApmForm = false">取消</el-button>
            </el-form-item>
          </el-form>
        </template>

        <!-- 未检测到 APM -->
        <div v-else style="padding: 12px; color: #888; text-align: center; border: 1px dashed #444; border-radius: 4px;">
          无法获取 APM 信息（hdparm 可能未安装或不支持）
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { api } from '@/stores'
import { Refresh, Monitor } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const activeTab = ref('disks')
const disks = ref([])
const mounts = ref([])
const smartInfo = ref({})
const detailDialog = ref({ visible: false, disk: null })

// APM state
const apmLoading = ref(false)
const apmSaving = ref(false)
const apmError = ref('')
const apmData = ref({})
const showApmForm = ref(false)
const apmForm = ref({
  apm_level: 128,
  spindown_timeout: 0,
  spindown_timeout_label: '',
  apm_level_name: '',
})

// APM level name lookup
const APM_LEVEL_NAMES = {
  '1-63': '高性能（极低延迟）',
  '64-127': '性能优先',
  '128-254': '中间值（允许旋转降速）',
  '255-255': '禁用 APM',
}

// Spindown timeout options with labels
function getSpindownLabel(value) {
  if (value === 0) return '永不超时'
  if (value <= 11) return `${value * 5} 秒`
  if (value <= 240) return `${value * 5} 秒 (约 ${Math.round(value * 5 / 60)} 分钟)`
  if (value <= 251) return `${(value - 240) * 30} 分钟`
  if (value === 252) return '21 分钟'
  if (value === 253) return '~8 小时'
  if (value === 254) return '预留'
  if (value === 255) return '21 分钟 + 15 分钟'
  return `${value}`
}

function getApmLevelName(level) {
  if (!level) return '未知'
  if (level >= 1 && level <= 63) return '高性能（极低延迟）'
  if (level >= 64 && level <= 127) return '性能优先'
  if (level >= 128 && level <= 254) return '中间值（允许旋转降速）'
  if (level === 255) return '禁用 APM'
  return '未知'
}

// Watch APM level changes to update the name
watch(() => apmForm.value.apm_level, (val) => {
  apmForm.value.apm_level_name = getApmLevelName(val)
})

// Status display
const statusLabel = computed(() => {
  const s = apmData.value.status
  if (!s || s === 'unknown') return '未知'
  if (s === 'active') return '工作中'
  if (s === 'idle') return '空闲'
  if (s === 'standby') return '待机/休眠'
  if (s === 'sleep') return '睡眠'
  return s
})

const statusTagType = computed(() => {
  const s = apmData.value.status
  if (!s || s === 'unknown') return 'info'
  if (s === 'active') return 'success'
  if (s === 'idle') return 'warning'
  if (s === 'standby' || s === 'sleep') return 'danger'
  return 'info'
})

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

async function fetchOverview() {
  loading.value = true
  try {
    const res = await api.get('/storage/overview')
    disks.value = res.data.disks || []
    mounts.value = res.data.mounts || []
  } catch (e) {
    ElMessage.error('获取存储信息失败')
  }
  loading.value = false
}

async function showDiskDetail(disk) {
  detailDialog.value = { visible: true, disk }
  smartInfo.value = {}
  // Reset APM state
  apmData.value = {}
  apmError.value = ''
  showApmForm.value = false

  // Fetch SMART info
  try {
    const res = await api.get(`/storage/disks/${disk.name}`)
    if (res.data.smart_info) {
      smartInfo.value = res.data.smart_info
    }
    if (res.data.smart) {
      smartInfo.value = res.data.smart
    }
  } catch (e) {
    smartInfo.value = { error: '获取 SMART 信息失败' }
  }

  // Fetch APM status
  await fetchApmStatus()
}

async function fetchApmStatus() {
  if (!detailDialog.value.disk) return
  apmLoading.value = true
  apmError.value = ''
  try {
    const res = await api.get(`/storage/disks/${detailDialog.value.disk.name}/apm`)
    apmData.value = res.data
    // Pre-fill form with current values
    apmForm.value.apm_level = res.data.apm_level || 128
    apmForm.value.apm_level_name = getApmLevelName(res.data.apm_level)
    apmForm.value.spindown_timeout = res.data.spindown_timeout || 0
    apmForm.value.spindown_timeout_label = getSpindownLabel(res.data.spindown_timeout)
  } catch (e) {
    if (e.response?.status === 400 && e.response?.data?.detail?.includes('hdparm')) {
      apmError.value = 'hdparm 未安装，请先安装: sudo apt install hdparm'
    } else if (e.response?.status === 404) {
      apmError.value = '设备不存在'
    } else {
      apmError.value = '获取 APM 信息失败: ' + (e.response?.data?.detail || e.message)
    }
  }
  apmLoading.value = false
}

async function saveApmSettings() {
  apmSaving.value = true
  try {
    const payload = {}
    const devName = detailDialog.value.disk?.name

    if (apmForm.value.apm_level !== undefined && apmForm.value.apm_level !== null) {
      payload.apm_level = apmForm.value.apm_level
    }

    if (apmForm.value.spindown_timeout !== undefined && apmForm.value.spindown_timeout !== null) {
      payload.spindown_timeout = apmForm.value.spindown_timeout
    }

    const res = await api.post(`/storage/disks/${devName}/apm`, payload)
    ElMessage.success('APM/休眠设置已更新')
    showApmForm.value = false
    // Refresh APM status
    await fetchApmStatus()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
  apmSaving.value = false
}

onMounted(() => fetchOverview())
</script>

<style scoped>
.storage-page { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.disk-card { cursor: pointer; transition: transform 0.2s; }
.disk-card:hover { transform: translateY(-2px); }
.disk-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.disk-name { font-size: 16px; font-weight: 500; }
.disk-body { }
.disk-info { display: flex; justify-content: space-between; padding: 4px 0; font-size: 14px; border-bottom: 1px solid #222; }
.disk-info .label { color: #888; }
.smart-error { color: #e6a23c; padding: 8px; background: #1a1a1a; border-radius: 4px; }
</style>
