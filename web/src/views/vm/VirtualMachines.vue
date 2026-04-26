<template>
  <div class="vm-page">
    <h2>虚拟机管理</h2>

    <!-- VM 可用性警告 -->
    <el-alert
      v-if="availabilityChecked && !available"
      :title="availabilityMessage"
      type="warning"
      show-icon
      :closable="false"
      class="warn-alert"
    />

    <!-- 主 Tabs -->
    <el-tabs v-model="activeTab" v-if="available">
      <!-- ====== Tab 1: 虚拟机列表 ====== -->
      <el-tab-pane label="虚拟机列表" name="list">
        <div class="toolbar">
          <el-button type="primary" size="small" @click="openCreateDialog">
            <el-icon><Plus /></el-icon> 创建虚拟机
          </el-button>
          <el-button size="small" @click="fetchDomains">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>

        <el-table :data="domains" stripe style="width: 100%" v-loading="loadingDomains" empty-text="暂无虚拟机">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag
                :type="stateTagType(row.state)"
                size="small"
                effect="dark"
              >
                <el-icon style="margin-right: 4px; vertical-align: middle;">
                  <VideoPlay v-if="row.state === 'running'" />
                  <VideoPause v-else-if="row.state === 'paused'" />
                  <SwitchButton v-else />
                </el-icon>
                {{ stateLabel(row.state) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="vcpus" label="CPU" width="80" align="center" class="hide-mobile" />
          <el-table-column prop="memory_mb" label="内存" width="100" align="center" class="hide-mobile">
            <template #default="{ row }">
              {{ formatMemory(row.memory_mb) }}
            </template>
          </el-table-column>
          <el-table-column prop="disk_gb" label="磁盘" width="80" align="center" class="hide-mobile">
            <template #default="{ row }">
              {{ row.disk_gb || '-' }} GB
            </template>
          </el-table-column>
          <el-table-column label="VNC 端口" width="110" align="center" class="hide-mobile">
            <template #default="{ row }">
              <span v-if="row.vnc_port">{{ row.vnc_port }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320" fixed="right">
            <template #default="{ row }">
              <el-button-group>
                <el-button
                  v-if="row.state !== 'running'"
                  size="small"
                  type="success"
                  @click="startVm(row)"
                >
                  启动
                </el-button>
                <el-button
                  v-if="row.state === 'running'"
                  size="small"
                  type="warning"
                  @click="shutdownVm(row)"
                >
                  关机
                </el-button>
                <el-button
                  v-if="row.state === 'running'"
                  size="small"
                  @click="restartVm(row)"
                >
                  重启
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="confirmDelete(row)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ====== Tab 2: 模板管理 ====== -->
      <el-tab-pane label="模板管理" name="templates">
        <div class="toolbar">
          <el-button size="small" @click="fetchTemplates">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <div v-if="loadingTemplates" class="loading-center">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else-if="templates.length === 0" class="empty-state">
          <el-empty description="暂无模板" />
        </div>
        <div v-else class="template-grid">
          <el-card
            v-for="tpl in templates"
            :key="tpl.name"
            shadow="never"
            class="template-card"
          >
            <div class="template-header">
              <el-icon><Monitor /></el-icon>
              <span class="template-name">{{ tpl.name }}</span>
            </div>
            <div class="template-os">{{ tpl.os_type || '未知系统' }}</div>
            <div class="template-desc">{{ tpl.description || '无描述' }}</div>
            <div class="template-minreq">
              <el-tag size="small" type="info" v-if="tpl.min_ram">RAM ≥ {{ tpl.min_ram }}MB</el-tag>
              <el-tag size="small" type="info" v-if="tpl.min_disk" style="margin-left: 6px;">磁盘 ≥ {{ tpl.min_disk }}GB</el-tag>
              <el-tag size="small" type="info" v-if="tpl.default_vcpus" style="margin-left: 6px;">CPU ≥ {{ tpl.default_vcpus }}核</el-tag>
            </div>
            <div class="template-actions">
              <el-button size="small" @click="openDownloadDialog(tpl)">
                <el-icon><Download /></el-icon> 下载镜像
              </el-button>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ====== Tab 3: VNC 控制台 ====== -->
      <el-tab-pane label="VNC 控制台" name="vnc">
        <div class="vnc-selector">
          <span class="vnc-label">选择虚拟机：</span>
          <el-select v-model="vncSelectedVm" placeholder="选择一个运行中的虚拟机" @change="fetchVncInfo">
            <el-option
              v-for="vm in runningDomains"
              :key="vm.name"
              :label="vm.name"
              :value="vm.name"
            />
          </el-select>
        </div>

        <div v-if="vncInfo" class="vnc-info-panel">
          <el-card shadow="never" class="vnc-card">
            <template #header>
              <span>连接信息 - {{ vncSelectedVm }}</span>
            </template>
            <div class="vnc-info-row">
              <span class="vnc-info-label">VNC 端口：</span>
              <el-tag>{{ vncInfo.vnc_port }}</el-tag>
            </div>
            <div class="vnc-info-row" v-if="vncInfo.websocket_url">
              <span class="vnc-info-label">WebSocket URL：</span>
              <div class="vnc-url-copy">
                <code class="vnc-url">{{ vncInfo.websocket_url }}</code>
                <el-button size="small" text @click="copyText(vncInfo.websocket_url)">
                  <el-icon><Connection /></el-icon> 复制
                </el-button>
              </div>
            </div>
            <el-alert
              title="使用 noVNC 连接"
              type="info"
              :closable="false"
              show-icon
              class="vnc-tip"
            >
              <template #default>
                <p>如果尚未安装 noVNC，请执行：</p>
                <code class="vnc-code">apt install novnc</code>
                <p>然后通过 WebSocket URL 连接到虚拟机控制台。</p>
              </template>
            </el-alert>
          </el-card>
        </div>
        <div v-else-if="vncSelectedVm && !vncInfo" class="empty-state">
          <el-empty description="无法获取 VNC 连接信息，请确保虚拟机正在运行" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- ====== 创建虚拟机对话框 ====== -->
    <el-dialog
      v-model="createDialogVisible"
      title="创建虚拟机"
      width="600px"
      :close-on-click-modal="false"
      @close="resetCreateForm"
    >
      <el-steps :active="createStep" align-center finish-status="success" class="create-steps">
        <el-step title="名称" />
        <el-step title="模板" />
        <el-step title="配置" />
        <el-step title="确认" />
      </el-steps>

      <!-- 步骤 1: 名称 -->
      <div v-if="createStep === 0" class="step-content">
        <el-form :model="createForm" label-width="100px">
          <el-form-item label="虚拟机名称" required>
            <el-input
              v-model="createForm.name"
              placeholder="输入虚拟机名称（字母数字及中划线）"
              :rules="[{ required: true, message: '名称不能为空', trigger: 'blur' }]"
            />
          </el-form-item>
        </el-form>
        <div class="step-nav">
          <el-button type="primary" :disabled="!createForm.name.trim()" @click="createStep = 1">下一步</el-button>
        </div>
      </div>

      <!-- 步骤 2: 模板选择 -->
      <div v-if="createStep === 1" class="step-content">
        <div v-if="loadingTemplates" class="loading-center">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else-if="templates.length === 0" class="empty-state">
          <el-empty description="暂无可用模板，请先在模板管理中添加" />
        </div>
        <div v-else class="template-select-grid">
          <div
            v-for="tpl in templates"
            :key="tpl.name"
            class="template-select-card"
            :class="{ selected: createForm.template === tpl.name }"
            @click="createForm.template = tpl.name"
          >
            <div class="template-select-name">{{ tpl.name }}</div>
            <div class="template-select-os">{{ tpl.os_type || '未知' }}</div>
            <div class="template-select-desc">{{ tpl.description || '无描述' }}</div>
            <div class="template-select-req">
              <span v-if="tpl.min_ram">RAM ≥ {{ tpl.min_ram }}MB</span>
              <span v-if="tpl.min_disk" style="margin-left: 8px;">磁盘 ≥ {{ tpl.min_disk }}GB</span>
            </div>
          </div>
        </div>
        <div class="step-nav">
          <el-button @click="createStep = 0">上一步</el-button>
          <el-button type="primary" :disabled="!createForm.template" @click="createStep = 2">下一步</el-button>
        </div>
      </div>

      <!-- 步骤 3: 自定义配置 -->
      <div v-if="createStep === 2" class="step-content">
        <el-form :model="createForm" label-width="130px">
          <el-form-item label="CPU 核心数">
            <el-input-number v-model="createForm.vcpus" :min="1" :max="64" />
          </el-form-item>
          <el-form-item label="内存 (MB)">
            <el-input-number v-model="createForm.memory_mb" :min="256" :max="1048576" :step="256" />
          </el-form-item>
          <el-form-item label="磁盘大小 (GB)">
            <el-input-number v-model="createForm.disk_size_gb" :min="1" :max="10240" />
          </el-form-item>
          <el-form-item label="ISO URL">
            <el-input v-model="createForm.iso_url" placeholder="输入 ISO 镜像 URL（可选）" />
          </el-form-item>
        </el-form>
        <div class="step-nav">
          <el-button @click="createStep = 1">上一步</el-button>
          <el-button type="primary" @click="createStep = 3">下一步</el-button>
        </div>
      </div>

      <!-- 步骤 4: 确认 -->
      <div v-if="createStep === 3" class="step-content">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="名称">{{ createForm.name }}</el-descriptions-item>
          <el-descriptions-item label="模板">{{ createForm.template }}</el-descriptions-item>
          <el-descriptions-item label="CPU 核心">{{ createForm.vcpus }}</el-descriptions-item>
          <el-descriptions-item label="内存">{{ createForm.memory_mb }} MB</el-descriptions-item>
          <el-descriptions-item label="磁盘">{{ createForm.disk_size_gb }} GB</el-descriptions-item>
          <el-descriptions-item label="ISO URL" v-if="createForm.iso_url">
            {{ createForm.iso_url }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="step-nav">
          <el-button @click="createStep = 2">上一步</el-button>
          <el-button type="primary" :loading="creatingVm" @click="createVm">
            {{ creatingVm ? '创建中...' : '确认创建' }}
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- ====== 下载镜像对话框 ====== -->
    <el-dialog
      v-model="downloadDialogVisible"
      title="下载镜像"
      width="480px"
    >
      <el-form>
        <el-form-item label="模板名称">
          <el-input :model-value="downloadTemplateName" disabled />
        </el-form-item>
        <el-form-item label="镜像 URL" required>
          <el-input
            v-model="downloadUrl"
            placeholder="输入镜像下载 URL"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="downloadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="downloading" @click="downloadTemplate">
          {{ downloading ? '下载中...' : '开始下载' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ====== 删除确认对话框 ====== -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="删除虚拟机"
      width="400px"
    >
      <p>确定要删除虚拟机 <strong>{{ deleteTarget?.name }}</strong> 吗？此操作不可恢复。</p>
      <el-checkbox v-model="removeDisks">同时删除磁盘文件</el-checkbox>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deletingVm" @click="deleteVm">
          {{ deletingVm ? '删除中...' : '确认删除' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/stores'
import {
  Plus, Refresh, Delete, Monitor, Download, Connection,
  VideoPlay, VideoPause, SwitchButton,
} from '@element-plus/icons-vue'

// ====== 状态 ======
const activeTab = ref('list')
const loadingDomains = ref(false)
const loadingTemplates = ref(false)
const domains = ref([])
const templates = ref([])

// VM 可用性
const available = ref(false)
const availabilityChecked = ref(false)
const availabilityMessage = ref('')

// 创建虚拟机
const createDialogVisible = ref(false)
const createStep = ref(0)
const creatingVm = ref(false)
const createForm = ref({
  name: '',
  template: '',
  vcpus: 2,
  memory_mb: 2048,
  disk_size_gb: 20,
  iso_url: '',
})

// 下载镜像
const downloadDialogVisible = ref(false)
const downloadTemplateName = ref('')
const downloadUrl = ref('')
const downloading = ref(false)

// 删除
const deleteDialogVisible = ref(false)
const deleteTarget = ref(null)
const removeDisks = ref(true)
const deletingVm = ref(false)

// VNC
const vncSelectedVm = ref('')
const vncInfo = ref(null)

// ====== 计算属性 ======
const runningDomains = computed(() =>
  domains.value.filter(d => d.state === 'running')
)

// ====== 方法 ======

// 状态标签
function stateTagType(state) {
  if (state === 'running') return 'success'
  if (state === 'paused') return 'warning'
  return 'info'
}

function stateLabel(state) {
  if (state === 'running') return '运行中'
  if (state === 'paused') return '已暂停'
  return '已关机'
}

function formatMemory(mb) {
  if (!mb) return '-'
  if (mb >= 1024) return (mb / 1024).toFixed(1) + ' GB'
  return mb + ' MB'
}

// 检查可用性
async function checkAvailability() {
  try {
    const res = await api.get('/vm/available')
    available.value = res.data.available
    availabilityMessage.value = res.data.message || ''
    availabilityChecked.value = true
    if (available.value) {
      fetchDomains()
      fetchTemplates()
    }
  } catch {
    available.value = false
    availabilityChecked.value = true
    availabilityMessage.value = '无法检测 KVM/libvirt 状态'
  }
}

// 获取虚拟机列表
async function fetchDomains() {
  loadingDomains.value = true
  try {
    const res = await api.get('/vm/domains')
    domains.value = res.data || []
  } catch (e) {
    ElMessage.error('获取虚拟机列表失败: ' + (e.response?.data?.detail || e.message))
  }
  loadingDomains.value = false
}

// 获取模板列表
async function fetchTemplates() {
  loadingTemplates.value = true
  try {
    const res = await api.get('/vm/templates')
    templates.value = res.data || []
  } catch (e) {
    ElMessage.error('获取模板列表失败: ' + (e.response?.data?.detail || e.message))
  }
  loadingTemplates.value = false
}

// 启动虚拟机
async function startVm(vm) {
  try {
    await api.post(`/vm/domains/${vm.name}/start`)
    ElMessage.success(`虚拟机 ${vm.name} 已启动`)
    fetchDomains()
  } catch (e) {
    ElMessage.error('启动失败: ' + (e.response?.data?.detail || e.message))
  }
}

// 关机
async function shutdownVm(vm) {
  try {
    await ElMessageBox.confirm(
      '请选择关机方式：',
      `关机 - ${vm.name}`,
      {
        confirmButtonText: '正常关机',
        cancelButtonText: '强制关机',
        distinguishCancelAndClose: true,
        type: 'warning',
      }
    )
    // 正常关机
    await api.post(`/vm/domains/${vm.name}/shutdown`, null, { params: { force: false } })
    ElMessage.success(`虚拟机 ${vm.name} 正在关机`)
  } catch (action) {
    if (action === 'cancel') {
      // 强制关机
      try {
        await api.post(`/vm/domains/${vm.name}/shutdown`, null, { params: { force: true } })
        ElMessage.success(`虚拟机 ${vm.name} 已强制关机`)
      } catch (e) {
        ElMessage.error('强制关机失败: ' + (e.response?.data?.detail || e.message))
      }
    } else if (action !== 'close') {
      ElMessage.error('关机失败')
    }
  }
  fetchDomains()
}

// 重启
async function restartVm(vm) {
  try {
    await api.post(`/vm/domains/${vm.name}/reboot`)
    ElMessage.success(`虚拟机 ${vm.name} 正在重启`)
    fetchDomains()
  } catch (e) {
    ElMessage.error('重启失败: ' + (e.response?.data?.detail || e.message))
  }
}

// 删除确认
function confirmDelete(vm) {
  deleteTarget.value = vm
  deleteDialogVisible.value = true
}

async function deleteVm() {
  if (!deleteTarget.value) return
  deletingVm.value = true
  try {
    await api.delete(`/vm/domains/${deleteTarget.value.name}`, {
      params: { remove_disks: removeDisks.value },
    })
    ElMessage.success(`虚拟机 ${deleteTarget.value.name} 已删除`)
    deleteDialogVisible.value = false
    deleteTarget.value = null
    fetchDomains()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
  deletingVm.value = false
}

// 创建虚拟机
function openCreateDialog() {
  resetCreateForm()
  createDialogVisible.value = true
  if (templates.value.length === 0) {
    fetchTemplates()
  }
}

function resetCreateForm() {
  createStep.value = 0
  createForm.value = {
    name: '',
    template: '',
    vcpus: 2,
    memory_mb: 2048,
    disk_size_gb: 20,
    iso_url: '',
  }
}

async function createVm() {
  creatingVm.value = true
  try {
    const payload = {
      name: createForm.value.name,
      template: createForm.value.template,
      vcpus: createForm.value.vcpus,
      memory_mb: createForm.value.memory_mb,
      disk_size_gb: createForm.value.disk_size_gb,
    }
    if (createForm.value.iso_url) {
      payload.iso_url = createForm.value.iso_url
    }
    await api.post('/vm/domains', payload)
    ElMessage.success(`虚拟机 ${createForm.value.name} 创建成功`)
    createDialogVisible.value = false
    fetchDomains()
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  }
  creatingVm.value = false
}

// 下载模板镜像
function openDownloadDialog(tpl) {
  downloadTemplateName.value = tpl.name
  downloadUrl.value = ''
  downloadDialogVisible.value = true
}

async function downloadTemplate() {
  if (!downloadUrl.value.trim()) {
    ElMessage.warning('请输入镜像 URL')
    return
  }
  downloading.value = true
  try {
    await api.post(`/vm/templates/${downloadTemplateName.value}/download`, {
      url: downloadUrl.value,
    })
    ElMessage.success(`开始下载镜像到模板 ${downloadTemplateName.value}`)
    downloadDialogVisible.value = false
  } catch (e) {
    ElMessage.error('下载失败: ' + (e.response?.data?.detail || e.message))
  }
  downloading.value = false
}

// VNC 信息
async function fetchVncInfo(name) {
  if (!name) {
    vncInfo.value = null
    return
  }
  try {
    const res = await api.get(`/vm/vnc/${name}`)
    vncInfo.value = res.data
  } catch (e) {
    vncInfo.value = null
    ElMessage.error('获取 VNC 信息失败: ' + (e.response?.data?.detail || e.message))
  }
}

// 复制文本
function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success('已复制到剪贴板')
  })
}

// ====== 初始化 ======
onMounted(() => {
  checkAvailability()
})
</script>

<style scoped>
.vm-page {
  color: #ccc;
}

.vm-page h2 {
  font-size: 20px;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 16px;
}

.warn-alert {
  margin-bottom: 16px;
}

.toolbar {
  margin-bottom: 16px;
  display: flex;
  gap: 8px;
}

.text-muted {
  color: #666;
}

/* ====== Steps / Create Dialog ====== */
.create-steps {
  margin-bottom: 24px;
}

.step-content {
  min-height: 200px;
}

.step-nav {
  margin-top: 24px;
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* ====== 模板选择卡片（创建对话框内） ====== */
.template-select-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.template-select-card {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-select-card:hover {
  border-color: #409EFF;
}

.template-select-card.selected {
  border-color: #409EFF;
  background: rgba(64, 158, 255, 0.1);
}

.template-select-name {
  font-weight: 600;
  font-size: 15px;
  color: #e0e0e0;
  margin-bottom: 4px;
}

.template-select-os {
  font-size: 12px;
  color: #888;
  margin-bottom: 6px;
}

.template-select-desc {
  font-size: 13px;
  color: #aaa;
  margin-bottom: 8px;
}

.template-select-req {
  font-size: 11px;
  color: #666;
}

/* ====== 模板网格（模板管理 Tab） ====== */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.template-card {
  background: #1a1a1a !important;
  border: 1px solid #333 !important;
  border-radius: 8px;
}

.template-card :deep(.el-card__body) {
  padding: 16px;
}

.template-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  color: #409EFF;
}

.template-name {
  font-weight: 600;
  font-size: 16px;
  color: #e0e0e0;
}

.template-os {
  font-size: 13px;
  color: #888;
  margin-bottom: 6px;
}

.template-desc {
  font-size: 13px;
  color: #aaa;
  margin-bottom: 10px;
  line-height: 1.4;
}

.template-minreq {
  margin-bottom: 12px;
}

.template-actions {
  margin-top: 8px;
}

/* ====== VNC Tab ====== */
.vnc-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.vnc-label {
  font-size: 14px;
  color: #ccc;
  white-space: nowrap;
}

.vnc-info-panel {
  max-width: 600px;
}

.vnc-card {
  background: #1a1a1a !important;
  border: 1px solid #333 !important;
  border-radius: 8px;
}

.vnc-card :deep(.el-card__header) {
  border-bottom: 1px solid #333;
  color: #e0e0e0;
  font-weight: 600;
}

.vnc-info-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
}

.vnc-info-label {
  font-size: 14px;
  color: #ccc;
  white-space: nowrap;
  min-width: 110px;
  padding-top: 2px;
}

.vnc-url-copy {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.vnc-url {
  font-size: 13px;
  background: #0a0a0a;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #333;
  color: #409EFF;
  word-break: break-all;
}

.vnc-tip {
  margin-top: 16px;
}

.vnc-tip p {
  margin: 4px 0;
  font-size: 13px;
}

.vnc-code {
  display: inline-block;
  background: #0a0a0a;
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid #333;
  color: #ccc;
  font-family: monospace;
  margin: 4px 0;
}

/* ====== 通用 ====== */
.loading-center {
  padding: 40px 0;
}

.empty-state {
  padding: 40px 0;
}
</style>
