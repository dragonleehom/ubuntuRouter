<template>
  <div class="mount-page">
    <div class="page-header">
      <h2>网络共享挂载</h2>
      <div class="header-actions">
        <el-button size="small" @click="fetchMounts" :loading="loading">
          <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 当前挂载列表 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>已挂载的共享</span>
      </template>
      <el-table :data="mounts" stripe size="small" v-loading="loading">
        <el-table-column prop="target" label="挂载点" min-width="180" />
        <el-table-column prop="source" label="源" min-width="200" />
        <el-table-column prop="fs_type" label="类型" width="80" />
        <el-table-column prop="size" label="容量" width="100" align="right" class="hide-mobile" />
        <el-table-column prop="used" label="已用" width="100" align="right" class="hide-mobile" />
        <el-table-column prop="avail" label="可用" width="100" align="right" class="hide-mobile" />
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="unmountFilesystem(row)">
              卸载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && mounts.length === 0" description="暂无挂载" />
    </el-card>

    <!-- NFS 挂载 -->
    <el-card shadow="never" class="section-card" style="margin-top: 16px">
      <template #header><span>挂载 NFS 共享</span></template>
      <el-form :model="nfsForm" label-width="110px" size="small">
        <el-form-item label="服务器地址" required>
          <el-input v-model="nfsForm.server" placeholder="如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="远程路径" required>
          <el-input v-model="nfsForm.remote_path" placeholder="如 /exports/data" />
        </el-form-item>
        <el-form-item label="本地挂载点" required>
          <el-input v-model="nfsForm.mount_point" placeholder="如 /mnt/nfs_data" />
        </el-form-item>
        <el-form-item label="挂载选项">
          <el-input v-model="nfsForm.options" placeholder="vers=4.2,soft,timeo=100" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doMountNfs" :loading="nfsLoading">挂载 NFS</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- CIFS 挂载 -->
    <el-card shadow="never" class="section-card" style="margin-top: 16px">
      <template #header><span>挂载 CIFS/SMB 共享</span></template>
      <el-form :model="cifsForm" label-width="110px" size="small">
        <el-form-item label="服务器地址" required>
          <el-input v-model="cifsForm.server" placeholder="如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="共享名称" required>
          <el-input v-model="cifsForm.share" placeholder="如 shared" />
        </el-form-item>
        <el-form-item label="本地挂载点" required>
          <el-input v-model="cifsForm.mount_point" placeholder="如 /mnt/smb_share" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="cifsForm.username" placeholder="可选" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="cifsForm.password" type="password" show-password placeholder="可选" />
        </el-form-item>
        <el-form-item label="工作组">
          <el-input v-model="cifsForm.domain" placeholder="WORKGROUP" />
        </el-form-item>
        <el-form-item label="挂载选项">
          <el-input v-model="cifsForm.options" placeholder="vers=3.0,sec=ntlmssp" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doMountCifs" :loading="cifsLoading">挂载 CIFS</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { api } from '@/stores'

const loading = ref(false)
const nfsLoading = ref(false)
const cifsLoading = ref(false)
const mounts = ref([])

const nfsForm = ref({ server: '', remote_path: '', mount_point: '', options: '' })
const cifsForm = ref({ server: '', share: '', mount_point: '', username: '', password: '', domain: '', options: '' })

onMounted(fetchMounts)

async function fetchMounts() {
  loading.value = true
  try {
    const res = await api.get('/storage/mounts')
    mounts.value = res.data.mounts || []
  } catch {
    ElMessage.error('获取挂载列表失败')
  }
  loading.value = false
}

async function doMountNfs() {
  const f = nfsForm.value
  if (!f.server || !f.remote_path || !f.mount_point) {
    ElMessage.warning('请填写必填项')
    return
  }
  nfsLoading.value = true
  try {
    const res = await api.post('/storage/mount/nfs', f)
    ElMessage.success(res.data.message)
    await fetchMounts()
    nfsForm.value = { server: '', remote_path: '', mount_point: '', options: '' }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'NFS 挂载失败')
  }
  nfsLoading.value = false
}

async function doMountCifs() {
  const f = cifsForm.value
  if (!f.server || !f.share || !f.mount_point) {
    ElMessage.warning('请填写必填项')
    return
  }
  cifsLoading.value = true
  try {
    const res = await api.post('/storage/mount/cifs', f)
    ElMessage.success(res.data.message)
    await fetchMounts()
    cifsForm.value = { server: '', share: '', mount_point: '', username: '', password: '', domain: '', options: '' }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'CIFS 挂载失败')
  }
  cifsLoading.value = false
}

async function unmountFilesystem(row) {
  try {
    const res = await api.post('/storage/unmount', { target: row.target })
    ElMessage.success(res.data.message || '卸载成功')
    await fetchMounts()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '卸载失败')
  }
}
</script>

<style scoped>
.mount-page { padding: 0; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0; color: #e0e0e0; }
.header-actions { display: flex; gap: 8px; }
.section-card {
  background: #141414;
  border: 1px solid #222;
}
</style>
