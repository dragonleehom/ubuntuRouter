<template>
  <div class="page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="system-card">
          <template #header><span>系统信息</span></template>
          <div class="info-grid" v-if="systemInfo">
            <div class="info-row">
              <span class="label">主机名</span>
              <span class="value">{{ systemInfo.hostname }}</span>
            </div>
            <div class="info-row">
              <span class="label">系统</span>
              <span class="value">{{ systemInfo.os?.distro }} {{ systemInfo.os?.version }}</span>
            </div>
            <div class="info-row">
              <span class="label">初始化状态</span>
              <el-tag :type="systemInfo.initialized ? 'success' : 'warning'" size="small">
                {{ systemInfo.initialized ? '已初始化' : '未初始化' }}
              </el-tag>
            </div>
          </div>
          <el-skeleton :rows="3" animated v-else />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="system-card">
          <template #header><span>服务状态</span></template>
          <div class="service-list" v-if="systemInfo?.services">
            <div v-for="(svc, name) in systemInfo.services" :key="name" class="service-item">
              <span class="service-name">{{ name }}</span>
              <el-tag :type="svc.active ? 'success' : 'danger'" size="small">
                {{ svc.active ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </div>
          <el-skeleton :rows="3" animated v-else />
        </el-card>
      </el-col>
    </el-row>

    <el-card class="snapshot-card">
      <template #header>
        <div class="card-header">
          <span>配置快照</span>
          <el-button size="small" @click="fetchSnapshots">刷新</el-button>
        </div>
      </template>
      <el-table :data="snapshots" stripe v-loading="snapLoading" v-if="snapshots.length">
        <el-table-column prop="created_at" label="创建时间" width="200" />
        <el-table-column prop="summary" label="描述" />
        <el-table-column prop="snapshot_id" label="快照 ID" width="200" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.good" type="success" size="small">正常</el-tag>
            <el-tag v-else type="info" size="small">未知</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!snapLoading" description="暂无快照" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'

const systemInfo = ref(null)
const snapshots = ref([])
const snapLoading = ref(false)

onMounted(async () => {
  try {
    const res = await api.get('/system/status')
    systemInfo.value = res.data
  } catch (e) {
    console.error('获取系统信息失败:', e)
  }
  await fetchSnapshots()
})

async function fetchSnapshots() {
  snapLoading.value = true
  try {
    const res = await api.get('/system/snapshots')
    snapshots.value = res.data.snapshots
  } catch (e) {
    console.error('获取快照列表失败:', e)
  }
  snapLoading.value = false
}
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; color: #e0e0e0; }
.system-card { margin-bottom: 20px; }
.info-grid { display: flex; flex-direction: column; gap: 12px; }
.info-row { display: flex; justify-content: space-between; align-items: center; }
.info-row .label { color: #888; font-size: 14px; }
.info-row .value { color: #ccc; font-size: 14px; }
.service-list { display: flex; flex-direction: column; gap: 8px; }
.service-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
.service-name { color: #ccc; font-size: 14px; }
.snapshot-card { margin-top: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
