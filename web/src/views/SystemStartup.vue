<template>
  <div class="startup-page">
    <div class="page-header">
      <h2>启动项管理</h2>
      <div class="header-actions">
        <el-input
          v-model="search"
          size="small"
          placeholder="搜索服务..."
          clearable
          style="width: 200px"
          prefix-icon="Search"
        />
        <el-button size="small" @click="fetchItems" :loading="loading">刷新</el-button>
      </div>
    </div>

    <!-- 分类筛选标签 -->
    <el-tabs v-model="activeCategory" @tab-change="fetchItems">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane v-for="cat in categories" :key="cat" :label="cat" :name="cat" />
    </el-tabs>

    <!-- 启动项卡片列表 -->
    <div class="service-grid" v-loading="loading">
      <div
        v-for="item in filteredItems"
        :key="item.name"
        class="service-card"
        :class="{ disabled: !item.enabled }"
      >
        <div class="card-header">
          <div class="service-name-row">
            <el-icon :size="16" :color="item.active ? '#67C23A' : '#909399'">
              <Monitor />
            </el-icon>
            <span class="service-name">{{ item.name.replace('.service', '') }}</span>
          </div>
          <div class="status-tags">
            <el-tag :type="item.active ? 'success' : 'danger'" size="small">
              {{ item.active ? '运行中' : '已停止' }}
            </el-tag>
            <el-tag :type="item.enabled ? 'primary' : 'info'" size="small" effect="plain">
              {{ item.enabled ? '自启' : '手动' }}
            </el-tag>
          </div>
        </div>
        <div class="card-body">
          <div class="desc">{{ item.description }}</div>
          <div class="meta">
            <span class="category-tag">{{ item.category }}</span>
            <span class="state-text">{{ item.state }}</span>
          </div>
        </div>
        <div class="card-actions">
          <el-switch
            :model-value="item.enabled"
            @change="(val) => toggleEnabled(item, val)"
            active-text="自启"
            inactive-text="手动"
            size="small"
          />
          <el-button
            v-if="!item.active"
            size="small"
            text
            type="success"
            @click="controlService(item, 'start')"
          >启动</el-button>
          <el-button
            v-if="item.active"
            size="small"
            text
            type="warning"
            @click="controlService(item, 'stop')"
          >停止</el-button>
          <el-button
            size="small"
            text
            type="primary"
            @click="controlService(item, 'restart')"
          >重启</el-button>
        </div>
        <!-- 启动延时设置（仅应用/存储/远程类服务可设） -->
        <div v-if="item.can_delay" class="delay-section">
          <div class="delay-label">
            <el-icon :size="14"><Timer /></el-icon>
            <span>启动延时</span>
            <el-tooltip content="设置服务启动前等待的秒数，用于解决服务依赖问题" placement="top">
              <el-icon :size="14" style="cursor:help;color:var(--el-color-info)"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <div class="delay-control">
            <el-input-number
              v-model="item.delay"
              :min="0"
              :max="300"
              :step="5"
              size="small"
              controls-position="right"
              style="width: 120px"
              :disabled="savingDelay === item.name"
            />
            <span class="delay-unit">秒</span>
            <el-button
              size="small"
              type="primary"
              text
              :loading="savingDelay === item.name"
              @click="saveDelay(item)"
            >应用</el-button>
            <el-tag v-if="item.delay > 0" size="small" type="warning" effect="plain">
              延迟 {{ item.delay }}s 启动
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <el-empty v-if="!loading && filteredItems.length === 0" description="没有匹配的服务" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/stores'
import { ElMessage } from 'element-plus'
import { Monitor, Timer, QuestionFilled } from '@element-plus/icons-vue'

const loading = ref(false)
const savingDelay = ref('')
const items = ref([])
const categories = ref([])
const activeCategory = ref('all')
const search = ref('')

const filteredItems = computed(() => {
  let list = items.value
  if (activeCategory.value !== 'all') {
    list = list.filter(i => i.category === activeCategory.value)
  }
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(q) || i.description.toLowerCase().includes(q))
  }
  return list
})

onMounted(fetchItems)

async function fetchItems() {
  loading.value = true
  try {
    const res = await api.get('/system/startup')
    items.value = res.data.items
    categories.value = res.data.categories
  } catch (e) {
    ElMessage.error('获取启动项失败')
  }
  loading.value = false
}

async function toggleEnabled(item, enabled) {
  try {
    await api.put(`/system/startup/${encodeURIComponent(item.name)}`, null, {
      params: { enabled }
    })
    item.enabled = enabled
    ElMessage.success(`${item.name} 已${enabled ? '启用' : '禁用'}开机自启`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function controlService(item, action) {
  try {
    await api.post('/system/service/control', { name: item.name, action })
    ElMessage.success(`${action} ${item.name} 成功`)
    await fetchItems()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || `${action} 失败`)
  }
}

async function saveDelay(item) {
  savingDelay.value = item.name
  try {
    const res = await api.put(`/system/startup/delay/${encodeURIComponent(item.name)}`, {
      delay: item.delay || 0
    })
    item.delay = res.data.delay
    ElMessage.success(res.data.message)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '设置延时失败')
  }
  savingDelay.value = ''
}
</script>

<style scoped>
.startup-page {
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
.service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.service-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 14px;
  transition: all 0.2s;
  background: var(--el-bg-color);
}
.service-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.service-card.disabled {
  opacity: 0.7;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.service-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.service-name {
  font-weight: 500;
  font-size: 14px;
}
.status-tags {
  display: flex;
  gap: 4px;
}
.card-body {
  margin-bottom: 10px;
}
.desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.meta {
  display: flex;
  gap: 8px;
  align-items: center;
}
.category-tag {
  font-size: 11px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  padding: 1px 8px;
  border-radius: 4px;
}
.state-text {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.card-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  border-top: 1px solid var(--el-border-color-light);
  padding-top: 10px;
}

/* 延时设置 */
.delay-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-light);
}
.delay-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.delay-control {
  display: flex;
  align-items: center;
  gap: 4px;
}
.delay-unit {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
