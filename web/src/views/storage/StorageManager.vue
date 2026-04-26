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
    <el-dialog v-model="detailDialog.visible" :title="`/dev/${detailDialog.disk?.name} 详情`" width="700px">
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

        <!-- SMART 信息 -->
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
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { Refresh, Monitor } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const activeTab = ref('disks')
const disks = ref([])
const mounts = ref([])
const smartInfo = ref({})
const detailDialog = ref({ visible: false, disk: null })

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
