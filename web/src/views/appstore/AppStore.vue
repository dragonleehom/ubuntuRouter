<template>
  <div class="appstore-page">
    <div class="page-header">
      <h2>应用市场</h2>
      <el-button size="small" @click="repoDialogVisible = true">
        <el-icon><Setting /></el-icon> 仓库管理
      </el-button>
    </div>

    <!-- 搜索和分类 -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索应用..."
        clearable
        style="width: 300px"
        @clear="fetchApps"
        @keyup.enter="fetchApps"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select v-model="selectedCategory" placeholder="全部分类" clearable @change="fetchApps">
        <el-option label="全部分类" value="" />
        <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
      </el-select>

      <el-button type="primary" @click="fetchApps">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <!-- Tab: 应用市场 / 已安装 -->
    <el-tabs v-model="activeTab">
      <el-tab-pane label="应用市场" name="market">
        <el-row :gutter="16">
          <el-col v-for="app in apps" :key="app.id" :xs="12" :sm="8" :md="6" :lg="4" style="margin-bottom: 16px">
            <el-card shadow="hover" class="app-card" @click="viewDetail(app)">
              <div class="app-icon">
                <img v-if="app.icon" :src="app.icon" :alt="app.name" />
                <el-icon v-else :size="32" color="#409EFF"><Monitor /></el-icon>
              </div>
              <div class="app-name">{{ app.name }}</div>
              <div class="app-desc">{{ app.description || app.id }}</div>
              <el-tag size="small" :type="catTagType(app.category)" class="app-cat">{{ app.category }}</el-tag>
              <div class="app-footer">
                <el-tag v-if="app.installed" size="small" type="success">已安装</el-tag>
                <span v-else class="app-version">v{{ app.version }}</span>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-if="!loading && apps.length === 0" description="暂无应用" />
      </el-tab-pane>

      <el-tab-pane label="已安装" name="installed">
        <el-table :data="installedApps" stripe v-loading="installedLoading">
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'running'" size="small" type="success">运行中</el-tag>
              <el-tag v-else-if="row.status === 'stopped'" size="small" type="info">已停止</el-tag>
              <el-tag v-else size="small" type="warning">未知</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column label="更新" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.has_update" type="danger" size="small">
                {{ row.available_version }} 可用
              </el-tag>
              <span v-else class="text-muted">最新版</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="startApp(row)" :loading="row._operating === 'start'">启动</el-button>
              <el-button size="small" type="warning" @click="stopApp(row)" :loading="row._operating === 'stop'">停止</el-button>
              <el-button size="small" @click="viewDetail({ id: row.id })">详情</el-button>
              <el-button size="small" type="danger" @click="uninstallApp(row)">卸载</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!installedLoading && installedApps.length === 0" description="暂未安装任何应用" />
      </el-tab-pane>
    </el-tabs>

    <!-- 应用详情对话框 -->
    <el-dialog v-model="detailDialog.visible" :title="detailDialog.app?.name || '应用详情'" width="700px">
      <template v-if="detailDialog.app">
        <div class="detail-header">
          <div class="detail-icon">
            <img v-if="detailDialog.app.icon" :src="detailDialog.app.icon" />
            <el-icon v-else :size="48" color="#409EFF"><Monitor /></el-icon>
          </div>
          <div class="detail-meta">
            <h3>{{ detailDialog.app.name }}</h3>
            <p>{{ detailDialog.app.description }}</p>
            <div class="meta-tags">
              <el-tag :type="catTagType(detailDialog.app.category)" size="small">{{ detailDialog.app.category }}</el-tag>
              <el-tag size="small" type="info">v{{ detailDialog.app.version }}</el-tag>
              <el-tag v-if="detailDialog.app.author" size="small" type="warning">{{ detailDialog.app.author }}</el-tag>
            </div>
          </div>
        </div>

        <el-divider />

        <!-- 端口配置 -->
        <div v-if="detailDialog.app.ports?.length" class="config-section">
          <h4>端口映射</h4>
          <el-table :data="detailDialog.app.ports" size="small">
            <el-table-column prop="label" label="名称" />
            <el-table-column prop="host_port" label="主机端口" width="100" />
            <el-table-column prop="container_port" label="容器端口" width="100" />
            <el-table-column prop="protocol" label="协议" width="80" />
          </el-table>
        </div>

        <!-- 环境变量 -->
        <div v-if="detailDialog.app.env_vars?.length" class="config-section">
          <h4>环境变量</h4>
          <el-table :data="detailDialog.app.env_vars" size="small">
            <el-table-column prop="label" label="名称" />
            <el-table-column prop="description" label="说明" />
            <el-table-column prop="default" label="默认值" />
            <el-table-column prop="required" label="必填" width="60">
              <template #default="{ row }">
                <el-tag v-if="row.required" size="small" type="danger">是</el-tag>
                <span v-else class="text-muted">否</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 数据卷 -->
        <div v-if="detailDialog.app.volumes?.length" class="config-section">
          <h4>数据卷</h4>
          <el-table :data="detailDialog.app.volumes" size="small">
            <el-table-column prop="label" label="说明" />
            <el-table-column prop="container_path" label="容器路径" />
            <el-table-column prop="host_path" label="主机路径" />
          </el-table>
        </div>

        <div class="detail-actions">
          <el-button v-if="detailDialog.app.installed" type="danger" @click="uninstallApp(detailDialog.app)">卸载</el-button>
          <el-button v-else type="primary" size="large" @click="showInstallForm(detailDialog.app)">安装</el-button>
          <el-button v-if="detailDialog.app.installed && detailDialog.app.installed_version !== detailDialog.app.version"
            type="warning" @click="updateApp(detailDialog.app)">更新到 {{ detailDialog.app.version }}</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 安装配置对话框 -->
    <el-dialog v-model="installDialog.visible" title="安装配置" width="600px">
      <el-form :model="installForm" label-width="120px" v-if="installDialog.app">
        <div v-for="ev in installDialog.app.env_vars" :key="ev.name">
          <el-form-item :label="ev.label || ev.name" :required="ev.required">
            <el-input
              v-if="ev.type === 'password'"
              v-model="installForm.env[ev.name]"
              :placeholder="ev.default || ev.description"
              type="password"
              show-password
            />
            <el-switch
              v-else-if="ev.type === 'boolean'"
              v-model="installForm.env[ev.name]"
              :active-value="'true'"
              :inactive-value="'false'"
            />
            <el-input-number
              v-else-if="ev.type === 'number'"
              v-model="installForm.env[ev.name]"
              :placeholder="String(ev.default || '')"
            />
            <el-input
              v-else
              v-model="installForm.env[ev.name]"
              :placeholder="ev.default || ev.description"
            />
            <div class="form-help" v-if="ev.description">{{ ev.description }}</div>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="installDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="doInstall" :loading="installing">开始安装</el-button>
      </template>
    </el-dialog>

    <!-- 仓库管理对话框 -->
    <el-dialog v-model="repoDialogVisible" title="仓库管理" width="600px">
      <div class="repo-header">
        <el-button type="primary" size="small" @click="showAddRepo = !showAddRepo">
          <el-icon><Plus /></el-icon> 添加仓库
        </el-button>
        <el-button size="small" @click="syncAllRepos" :loading="syncing">
          <el-icon><Refresh /></el-icon> 同步全部
        </el-button>
      </div>

      <el-form v-if="showAddRepo" class="add-repo-form" @submit.prevent="addRepo">
        <el-form-item label="名称">
          <el-input v-model="newRepo.name" placeholder="my-repo" size="small" />
        </el-form-item>
        <el-form-item label="仓库地址">
          <el-input v-model="newRepo.url" placeholder="https://github.com/user/repo" size="small" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="small" @click="addRepo" :loading="addingRepo">添加</el-button>
          <el-button size="small" @click="showAddRepo = false">取消</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="repos" stripe size="small">
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="url" label="仓库地址" min-width="200">
          <template #default="{ row }">
            <a :href="row.url" target="_blank" class="repo-url">{{ row.url }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ok' ? 'success' : row.status === 'syncing' ? 'warning' : 'danger'" size="small">
              {{ row.status === 'ok' ? '正常' : row.status === 'syncing' ? '同步中' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="syncRepo(row)" :loading="row._syncing">同步</el-button>
            <el-button v-if="row.name !== 'official'" size="small" type="danger" @click="removeRepo(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { Search, Refresh, Plus, Setting, Monitor } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const apps = ref([])
const categories = ref([])
const installedApps = ref([])
const installedLoading = ref(false)
const searchQuery = ref('')
const selectedCategory = ref('')
const activeTab = ref('market')

const detailDialog = ref({ visible: false, app: null })
const installDialog = ref({ visible: false, app: null })
const installForm = ref({ env: {} })
const installing = ref(false)

// 仓库管理
const repoDialogVisible = ref(false)
const repos = ref([])
const showAddRepo = ref(false)
const newRepo = ref({ name: '', url: '' })
const addingRepo = ref(false)
const syncing = ref(false)

function catTagType(cat) {
  const map = {
    '数据库': 'danger',
    'NAS': 'warning', '缓存': 'warning', '键值存储': 'warning',
    '网络工具': 'primary', '代理': 'primary', 'DNS': 'primary', 'VPN': 'primary',
    '下载工具': 'info',
    '开发工具': '', '运行环境': '', '中间件': '',
    '服务器': 'warning', 'Web 服务器': 'warning',
    '安全': 'danger', '认证': 'danger',
    '网站': 'success', 'Web 应用': 'success',
    '多媒体': 'success', '媒体管理': 'success',
    '工具': 'info', '实用工具': 'info',
    '商业软件': '', '内容管理': 'warning', '企业管理': 'warning',
    '系统监控': 'success', '监控': 'success', '日志管理': 'success',
    '消息通讯': '', '社交': '',
    '人工智能': 'danger', '大语言模型': 'danger',
    '服务': 'info',
    '路由器功能': 'warning',
    '物联网': 'success', '智能家居': 'success',
    // 英文分类兜底
    'database': 'danger', 'tool': 'info', 'runtime': '',
    'middleware': '', 'storage': 'warning', 'network': 'primary',
    'business': '', 'website': 'success',
    'monitor': 'success', 'download': 'info', 'nas': 'warning',
    'service': 'info', 'messaging': '', 'server': 'warning',
    'multimedia': 'success', 'ai': 'danger', 'networking': 'primary',
    'security': 'danger', 'development': '',
  }
  return map[cat] || 'info'
}

async function fetchApps() {
  loading.value = true
  try {
    const params = {}
    if (searchQuery.value) params.search = searchQuery.value
    if (selectedCategory.value) params.category = selectedCategory.value
    const res = await api.get('/appstore/apps', { params })
    apps.value = res.data.apps || []
    categories.value = res.data.categories || []
  } catch (e) {
    ElMessage.error('获取应用列表失败')
  }
  loading.value = false
}

async function fetchInstalled() {
  installedLoading.value = true
  try {
    const res = await api.get('/appstore/installed')
    // 尝试获取运行状态
    const containers = []
    try {
      const c = await api.get('/containers/list')
      containers.push(...c.data.containers)
    } catch {}
    installedApps.value = (res.data.apps || []).map(app => {
      app._operating = ''
      // Search containers for this app's compose project
      const running = containers.some(c => c.compose_project === app.id && c.status === 'running')
      app.status = running ? 'running' : 'stopped'
      return app
    })
  } catch (e) {
    ElMessage.error('获取已安装列表失败')
  }
  installedLoading.value = false
}

async function viewDetail(app) {
  try {
    const res = await api.get(`/appstore/apps/${app.id}`)
    detailDialog.value = { visible: true, app: res.data.app }
  } catch (e) {
    ElMessage.error('获取应用详情失败')
  }
}

function showInstallForm(app) {
  installForm.value = { env: {} }
  installDialog.value = { visible: true, app }
}

async function doInstall() {
  installing.value = true
  try {
    const res = await api.post(`/appstore/apps/${installDialog.value.app.id}/install`, {
      env: installForm.value.env,
    })
    ElMessage.success(res.data.message || '安装成功')
    installDialog.value.visible = false
    detailDialog.value.visible = false
    await fetchApps()
    await fetchInstalled()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '安装失败')
  }
  installing.value = false
}

async function updateApp(app) {
  try {
    await ElMessageBox.confirm(`确认更新 "${app.name}"？`, '确认')
    const res = await api.post(`/appstore/apps/${app.id}/update`)
    ElMessage.success(res.data.message || '更新成功')
    await fetchApps()
    await fetchInstalled()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

async function uninstallApp(app) {
  try {
    await ElMessageBox.confirm(`确认卸载 "${app.name}"？数据将被保留。`, '确认')
    const res = await api.post(`/appstore/apps/${app.id}/uninstall?keep_data=true`)
    ElMessage.success(res.data.message || '卸载成功')
    detailDialog.value.visible = false
    await fetchApps()
    await fetchInstalled()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '卸载失败')
  }
}

// ── App lifecycle (start/stop) ────────────────────
async function startApp(row) {
  row._operating = 'start'
  try {
    const res = await api.post(`/appstore/apps/${row.id}/install`, {})
    ElMessage.success(res.data.message || '已启动')
    await fetchInstalled()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '启动失败')
  }
  row._operating = ''
}

async function stopApp(row) {
  row._operating = 'stop'
  try {
    const res = await api.post(`/appstore/apps/${row.id}/uninstall?keep_data=true`)
    ElMessage.success('已停止')
    await fetchInstalled()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '停止失败')
  }
  row._operating = ''
}

// ── 仓库管理 ──────────────────────────────────────
async function fetchRepos() {
  try {
    const res = await api.get('/appstore/repo/list')
    repos.value = (res.data.repos || []).map(r => ({ ...r, _syncing: false }))
  } catch (e) {
    ElMessage.error('获取仓库列表失败')
  }
}

async function addRepo() {
  if (!newRepo.value.name || !newRepo.value.url) {
    ElMessage.warning('请填写仓库名称和地址')
    return
  }
  addingRepo.value = true
  try {
    const res = await api.post('/appstore/repo/add', {
      name: newRepo.value.name,
      url: newRepo.value.url,
    })
    ElMessage.success(res.data.message || '仓库添加成功')
    newRepo.value = { name: '', url: '' }
    showAddRepo.value = false
    await fetchRepos()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加仓库失败')
  }
  addingRepo.value = false
}

async function syncRepo(row) {
  row._syncing = true
  try {
    const res = await api.post(`/appstore/repo/sync/${row.name}`)
    ElMessage.success(res.data.message || '同步完成')
    await fetchRepos()
    await fetchApps()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '同步失败')
  }
  row._syncing = false
}

async function syncAllRepos() {
  syncing.value = true
  try {
    const res = await api.post('/appstore/repo/sync')
    ElMessage.success(`同步完成 (${res.data.total} 个仓库)`)
    await fetchRepos()
    await fetchApps()
  } catch (e) {
    ElMessage.error('同步失败')
  }
  syncing.value = false
}

async function removeRepo(row) {
  try {
    await ElMessageBox.confirm(`确认删除仓库 "${row.name}"？`, '确认')
    await api.delete(`/appstore/repo/${row.name}`)
    ElMessage.success('仓库已删除')
    await fetchRepos()
    await fetchApps()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除仓库失败')
  }
}

// ── Init ──────────────────────────────────────────
onMounted(() => {
  fetchApps()
  fetchInstalled()
})
</script>

<style scoped>
.appstore-page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.app-card { cursor: pointer; text-align: center; padding: 8px; transition: transform 0.2s; }
.app-card:hover { transform: translateY(-2px); }
.app-icon { height: 64px; display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }
.app-icon img { max-width: 48px; max-height: 48px; }
.app-name { font-size: 14px; font-weight: 500; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.app-desc { font-size: 12px; color: #999; margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.app-cat { margin-bottom: 8px; }
.app-footer { margin-top: 8px; }
.app-version { font-size: 12px; color: #666; }
.text-muted { color: #666; }
.detail-header { display: flex; gap: 20px; }
.detail-icon { width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; }
.detail-icon img { max-width: 64px; max-height: 64px; }
.detail-meta h3 { margin: 0 0 8px 0; font-size: 20px; }
.detail-meta p { color: #999; margin: 0 0 12px 0; }
.meta-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.config-section h4 { margin: 0 0 8px 0; color: #ccc; }
.form-help { font-size: 12px; color: #888; margin-top: 4px; }
.detail-actions { margin-top: 20px; display: flex; gap: 12px; justify-content: flex-end; }
.repo-header { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.add-repo-form { padding: 16px; background: #1a1a1a; border-radius: 6px; margin-bottom: 16px; }
.repo-url { color: #409EFF; text-decoration: none; font-size: 12px; }
.repo-url:hover { text-decoration: underline; }
</style>
