<template>
  <div class="devices-page">
    <div class="page-header">
      <h2>在线设备</h2>
      <p class="page-desc">当前网络中已发现的在线设备</p>
    </div>

    <!-- 统计栏 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ devices.length }}</div>
          <div class="stat-label">设备总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ wiredCount }}</div>
          <div class="stat-label">有线设备</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ wirelessCount }}</div>
          <div class="stat-label">无线设备</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ unknownCount }}</div>
          <div class="stat-label">未知设备</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 设备列表 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="table-header">
          <span>设备列表</span>
          <el-button size="small" @click="fetchDevices" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>

      <el-table :data="devices" stripe v-loading="loading" style="width: 100%">
        <el-table-column label="IP 地址" prop="ip" width="140" />
        <el-table-column label="MAC 地址" prop="mac" width="180">
          <template #default="{ row }">
            <code style="font-size: 12px">{{ row.mac }}</code>
          </template>
        </el-table-column>
        <el-table-column label="主机名" prop="hostname" min-width="160">
          <template #default="{ row }">
            <span :class="{ 'text-muted': !row.hostname }">{{ row.hostname || '未知' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="厂商" prop="vendor" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.vendor !== '未知'" size="small" type="info" effect="plain">{{ row.vendor }}</el-tag>
            <span v-else class="text-muted">未知</span>
          </template>
        </el-table-column>
        <el-table-column label="接口" prop="interface" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="dark">{{ row.interface }}</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && devices.length === 0" description="未发现在线设备" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/stores'
import { Refresh } from '@element-plus/icons-vue'

const route = useRoute()
const loading = ref(false)
const devices = ref([])

onMounted(() => {
  document.title = route.meta?.title || '在线设备'
  fetchDevices()
})

async function fetchDevices() {
  loading.value = true
  try {
    const res = await api.get('/arp/list')
    devices.value = res.data.devices || []
  } catch {
    devices.value = []
  }
  loading.value = false
}

const wiredCount = computed(() => devices.value.filter(d => d.interface && !d.interface.startsWith('wl')).length)
const wirelessCount = computed(() => devices.value.filter(d => d.interface && d.interface.startsWith('wl')).length)
const unknownCount = computed(() => devices.value.filter(d => !d.interface).length)
</script>

<style scoped>
.devices-page { padding: 0; }
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px 0; color: #e0e0e0; }
.page-desc { margin: 0; font-size: 13px; color: #888; }

.stats-row { margin-bottom: 20px; }
.stat-card { text-align: center; padding: 12px 0; }
.stat-value { font-size: 28px; font-weight: 700; color: #409EFF; }
.stat-label { font-size: 13px; color: #888; margin-top: 4px; }

.table-card { margin-bottom: 20px; }
.table-header { display: flex; justify-content: space-between; align-items: center; }

.text-muted { color: #666; }
code { font-family: 'Courier New', monospace; }
</style>
