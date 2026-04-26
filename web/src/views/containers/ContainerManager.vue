<template>
  <div class="containers-page">
    <h2>容器管理</h2>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">容器总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-running">
          <div class="stat-value">{{ stats.running }}</div>
          <div class="stat-label">运行中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-stopped">
          <div class="stat-value">{{ stats.stopped }}</div>
          <div class="stat-label">已停止</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-projects">
          <div class="stat-value">{{ composeProjects.length }}</div>
          <div class="stat-label">Compose 项目</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tabs: 容器列表 / Compose 项目 -->
    <el-tabs v-model="activeTab">
      <el-tab-pane label="容器列表" name="containers">
        <div class="toolbar">
          <el-button type="primary" size="small" @click="refreshContainers">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>

        <el-table :data="containers" stripe style="width: 100%" v-loading="loading">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="image" label="镜像" min-width="200">
            <template #default="{ row }">
              <span class="image-name">{{ row.image }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'running' ? 'success' : 'info'" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="state" label="详情" min-width="160" />
          <el-table-column prop="ports" label="端口" min-width="160">
            <template #default="{ row }">
              <span v-if="row.ports && row.ports.length">
                <el-tag v-for="p in row.ports" :key="`${p.host_port}-${p.container_port}`" size="small" style="margin: 1px">
                  {{ p.host_port }}:{{ p.container_port }}/{{ p.protocol }}
                </el-tag>
              </span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button-group>
                <el-button v-if="row.status === 'running'" size="small" type="warning" @click="stopContainer(row)">
                  停止
                </el-button>
                <el-button v-else size="small" type="success" @click="startContainer(row)">
                  启动
                </el-button>
                <el-button size="small" @click="restartContainer(row)">重启</el-button>
                <el-button size="small" type="danger" @click="removeContainer(row)">删除</el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Compose 项目" name="compose">
        <div class="toolbar">
          <el-button type="primary" size="small" @click="refreshCompose">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>

        <el-table :data="composeProjects" stripe style="width: 100%">
          <el-table-column prop="name" label="项目名称" min-width="200" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.status === 'running' ? 'success' : 'info'" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="services" label="服务" min-width="200">
            <template #default="{ row }">
              <el-tag v-for="s in row.services" :key="s.name" size="small" style="margin: 1px"
                :type="s.state === 'running' ? 'success' : 'info'">
                {{ s.name }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button size="small" @click="viewComposeLogs(row)">日志</el-button>
              <el-button size="small" @click="restartCompose(row)">重启</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 日志对话框 -->
    <el-dialog v-model="logDialog.visible" :title="`日志: ${logDialog.title}`" width="80%">
      <pre class="log-viewer">{{ logDialog.content }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '@/stores'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const containers = ref([])
const composeProjects = ref([])
const activeTab = ref('containers')

const logDialog = ref({
  visible: false,
  title: '',
  content: '',
})

const stats = computed(() => {
  const total = containers.value.length
  const running = containers.value.filter(c => c.status === 'running').length
  const stopped = total - running
  return { total, running, stopped }
})

async function refreshContainers() {
  loading.value = true
  try {
    const res = await api.get('/containers')
    containers.value = res.data.containers || []
  } catch (e) {
    ElMessage.error('获取容器列表失败')
  }
  loading.value = false
}

async function refreshCompose() {
  try {
    const res = await api.get('/containers/compose/projects')
    composeProjects.value = res.data.projects || []
  } catch (e) {
    ElMessage.error('获取 Compose 项目列表失败')
  }
}

async function startContainer(row) {
  try {
    await api.post(`/containers/${row.id}/start`)
    ElMessage.success('容器已启动')
    await refreshContainers()
  } catch (e) {
    ElMessage.error('启动失败')
  }
}

async function stopContainer(row) {
  try {
    await api.post(`/containers/${row.id}/stop`)
    ElMessage.success('容器已停止')
    await refreshContainers()
  } catch (e) {
    ElMessage.error('停止失败')
  }
}

async function restartContainer(row) {
  try {
    await api.post(`/containers/${row.id}/restart`)
    ElMessage.success('容器已重启')
    await refreshContainers()
  } catch (e) {
    ElMessage.error('重启失败')
  }
}

async function removeContainer(row) {
  try {
    await ElMessageBox.confirm(`确认删除容器 "${row.name}"？`, '确认')
    await api.delete(`/containers/${row.id}`)
    ElMessage.success('容器已删除')
    await refreshContainers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function viewComposeLogs(project) {
  try {
    const res = await api.get(`/containers/compose/${project.name}/logs`, {
      params: { tail: 200 },
    })
    logDialog.value = {
      visible: true,
      title: project.name,
      content: res.data.logs || '暂无日志',
    }
  } catch (e) {
    ElMessage.error('获取日志失败')
  }
}

async function restartCompose(project) {
  try {
    await api.post(`/containers/compose/${project.name}/restart`)
    ElMessage.success('项目已重启')
    await refreshCompose()
  } catch (e) {
    ElMessage.error('重启失败')
  }
}

onMounted(() => {
  refreshContainers()
  refreshCompose()
})
</script>

<style scoped>
.containers-page { padding: 0; }
.stat-row { margin-bottom: 20px; }
.stat-card { text-align: center; padding: 8px; }
.stat-value { font-size: 32px; font-weight: 600; color: #409EFF; }
.stat-running .stat-value { color: #67C23A; }
.stat-stopped .stat-value { color: #909399; }
.stat-projects .stat-value { color: #E6A23C; }
.stat-label { font-size: 13px; color: #999; margin-top: 4px; }
.toolbar { margin-bottom: 12px; display: flex; gap: 8px; }
.image-name { font-family: monospace; font-size: 13px; }
.text-muted { color: #666; }
.log-viewer {
  background: #1a1a1a;
  color: #e0e0e0;
  padding: 16px;
  border-radius: 4px;
  font-size: 13px;
  font-family: monospace;
  max-height: 500px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
