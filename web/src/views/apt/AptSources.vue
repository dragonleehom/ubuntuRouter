<template>
  <div class="apt-page">
    <h2>软件源管理</h2>

    <!-- 状态卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">源总数</div>
            <div class="stat-value">{{ status.total_sources || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">活跃源</div>
            <div class="stat-value">{{ status.active_sources || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">当前镜像</div>
            <div class="stat-value small">{{ status.current_mirror_display || '未知' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">Ubuntu</div>
            <div class="stat-value small">{{ status.codename || '未知' }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon> 添加源
      </el-button>
      <el-button @click="runAptUpdate" :loading="updating" :disabled="updating">
        <el-icon><Refresh /></el-icon> apt update
      </el-button>
      <el-button @click="fetchAll" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <!-- 镜像切换 -->
    <el-card shadow="hover" style="margin-bottom: 20px">
      <template #header><span>切换镜像源</span></template>
      <el-row :gutter="12">
        <el-col v-for="m in mirrors" :key="m.key" :span="8" style="margin-bottom: 12px">
          <el-button
            :type="m.active ? 'primary' : 'default'"
            @click="switchMirror(m.key)"
            :loading="switching === m.key"
            style="width: 100%"
          >
            {{ m.display }}
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 源列表 -->
    <el-table :data="sources" stripe v-loading="loading" style="width: 100%" max-height="400">
      <el-table-column prop="type" label="类型" width="80">
        <template #default="{ row }">
          <el-tag :type="row.type === 'deb' ? 'primary' : 'warning'" size="small">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="uri" label="URI" min-width="300" show-overflow-tooltip />
      <el-table-column prop="distribution" label="发行版" width="120" />
      <el-table-column prop="components" label="组件" width="200">
        <template #default="{ row }">
          <el-tag v-for="c in row.components" :key="c" size="small" style="margin-right: 4px">{{ c }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="file" label="源文件" width="160" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="removeSource(row.uri)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && sources.length === 0" description="暂无软件源" />

    <!-- 添加源对话框 -->
    <el-dialog v-model="showAddDialog" title="添加 APT 源" width="550px">
      <el-form label-width="100px">
        <el-form-item label="源行" required>
          <el-input
            v-model="addLine"
            type="textarea"
            :rows="3"
            placeholder="deb http://archive.ubuntu.com/ubuntu noble main"
          />
        </el-form-item>
        <p style="color: #888; font-size: 12px; margin-top: -8px;">
          可使用 {codename} 占位符，会自动替换为当前 Ubuntu 版本代号
        </p>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addSource" :loading="adding">添加</el-button>
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
const updating = ref(false)
const adding = ref(false)
const switching = ref('')
const sources = ref([])
const mirrors = ref([])
const status = ref({})
const showAddDialog = ref(false)
const addLine = ref('')

async function fetchSources() {
  try {
    const res = await api.get('/apt/sources')
    sources.value = res.data.sources || []
  } catch (e) {
    ElMessage.error('获取源列表失败')
  }
}

async function fetchMirrors() {
  try {
    const res = await api.get('/apt/mirrors')
    mirrors.value = res.data.mirrors || []
  } catch (e) {
    /* ignore */
  }
}

async function fetchStatus() {
  try {
    const res = await api.get('/apt/status')
    status.value = res.data
  } catch (e) { /* ignore */ }
}

async function fetchAll() {
  loading.value = true
  await Promise.all([fetchSources(), fetchMirrors(), fetchStatus()])
  loading.value = false
}

async function addSource() {
  if (!addLine.value.trim()) {
    ElMessage.warning('请输入源行')
    return
  }
  adding.value = true
  try {
    const res = await api.post('/apt/sources', { line: addLine.value })
    ElMessage.success(res.data.message || '添加成功')
    showAddDialog.value = false
    addLine.value = ''
    await fetchSources()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  }
  adding.value = false
}

async function removeSource(uri) {
  try {
    await ElMessageBox.confirm(`确认删除包含 ${uri} 的所有源？`, '确认')
    const res = await api.delete('/apt/sources', { data: { uri } })
    ElMessage.success(res.data.message || '删除成功')
    await fetchAll()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function switchMirror(key) {
  switching.value = key
  try {
    const res = await api.put('/apt/sources/mirror', { mirror: key })
    ElMessage.success(res.data.message || '镜像切换成功')
    await fetchAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '切换失败')
  }
  switching.value = ''
}

async function runAptUpdate() {
  updating.value = true
  try {
    const res = await api.post('/apt/update')
    if (res.data.success) {
      ElMessage.success('apt update 完成')
    } else {
      ElMessage.warning('apt update 返回非零状态码')
    }
    await fetchStatus()
  } catch (e) {
    ElMessage.error('apt update 失败')
  }
  updating.value = false
}

onMounted(fetchAll)
</script>

<style scoped>
.apt-page { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.stat-item { text-align: center; padding: 8px; }
.stat-label { font-size: 13px; color: #888; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #e0e0e0; }
.stat-value.small { font-size: 14px; }
</style>
