<template>
  <div class="nfs-page">
    <h2>NFS 文件共享</h2>

    <!-- 服务状态卡 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :xs="24" :sm="8" style="margin-bottom: 12px">
        <el-card shadow="hover" :body-style="{ padding: '14px' }">
          <div class="stat-card">
            <div class="stat-label">NFS 服务状态</div>
            <div class="stat-value">
              <el-tag :type="nfsActive ? 'success' : 'danger'" size="small" effect="dark">
                {{ nfsActive ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 服务控制工具栏 -->
    <div class="toolbar">
      <el-button v-if="!nfsActive" type="success" @click="startService" :loading="svcLoading">
        启动 NFS
      </el-button>
      <el-button v-else type="warning" @click="stopService" :loading="svcLoading">
        停止 NFS
      </el-button>
      <el-button @click="restartService" :loading="svcLoading" :disabled="!nfsActive">
        重启
      </el-button>
      <el-button @click="refreshStatus" :loading="statusLoading" circle>
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <!-- NFS 导出管理 -->
    <div class="toolbar" style="margin-top: 20px">
      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon> 添加导出
      </el-button>
    </div>

    <el-table :data="exports" stripe v-loading="exportsLoading" style="width: 100%">
      <el-table-column prop="path" label="导出路径" min-width="200" />
      <el-table-column label="客户端" min-width="200">
        <template #default="{ row }">
          <div v-for="c in row.clients" :key="c.client" style="margin-bottom: 4px">
            <el-tag size="small">{{ c.client }}</el-tag>
            <span v-if="c.options && c.options.length" style="margin-left: 6px; color: #909399; font-size: 12px">
              ({{ c.options.join(', ') }})
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="editExport(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteExport(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!exportsLoading && exports.length === 0" description="暂无 NFS 导出" />

    <!-- 添加/编辑导出对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑导出' : '添加导出'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="导出路径" required>
          <el-input v-model="form.path" :disabled="isEditing" placeholder="/path/to/share" />
        </el-form-item>

        <el-form-item label="客户端列表" required>
          <div v-for="(client, idx) in form.clients" :key="idx" style="display: flex; gap: 8px; margin-bottom: 8px; align-items: flex-start;">
            <div style="flex: 1">
              <el-input v-model="client.client" placeholder="例: 192.168.1.0/24 或 *" size="small" />
            </div>
            <div style="flex: 1">
              <el-select v-model="client.options" multiple placeholder="选项" size="small" style="width: 100%">
                <el-option label="ro" value="ro" />
                <el-option label="rw" value="rw" />
                <el-option label="sync" value="sync" />
                <el-option label="async" value="async" />
                <el-option label="no_subtree_check" value="no_subtree_check" />
                <el-option label="insecure" value="insecure" />
              </el-select>
            </div>
            <el-button size="small" type="danger" @click="removeClient(idx)" :disabled="form.clients.length <= 1">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-button size="small" @click="addClient">
            <el-icon><Plus /></el-icon> 添加客户端
          </el-button>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">
          {{ isEditing ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Refresh } from '@element-plus/icons-vue'

const API_BASE = '/api/v1/nfs'

// ─── 服务状态 ──────────────────────────────────────────────────────────────
const nfsActive = ref(false)
const svcLoading = ref(false)
const statusLoading = ref(false)
let pollTimer = null

async function fetchStatus() {
  statusLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/status`, { credentials: 'include' })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    nfsActive.value = data.active
  } catch (e) {
    console.error('获取 NFS 状态失败:', e)
  } finally {
    statusLoading.value = false
  }
}

async function refreshStatus() {
  await fetchStatus()
}

function startPolling() {
  pollTimer = setInterval(fetchStatus, 10000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function startService() {
  svcLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/start`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '启动失败')
    }
    ElMessage.success('NFS 服务已启动')
    await fetchStatus()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    svcLoading.value = false
  }
}

async function stopService() {
  svcLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/stop`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '停止失败')
    }
    ElMessage.success('NFS 服务已停止')
    await fetchStatus()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    svcLoading.value = false
  }
}

async function restartService() {
  svcLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/restart`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '重启失败')
    }
    ElMessage.success('NFS 服务已重启')
    await fetchStatus()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    svcLoading.value = false
  }
}

// ─── 导出管理 ──────────────────────────────────────────────────────────────
const exports = ref([])
const exportsLoading = ref(false)

async function fetchExports() {
  exportsLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/exports`, { credentials: 'include' })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    exports.value = data.entries || []
  } catch (e) {
    console.error('获取 NFS 导出失败:', e)
  } finally {
    exportsLoading.value = false
  }
}

// ─── 对话框 ────────────────────────────────────────────────────────────────
const dialogVisible = ref(false)
const isEditing = ref(false)
const submitLoading = ref(false)
const editingPath = ref('')

const defaultClient = () => ({ client: '192.168.1.0/24', options: ['rw', 'sync', 'no_subtree_check'] })

const form = ref({
  path: '',
  clients: [defaultClient()],
})

function resetForm() {
  form.value = { path: '', clients: [defaultClient()] }
  isEditing.value = false
  editingPath.value = ''
}

function openAddDialog() {
  resetForm()
  dialogVisible.value = true
}

function addClient() {
  form.value.clients.push(defaultClient())
}

function removeClient(idx) {
  form.value.clients.splice(idx, 1)
}

function editExport(row) {
  isEditing.value = true
  editingPath.value = row.path
  form.value = {
    path: row.path,
    clients: row.clients.map((c) => ({
      client: c.client,
      options: [...(c.options || [])],
    })),
  }
  // Ensure at least one client
  if (form.value.clients.length === 0) {
    form.value.clients.push(defaultClient())
  }
  dialogVisible.value = true
}

async function submitForm() {
  // Validate
  if (!form.value.path) {
    ElMessage.warning('请填写导出路径')
    return
  }
  if (!form.value.clients.length || !form.value.clients[0].client) {
    ElMessage.warning('请填写至少一个客户端')
    return
  }

  submitLoading.value = true
  try {
    const body = {
      path: form.value.path,
      clients: form.value.clients.map((c) => ({
        client: c.client,
        options: c.options || [],
      })),
    }

    let res
    if (isEditing.value) {
      res = await fetch(`${API_BASE}/exports/${encodeURIComponent(editingPath.value)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ clients: body.clients }),
      })
    } else {
      res = await fetch(`${API_BASE}/exports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      })
    }

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '操作失败')
    }

    ElMessage.success(isEditing.value ? '导出已更新' : '导出已添加')
    dialogVisible.value = false
    await fetchExports()
    // Also restart service to apply changes
    await restartService()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitLoading.value = false
  }
}

async function deleteExport(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除导出路径 "${row.path}" 吗？`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  try {
    const res = await fetch(`${API_BASE}/exports/${encodeURIComponent(row.path)}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '删除失败')
    }
    ElMessage.success('导出已删除')
    await fetchExports()
    await restartService()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// ─── 生命周期 ──────────────────────────────────────────────────────────────
onMounted(() => {
  document.title = 'NFS'
  fetchStatus()
  fetchExports()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.nfs-page {
  padding: 0;
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-label {
  font-size: 14px;
  color: #909399;
}
.stat-value {
  font-size: 18px;
  font-weight: 600;
}
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
</style>
