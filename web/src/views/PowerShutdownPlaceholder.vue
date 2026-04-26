<template>
  <div class="page">
    <div class="page-header">
      <h2>关机</h2>
      <p class="page-desc">关闭路由器电源，系统将彻底停止运行</p>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="never" class="action-card">
          <template #header><span>立即关机</span></template>
          <div style="text-align: center; padding: 24px 0">
            <el-icon :size="64" color="#f56c6c"><SwitchButton /></el-icon>
            <p style="margin: 16px 0 24px; color: #888">
              点击下方按钮立即关机。此操作不可撤销，需要通过物理电源键重新开机。
            </p>
            <el-button type="danger" size="large" @click="shutdownImmediate" :loading="loading">
              <el-icon><SwitchButton /></el-icon> 立即关机
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="action-card">
          <template #header><span>定时关机</span></template>
          <div style="padding: 16px 0">
            <el-form label-width="100px">
              <el-form-item label="延迟时间">
                <el-select v-model="delayMinutes" style="width: 100%">
                  <el-option :value="5" label="5 分钟后" />
                  <el-option :value="15" label="15 分钟后" />
                  <el-option :value="30" label="30 分钟后" />
                  <el-option :value="60" label="1 小时后" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="danger" @click="shutdownDelayed" :loading="loading">
                  <el-icon><Clock /></el-icon> 定时关机
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
        <el-icon :size="20" color="#f56c6c"><Timer /></el-icon>
        <span>系统将在 {{ scheduled }} 后关机</span>
      </div>
    </el-card>

    <!-- 确认对话框 -->
    <el-dialog v-model="confirmVisible" title="确认关机" width="420px">
      <div style="text-align: center; padding: 12px">
        <el-icon :size="48" color="#f56c6c"><WarningFilled /></el-icon>
        <p style="margin: 16px 0 0; color: #ccc">
          {{ confirmMessage }}
        </p>
      </div>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="danger" @click="doShutdown">确认关机</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '@/stores'
import { SwitchButton, Clock, Timer, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const confirmVisible = ref(false)
const confirmMessage = ref('')
const delayMinutes = ref(15)
const scheduled = ref('')
let pendingAction = null

function shutdownImmediate() {
  confirmMessage.value = '系统将立即关机，所有服务停止。需要通过物理电源键重新开机。'
  pendingAction = 'immediate'
  confirmVisible.value = true
}

function shutdownDelayed() {
  confirmMessage.value = `系统将在 ${delayMinutes.value} 分钟后关机。`
  pendingAction = 'delayed'
  confirmVisible.value = true
}

async function doShutdown() {
  confirmVisible.value = false
  loading.value = true
  try {
    const delay = pendingAction === 'immediate' ? 0 : delayMinutes.value * 60
    const res = await api.post('/system/shutdown', { delay })
    ElMessage.success(res.data.message || '关机指令已发送')
    if (delay === 0) {
      scheduled.value = '立即'
    } else {
      scheduled.value = `${delayMinutes.value} 分钟`
    }
  } catch (e) {
    ElMessage.error('关机失败: ' + (e.response?.data?.detail || e.message))
  }
  loading.value = false
}

async function cancelShutdown() {
  try {
    await api.post('/system/cancel-shutdown')
    ElMessage.success('已取消计划的关机')
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
