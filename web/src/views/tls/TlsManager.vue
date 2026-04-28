<template>
  <div class="tls-manager">
    <h2>HTTPS 证书管理</h2>

    <!-- 证书状态卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>证书状态</span>
              <el-button size="small" @click="fetchStatus" :loading="loading">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>

          <el-descriptions :column="2" border size="small" v-if="certInfo.exists">
            <el-descriptions-item label="证书路径" :span="2">
              <code>{{ certInfo.cert_path }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="密钥路径" :span="2">
              <code>{{ certInfo.key_path }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="主题 (Subject)">
              <code style="font-size: 12px">{{ certInfo.subject || '-' }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="签发者 (Issuer)">
              <code style="font-size: 12px">{{ certInfo.issuer || '-' }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="生效时间">
              {{ certInfo.not_before || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="到期时间">
              <span :style="{ color: certExpiryColor }">{{ certInfo.not_after || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="剩余天数">
              <el-tag :type="certTagType" size="small" effect="dark">
                {{ certInfo.days_remaining !== null ? certInfo.days_remaining + ' 天' : '未知' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="HTTPS 状态">
              <el-tag :type="certInfo.https_enabled ? 'success' : 'info'" size="small" effect="dark">
                {{ certInfo.https_enabled ? '已启用' : '未启用' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <el-empty v-else description="证书不存在" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作按钮区 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>操作</span>
          </template>
          <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
            <el-button type="primary" @click="renewCert" :loading="renewing" :disabled="!certInfo.exists">
              <el-icon><Refresh /></el-icon> 重新生成自签证书
            </el-button>
            <el-button @click="showUploadDialog = true">
              <el-icon><Upload /></el-icon> 上传自定义证书
            </el-button>
            <el-button v-if="certInfo.exists" @click="showCertDetail = true">
              <el-icon><View /></el-icon> 查看证书详情
            </el-button>
            <el-button @click="toggleHttps" :loading="toggling" type="warning">
              <el-icon><Switch /></el-icon> HTTPS 状态 / 重启提示
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- HTTPS 状态提示 -->
    <el-row :gutter="16" v-if="toggleResult" style="margin-bottom: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>HTTPS 状态信息</span>
          </template>
          <el-alert
            :title="toggleResult.message"
            :type="toggleResult.https_enabled ? 'success' : 'warning'"
            :closable="false"
            show-icon
            style="margin-bottom: 12px"
          />
          <div style="color: #888; font-size: 13px;">
            <p>重启命令: <code>{{ toggleResult.restart_command }}</code></p>
            <p>服务名称: <code>{{ toggleResult.service }}</code></p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 上传证书对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传自定义证书" width="500px">
      <el-form label-width="100px">
        <el-form-item label="证书文件">
          <el-upload
            ref="certUploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".pem,.crt,.cert,.cer"
            @change="onCertFileChange"
          >
            <template #trigger>
              <el-button type="primary">选择文件</el-button>
            </template>
            <template #tip>
              <div style="color: #888; font-size: 12px; margin-top: 4px;">
                PEM 格式证书文件 (*.pem, *.crt, *.cer)
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="密钥文件">
          <el-upload
            ref="keyUploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".pem,.key"
            @change="onKeyFileChange"
          >
            <template #trigger>
              <el-button type="primary">选择文件</el-button>
            </template>
            <template #tip>
              <div style="color: #888; font-size: 12px; margin-top: 4px;">
                PEM 格式私钥文件 (*.pem, *.key)
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="uploadCert" :loading="uploading" :disabled="!selectedCert || !selectedKey">
          上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 证书详情对话框 -->
    <el-dialog v-model="showCertDetail" title="证书详情" width="700px">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="证书路径" :span="2">
          <code>{{ certInfo.cert_path }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="主题 (Subject)" :span="2">
          <code style="font-size: 12px;">{{ certInfo.subject || '-' }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="签发者 (Issuer)" :span="2">
          <code style="font-size: 12px;">{{ certInfo.issuer || '-' }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="生效时间">
          {{ certInfo.not_before || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="到期时间">
          <span :style="{ color: certExpiryColor }">{{ certInfo.not_after || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="剩余天数">
          <el-tag :type="certTagType" size="small" effect="dark">
            {{ certInfo.days_remaining !== null ? certInfo.days_remaining + ' 天' : '未知' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="HTTPS">
          <el-tag :type="certInfo.https_enabled ? 'success' : 'info'" size="small" effect="dark">
            {{ certInfo.https_enabled ? '已启用' : '未启用' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="showCertDetail = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/stores'
import { Refresh, Upload, View, Switch } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const renewing = ref(false)
const uploading = ref(false)
const toggling = ref(false)
const showUploadDialog = ref(false)
const showCertDetail = ref(false)
const certInfo = ref({
  exists: false,
  cert_path: '',
  key_path: '',
  subject: null,
  not_before: null,
  not_after: null,
  days_remaining: null,
  issuer: null,
  https_enabled: false,
})
const toggleResult = ref(null)
const selectedCert = ref(null)
const selectedKey = ref(null)

const certTagType = computed(() => {
  if (certInfo.value.days_remaining === null) return 'info'
  if (certInfo.value.days_remaining > 90) return 'success'
  if (certInfo.value.days_remaining > 30) return 'warning'
  return 'danger'
})

const certExpiryColor = computed(() => {
  if (certInfo.value.days_remaining === null) return '#888'
  if (certInfo.value.days_remaining > 90) return '#67c23a'
  if (certInfo.value.days_remaining > 30) return '#e6a23c'
  return '#f56c6c'
})

function onCertFileChange(file) {
  selectedCert.value = file.raw
}

function onKeyFileChange(file) {
  selectedKey.value = file.raw
}

async function fetchStatus() {
  loading.value = true
  try {
    const res = await api.get('/tls/status')
    certInfo.value = res.data
  } catch (e) {
    ElMessage.error('获取证书状态失败')
  }
  loading.value = false
}

async function renewCert() {
  try {
    await ElMessageBox.confirm(
      '确认重新生成自签证书？现有的 HTTPS 连接将暂时中断。',
      '确认重新生成',
      { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' },
    )
    renewing.value = true
    const res = await api.post('/tls/renew')
    ElMessage.success(res.data.message || '证书重新生成成功')
    await fetchStatus()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '证书重新生成失败')
    }
  }
  renewing.value = false
}

async function uploadCert() {
  if (!selectedCert.value || !selectedKey.value) {
    ElMessage.warning('请选择证书和密钥文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('cert', selectedCert.value)
    formData.append('key', selectedKey.value)

    const res = await api.post('/tls/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(res.data.message || '证书上传成功')
    showUploadDialog.value = false
    selectedCert.value = null
    selectedKey.value = null
    await fetchStatus()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '证书上传失败')
  }
  uploading.value = false
}

async function toggleHttps() {
  toggling.value = true
  try {
    const res = await api.post('/tls/toggle')
    toggleResult.value = res.data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '查询 HTTPS 状态失败')
  }
  toggling.value = false
}

onMounted(fetchStatus)
</script>

<style scoped>
.tls-manager { padding: 0; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
code {
  background: #1a1a1a;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
  color: #e6e6e6;
}
</style>
