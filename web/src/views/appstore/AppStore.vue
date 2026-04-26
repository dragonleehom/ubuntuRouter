<template>
  <div class="appstore-page">
    <h2>应用市场</h2>

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
              <el-tag size="small" type="info" class="app-cat">{{ app.category }}</el-tag>
              <div class="app-footer">
                <el-tag v-if="app.installed" size="small" type="success">已安装</el-tag>
                <span v-else class="app-version">{{ app.version }}</span>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-empty v-if="!loading && apps.length === 0" description="暂无应用" />
      </el-tab-pane>

      <el-tab-pane label="已安装" name="installed">
        <el-table :data="installedApps" stripe v-loading="installedLoading">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="version" label="版本" width="100" />
          <el-table-column label="更新" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.has_update" type="danger" size="small">
                {{ row.available_version }} 可用
              </el-tag>
              <span v-else class="text-muted">最新版</span>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="分类" width="100" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.has_update" size="small" type="warning" @click="updateApp(row)">
                更新
              </el-button>
              <el-button size="small" @click="viewDetail({ id: row.id })">详情</el-button>
              <el-button size="small" type="danger" @click="uninstallApp(row)">卸载</el-button>
            </template>
          </el-table-column>
        </el-table>
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
              <el-tag size="small">{{ detailDialog.app.category }}</el-tag>
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/stores'
import { Search, Refresh, Monitor } from '@element-plus/icons-vue'
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
    installedApps.value = res.data.apps || []
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

onMounted(() => {
  fetchApps()
  fetchInstalled()
})
</script>

<style scoped>
.appstore-page { padding: 0; }
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
</style>
