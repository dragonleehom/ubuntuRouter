<template>
  <div class="page">
    <div class="page-header">
      <h2>网络接口</h2>
      <el-button type="primary" @click="fetchInterfaces">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <el-table :data="interfaces" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="接口名" width="150" />
      <el-table-column prop="state" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.state === 'UP' ? 'success' : 'danger'" size="small">
            {{ row.state }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="mac" label="MAC 地址" width="200" />
      <el-table-column label="IPv4 地址">
        <template #default="{ row }">
          <span v-if="row.ipv4 && row.ipv4.length">{{ row.ipv4.join(', ') }}</span>
          <span v-else class="text-muted">未配置</span>
        </template>
      </el-table-column>
      <el-table-column prop="mtu" label="MTU" width="80" />
      <el-table-column prop="speed" label="速率" width="80">
        <template #default="{ row }">
          {{ row.speed ? row.speed + 'M' : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="type" label="类型" width="100" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button text type="primary" size="small" @click="showEditDialog(row)">编辑 IP</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑 IP 对话框 -->
    <el-dialog v-model="showEdit" title="编辑接口 IP 配置" width="500px">
      <el-form :model="editForm" label-width="120px" size="small">
        <el-form-item label="接口">
          <el-tag>{{ editForm.iface }}</el-tag>
        </el-form-item>
        <el-form-item label="IP 地址">
          <el-input v-model="editForm.ip" placeholder="如 192.168.1.1/24" />
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="editForm.gateway" placeholder="如 192.168.1.254" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="saveIpConfig" :loading="saving">保存并应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/stores'
import { Refresh } from '@element-plus/icons-vue'

const interfaces = ref([])
const loading = ref(false)
const showEdit = ref(false)
const saving = ref(false)
const editForm = reactive({ iface: '', ip: '', gateway: '' })

async function fetchInterfaces() {
  loading.value = true
  try {
    const res = await api.get('/interfaces/list')
    interfaces.value = res.data.interfaces
  } catch (e) {
    console.error('获取接口列表失败:', e)
  }
  loading.value = false
}

function showEditDialog(row) {
  editForm.iface = row.name
  editForm.ip = row.ipv4 && row.ipv4.length ? row.ipv4[0] : ''
  editForm.gateway = ''
  showEdit.value = true
}

async function saveIpConfig() {
  saving.value = true
  try {
    await ElMessageBox.confirm(
      `将 ${editForm.iface} 的 IP 修改为 ${editForm.ip}，此操作可能断开当前网络连接，确认？`,
      '警告',
      { confirmButtonText: '确认修改', cancelButtonText: '取消', type: 'warning' }
    )
    const res = await api.post('/interfaces/config', {
      name: editForm.iface,
      ip: editForm.ip,
      gateway: editForm.gateway || undefined,
    })
    if (res.data.success) {
      ElMessage.success('配置已应用，网络可能短暂中断')
      showEdit.value = false
    } else {
      ElMessage.error(res.data.message || '配置失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('配置失败: ' + (e.response?.data?.detail || e.message))
    }
  }
  saving.value = false
}

onMounted(fetchInterfaces)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #e0e0e0;
}
.text-muted { color: #666; }
</style>
