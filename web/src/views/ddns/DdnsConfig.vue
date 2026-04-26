<template>
  <div class="ddns-page">
    <h2>动态 DNS (DDNS)</h2>

    <!-- 状态卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">记录数</div>
            <div class="stat-value">{{ status.record_count || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">上次检查</div>
            <div class="stat-value small">{{ status.last_check || '未运行' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">调度器</div>
            <div class="stat-value">
              <el-tag :type="status.scheduler_running ? 'success' : 'info'" size="small">
                {{ status.scheduler_running ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="stat-label">下次检查</div>
            <div class="stat-value small">{{ status.next_check || '-' }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon> 添加记录
      </el-button>
      <el-button @click="triggerCheck" :loading="checking">
        <el-icon><Refresh /></el-icon> 立即检查
      </el-button>
      <el-button @click="fetchAll" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <!-- 记录列表 -->
    <el-table :data="records" stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="type" label="服务商" width="100">
        <template #default="{ row }">
          <el-tag>{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="domain" label="域名" min-width="180" />
      <el-table-column prop="subdomain" label="子域名" width="120" />
      <el-table-column prop="current_ip" label="当前 IP" width="140" />
      <el-table-column prop="last_update" label="上次更新" width="160" />
      <el-table-column prop="enabled" label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled !== false ? 'success' : 'info'" size="small">
            {{ row.enabled !== false ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="forceUpdate(row)">更新</el-button>
          <el-button size="small" type="danger" @click="removeRecord(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && records.length === 0" description="暂无 DDNS 记录" />

    <!-- 添加记录对话框 -->
    <el-dialog v-model="showAddDialog" title="添加 DDNS 记录" width="550px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="服务商" required>
          <el-select v-model="form.type" style="width: 100%" @change="onProviderChange">
            <el-option v-for="p in providers" :key="p.type" :label="p.name" :value="p.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="主域名" required>
          <el-input v-model="form.domain" placeholder="example.com" />
        </el-form-item>
        <el-form-item label="子域名">
          <el-input v-model="form.subdomain" placeholder="@ 或 www（留空=@）" />
        </el-form-item>

        <!-- 动态参数 -->
        <template v-if="selectedProvider">
          <el-form-item v-for="param in selectedProvider.params" :key="param.name"
            :label="param.label || param.name" :required="param.required">
            <el-input
              v-if="param.type !== 'password'"
              v-model="form.params[param.name]"
              :placeholder="param.placeholder || ''"
            />
            <el-input
              v-else
              v-model="form.params[param.name]"
              type="password"
              show-password
              :placeholder="param.placeholder || ''"
            />
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addRecord" :loading="saving">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/stores'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const checking = ref(false)
const saving = ref(false)
const records = ref([])
const providers = ref([])
const status = ref({})
const showAddDialog = ref(false)

const form = ref({
  type: '',
  domain: '',
  subdomain: '',
  params: {},
})

const selectedProvider = computed(() => {
  return providers.value.find(p => p.type === form.value.type) || null
})

async function fetchRecords() {
  try {
    const res = await api.get('/ddns/records')
    records.value = res.data.records || []
  } catch (e) {
    ElMessage.error('获取记录失败')
  }
}

async function fetchProviders() {
  try {
    const res = await api.get('/ddns/providers')
    providers.value = res.data.providers || []
  } catch (e) {
    ElMessage.error('获取服务商列表失败')
  }
}

async function fetchStatus() {
  try {
    const res = await api.get('/ddns/status')
    status.value = res.data
  } catch (e) { /* ignore */ }
}

async function fetchAll() {
  loading.value = true
  await Promise.all([fetchRecords(), fetchProviders(), fetchStatus()])
  loading.value = false
}

function onProviderChange() {
  form.value.params = {}
}

async function addRecord() {
  saving.value = true
  try {
    const payload = {
      type: form.value.type,
      domain: form.value.domain,
      subdomain: form.value.subdomain || '@',
      params: form.value.params,
    }
    const res = await api.post('/ddns/records', payload)
    ElMessage.success(res.data.message || '添加成功')
    showAddDialog.value = false
    form.value = { type: '', domain: '', subdomain: '', params: {} }
    await fetchRecords()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  }
  saving.value = false
}

async function removeRecord(record) {
  try {
    await ElMessageBox.confirm(`确认删除 ${record.domain} 的 DDNS 记录？`, '确认')
    await api.delete(`/ddns/records/${record.id}`)
    ElMessage.success('已删除')
    await fetchRecords()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function forceUpdate(record) {
  try {
    const res = await api.post(`/ddns/records/${record.id}/update`)
    ElMessage.success(res.data.message || '更新成功')
    await fetchRecords()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

async function triggerCheck() {
  checking.value = true
  try {
    const res = await api.post('/ddns/check')
    ElMessage.success(`检查完成: ${res.data.updated || 0} 条已更新`)
    await fetchRecords()
  } catch (e) {
    ElMessage.error('检查失败')
  }
  checking.value = false
}

onMounted(() => fetchAll())
</script>

<style scoped>
.ddns-page { padding: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.stat-item { text-align: center; padding: 8px; }
.stat-label { font-size: 13px; color: #888; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #e0e0e0; }
.stat-value.small { font-size: 14px; }
</style>
