<template>
  <div class="page">
    <div class="page-header">
      <h2>SSH 密钥管理</h2>
    </div>

    <el-row :gutter="20">
      <!-- 密码修改 -->
      <el-col :span="12">
        <el-card class="card">
          <template #header><span>修改密码</span></template>
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-position="top"
            @keyup.enter="changePassword"
          >
            <el-form-item label="当前密码" prop="current_password">
              <el-input
                v-model="passwordForm.current_password"
                type="password"
                show-password
                placeholder="输入当前密码"
              />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="passwordForm.new_password"
                type="password"
                show-password
                placeholder="输入新密码"
              />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input
                v-model="passwordForm.confirm_password"
                type="password"
                show-password
                placeholder="再次输入新密码"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwLoading" @click="changePassword">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- SSH 公钥列表 -->
      <el-col :span="12">
        <el-card class="card">
          <template #header>
            <div class="card-header">
              <span>SSH 公钥 ({{ username }})</span>
              <el-button size="small" type="primary" @click="showAddDialog = true">
                + 添加公钥
              </el-button>
            </div>
          </template>

          <div class="key-list" v-if="keys.length > 0">
            <div v-for="k in keys" :key="k.id" class="key-item">
              <div class="key-info">
                <div class="key-meta">
                  <el-tag size="small" type="info">{{ k.type }}</el-tag>
                  <span class="key-comment">{{ k.comment || '（无注释）' }}</span>
                </div>
                <div class="key-fingerprint">{{ k.fingerprint }}</div>
              </div>
              <el-popconfirm
                title="确定删除此公钥？"
                @confirm="deleteKey(k.id)"
              >
                <template #reference>
                  <el-button size="small" type="danger" :icon="'Delete'" circle />
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-else description="暂无 SSH 公钥" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加公钥对话框 -->
    <el-dialog v-model="showAddDialog" title="添加 SSH 公钥" width="600px">
      <el-input
        v-model="newKey"
        type="textarea"
        :rows="6"
        placeholder="粘贴 SSH 公钥内容&#10;例如: ssh-rsa AAAAB3NzaC1yc2E... user@host"
      />
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="addKey">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '@/stores'
import { ElMessage } from 'element-plus'

const passwordFormRef = ref(null)
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})
const pwLoading = ref(false)

const passwordRules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少 6 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const keys = ref([])
const username = ref('')
const showAddDialog = ref(false)
const newKey = ref('')
const addLoading = ref(false)

onMounted(async () => {
  await fetchKeys()
})

async function fetchKeys() {
  try {
    const res = await api.get('/system/ssh-keys')
    keys.value = res.data.keys
    username.value = res.data.username
  } catch (e) {
    console.error('获取 SSH 密钥失败:', e)
  }
}

async function changePassword() {
  if (!passwordFormRef.value) return
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return

  pwLoading.value = true
  try {
    const res = await api.post('/system/password', {
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    ElMessage.success(res.data.message)
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '密码修改失败')
  }
  pwLoading.value = false
}

async function addKey() {
  if (!newKey.value.trim()) {
    ElMessage.warning('请输入公钥内容')
    return
  }
  addLoading.value = true
  try {
    const res = await api.post('/system/ssh-keys', { key: newKey.value.trim() })
    ElMessage.success(res.data.message)
    showAddDialog.value = false
    newKey.value = ''
    await fetchKeys()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加公钥失败')
  }
  addLoading.value = false
}

async function deleteKey(id) {
  try {
    const res = await api.delete('/system/ssh-keys', { data: { id } })
    ElMessage.success(res.data.message)
    await fetchKeys()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除公钥失败')
  }
}
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; color: #e0e0e0; }
.card { margin-bottom: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.key-list { display: flex; flex-direction: column; gap: 8px; }
.key-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
}
.key-info { flex: 1; min-width: 0; }
.key-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.key-comment { color: #aaa; font-size: 13px; }
.key-fingerprint { color: #888; font-size: 12px; font-family: monospace; word-break: break-all; }
</style>
