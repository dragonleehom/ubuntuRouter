<template>
  <div class="page">
    <div class="page-header">
      <h2>重启系统</h2>
      <p class="page-desc">重新启动路由器，所有服务将短暂中断</p>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="never" class="action-card">
          <template #header><span>立即重启</span></template>
          <div style="text-align: center; padding: 24px 0">
            <el-icon :size="64" color="#E6A23C"><Refresh /></el-icon>
            <p style="margin: 16px 0 24px; color: #888">
              点击下方按钮立即重启系统。重启过程约需 1-2 分钟，之后页面将自动重连。
            </p>
            <el-button type="warning" size="large" @click="rebootImmediate" :loading="loading">
              <el-icon><Refresh /></el-icon> 立即重启
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="action-card">
          <template #header><span>定时重启</span></template>
          <div style="padding: 16px 0">
            <el-form label-width="100px">
              <el-form-item label="延迟时间">
                <el-select v-model="delayMinutes" style="width: 100%">
                  <el-option :value="1" label="1 分钟后" />
                  <el-option :value="5" label="5 分钟后" />
                  <el-option :value="15" label="15 分钟后" />
                  <el-option :value="30" label="30 分钟后" />
                  <el-option :value="60" label="1 小时后" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="warning" @click="rebootDelayed" :loading="loading">
                  <el-icon><Clock /></el-icon> 定时重启
                </el-button>
                <el-button v-if="scheduled" text type="info" @click="cancelShutdown">
                  取消已计划的定时任务
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="scheduled" shadow="never" style="margin-top: 20px">
      <template #header><span>已计划的操作</span></template>
      <div class="scheduled-info">
        <el-icon :size="20" color="#E6A23C"><Timer /></el-icon>
        <span>系统将在 {{ scheduled }} 后重启</span>
      </div>
    </el-card>

    <!-- 确认对话框 -->
    <el-dialog v-model="confirmVisible" title="确认重启" width="420px">
      <div style="text-align: center; padding: 12px">
        <el-icon :size="48" color="#E6A23C"><WarningFilled /></el-icon>
        <p style="margin: 16px 0 0; color: #ccc">
          {{ confirmMessage }}
        </p>
      </div>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="warning" @click="doReboot">确认重启</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '@/stores'
import { Refresh, Clock, Timer, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const confirmVisible = ref(false)
const confirmMessage = ref('')
const delayMinutes = ref(5)
const scheduled = ref('')
let pendingAction = null

function rebootImmediate() {
  confirmMessage.value = '系统将立即重启，所有连接会断开。页面将在重启完成后自动重连。'
  pendingAction = 'immediate'
  confirmVisible.value = true
}

function rebootDelayed() {
  confirmMessage.value = `系统将在 ${delayMinutes.value} 分钟后重启。`
  pendingAction = 'delayed'
  confirmVisible.value = true
}

async function doReboot() {
  confirmVisible.value = false
  loading.value = true
  try {
    const delay = pendingAction === 'immediate' ? 0 : delayMinutes.value * 60
    const res = await api.post('/system/reboot', { delay })
    ElMessage.success(res.data.message || '重启指令已发送')
    if (delay === 0) {
      scheduled.value = '立即'
      // 几秒后尝试重连
      setTimeout(() => {
        ElMessage.info('系统正在重启，页面将自动刷新...')
        setTimeout(() => { window.location.reload() }, 5000)
      }, 2000)
    } else {
      scheduled.value = `${delayMinutes.value} 分钟`
    }
  } catch (e) {
    ElMessage.error('重启失败: ' + (e.response?.data?.detail || e.message))
  }
  loading.value = false
}

async function cancelShutdown() {
  try {
    await api.post('/system/cancel-shutdown')
    ElMessage.success('已取消计划的重启')
    scheduled.value = ''
  } catch (e) {
    ElMessage.error('取消失败: ' + (e.response?.data?.detail || e.message))
  }
}
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 0 0 4px 0; color: #e0e0e0; }
.page-desc { margin: 0; font-size: 13px; color: #888; }
.action-card { margin-bottom: 20px; }
.scheduled-info { display: flex; align-items: center; gap: 12px; color: #ccc; }
</style>
