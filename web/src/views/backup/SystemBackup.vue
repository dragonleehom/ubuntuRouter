<template>
  <div class="backup-page">
    <h2>配置备份与恢复</h2>

    <!-- 操作栏 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
            <el-button type="primary" @click="createBackup" :loading="creating">
              <el-icon><Plus /></el-icon> 创建备份
            </el-button>
            <el-button @click="fetchBackups" :loading="loading">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
            <span style="color: #888; font-size: 13px; margin-left: auto;">
              备份目录: {{ backupDir }}
            </span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 备份列表 -->
    <el-table :data="backups" stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="200">
        <template #default="{ row }">
          <code style="font-size: 12px">{{ row.id }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200">
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ row.created_at || new Date(row.timestamp * 1000).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column prop="file_count" label="文件数" width="80" align="center" />
      <el-table-column label="大小" width="120">
        <template #default="{ row }">
          {{ formatBytes(row.file_size_bytes) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="previewBackup(row)">预览</el-button>
          <el-button size="small" type="primary" @click="downloadBackup(row)">下载</el-button>
          <el-button size="small" type="warning" @click="restoreBackup(row)" :disabled="restoring">恢复</el-button>
          <el-button size="small" type="danger" @click="deleteBackup(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && backups.length === 0" description="暂无备份" />

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreview" title="备份文件列表" width="600px">
      <el-table :data="previewFiles" stripe max-height="400">
        <el-table-column prop="path" label="文件路径" min-width="300" />
        <el-table-column prop="size" label="大小" width="100">
          <template #default="{ row }">{{ formatBytes(row.size) }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showPreview = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const creating = ref(false)
const restoring = ref(false)
const backups = ref([])
const backupDir = ref('')
const showPreview = ref(false)
const previewFiles = ref([])

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0; let size = bytes
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return `${size.toFixed(1)} ${units[i]}`
}

async function fetchBackups() {
  loading.value = true
  try {
    const res = await api.get('/backup/list')
    backups.value = res.data.backups || []
    backupDir.value = res.data.backup_dir || ''
  } catch (e) {
    ElMessage.error('获取备份列表失败')
  }
  loading.value = false
}

async function createBackup() {
  creating.value = true
  try {
    const res = await api.post('/backup/create', { description: '' })
    ElMessage.success(res.data.message || '备份创建成功')
    await fetchBackups()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '备份失败')
  }
  creating.value = false
}

async function previewBackup(row) {
  try {
    const res = await api.get(`/backup/${row.id}/preview`)
    previewFiles.value = res.data.files || []
    showPreview.value = true
  } catch (e) {
    ElMessage.error('获取预览失败')
  }
}

async function downloadBackup(row) {
  try {
    const res = await api.get(`/backup/${row.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/gzip' }))
    const a = document.createElement('a')
    a.href = url; a.download = `${row.id}.tar.gz`
    a.click(); URL.revokeObjectURL(url)
    ElMessage.success('下载开始')
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

async function restoreBackup(row) {
  try {
    await ElMessageBox.confirm(
      `确认从备份 "${row.id}" 恢复配置？\n系统将首先创建当前配置的备份。`,
      '确认恢复',
      { confirmButtonText: '恢复', cancelButtonText: '取消', type: 'warning' },
    )
    restoring.value = true
    const res = await api.post(`/backup/${row.id}/restore`)
    ElMessage.success(res.data.message || '恢复成功')
    await fetchBackups()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '恢复失败')
  }
  restoring.value = false
}

async function deleteBackup(row) {
  try {
    await ElMessageBox.confirm(`确认删除备份 "${row.id}"？`, '确认')
    const res = await api.delete(`/backup/${row.id}`)
    ElMessage.success(res.data.message || '已删除')
    await fetchBackups()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(fetchBackups)
</script>

<style scoped>
.backup-page { padding: 0; }
</style>
