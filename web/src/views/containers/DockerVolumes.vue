<template>
  <div class="docker-volumes">
    <div class="toolbar">
      <el-button type="primary" size="small" @click="refreshVolumes" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
      <el-button size="small" type="success" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 创建卷
      </el-button>
    </div>

    <el-table :data="volumes" stripe style="width: 100%" v-loading="loading"
      highlight-current-row @row-click="viewVolumeDetails"
      empty-text="暂无 Docker 卷">
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="driver" label="驱动" width="80" />
      <el-table-column prop="mountpoint" label="挂载点" min-width="240" class="hide-mobile">
        <template #default="{ row }">
          <span class="mountpoint-text">{{ row.mountpoint || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="size" label="大小" width="100" align="right" />
      <el-table-column label="创建时间" min-width="160" class="hide-mobile">
        <template #default="{ row }">
          {{ row.created ? formatTime(row.created) : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="danger" @click.stop="removeVolume(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建卷弹窗 -->
    <el-dialog v-model="showCreateDialog" title="创建 Docker 卷" width="420px">
      <el-form :model="createForm" label-width="80px" size="small">
        <el-form-item label="卷名称" required>
          <el-input v-model="createForm.name" placeholder="my_volume" />
        </el-form-item>
        <el-form-item label="驱动">
          <el-select v-model="createForm.driver" style="width:100%">
            <el-option label="local" value="local" />
            <el-option v-for="d in extraDrivers" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="showCreateDialog = false">取消</el-button>
        <el-button size="small" type="primary" @click="doCreateVolume" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 卷详情弹窗 -->
    <el-dialog v-model="detailDialog.visible" title="卷详情" width="550px">
      <div v-if="detailDialog.loading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else-if="detailData">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="名称">{{ detailData.name }}</el-descriptions-item>
          <el-descriptions-item label="驱动">{{ detailData.driver }}</el-descriptions-item>
          <el-descriptions-item label="挂载点">
            <code>{{ detailData.mountpoint }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="大小">{{ detailData.size || '-' }}</el-descriptions-item>
          <el-descriptions-item label="范围">{{ detailData.scope || 'local' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detailData.created || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="Object.keys(detailData.labels || {}).length" label="标签">
            <el-tag v-for="(v, k) in detailData.labels" :key="k" size="small" style="margin:1px">
              {{ k }}: {{ v }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="Object.keys(detailData.options || {}).length" label="选项">
            <pre class="options-view">{{ JSON.stringify(detailData.options, null, 2) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <div v-else style="text-align:center;color:#999">未找到卷详情</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { Refresh, Plus, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const volumes = ref([])
const showCreateDialog = ref(false)
const creating = ref(false)
const extraDrivers = ref(['nfs', 'cifs', 'tmpfs'])
const createForm = ref({
  name: '',
  driver: 'local',
})
const detailDialog = ref({ visible: false, loading: false })
const detailData = ref(null)

onMounted(() => { refreshVolumes() })

async function refreshVolumes() {
  loading.value = true
  try {
    const res = await api.get('/containers/volumes')
    volumes.value = res.data.volumes || []
  } catch (e) {
    ElMessage.error('获取卷列表失败')
  }
  loading.value = false
}

async function doCreateVolume() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入卷名称')
    return
  }
  creating.value = true
  try {
    const payload = {
      name: createForm.value.name.trim(),
      driver: createForm.value.driver,
    }
    await api.post('/containers/volumes', payload)
    ElMessage.success(`卷 '${payload.name}' 创建成功`)
    showCreateDialog.value = false
    createForm.value = { name: '', driver: 'local' }
    await refreshVolumes()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建卷失败')
  }
  creating.value = false
}

async function removeVolume(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除卷 "${row.name}"？\n此操作不可恢复，卷中的数据将被删除。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete(`/containers/volumes/${row.name}`)
    ElMessage.success(`卷 '${row.name}' 已删除`)
    await refreshVolumes()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function viewVolumeDetails(row) {
  detailDialog.value = { visible: true, loading: true }
  detailData.value = null
  try {
    const res = await api.post(`/containers/volumes/${row.name}/inspect`)
    detailData.value = res.data.volume
  } catch (e) {
    ElMessage.error('获取卷详情失败')
  }
  detailDialog.value.loading = false
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return ts
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.text-muted {
  color: #999;
}
.mountpoint-text {
  font-family: monospace;
  font-size: 12px;
  color: #666;
}
.options-view {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  max-height: 120px;
  overflow: auto;
  margin: 0;
}
</style>
