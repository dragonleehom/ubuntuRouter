<template>
  <transition name="slide-up">
    <div v-if="store.hasPending" class="pending-bar">
      <div class="pending-bar-inner">
        <div class="pending-info">
          <el-icon color="#E6A23C" size="18"><WarningFilled /></el-icon>
          <span class="pending-text">
            有 <strong>{{ store.pendingSectionCount }}</strong> 个配置节变更待应用
          </span>
          <el-tag size="small" type="warning" effect="plain">
            {{ store.diffResult?.summary || '未计算差异' }}
          </el-tag>
        </div>
        <div class="pending-actions">
          <el-button size="small" @click="showDiff = !showDiff">
            {{ showDiff ? '隐藏差异' : '查看差异' }}
          </el-button>
          <el-button size="small" @click="store.discardPending()">
            丢弃
          </el-button>
          <el-button type="primary" size="small" @click="handleApply" :loading="applying">
            应用配置
          </el-button>
        </div>
      </div>

      <!-- 差异面板 -->
      <div v-if="showDiff" class="diff-panel">
        <div v-if="store.pendingChanges.length === 0" class="diff-empty">
          暂无差异信息
        </div>
        <div v-else v-for="item in store.pendingChanges" :key="item.section" class="diff-section">
          <div class="diff-section-header">
            <el-tag size="small" effect="dark">{{ item.section }}</el-tag>
            <span class="diff-section-change">已变更</span>
          </div>
          <div class="diff-compare">
            <div class="diff-old">
              <div class="diff-label">当前</div>
              <pre class="diff-code">{{ formatValue(item.old) }}</pre>
            </div>
            <div class="diff-arrow">
              <el-icon :size="24" color="#409EFF"><ArrowRight /></el-icon>
            </div>
            <div class="diff-new">
              <div class="diff-label">新的</div>
              <pre class="diff-code">{{ formatValue(item.new) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </transition>

  <!-- Apply 结果对话框 -->
  <el-dialog v-model="resultVisible" title="应用结果" width="500px">
    <div v-if="applyResult">
      <el-alert
        :type="applyResult.success ? 'success' : 'error'"
        :title="applyResult.success ? '配置已应用' : '配置应用失败'"
        :description="applyResult.message"
        show-icon
        :closable="false"
      />
      <div class="result-meta" v-if="applyResult.snapshot_id">
        <p><strong>快照 ID：</strong><code>{{ applyResult.snapshot_id }}</code></p>
        <p><strong>耗时：</strong>{{ applyResult.execution_time_ms }}ms</p>
      </div>
    </div>
    <div v-else>
      <el-alert type="error" title="操作失败" description="无法获取应用结果" show-icon />
    </div>
    <template #footer>
      <el-button type="primary" @click="resultVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { WarningFilled, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useConfigStore } from '@/stores'

const store = useConfigStore()
const showDiff = ref(false)
const applying = ref(false)
const resultVisible = ref(false)
const applyResult = ref(null)

function formatValue(val) {
  if (val === null || val === undefined) return '(无)'
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  return String(val)
}

async function handleApply() {
  applying.value = true
  try {
    const result = await store.applyPending()
    applyResult.value = result
    resultVisible.value = true
    showDiff.value = false
    if (result?.success) {
      ElMessage.success('配置已应用')
    } else {
      ElMessage.error(result?.message || '应用失败')
    }
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    applyResult.value = { success: false, message: detail }
    resultVisible.value = true
    ElMessage.error('应用失败')
  } finally {
    applying.value = false
  }
}
</script>

<style scoped>
.pending-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2000;
  background: #fff;
  border-top: 2px solid #E6A23C;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.15);
}

.pending-bar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.pending-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pending-text {
  font-size: 14px;
  color: #333;
}

.pending-actions {
  display: flex;
  gap: 8px;
}

.diff-panel {
  max-height: 50vh;
  overflow-y: auto;
  padding: 0 24px 16px;
  border-top: 1px solid #eee;
}

.diff-empty {
  text-align: center;
  color: #999;
  padding: 20px;
}

.diff-section {
  margin-bottom: 16px;
  border: 1px solid #eee;
  border-radius: 6px;
  overflow: hidden;
}

.diff-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
}

.diff-section-change {
  font-size: 12px;
  color: #E6A23C;
}

.diff-compare {
  display: flex;
  gap: 0;
}

.diff-old, .diff-new {
  flex: 1;
  padding: 8px 12px;
}

.diff-old {
  background: #fef0f0;
}

.diff-new {
  background: #f0f9eb;
}

.diff-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  background: #fff;
}

.diff-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 4px;
  color: #666;
}

.diff-code {
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  line-height: 1.5;
}

.result-meta {
  margin-top: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
}

.result-meta p {
  margin: 4px 0;
  font-size: 13px;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}
</style>
