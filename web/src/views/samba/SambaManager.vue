<template>
  <div class="samba-page">
    <h2>Samba 共享</h2>

    <!-- 服务状态 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :xs="12" :sm="6" v-for="s in serviceCards" :key="s.label" style="margin-bottom: 12px">
        <el-card shadow="hover" :body-style="{ padding: '14px' }">
          <div class="stat-card">
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-value">
              <el-tag :type="s.active ? 'success' : 'danger'" size="small" effect="dark">
                {{ s.active ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button :type="sambaActive ? 'warning' : 'success'" @click="toggleService">
        {{ sambaActive ? '停止 Samba' : '启动 Samba' }}
      </el-button>
      <el-button @click="restartService">重启</el-button>
    </div>

    <el-tabs v-model="activeTab">
      <!-- 共享目录 -->
      <el-tab-pane label="共享目录" name="shares">
        <div class="toolbar">
          <el-button type="primary" @click="showAddShare = true">
            <el-icon><Plus /></el-icon> 添加共享
          </el-button>
        </div>

        <el-table :data="shares" stripe v-loading="sharesLoading" style="width: 100%">
          <el-table-column prop="name" label="名称" width="180" />
          <el-table-column prop="path" label="路径" min-width="200" />
          <el-table-column label="可写" width="70">
            <template #default="{ row }">
              <el-tag :type="row.writable ? 'success' : 'info'" size="small">{{ row.writable ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="访客" width="70" class-name="hide-mobile">
            <template #default="{ row }">
              <el-tag :type="row.guest_ok ? 'warning' : 'info'" size="small">{{ row.guest_ok ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="valid_users" label="用户" width="150" class-name="hide-mobile" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="editShare(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteShare(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!sharesLoading && shares.length === 0" description="暂无共享目录" />
      </el-tab-pane>

      <!-- Samba 用户 -->
      <el-tab-pane label="Samba 用户" name="users">
        <div class="toolbar">
          <el-button type="primary" @click="showAddUser = true">
            <el-icon><Plus /></el-icon> 添加用户
          </el-button>
        </div>

        <el-table :data="users" stripe v-loading="usersLoading">
          <el-table-column prop="username" label="用户名" min-width="200" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="deleteUser(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加共享对话框 -->
    <el-dialog v-model="showAddShare" :title="editTarget ? '编辑共享' : '添加共享'" width="500px">
      <el-form :model="shareForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="shareForm.name" :disabled="!!editTarget" placeholder="my-share" />
        </el-form-item>
        <el-form-item label="路径" required>
          <el-input v-model="shareForm.path" placeholder="/path/to/share" />
        </el-form-item>
        <el-form-item label="可写">
          <el-switch v-model="shareForm.writable" />
        </el-form-item>
        <el-form-item label="访客可访问">
          <el-switch v-model="shareForm.guest_ok" />
        </el-form-item>
        <el-form-item label="授权用户">
          <el-input v-model="shareForm.valid_users" placeholder="user1, user2（留空=所有人）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddShare = false">取消</el-button>
        <el-button type="primary" @click="saveShare" :loading="savingShare">{{ editTarget ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- 添加用户对话框 -->
    <el-dialog v-model="showAddUser" title="添加 Samba 用户" width="400px">
      <el-form :model="userForm" label-width="100px">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" placeholder="username" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="userForm.password" type="password" show-password placeholder="密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddUser = false">取消</el-button>
        <el-button type="primary" @click="saveUser" :loading="savingUser">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/stores'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('shares')
const shares = ref([])
const users = ref([])
const sharesLoading = ref(false)
const usersLoading = ref(false)
const statusInfo = ref({})
const showAddShare = ref(false)
const showAddUser = ref(false)
const editTarget = ref(null)
const savingShare = ref(false)
const savingUser = ref(false)

const shareForm = ref({ name: '', path: '', writable: true, guest_ok: false, valid_users: '' })
const userForm = ref({ username: '', password: '' })

const sambaActive = computed(() => statusInfo.value.smbd_active || false)

const serviceCards = computed(() => {
  const s = statusInfo.value
  return [
    { label: 'SMB', active: s.smbd_active },
    { label: 'NMB', active: s.nmbd_active },
    { label: '配置有效', active: s.config_valid },
  ]
})

async function fetchStatus() {
  try {
    const res = await api.get('/samba/status')
    statusInfo.value = res.data
  } catch (e) { /* ignore */ }
}

async function fetchShares() {
  sharesLoading.value = true
  try {
    const res = await api.get('/samba/shares')
    shares.value = res.data.shares || []
  } catch (e) { ElMessage.error('获取共享列表失败') }
  sharesLoading.value = false
}

async function fetchUsers() {
  usersLoading.value = true
  try {
    const res = await api.get('/samba/users')
    users.value = res.data.users || []
  } catch (e) { /* ignore */ }
  usersLoading.value = false
}

async function toggleService() {
  try {
    const action = sambaActive.value ? 'stop' : 'start'
    await api.post(`/samba/${action}`)
    ElMessage.success(sambaActive.value ? 'Samba 已停止' : 'Samba 已启动')
    await fetchStatus()
  } catch (e) { ElMessage.error('操作失败') }
}

async function restartService() {
  try {
    await api.post('/samba/restart')
    ElMessage.success('Samba 已重启')
    await fetchStatus()
  } catch (e) { ElMessage.error('重启失败') }
}

function editShare(share) {
  editTarget.value = share
  shareForm.value = {
    name: share.name,
    path: share.path || '',
    writable: share.writable !== false,
    guest_ok: !!share.guest_ok,
    valid_users: share.valid_users || '',
  }
  showAddShare.value = true
}

async function saveShare() {
  savingShare.value = true
  try {
    const payload = { ...shareForm.value }
    if (editTarget.value) {
      await api.put(`/samba/shares/${editTarget.value.name}`, payload)
      ElMessage.success('共享已更新')
    } else {
      await api.post('/samba/shares', payload)
      ElMessage.success('共享已添加')
    }
    showAddShare.value = false
    editTarget.value = null
    shareForm.value = { name: '', path: '', writable: true, guest_ok: false, valid_users: '' }
    await fetchShares()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
  savingShare.value = false
}

async function deleteShare(share) {
  try {
    await ElMessageBox.confirm(`确认删除共享 "${share.name}"？`, '确认')
    await api.delete(`/samba/shares/${share.name}`)
    ElMessage.success('已删除')
    await fetchShares()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

async function saveUser() {
  savingUser.value = true
  try {
    await api.post('/samba/users', { ...userForm.value })
    ElMessage.success('用户已添加')
    showAddUser.value = false
    userForm.value = { username: '', password: '' }
    await fetchUsers()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '添加失败') }
  savingUser.value = false
}

async function deleteUser(user) {
  try {
    await ElMessageBox.confirm(`确认删除用户 "${user.username}"？`, '确认')
    await api.delete(`/samba/users/${user.username}`)
    ElMessage.success('已删除')
    await fetchUsers()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

onMounted(async () => {
  await Promise.all([fetchStatus(), fetchShares(), fetchUsers()])
})
</script>

<style scoped>
.samba-page { padding: 0; }
.stat-card { text-align: center; }
.stat-label { font-size: 12px; color: #888; margin-bottom: 4px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }
</style>
