<template>
  <div class="config-editor">
    <div class="page-header">
      <h2>配置编辑器</h2>
      <div class="header-actions">
        <el-button size="small" @click="loadConfig" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新当前配置
        </el-button>
        <el-button size="small" type="warning" @click="saveChanges" :loading="saving"
                   :disabled="!hasChanges">
          <el-icon><FolderChecked /></el-icon> 保存修改
        </el-button>
      </div>
    </div>

    <el-alert
      title="Save & Apply 模式"
      type="info"
      :closable="false"
      show-icon
      class="mode-hint"
    >
      <template #default>
        修改下方 YAML 配置后，点击 <strong>"保存修改"</strong> 暂存变更。
        底部会出现 <strong>"应用配置"</strong> 按钮，可查看差异对比后统一生效。
        支持多次修改与保存，最后一次性 Apply。
      </template>
    </el-alert>

    <el-card class="editor-card">
      <template #header>
        <div class="card-header">
          <span>YAML 配置</span>
          <div class="card-header-right">
            <el-tag size="small" :type="hasChanges ? 'warning' : 'info'" effect="plain">
              {{ hasChanges ? '有未保存的修改' : '已同步' }}
            </el-tag>
            <el-tag v-if="configStore.hasPending" size="small" type="warning" effect="dark" style="margin-left: 8px">
              待应用: {{ configStore.pendingSectionCount }} 个配置节
            </el-tag>
          </div>
        </div>
      </template>

      <div class="editor-container">
        <el-input
          v-model="yamlContent"
          type="textarea"
          :rows="28"
          class="yaml-input"
          @input="onInput"
          placeholder="正在加载配置..."
          :disabled="loading"
        />
      </div>
    </el-card>

    <!-- 快速修改面板 -->
    <el-card class="quick-card">
      <template #header>
        <span>常用配置快速修改</span>
      </template>

      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="DNSSEC" v-if="configStore.currentConfig">
          <el-switch
            :model-value="getField('dns.enable_dnssec')"
            @change="setField('dns.enable_dnssec', $event)"
            size="small"
          />
        </el-descriptions-item>
        <el-descriptions-item label="缓存大小" v-if="configStore.currentConfig">
          <el-input-number
            :model-value="getField('dns.cache_size')"
            @change="setField('dns.cache_size', $event)"
            :min="0" :max="100000" size="small"
            style="width: 140px"
          />
        </el-descriptions-item>
        <el-descriptions-item label="上游 DNS">
          <span style="font-size: 12px; color: #999;">
            {{ getField('dns.upstream')?.join(', ') || '-' }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="主机名">
          <el-input
            :model-value="getField('system.hostname')"
            @change="setField('system.hostname', $event)"
            size="small" style="width: 160px"
          />
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, FolderChecked } from '@element-plus/icons-vue'
import { useConfigStore } from '@/stores'

const configStore = useConfigStore()

const loading = ref(false)
const saving = ref(false)
const yamlContent = ref('')
const originalYaml = ref('')

const hasChanges = computed(() => {
  return yamlContent.value !== originalYaml.value
})

/** 从 YAML 中按 keypath 获取值 */
function getField(keypath) {
  try {
    const lines = yamlContent.value.split('\n')
    const keys = keypath.split('.')
    // Simple YAML value extraction for known fields
    let prefix = ''
    for (let i = 0; i < keys.length - 1; i++) {
      prefix += '  '.repeat(i) + keys[i] + ':'
    }
    const lastKey = keys[keys.length - 1]
    for (const line of lines) {
      if (line.trimStart().startsWith(lastKey + ':')) {
        const val = line.split(':')[1]?.trim()
        if (val === 'true') return true
        if (val === 'false') return false
        if (/^\d+$/.test(val)) return parseInt(val)
        if (val?.startsWith('[')) {
          try { return JSON.parse(val.replace(/'/g, '"')) } catch {}
        }
        return val?.replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1') || ''
      }
    }
  } catch {}
  return null
}

/** 通过正则替换 YAML 中的值 */
function setField(keypath, value) {
  const keys = keypath.split('.')
  const lastKey = keys[keys.length - 1]
  const lines = yamlContent.value.split('\n')

  // Convert value to YAML literal
  let yamlVal = String(value)
  if (typeof value === 'boolean') yamlVal = value ? 'true' : 'false'
  else if (typeof value === 'number') yamlVal = String(value)
  else if (value && (value.includes(' ') || value.includes('#'))) yamlVal = `"${value}"`

  let found = false
  const newLines = lines.map(line => {
    const trimmed = line.trimStart()
    if (!found && trimmed.startsWith(lastKey + ':')) {
      found = true
      const indent = line.match(/^\s*/)[0]
      return `${indent}${lastKey}: ${yamlVal}`
    }
    return line
  })

  if (found) {
    yamlContent.value = newLines.join('\n')
  }
}

function onInput() {
  // Just flag that content changed — no YAML parsing needed
}

async function loadConfig() {
  loading.value = true
  try {
    const data = await configStore.loadCurrent()
    if (data?.config_yaml) {
      yamlContent.value = data.config_yaml
      originalYaml.value = data.config_yaml
      ElMessage.success('配置已加载')
    }
  } catch (e) {
    if (e.response?.status === 404) {
      ElMessage.warning('系统未初始化，请先初始化')
    } else {
      ElMessage.error('加载失败: ' + (e.response?.data?.detail || e.message))
    }
  }
  loading.value = false
}

async function saveChanges() {
  if (!hasChanges.value) {
    ElMessage.info('没有变更需要保存')
    return
  }

  saving.value = true
  try {
    const result = await configStore.stageConfig(yamlContent.value)
    if (result?.has_changes) {
      originalYaml.value = yamlContent.value
      ElMessage.success(`已暂存修改（${result.changed_sections.length} 个配置节变更），请在底部检查差异并点击"应用配置"`)
    } else {
      ElMessage.info('配置没有变化')
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
  saving.value = false
}

onMounted(loadConfig)
</script>

<style scoped>
.config-editor {
  padding: 0 0 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.mode-hint {
  margin-bottom: 20px;
}

.editor-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editor-container {
  position: relative;
}

.yaml-input :deep(.el-textarea__inner) {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #1a1a1a;
  color: #e0e0e0;
  border-color: #333;
}

.quick-card {
  margin-bottom: 20px;
}
</style>
