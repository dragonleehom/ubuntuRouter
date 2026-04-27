<template>
  <div class="appstore-page">
    <div class="page-header">
      <h2>应用市场</h2>
      <el-button size="small" @click="repoDialogVisible = true">
        <el-icon><Setting /></el-icon> 仓库管理
      </el-button>
    </div>

    <!-- 标签筛选 + 搜索 -->
    <div class="toolbar">
      <div class="tag-row">
        <el-check-tag :checked="selectedTag === ''" @click="changeTag('')">
          全部
        </el-check-tag>
        <el-check-tag
          v-for="tag in sortedTags"
          :key="tag"
          :checked="selectedTag === tag"
          @click="changeTag(tag)"
          class="tag-item"
        >
          {{ tag }}
        </el-check-tag>
      </div>
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          placeholder="搜索应用..."
          clearable
          style="width: 260px"
          @clear="fetchApps"
          @keyup.enter="fetchApps"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="fetchApps">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- 统计信息 + 分页 -->
    <div class="stats-bar">
      <span class="stats-text">共 {{ totalApps }} 个应用</span>
      <span class="stats-divider">|</span>
      <span class="stats-text">当前页 {{ apps.length }} 个</span>
      <span v-if="totalApps > 60" class="pagination-hint">
        分页显示，可使用标签筛选缩小范围
      </span>
    </div>

    <!-- Tab: 应用市场 / 已安装 -->
    <el-tabs v-model="activeTab">
      <el-tab-pane label="应用市场" name="market">
        <el-row v-if="apps.length > 0" :gutter="12">
          <el-col
            v-for="app in apps"
            :key="app.id"
            :xs="12"
            :sm="8"
            :md="6"
            :lg="4"
            style="margin-bottom: 14px"
          >
            <el-card shadow="hover" class="app-card" @click="viewDetail(app)">
              <div class="app-icon">
                <div class="icon-wrapper">
                  <img :src="getIconUrl(app.id)" :alt="app.name" @load="onIconLoad($event)" @error="onIconError($event, app.id)" style="max-width:48px;max-height:48px" />
                  <el-icon v-if="iconErrors[app.id]" :size="32" color="#409EFF"><Monitor /></el-icon>
                </div>
              </div>
              <div class="app-name">{{ app.name }}</div>
              <div class="app-desc">{{ app.description || app.id }}</div>
              <div class="app-meta">
                <el-tag size="small" :type="catTagType(app.category)" class="app-cat">{{ app.category }}</el-tag>
              </div>
              <div class="app-footer">
                <el-tag v-if="app.installed" size="small" type="success" effect="dark" class="installed-tag">已安装</el-tag>
                <span v-else class="app-version">v{{ app.version }}</span>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-if="!loading && apps.length === 0" description="暂无应用" />

        <!-- 分页 -->
        <div v-if="totalApps > pageSize" class="pagination-row">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="totalApps"
            :page-sizes="[30, 60, 90]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="fetchApps"
            @current-change="fetchApps"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="已安装" name="installed">
        <el-table :data="installedApps" stripe v-loading="installedLoading" style="width: 100%">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'running'" size="small" type="success">运行中</el-tag>
              <el-tag v-else-if="row.status === 'stopped'" size="small" type="info">已停止</el-tag>
              <el-tag v-else size="small" type="warning">未知</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="分类" width="100" />
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column label="更新" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.has_update" type="danger" size="small">
                {{ row.available_version }} 可用
              </el-tag>
              <span v-else class="text-muted">最新版</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="300" fixed="right">
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

    <!-- 应用详情对话框（含安装配置） -->
    <el-dialog v-model="detailDialog.visible" :title="detailDialog.app?.name || '应用详情'" width="740px">
      <template v-if="detailDialog.app">
        <div class="detail-header">
          <div class="detail-icon">
            <img v-if="detailDialog.app.icon" :src="detailDialog.app.icon" :alt="detailDialog.app.name" @load="onIconLoad($event)" />
            <img v-else :src="getIconUrl(detailDialog.app.id)" :alt="detailDialog.app.name" @load="onIconLoad($event)" @error="$event.target.style.display='none'" style="max-width:80px;max-height:80px" />
            <el-icon v-if="!detailDialog.app.icon" :size="48" color="#409EFF" style="display:none"><Monitor /></el-icon>
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

        <!-- 端口映射（只读） -->
        <div v-if="detailDialog.app.ports?.length" class="config-section">
          <h4>端口映射</h4>
          <el-table :data="detailDialog.app.ports" size="small">
            <el-table-column prop="label" label="名称" />
            <el-table-column prop="host_port" label="主机端口" width="100" />
            <el-table-column prop="container_port" label="容器端口" width="100" />
            <el-table-column prop="protocol" label="协议" width="80" />
          </el-table>
        </div>

        <el-form :model="installForm" label-width="120px" v-if="!detailDialog.app.installed">
          <!-- 环境变量（可修改） -->
          <div v-if="detailDialog.app.env_vars?.length" class="config-section">
            <h4>
              环境变量
              <el-button size="small" type="primary" link @click="addCustomEnv">
                <el-icon><Plus /></el-icon> 添加环境变量
              </el-button>
            </h4>
            <div v-for="ev in detailDialog.app.env_vars" :key="ev.name" class="env-item">
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
          </div>

          <!-- 自定义环境变量 -->
          <div class="config-section">
            <h4>
              自定义环境变量
              <el-button size="small" type="primary" link @click="addCustomEnv">
                <el-icon><Plus /></el-icon> 添加
              </el-button>
            </h4>
            <div v-for="(ce, idx) in installForm.customEnv" :key="'ce-'+idx" class="custom-row">
              <el-input v-model="ce.key" placeholder="变量名" size="small" style="width:180px;margin-right:6px" />
              <el-input v-model="ce.value" placeholder="值" size="small" style="width:260px;margin-right:6px" />
              <el-button size="small" type="danger" link @click="installForm.customEnv.splice(idx,1)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- 数据卷（只读） + 自定义卷挂载 -->
          <div v-if="detailDialog.app.volumes?.length" class="config-section">
            <h4>数据卷</h4>
            <el-table :data="detailDialog.app.volumes" size="small">
              <el-table-column prop="label" label="说明" />
              <el-table-column prop="container_path" label="容器路径" />
              <el-table-column prop="host_path" label="主机路径" />
            </el-table>
          </div>
          <div class="config-section">
            <h4>
              自定义卷挂载
              <el-button size="small" type="primary" link @click="addCustomVolume">
                <el-icon><Plus /></el-icon> 添加
              </el-button>
            </h4>
            <div v-for="(cv, idx) in installForm.customVolumes" :key="'cv-'+idx" class="custom-row">
              <el-input v-model="cv.hostPath" placeholder="主机路径" size="small" style="width:180px;margin-right:6px" />
              <el-input v-model="cv.containerPath" placeholder="容器路径" size="small" style="width:220px;margin-right:6px" />
              <el-select v-model="cv.mode" size="small" style="width:70px;margin-right:6px">
                <el-option label="rw" value="rw" />
                <el-option label="ro" value="ro" />
              </el-select>
              <el-button size="small" type="danger" link @click="installForm.customVolumes.splice(idx,1)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- 自定义端口映射 -->
          <div class="config-section">
            <h4>
              自定义端口映射
              <el-button size="small" type="primary" link @click="addCustomPort">
                <el-icon><Plus /></el-icon> 添加
              </el-button>
            </h4>
            <div v-for="(cp, idx) in installForm.customPorts" :key="'cp-'+idx" class="custom-row">
              <el-input-number v-model="cp.hostPort" :min="1" :max="65535" size="small" style="width:110px;margin-right:6px" placeholder="主机端口" />
              <el-input-number v-model="cp.containerPort" :min="1" :max="65535" size="small" style="width:110px;margin-right:6px" placeholder="容器端口" />
              <el-select v-model="cp.protocol" size="small" style="width:70px;margin-right:6px">
                <el-option label="tcp" value="tcp" />
                <el-option label="udp" value="udp" />
              </el-select>
              <el-button size="small" type="danger" link @click="installForm.customPorts.splice(idx,1)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </el-form>

        <div class="detail-actions">
          <el-button v-if="detailDialog.app.installed" type="danger" @click="uninstallApp(detailDialog.app)">卸载</el-button>
          <el-button v-else type="primary" size="large" @click="doInstallFromDetail" :loading="installing">安装</el-button>
          <el-button v-if="detailDialog.app.installed && detailDialog.app.installed_version !== detailDialog.app.version"
            type="warning" @click="updateApp(detailDialog.app)">更新到 {{ detailDialog.app.version }}</el-button>
        </div>
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
import { ref, computed, onMounted, nextTick } from 'vue'
import { api } from '@/stores'
import { Search, Refresh, Plus, Setting, Monitor, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const apps = ref([])
const totalApps = ref(0)
const currentPage = ref(1)
const pageSize = ref(60)
const categories = ref([])
const allCategories = ref([])
const installedApps = ref([])
const installedLoading = ref(false)
const searchQuery = ref('')
const selectedCategory = ref('')
const selectedTag = ref('')
const activeTab = ref('market')

const detailDialog = ref({ visible: false, app: null })
const iconErrors = ref({})
const installForm = ref({ env: {}, customEnv: [], customVolumes: [], customPorts: [] })
const installing = ref(false)

function onIconLoad(event) {
  const img = event.target
  try {
    const canvas = document.createElement('canvas')
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0)
    const pixel = ctx.getImageData(0, 0, 1, 1).data
    if (pixel[0] > 240 && pixel[1] > 240 && pixel[2] > 240) {
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      const data = imageData.data
      for (let i = 0; i < data.length; i += 4) {
        if (data[i] > 235 && data[i + 1] > 235 && data[i + 2] > 235) {
          data[i + 3] = 0
        }
      }
      ctx.putImageData(imageData, 0, 0)
      img.src = canvas.toDataURL('image/png')
    }
  } catch {}
}

function onIconError(event, appId) {
  iconErrors.value[appId] = true
}

// 自定义参数操作
function addCustomEnv() { installForm.value.customEnv.push({ key: '', value: '' }) }
function addCustomVolume() { installForm.value.customVolumes.push({ hostPath: '', containerPath: '', mode: 'rw' }) }
function addCustomPort() { installForm.value.customPorts.push({ hostPort: null, containerPort: null, protocol: 'tcp' }) }

// 仓库管理
const repoDialogVisible = ref(false)
const repos = ref([])
const showAddRepo = ref(false)
const newRepo = ref({ name: '', url: '' })
const addingRepo = ref(false)
const syncing = ref(false)

// ─── 标签筛选（全部展开，支持多选切换） ──────

const sortedTags = computed(() => {
  // 使用独立的 allCategories（不受 API 筛选影响）
  // 排其他到末尾
  return [...allCategories.value].sort((a, b) => {
    if (a === '其他') return 1
    if (b === '其他') return -1
    return 0
  })
})

function changeTag(tag) {
  selectedTag.value = tag
  selectedCategory.value = tag
  currentPage.value = 1
  fetchApps()
}

// ─── 分类颜色映射 ────────────────────────────

function getIconUrl(appId) {
  const base = window.location.origin + '/api/v1/appstore/icon/' + appId
  return base
}

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

// ─── API ──────────────────────────────────────

async function fetchApps() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchQuery.value) params.search = searchQuery.value
    if (selectedCategory.value) params.category = selectedCategory.value
    const res = await api.get('/appstore/apps', { params })
    apps.value = res.data.apps || []
    totalApps.value = res.data.total || 0
    categories.value = res.data.categories || []
    // 独立存储全部分类（首次调用时）
    if (allCategories.value.length === 0 && categories.value.length > 0) {
      allCategories.value = [...categories.value]
    }
  } catch (e) {
    ElMessage.error('获取应用列表失败')
  }
  loading.value = false
}

async function fetchInstalled() {
  installedLoading.value = true
  try {
    const params = { page: 1, page_size: 200 }
    const res = await api.get('/appstore/installed', { params })
    installedApps.value = (res.data.apps || []).map(app => {
      app._operating = ''
      app.status = 'unknown'
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
    // 打开详情时即初始化安装表单
    installForm.value = { env: {}, customEnv: [], customVolumes: [], customPorts: [] }
    if (res.data.app.env_vars) {
      for (const ev of res.data.app.env_vars) {
        if (ev.default) installForm.value.env[ev.name] = ev.default
      }
    }
  } catch (e) {
    ElMessage.error('获取应用详情失败')
  }
}

async function doInstallFromDetail() {
  installing.value = true
  try {
    const payload = { env: {} }
    // 环境变量
    for (const key of Object.keys(installForm.value.env)) {
      const val = installForm.value.env[key]
      if (val !== '' && val !== null && val !== undefined) {
        payload.env[key] = val
      }
    }
    // 自定义 env
    for (const ce of installForm.value.customEnv) {
      if (ce.key) payload.env[ce.key] = ce.value
    }
    // 自定义卷/端口
    if (installForm.value.customVolumes.length) {
      payload.custom_volumes = installForm.value.customVolumes.filter(v => v.hostPath && v.containerPath)
    }
    if (installForm.value.customPorts.length) {
      payload.custom_ports = installForm.value.customPorts.filter(p => p.hostPort && p.containerPort)
    }
    const res = await api.post(`/appstore/apps/${detailDialog.value.app.id}/install`, payload)
    ElMessage.success(res.data.message || '安装成功')
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
onMounted(async () => {
  // 单独获取全部分类（不受 fetchApps 筛选影响）
  try {
    const res2 = await api.get('/appstore/categories')
    if (res2.data.categories?.length) {
      allCategories.value = res2.data.categories
    }
  } catch {}
  fetchApps()
  fetchInstalled()
})
</script>

<style scoped>
.appstore-page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }

/* 工具行（标签+搜索） */
.toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.tag-row .el-check-tag {
  flex-shrink: 0;
}
.more-tag { flex-shrink: 0; }
.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 统计条 */
.stats-bar {
  font-size: 13px;
  color: #888;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.stats-divider { color: #333; }
.pagination-hint { color: #666; font-size: 12px; }

/* 应用卡片 */
.app-card { cursor: pointer; text-align: center; padding: 8px; transition: transform 0.2s; }
.app-card:hover { transform: translateY(-2px); }
.app-icon { height: 64px; display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }
.icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
}
.icon-wrapper img { max-width: 48px; max-height: 48px; }
.app-name { font-size: 14px; font-weight: 500; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.app-desc { font-size: 12px; color: #999; margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.app-meta { margin-bottom: 8px; }
.app-cat { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
.app-footer { display: flex; justify-content: center; align-items: center; }
.app-version { font-size: 11px; color: #666; }
.installed-tag { font-size: 11px; }

/* 详情弹窗 */
.detail-header { display: flex; gap: 20px; align-items: flex-start; }
.detail-icon { width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; border-radius: 12px; }
.detail-icon img { max-width: 64px; max-height: 64px; }
.detail-meta h3 { margin: 0 0 8px; font-size: 20px; }
.detail-meta p { margin: 0 0 12px; color: #999; font-size: 14px; }
.meta-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.config-section { margin: 16px 0; }
.config-section h4 { margin: 0 0 8px; font-size: 14px; color: #ccc; }
.detail-actions { margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end; }
.form-help { font-size: 12px; color: #888; margin-top: 2px; }

/* 仓库管理 */
.repo-header { display: flex; gap: 8px; margin-bottom: 16px; }
.add-repo-form { margin-bottom: 16px; padding: 12px; background: rgba(255,255,255,0.03); border-radius: 8px; }
.repo-url { color: #409EFF; font-size: 12px; text-decoration: none; }

/* 分页 */
.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

/* 已安装页 */
.text-muted { color: #666; }

/* 安装对话框自定义参数行 */
.custom-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  padding-left: 8px;
}

/* 安装对话框分隔线 */
.el-divider { margin: 16px 0; }
</style>
