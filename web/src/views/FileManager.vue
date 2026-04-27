<template>
  <div class="file-manager">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item>
            <el-icon><FolderOpened /></el-icon>
            <span style="margin-left:4px">文件系统</span>
          </el-breadcrumb-item>
          <el-breadcrumb-item v-for="(seg, idx) in breadcrumbs" :key="idx">
            <a v-if="idx < breadcrumbs.length - 1" href="#" @click.prevent="cd(seg.path)">{{ seg.name }}</a>
            <span v-else>{{ seg.name }}</span>
          </el-breadcrumb-item>
        </el-breadcrumb>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="currentPath"
          size="small"
          style="width: 240px"
          @keyup.enter="cd(currentPath)"
          placeholder="输入路径回车跳转"
        />
        <el-button size="small" @click="refresh" :loading="loading">刷新</el-button>
      </div>
    </div>

    <!-- 磁盘信息条 -->
    <div class="disk-bar" v-if="diskUsage">
      <div class="disk-item">
        <span class="disk-label">磁盘</span>
        <el-progress
          :percentage="diskUsage.usage_percent"
          :stroke-width="10"
          :format="() => diskUsage.used_str + ' / ' + diskUsage.total_str"
          style="width: 240px"
        />
      </div>
      <div class="stats">
        <span>{{ stats.dirs }} 目录</span>
        <span>{{ stats.files }} 文件</span>
        <span>共 {{ stats.total_size_str }}</span>
      </div>
    </div>

    <!-- 主体：目录树 + 文件列表 -->
    <div class="file-body">
      <div class="sidebar">
        <div class="sidebar-header">
          <span>目录</span>
          <el-button size="small" text @click="cd('/')" title="回到根目录">
            <el-icon><HomeFilled /></el-icon>
          </el-button>
        </div>
        <div class="dir-tree" v-loading="loading">
          <div
            v-for="item in dirTreeItems"
            :key="item.path"
            class="tree-item"
            :class="{ active: item.path === currentPath }"
            :style="{ paddingLeft: (item.depth || 0) * 16 + 8 + 'px' }"
            @click="cd(item.path)"
          >
            <el-icon :size="14" :color="item.path === currentPath ? '#409EFF' : '#E6A23C'">
              <FolderOpened />
            </el-icon>
            <span class="tree-name">{{ item.name }}</span>
          </div>
          <div v-if="!loading && dirTreeItems.length === 0" class="tree-empty">无子目录</div>
        </div>
      </div>
      <div class="content">
        <!-- 操作按钮 -->
        <div class="action-bar">
          <el-button size="small" @click="showNewFolder = true">
            <el-icon><FolderAdd /></el-icon> 新建目录
          </el-button>
          <el-button size="small" @click="triggerUpload">
            <el-icon><Upload /></el-icon> 上传文件
          </el-button>
          <input
            ref="fileInput"
            type="file"
            multiple
            style="display:none"
            @change="handleUpload"
          />
          <el-button
            size="small"
            :disabled="!selectedFile"
            @click="showDownload = true"
          >
            <el-icon><Download /></el-icon> 下载
          </el-button>
          <el-button
            size="small"
            :disabled="!selectedFile"
            type="danger"
            text
            @click="handleDelete"
          >
            <el-icon><Delete /></el-icon> 删除
          </el-button>
        </div>

        <!-- 文件列表 -->
        <el-table
          :data="items"
          stripe
          size="small"
          highlight-current-row
          @row-click="selectFile"
          @row-dblclick="openItem"
          v-loading="loading"
          empty-text="空目录"
          style="width:100%"
        >
          <el-table-column label="名称" min-width="240">
            <template #default="{ row }">
              <div class="file-name-cell" :class="{ 'is-hidden': row.is_hidden }">
                <el-icon :size="16" :color="row.type === 'dir' ? '#E6A23C' : '#409EFF'">
                  <FolderOpened v-if="row.type === 'dir'" />
                  <Document v-else />
                </el-icon>
                <span class="file-name">{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="100" align="right">
            <template #default="{ row }">
              <span class="size-text">{{ row.size_str }}</span>
            </template>
          </el-table-column>
          <el-table-column label="权限" width="90" align="center">
            <template #default="{ row }">
              <code class="perms">{{ row.perms }}</code>
            </template>
          </el-table-column>
          <el-table-column label="修改时间" width="160" align="center">
            <template #default="{ row }">
              <span class="mtime">{{ formatTime(row.mtime) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click.stop="showRename(row)">重命名</el-button>
              <el-button size="small" text type="warning" @click.stop="showChmod(row)">权限</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 新建目录对话框 -->
    <el-dialog v-model="showNewFolder" title="新建目录" width="400px">
      <el-input v-model="newFolderName" placeholder="目录名称" @keyup.enter="createFolder" />
      <template #footer>
        <el-button size="small" @click="showNewFolder = false">取消</el-button>
        <el-button size="small" type="primary" @click="createFolder" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重命名对话框 -->
    <el-dialog v-model="showRenameDialog" title="重命名" width="400px">
      <el-input v-model="renameName" placeholder="新名称" @keyup.enter="doRename" />
      <template #footer>
        <el-button size="small" @click="showRenameDialog = false">取消</el-button>
        <el-button size="small" type="primary" @click="doRename" :loading="renaming">确定</el-button>
      </template>
    </el-dialog>

    <!-- 权限修改对话框 -->
    <el-dialog v-model="showChmodDialog" title="修改权限" width="400px">
      <div class="chmod-form">
        <div class="chmod-field">
          <span>数字模式</span>
          <el-input v-model="chmodMode" size="small" style="width:100px" placeholder="755" />
        </div>
        <div class="chmod-hint">常用：755（目录）、644（文件）、777（所有权限）</div>
        <el-checkbox v-model="chmodRecursive">递归应用到子目录</el-checkbox>
      </div>
      <template #footer>
        <el-button size="small" @click="showChmodDialog = false">取消</el-button>
        <el-button size="small" type="primary" @click="doChmod" :loading="chmodding">应用</el-button>
      </template>
    </el-dialog>

    <!-- 下载对话框 -->
    <el-dialog v-model="showDownload" title="下载文件" width="400px">
      <div v-if="selectedFile">
        <p>文件名：<strong>{{ selectedFile.name }}</strong></p>
        <p>大小：{{ selectedFile.size_str }}</p>
        <p>路径：<code>{{ selectedFile.path }}</code></p>
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            请使用浏览器下载功能或 <code>wget</code> / <code>curl</code> 获取此文件
          </template>
        </el-alert>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/stores'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  FolderOpened, Upload, Download, Delete,
  FolderAdd, Document, HomeFilled,
} from '@element-plus/icons-vue'

const loading = ref(false)
const currentPath = ref('/')
const items = ref([])
const stats = ref({ total: 0, dirs: 0, files: 0, total_size: 0, total_size_str: '0 B' })
const diskUsage = ref(null)
const selectedFile = ref(null)
const dirTreeItems = ref([])

// 新建目录
const showNewFolder = ref(false)
const newFolderName = ref('')
const creating = ref(false)

// 重命名
const showRenameDialog = ref(false)
const renameTarget = ref(null)
const renameName = ref('')
const renaming = ref(false)

// 权限
const showChmodDialog = ref(false)
const chmodTarget = ref(null)
const chmodMode = ref('755')
const chmodRecursive = ref(false)
const chmodding = ref(false)

// 下载
const showDownload = ref(false)

// 上传
const fileInput = ref(null)

const breadcrumbs = computed(() => {
  const parts = currentPath.value.replace(/\/+/g, '/').split('/').filter(Boolean)
  const crumbs = []
  let acc = ''
  for (const part of parts) {
    acc += '/' + part
    crumbs.push({ name: part, path: acc })
  }
  return crumbs
})

onMounted(() => cd('/'))

async function cd(path) {
  if (!path) path = '/'
  currentPath.value = path
  await refresh()
}

async function refresh() {
  loading.value = true
  selectedFile.value = null
  try {
    const res = await api.get('/files/list', { params: { path: currentPath.value, show_hidden: false } })
    items.value = res.data.items
    stats.value = res.data.stats
    diskUsage.value = res.data.disk_usage

    // 构建目录树（仅当前目录的子目录）
    dirTreeItems.value = buildDirTree(res.data.items, currentPath.value)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '读取目录失败')
  }
  loading.value = false
}

function buildDirTree(fileItems, basePath) {
  const dirs = fileItems.filter(i => i.type === 'dir')
  return dirs.map(d => ({ ...d, depth: 0 }))
}

function selectFile(row) {
  selectedFile.value = selectedFile.value?.path === row.path ? null : row
}

function openItem(row) {
  if (row.type === 'dir') {
    cd(row.path)
  } else {
    selectedFile.value = row
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleUpload(e) {
  const files = e.target.files
  if (!files.length) return
  for (const file of files) {
    const formData = new FormData()
    formData.append('path', currentPath.value)
    formData.append('file', file)
    try {
      await api.post('/files/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      ElMessage.success(`已上传: ${file.name}`)
    } catch (e) {
      ElMessage.error(`上传 ${file.name} 失败: ${e.response?.data?.detail || e.message}`)
    }
  }
  e.target.value = ''
  await refresh()
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 新建目录
async function createFolder() {
  if (!newFolderName.value.trim()) return
  creating.value = true
  try {
    const path = currentPath.value.replace(/\/$/, '') + '/' + newFolderName.value.trim()
    await api.post('/files/mkdir', null, { params: { path } })
    ElMessage.success('目录已创建')
    showNewFolder.value = false
    newFolderName.value = ''
    await refresh()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
  creating.value = false
}

// 删除
async function handleDelete() {
  if (!selectedFile.value) return
  const isDir = selectedFile.value.type === 'dir'
  const msg = isDir
    ? `确认删除目录 "${selectedFile.value.name}" 及其所有内容？`
    : `确认删除文件 "${selectedFile.value.name}"？`
  try {
    await ElMessageBox.confirm(msg, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await api.delete('/files/delete', { params: { path: selectedFile.value.path, recursive: true } })
    ElMessage.success('已删除')
    selectedFile.value = null
    await refresh()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

// 重命名
function showRename(row) {
  renameTarget.value = row
  renameName.value = row.name
  showRenameDialog.value = true
}

async function doRename() {
  if (!renameName.value.trim()) return
  renaming.value = true
  try {
    await api.post('/files/rename', null, {
      params: { path: renameTarget.value.path, new_name: renameName.value.trim() }
    })
    ElMessage.success('已重命名')
    showRenameDialog.value = false
    await refresh()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重命名失败')
  }
  renaming.value = false
}

// 权限
function showChmod(row) {
  chmodTarget.value = row
  chmodMode.value = row.mode?.replace(/^0o?/, '') || '755'
  chmodRecursive.value = false
  showChmodDialog.value = true
}

async function doChmod() {
  chmodding.value = true
  try {
    await api.post('/files/chmod', null, {
      params: {
        path: chmodTarget.value.path,
        mode: chmodMode.value,
        recursive: chmodRecursive.value,
      }
    })
    ElMessage.success('权限已修改')
    showChmodDialog.value = false
    await refresh()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改权限失败')
  }
  chmodding.value = false
}
</script>

<style scoped>
.file-manager {
  padding: 16px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 12px;
}
.toolbar-left {
  flex: 1;
  min-width: 0;
}
.toolbar-right {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}
.disk-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  margin-bottom: 8px;
  font-size: 12px;
}
.disk-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.disk-label {
  font-weight: 500;
  white-space: nowrap;
}
.stats {
  display: flex;
  gap: 12px;
  color: var(--el-text-color-secondary);
}
.file-body {
  display: flex;
  flex: 1;
  gap: 12px;
  min-height: 0;
}
.sidebar {
  width: 200px;
  flex-shrink: 0;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: var(--el-fill-color-lighter);
  font-size: 12px;
  font-weight: 500;
  border-bottom: 1px solid var(--el-border-color-light);
}
.dir-tree {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.tree-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 12px;
  border-radius: 4px;
  margin: 1px 4px;
  transition: background 0.15s;
}
.tree-item:hover {
  background: var(--el-fill-color-light);
}
.tree-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.tree-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-empty {
  padding: 12px;
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
.content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.action-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}
.file-name-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.file-name-cell.is-hidden {
  opacity: 0.6;
}
.file-name {
  font-size: 13px;
}
.size-text {
  font-family: monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.perms {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.mtime {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.chmod-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.chmod-field {
  display: flex;
  align-items: center;
  gap: 12px;
}
.chmod-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
