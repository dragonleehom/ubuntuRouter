<template>
  <div class="scheduled-tasks-page">
    <div class="page-header">
      <h2>计划任务</h2>
      <div class="header-actions">
        <el-tag :type="cronStatus.active ? 'success' : 'danger'" size="small">
          cron 服务 {{ cronStatus.active ? '运行中' : '已停止' }}
        </el-tag>
        <el-button size="small" @click="toggleCron" :loading="toggling">
          {{ cronStatus.active ? '停止' : '启动' }}
        </el-button>
        <el-button size="small" type="primary" @click="showAdd = true">
          <el-icon><Plus /></el-icon> 新建任务
        </el-button>
      </div>
    </div>

    <!-- 任务列表 -->
    <el-card shadow="never" class="tasks-card">
      <el-table :data="tasks" stripe empty-text="暂无计划任务" v-loading="loading">
        <el-table-column label="时间描述" width="160">
          <template #default="{ row }">
            <div class="schedule-text">
              <span>{{ row.schedule_text || '自定义' }}</span>
            </div>
            <div class="cron-expr">
              <code>{{ row.expression }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="分" width="60" align="center">
          <template #default="{ row }"><code>{{ row.minute }}</code></template>
        </el-table-column>
        <el-table-column label="时" width="60" align="center">
          <template #default="{ row }"><code>{{ row.hour }}</code></template>
        </el-table-column>
        <el-table-column label="日" width="60" align="center">
          <template #default="{ row }"><code>{{ row.day }}</code></template>
        </el-table-column>
        <el-table-column label="月" width="60" align="center">
          <template #default="{ row }"><code>{{ row.month }}</code></template>
        </el-table-column>
        <el-table-column label="周" width="60" align="center">
          <template #default="{ row }"><code>{{ row.weekday }}</code></template>
        </el-table-column>
        <el-table-column label="命令" min-width="200">
          <template #default="{ row }">
            <div class="command-cell">
              <code class="command-text">{{ row.command }}</code>
              <el-tag v-if="row.comment" size="small" type="info">{{ row.comment }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="editTask(row)">编辑</el-button>
            <el-popconfirm title="确认删除此任务？" @confirm="deleteTask(row.id)">
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 常用模板 -->
    <el-card shadow="never" class="templates-card" v-if="!loading">
      <template #header><span>常用模板</span></template>
      <div class="template-grid">
        <div v-for="tpl in templates" :key="tpl.id" class="template-item" @click="applyTemplate(tpl)">
          <div class="template-icon">
            <el-icon :size="20"><Clock /></el-icon>
          </div>
          <div class="template-name">{{ tpl.name }}</div>
          <div class="template-desc">{{ tpl.desc }}</div>
          <code>{{ tpl.cron }}</code>
        </div>
      </div>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="showAdd"
      :title="editingTask ? '编辑任务' : '新建任务'"
      width="520px"
      @close="resetForm"
    >
      <el-form :model="form" label-width="80px" size="small">
        <el-form-item label="命令">
          <el-input v-model="form.command" placeholder="要执行的命令" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.comment" placeholder="可选：描述此任务的作用" />
        </el-form-item>
        <el-divider>Cron 表达式</el-divider>
        <div class="cron-fields">
          <div class="cron-field" v-for="(name, idx) in fieldNames" :key="idx">
            <div class="cron-field-label">{{ name }}</div>
            <el-input v-model="form.fields[idx]" placeholder="*" />
          </div>
        </div>
        <div class="cron-preview">
          <span>表达式：</span>
          <code>{{ cronPreview }}</code>
        </div>
        <el-divider />
        <el-form-item label="快速选择">
          <el-select v-model="quickCron" placeholder="选择常用周期" @change="applyQuick">
            <el-option v-for="q in quickOptions" :key="q.value" :label="q.label" :value="q.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="showAdd = false">取消</el-button>
        <el-button size="small" type="primary" @click="saveTask" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from '@/stores'
import { ElMessage } from 'element-plus'
import { Plus, Clock } from '@element-plus/icons-vue'

const loading = ref(false)
const saving = ref(false)
const toggling = ref(false)
const tasks = ref([])
const fieldNames = ref([])
const cronStatus = reactive({ active: false, enabled: false })
const showAdd = ref(false)
const editingTask = ref(null)

const form = reactive({
  command: '',
  comment: '',
  fields: ['*', '*', '*', '*', '*'],
})

const quickCron = ref('')

const quickOptions = [
  { label: '每分钟', value: '* * * * *' },
  { label: '每5分钟', value: '*/5 * * * *' },
  { label: '每10分钟', value: '*/10 * * * *' },
  { label: '每15分钟', value: '*/15 * * * *' },
  { label: '每30分钟', value: '*/30 * * * *' },
  { label: '每小时', value: '0 * * * *' },
  { label: '每2小时', value: '0 */2 * * *' },
  { label: '每6小时', value: '0 */6 * * *' },
  { label: '每天零点', value: '0 0 * * *' },
  { label: '每天凌晨3点', value: '0 3 * * *' },
  { label: '每周日零点', value: '0 0 * * 0' },
  { label: '每月1日零点', value: '0 0 1 * *' },
  { label: '自定义', value: 'custom' },
]

const templates = [
  { id: 1, name: '系统更新', desc: '每周日凌晨更新系统', cron: '0 3 * * 0', cmd: 'apt update && apt upgrade -y' },
  { id: 2, name: '磁盘清理', desc: '每日清理 apt 缓存', cron: '0 5 * * *', cmd: 'apt autoclean && apt autoremove -y' },
  { id: 3, name: '重启服务', desc: '每早6点重启 dnsmasq', cron: '0 6 * * *', cmd: 'systemctl restart dnsmasq' },
  { id: 4, name: '日志轮转', desc: '每天中午压缩日志', cron: '0 12 * * *', cmd: 'logrotate /etc/logrotate.conf' },
  { id: 5, name: '健康检查', desc: '每5分钟 ping 网关', cron: '*/5 * * * *', cmd: 'ping -c1 192.168.21.1 >/dev/null 2>&1 || logger "网关不可达"' },
  { id: 6, name: 'DDNS更新', desc: '每30分钟强制更新DDNS', cron: '*/30 * * * *', cmd: '/usr/bin/ubunturouter-ddns-update' },
]

const cronPreview = computed(() => form.fields.join(' '))

onMounted(async () => {
  await fetchTasks()
  await fetchStatus()
})

async function fetchTasks() {
  loading.value = true
  try {
    const res = await api.get('/system/cron')
    tasks.value = res.data.tasks
    fieldNames.value = res.data.field_names
  } catch (e) {
    ElMessage.error('获取计划任务失败')
  }
  loading.value = false
}

async function fetchStatus() {
  try {
    const res = await api.get('/system/cron/status')
    cronStatus.active = res.data.active
    cronStatus.enabled = res.data.enabled
  } catch (e) { /* ignore */ }
}

async function toggleCron() {
  toggling.value = true
  try {
    await api.post('/system/cron/toggle', null, { params: { enable: !cronStatus.active } })
    cronStatus.active = !cronStatus.active
    ElMessage.success(`cron 服务已${cronStatus.active ? '启动' : '停止'}`)
  } catch (e) {
    ElMessage.error('操作失败')
  }
  toggling.value = false
}

function editTask(task) {
  editingTask.value = task
  form.command = task.command
  form.comment = task.comment || ''
  form.fields = [task.minute, task.hour, task.day, task.month, task.weekday]
  showAdd.value = true
}

function resetForm() {
  editingTask.value = null
  form.command = ''
  form.comment = ''
  form.fields = ['*', '*', '*', '*', '*']
  quickCron.value = ''
}

function applyQuick(val) {
  if (val === 'custom') return
  const parts = val.split(' ')
  form.fields = parts
}

function applyTemplate(tpl) {
  const parts = tpl.cron.split(' ')
  form.fields = parts
  form.command = tpl.cmd
  form.comment = tpl.name
  showAdd.value = true
  ElMessage.info(`已填入模板：${tpl.name}`)
}

async function saveTask() {
  if (!form.command.trim()) {
    ElMessage.warning('请输入命令')
    return
  }
  saving.value = true
  try {
    const payload = {
      command: form.command.trim(),
      comment: form.comment.trim() || '',
      minute: form.fields[0] || '*',
      hour: form.fields[1] || '*',
      day: form.fields[2] || '*',
      month: form.fields[3] || '*',
      weekday: form.fields[4] || '*',
    }
    if (editingTask.value) {
      await api.put(`/system/cron/${editingTask.value.id}`, payload)
      ElMessage.success('任务已更新')
    } else {
      await api.post('/system/cron', payload)
      ElMessage.success('任务已创建')
    }
    showAdd.value = false
    await fetchTasks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
  saving.value = false
}

async function deleteTask(id) {
  try {
    await api.delete(`/system/cron/${id}`)
    ElMessage.success('任务已删除')
    await fetchTasks()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.scheduled-tasks-page {
  padding: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
  font-size: 18px;
}
.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.tasks-card {
  margin-bottom: 16px;
}
.schedule-text {
  font-size: 13px;
  color: var(--el-text-color-primary);
}
.cron-expr code {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.command-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.command-text {
  font-size: 12px;
  word-break: break-all;
}
.templates-card {
  margin-bottom: 16px;
}
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.template-item {
  padding: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.template-item:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.template-icon {
  margin-bottom: 6px;
  color: var(--el-color-primary);
}
.template-name {
  font-weight: 500;
  font-size: 13px;
  margin-bottom: 2px;
}
.template-desc {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.template-item code {
  font-size: 10px;
  color: var(--el-color-primary);
}
.cron-fields {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.cron-field {
  flex: 1;
}
.cron-field-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  text-align: center;
}
.cron-preview {
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.cron-preview code {
  font-size: 14px;
  color: var(--el-color-primary);
  font-weight: 500;
}
</style>
