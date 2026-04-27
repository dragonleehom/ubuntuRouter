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
        <el-card shadow="never" class="stat-card stat-images">
          <div class="stat-value">{{ imageTotal }}</div>
          <div class="stat-label">本地镜像</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 三标签页：容器 / 镜像 / Compose -->
    <el-tabs v-model="activeTab">
      <!-- ═══════════ 容器列表 ═══════════ -->
      <el-tab-pane label="容器列表" name="containers">
        <div class="toolbar">
          <el-button type="primary" size="small" @click="refreshContainers">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button size="small" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon> 创建容器
          </el-button>
          <el-button size="small" @click="scanOpenable" :loading="scanning">
            <el-icon><Link /></el-icon> 打开应用
          </el-button>
        </div>

        <el-table :data="containers" stripe style="width: 100%" v-loading="loading"
          highlight-current-row>
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="image" label="镜像" min-width="180" class="hide-mobile">
            <template #default="{ row }">
              <span class="image-name">{{ row.image }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'running' ? 'success' : 'info'" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="ports" label="端口" min-width="140" class="hide-mobile">
            <template #default="{ row }">
              <span v-if="row.ports && row.ports.length">
                <el-tag v-for="p in row.ports" :key="`${p.host_port}-${p.container_port}`"
                  size="small" style="margin: 1px">
                  {{ p.host_port }}:{{ p.container_port }}/{{ p.protocol }}
                </el-tag>
              </span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button-group>
                <el-button v-if="row.status === 'running'" size="small" type="warning"
                  @click="stopContainer(row)">停止</el-button>
                <el-button v-else size="small" type="success"
                  @click="startContainer(row)">启动</el-button>
                <el-button size="small" @click="restartContainer(row)">重启</el-button>
                <el-button size="small" type="danger"
                  @click="removeContainer(row)">删除</el-button>
              </el-button-group>
              <div class="row-actions" style="margin-top:4px">
                <el-button size="small" text type="primary"
                  @click="openTerminal(row)">终端</el-button>
                <el-button size="small" text type="primary"
                  @click="viewDetails(row)">详情</el-button>
                <el-button v-if="row.status === 'running'" size="small" text type="success"
                  @click="openWebUI(row)">打开</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ═══════════ 镜像管理 ═══════════ -->
      <el-tab-pane label="镜像管理" name="images">
        <div class="toolbar">
          <el-button type="primary" size="small" @click="refreshImages">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-input v-model="pullImageName" size="small" placeholder="镜像名 (如 nginx:alpine)"
            style="width: 220px" @keyup.enter="pullImage" />
          <el-button size="small" @click="pullImage" :loading="pulling">拉取</el-button>
          <el-button size="small" type="danger" text
            @click="pruneImages" :loading="pruning">清理无用镜像</el-button>
        </div>

        <el-table :data="images" stripe style="width: 100%" v-loading="imgLoading">
          <el-table-column label="镜像" min-width="240">
            <template #default="{ row }">
              <div class="image-cell">
                <span v-if="row.repo_tags && row.repo_tags.length">
                  <code v-for="t in row.repo_tags" :key="t">{{ t }}</code>
                </span>
                <span v-else class="text-muted">&lt;none&gt;:&lt;none&gt;</span>
                <span class="image-id">{{ row.id ? row.id.substring(0, 12) : '' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="size_human" label="大小" width="100" align="right" />
          <el-table-column prop="created" label="创建时间" min-width="160" class="hide-mobile" />
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="primary"
                @click="viewImageDetails(row)">详情</el-button>
              <el-button size="small" text type="danger"
                @click="removeImage(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ═══════════ Compose 项目 ═══════════ -->
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
              <el-tag :type="row.status === 'running' ? 'success' : row.status === 'partial' ? 'warning' : 'info'"
                size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="services" label="服务" min-width="200" class="hide-mobile">
            <template #default="{ row }">
              <el-tag v-for="s in row.services" :key="s.name" size="small" style="margin: 1px"
                :type="s.state === 'running' ? 'success' : 'info'">
                {{ s.name }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="composeUp(row)">部署</el-button>
              <el-button size="small" type="danger" @click="composeDown(row)">停止</el-button>
              <el-button size="small" @click="viewComposeLogs(row)">日志</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- ═══════════ 容器终端弹窗 ═══════════ -->
    <el-dialog v-model="terminalDialog.visible" :title="`终端: ${terminalDialog.containerName}`"
      width="700px" @closed="clearTerminal">
      <div class="terminal-box">
        <div class="terminal-input-row">
          <el-input v-model="terminalDialog.cmd" size="small" placeholder="输入命令..."
            @keyup.enter="execCommand" :disabled="terminalDialog.executing">
            <template #prepend>$</template>
          </el-input>
          <el-button size="small" type="primary" @click="execCommand"
            :loading="terminalDialog.executing">执行</el-button>
        </div>
        <pre class="terminal-output" ref="terminalOutputRef">{{ terminalDialog.output }}</pre>
      </div>
    </el-dialog>

    <!-- ═══════════ 容器详情弹窗 ═══════════ -->
    <el-dialog v-model="detailDialog.visible" :title="`详情: ${detailDialog.title}`"
      width="750px">
      <div v-if="detailDialog.loading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else class="detail-content">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="状态">
            <el-tag :type="detailInfo.state?.status === 'running' ? 'success' : 'info'" size="small">
              {{ detailInfo.state?.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="重启策略">
            {{ detailInfo.host_config?.restart_policy || 'no' }}
          </el-descriptions-item>
          <el-descriptions-item label="网络模式">
            {{ detailInfo.host_config?.network_mode || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="网络">
            {{ (detailInfo.network?.networks || []).join(', ') || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">
            {{ detailInfo.created || '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <h4>环境变量</h4>
        <pre class="env-viewer">{{ (detailInfo.config?.env || []).join('\n') || '无' }}</pre>
        <el-divider v-if="detailInfo.mounts?.length" />
        <h4 v-if="detailInfo.mounts?.length">挂载卷</h4>
        <el-table v-if="detailInfo.mounts?.length" :data="detailInfo.mounts" size="small">
          <el-table-column prop="Source" label="源路径" min-width="200" />
          <el-table-column prop="Destination" label="目标路径" min-width="200" />
          <el-table-column prop="Mode" label="模式" width="80" />
        </el-table>
      </div>
    </el-dialog>

    <!-- ═══════════ 创建容器弹窗 ═══════════ -->
    <el-dialog v-model="showCreateDialog" title="创建容器" width="550px">
      <el-form :model="createForm" label-width="100px" size="small">
        <el-form-item label="镜像">
          <el-input v-model="createForm.image" placeholder="nginx:alpine" />
        </el-form-item>
        <el-form-item label="容器名">
          <el-input v-model="createForm.name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="端口映射">
          <div class="port-rows">
            <div v-for="(p, i) in createForm.ports" :key="i" class="port-row">
              <el-input v-model="p.host_port" placeholder="主机端口" style="width:100px" />
              <span>:</span>
              <el-input v-model="p.container_port" placeholder="容器端口" style="width:100px" />
              <el-select v-model="p.protocol" style="width:70px">
                <el-option label="tcp" value="tcp" />
                <el-option label="udp" value="udp" />
              </el-select>
              <el-button size="small" text type="danger" @click="createForm.ports.splice(i,1)">×</el-button>
            </div>
            <el-button size="small" text @click="createForm.ports.push({host_port:'',container_port:'',protocol:'tcp'})">
              + 添加端口
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="重启策略">
          <el-select v-model="createForm.restart_policy">
            <el-option label="不自动重启" value="no" />
            <el-option label="总是重启" value="always" />
            <el-option label="异常时重启" value="on-failure" />
            <el-option label="除非停止" value="unless-stopped" />
          </el-select>
        </el-form-item>
        <el-form-item label="环境变量">
          <div class="env-rows">
            <div v-for="(e, i) in createForm.envList" :key="i" class="env-row">
              <el-input v-model="e.key" placeholder="KEY" style="width:130px" />
              <span>=</span>
              <el-input v-model="e.value" placeholder="VALUE" style="width:160px" />
              <el-button size="small" text type="danger" @click="createForm.envList.splice(i,1)">×</el-button>
            </div>
            <el-button size="small" text @click="createForm.envList.push({key:'',value:''})">
              + 添加变量
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="网络">
          <el-input v-model="createForm.network" placeholder="bridge (默认)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="showCreateDialog = false">取消</el-button>
        <el-button size="small" type="primary" @click="doCreateContainer" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- ═══════════ 日志对话框 ═══════════ -->
    <el-dialog v-model="logDialog.visible" :title="`日志: ${logDialog.title}`" width="80%">
      <pre class="log-viewer">{{ logDialog.content }}</pre>
    </el-dialog>

    <!-- ═══════════ 可打开应用列表 ═══════════ -->
    <el-dialog v-model="showAppList" title="可打开的应用" width="500px">
      <div v-if="openableApps.length === 0" style="text-align:center;color:#999">没有找到可打开的应用</div>
      <div v-for="app in openableApps" :key="app.container_id" class="app-open-item">
        <div class="app-info">
          <strong>{{ app.container_name }}</strong>
          <span class="app-image">{{ app.image }}</span>
          <span class="app-title" v-if="app.title">{{ app.title }}</span>
        </div>
        <el-button size="small" type="primary" @click="openUrl(app.url)">打开</el-button>
      </div>
    </el-dialog>

    <!-- ═══════════ 镜像详情弹窗 ═══════════ -->
    <el-dialog v-model="imgDetailDialog.visible" title="镜像详情" width="600px">
      <div v-if="imgDetail" class="img-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="镜像 ID">
            <code>{{ imgDetail.id ? imgDetail.id.substring(0, 19) + '...' : '-' }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="大小">{{ imgDetail.size_str || '-' }}</el-descriptions-item>
          <el-descriptions-item label="架构">{{ imgDetail.architecture || '-' }}</el-descriptions-item>
          <el-descriptions-item label="系统">{{ imgDetail.os || '-' }}</el-descriptions-item>
          <el-descriptions-item label="镜像层数">{{ imgDetail.layers || 0 }}</el-descriptions-item>
          <el-descriptions-item label="标签">
            <el-tag v-for="t in (imgDetail.repo_tags || [])" :key="t" size="small" style="margin:1px">{{ t }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <h4>暴露端口</h4>
        <code>{{ (imgDetail.exposed_ports || []).join(', ') || '无' }}</code>
        <el-divider v-if="imgDetail.env?.length" />
        <h4 v-if="imgDetail.env?.length">默认环境变量</h4>
        <pre class="env-viewer">{{ (imgDetail.env || []).join('\n') }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '@/stores'
import { Refresh, Plus, Link, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const imgLoading = ref(false)
const containers = ref([])
const images = ref([])
const imageTotal = ref(0)
const composeProjects = ref([])
const activeTab = ref('containers')
const pullImageName = ref('')
const pulling = ref(false)
const pruning = ref(false)
const scanning = ref(false)
const openableApps = ref([])
const showAppList = ref(false)
const creating = ref(false)
const showCreateDialog = ref(false)
const terminalDialog = ref({ visible: false, containerName: '', containerId: '', cmd: '', output: '', executing: false })
const terminalOutputRef = ref(null)
const detailDialog = ref({ visible: false, title: '', loading: false })
const detailInfo = ref({})
const logDialog = ref({ visible: false, title: '', content: '' })
const imgDetailDialog = ref({ visible: false })
const imgDetail = ref(null)
const createForm = ref({
  image: '', name: '', ports: [], envList: [],
  restart_policy: 'no', network: 'bridge',
})

const stats = computed(() => {
  const total = containers.value.length
  const running = containers.value.filter(c => c.status === 'running').length
  const stopped = total - running
  return { total, running, stopped }
})

onMounted(() => { refreshContainers(); refreshImages(); refreshCompose() })

async function refreshContainers() {
  loading.value = true
  try { const res = await api.get('/containers'); containers.value = res.data.containers || [] }
  catch (e) { ElMessage.error('获取容器列表失败') }
  loading.value = false
}
async function startContainer(row) {
  try { await api.post(`/containers/${row.id}/start`); ElMessage.success('容器已启动'); await refreshContainers() }
  catch (e) { ElMessage.error('启动失败') }
}
async function stopContainer(row) {
  try { await api.post(`/containers/${row.id}/stop`); ElMessage.success('容器已停止'); await refreshContainers() }
  catch (e) { ElMessage.error('停止失败') }
}
async function restartContainer(row) {
  try { await api.post(`/containers/${row.id}/restart`); ElMessage.success('容器已重启'); await refreshContainers() }
  catch (e) { ElMessage.error('重启失败') }
}
async function removeContainer(row) {
  try {
    await ElMessageBox.confirm(`确认删除容器 "${row.name}"？`, '确认')
    await api.delete(`/containers/${row.id}`)
    ElMessage.success('容器已删除'); await refreshContainers()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}
async function refreshImages() {
  imgLoading.value = true
  try { const res = await api.get('/containers/images/list'); images.value = res.data.images || []; imageTotal.value = res.data.total || 0 }
  catch (e) { ElMessage.error('获取镜像列表失败') }
  imgLoading.value = false
}
async function pullImage() {
  if (!pullImageName.value.trim()) return
  pulling.value = true
  try { await api.post('/containers/images/pull', null, { params: { image: pullImageName.value.trim() } }); ElMessage.success('镜像拉取完成'); pullImageName.value = ''; await refreshImages() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '拉取失败') }
  pulling.value = false
}
async function removeImage(row) {
  try { const tag = row.repo_tags?.[0] || row.id; await ElMessageBox.confirm(`确认删除镜像 "${tag}"？`, '确认'); await api.delete(`/containers/images/${row.id}`); ElMessage.success('镜像已删除'); await refreshImages() }
  catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}
async function pruneImages() {
  try { await ElMessageBox.confirm('确认清理所有未使用的镜像？', '确认'); pruning.value = true; const res = await api.post('/containers/images/prune'); ElMessage.success(`清理完成，释放 ${res.data.reclaimed_str || '空间'}`); await refreshImages() }
  catch (e) { if (e !== 'cancel') ElMessage.error('清理失败') }
  pruning.value = false
}
async function viewImageDetails(row) {
  imgDetail.value = null; imgDetailDialog.value = { visible: true }
  try { const res = await api.get(`/containers/images/${row.id}/inspect`); imgDetail.value = res.data.image }
  catch (e) { ElMessage.error('获取镜像详情失败') }
}
function openTerminal(row) {
  terminalDialog.value = { visible: true, containerName: row.name, containerId: row.id, cmd: '', output: '等待命令...\n', executing: false }
}
function clearTerminal() { terminalDialog.value.cmd = ''; terminalDialog.value.output = '' }
async function execCommand() {
  const d = terminalDialog.value
  if (!d.cmd.trim()) return
  d.executing = true; d.output += `$ ${d.cmd}\n`
  try {
    const res = await api.post(`/containers/${d.containerId}/exec`, { cmd: d.cmd.trim() })
    if (res.data.stdout) d.output += res.data.stdout
    if (res.data.stderr) d.output += `\n[stderr]\n${res.data.stderr}`
    d.output += `\n[退出码: ${res.data.exit_code}]\n\n`
  } catch (e) { d.output += `\n[错误] ${e.response?.data?.detail || e.message}\n\n` }
  d.cmd = ''; d.executing = false
  setTimeout(() => { const el = terminalOutputRef.value; if (el) el.scrollTop = el.scrollHeight }, 50)
}
async function viewDetails(row) {
  detailDialog.value = { visible: true, title: row.name, loading: true }; detailInfo.value = {}
  try { const res = await api.get(`/containers/${row.id}/inspect`); detailInfo.value = res.data.inspect }
  catch (e) { ElMessage.error('获取详情失败') }
  detailDialog.value.loading = false
}
async function openWebUI(row) {
  try { const res = await api.get(`/containers/app-open/${row.id}`); const data = res.data; if (data.url) { window.open(data.url, '_blank') } else { ElMessage.info(data.message || '未检测到 HTTP 服务') } }
  catch (e) { ElMessage.error('检测失败') }
}
async function scanOpenable() {
  scanning.value = true
  try { const res = await api.get('/containers/app-open/all'); openableApps.value = res.data.apps || []; showAppList.value = true }
  catch (e) { ElMessage.error('扫描失败') }
  scanning.value = false
}
function openUrl(url) { window.open(url, '_blank') }
async function doCreateContainer() {
  if (!createForm.value.image.trim()) { ElMessage.warning('请输入镜像名'); return }
  creating.value = true
  try {
    const env = {}; for (const e of createForm.value.envList) { if (e.key.trim()) env[e.key.trim()] = e.value }
    const payload = { image: createForm.value.image.trim(), name: createForm.value.name.trim(), ports: createForm.value.ports.filter(p => p.host_port && p.container_port), env, restart_policy: createForm.value.restart_policy, network: createForm.value.network }
    const res = await api.post('/containers/create', payload)
    ElMessage.success(`容器已创建: ${res.data.container_id}`); showCreateDialog.value = false; await refreshContainers()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') }
  creating.value = false
}
async function refreshCompose() {
  try { const res = await api.get('/containers/compose/projects'); composeProjects.value = res.data.projects || [] }
  catch (e) { ElMessage.error('获取 Compose 项目失败') }
}
async function composeUp(project) {
  try { await api.post(`/containers/compose/${project.name}/up`); ElMessage.success('项目已部署'); await refreshCompose() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '部署失败') }
}
async function composeDown(project) {
  try { await api.post(`/containers/compose/${project.name}/down`); ElMessage.success('项目已停止'); await refreshCompose() }
  catch (e) { ElMessage.error(e.response?.data?.detail || '停止失败') }
}
async function viewComposeLogs(project) {
  try { const res = await api.get(`/containers/compose/${project.name}/logs`, { params: { tail: 200 } }); logDialog.value = { visible: true, title: project.name, content: res.data.logs || '暂无日志' } }
  catch (e) { ElMessage.error('获取日志失败') }
}
</script>

<style scoped>
.containers-page { padding: 0; }
.stat-row { margin-bottom: 20px; }
.stat-card { text-align: center; padding: 8px; }
.stat-value { font-size: 32px; font-weight: 600; color: #409EFF; }
.stat-running .stat-value { color: #67C23A; }
.stat-stopped .stat-value { color: #909399; }
.stat-images .stat-value { color: #E6A23C; }
.stat-label { font-size: 13px; color: #999; margin-top: 4px; }
.toolbar { margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.image-name { font-family: monospace; font-size: 13px; }
.text-muted { color: #666; }
.image-id { font-size: 11px; color: #999; margin-left: 6px; font-family: monospace; }
.image-cell { display: flex; flex-direction: column; gap: 2px; }
.image-cell code { font-size: 12px; }
.row-actions { display: flex; gap: 4px; }
.terminal-box { border: 1px solid #333; border-radius: 4px; overflow: hidden; }
.terminal-input-row { display: flex; gap: 4px; padding: 8px; background: #1a1a1a; }
.terminal-input-row :deep(.el-input-group__prepend) { color: #67C23A; background: #2a2a2a; border-color: #444; }
.terminal-output {
  background: #1a1a1a; color: #e0e0e0; padding: 12px; margin: 0;
  font-size: 13px; font-family: monospace; max-height: 400px; overflow: auto;
  white-space: pre-wrap; word-break: break-all; min-height: 120px;
}
.log-viewer {
  background: #1a1a1a; color: #e0e0e0; padding: 16px; border-radius: 4px;
  font-size: 13px; font-family: monospace; max-height: 500px; overflow: auto;
  white-space: pre-wrap; word-break: break-all;
}
.detail-content h4 { margin: 0 0 8px; font-size: 14px; }
.env-viewer { background: #f5f5f5; padding: 10px; border-radius: 4px; font-size: 12px; max-height: 200px; overflow: auto; }
.port-rows, .env-rows { display: flex; flex-direction: column; gap: 6px; }
.port-row, .env-row { display: flex; gap: 6px; align-items: center; }
.app-open-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 0; border-bottom: 1px solid #eee;
}
.app-info { display: flex; flex-direction: column; gap: 2px; }
.app-image { font-size: 12px; color: #666; font-family: monospace; }
.app-title { font-size: 11px; color: #999; }
.img-detail h4 { margin: 0 0 8px; font-size: 14px; }
</style>
