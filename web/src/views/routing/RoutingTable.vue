<template>
  <div class="page">
    <div class="page-header">
      <h2>路由</h2>
      <div class="header-actions">
        <el-button size="small" @click="refreshData">
          <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 默认路由 -->
    <el-card shadow="never" class="section-card" style="margin-bottom:16px;">
      <template #header>
        <span style="color:#ccc;">默认路由</span>
      </template>
      <div v-if="defaultRoute.exists" class="default-route">
        <div class="route-row">
          <span class="label">网关</span>
          <span class="value">{{ defaultRoute.gateway }}</span>
        </div>
        <div class="route-row">
          <span class="label">接口</span>
          <span class="value">{{ defaultRoute.iface }}</span>
        </div>
        <div class="route-row">
          <span class="label">Metric</span>
          <span class="value">{{ defaultRoute.metric }}</span>
        </div>
      </div>
      <el-empty v-else description="无默认路由" />
    </el-card>

    <el-row :gutter="16">
      <!-- 路由表 -->
      <el-col :span="16">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="color:#ccc;">路由表 (main)</span>
              <el-button size="small" type="primary" @click="showAddRoute = true">
                <el-icon style="margin-right:4px"><Plus /></el-icon>添加静态路由
              </el-button>
            </div>
          </template>
          <el-table :data="routes" stripe size="small" v-loading="loading" max-height="400">
            <el-table-column prop="destination" label="目标网络" width="160" />
            <el-table-column prop="gateway" label="网关" width="140" />
            <el-table-column prop="iface" label="接口" width="100" />
            <el-table-column prop="metric" label="Metric" width="80" align="right" class="hide-mobile" />
            <el-table-column prop="proto" label="协议" width="80" class="hide-mobile" />
            <el-table-column label="默认" width="60" class="hide-mobile">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="success" size="small">主</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button v-if="!row.is_default" text type="danger" size="small" @click="deleteRoute(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- Multi-WAN -->
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header>
            <span style="color:#ccc;">Multi-WAN 状态</span>
          </template>
          <div v-for="wan in multiwan" :key="wan.name" class="wan-card">
            <div class="wan-header">
              <span class="wan-name">{{ wan.name }}</span>
              <el-tag :type="wan.online ? 'success' : 'danger'" size="small">
                {{ wan.online ? '在线' : '离线' }}
              </el-tag>
              <el-tag v-if="wan.is_active" type="warning" size="small" effect="dark">活跃</el-tag>
            </div>
            <div class="wan-detail">
              <div class="detail-row">
                <span class="label">网关</span>
                <span class="value">{{ wan.gateway }}</span>
              </div>
              <div class="detail-row">
                <span class="label">延迟</span>
                <span class="value" :style="{color: wan.latency_ms < 50 ? '#67C23A' : wan.latency_ms < 200 ? '#E6A23C' : '#F56C6C'}">
                  {{ wan.latency_ms }}ms
                </span>
              </div>
              <div class="detail-row">
                <span class="label">丢包率</span>
                <span class="value" :style="{color: wan.packet_loss < 5 ? '#67C23A' : '#F56C6C'}">
                  {{ wan.packet_loss }}%
                </span>
              </div>
              <el-button
                v-if="!wan.is_active && wan.online"
                size="small"
                type="primary"
                @click="switchToWan(wan)"
                style="margin-top:8px;width:100%;"
              >
                切换到此线路
              </el-button>
            </div>
          </div>
          <el-empty v-if="multiwan.length === 0" description="只有一条 WAN 线路" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加静态路由对话框 -->
    <el-dialog v-model="showAddRoute" title="添加静态路由" width="450px">
      <el-form :model="newRoute" label-width="100px" size="small">
        <el-form-item label="目标网络">
          <el-input v-model="newRoute.destination" placeholder="如 10.0.0.0/24" />
        </el-form-item>
        <el-form-item label="网关">
          <el-input v-model="newRoute.gateway" placeholder="如 192.168.1.1" />
        </el-form-item>
        <el-form-item label="接口">
          <el-input v-model="newRoute.iface" placeholder="可选，如 eth0" />
        </el-form-item>
        <el-form-item label="Metric">
          <el-input-number v-model="newRoute.metric" :min="0" :max="999" :step="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddRoute = false">取消</el-button>
        <el-button type="primary" @click="addRoute">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { api } from '@/stores'

const loading = ref(false)
const showAddRoute = ref(false)
const routes = ref([])
const defaultRoute = reactive({ exists: false })
const multiwan = ref([])

const newRoute = reactive({
  destination: '',
  gateway: '',
  iface: '',
  metric: 0,
})

async function refreshData() {
  loading.value = true
  try {
    const [routesRes, defaultRes, multiwanRes] = await Promise.all([
      api.get('/routing/table?table=main'),
      api.get('/routing/default'),
      api.get('/routing/multiwan'),
    ])
    routes.value = routesRes.data.routes || []
    Object.assign(defaultRoute, defaultRes.data)
    multiwan.value = multiwanRes.data.wans || []
  } catch (e) {
    ElMessage.error('获取路由数据失败')
  }
  loading.value = false
}

async function addRoute() {
  try {
    await api.post('/routing/static', newRoute)
    ElMessage.success('静态路由已添加')
    showAddRoute.value = false
    await refreshData()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteRoute(row) {
  try {
    await ElMessageBox.confirm(`确定删除到 ${row.destination} 的路由？`, '确认')
    await api.delete('/routing/static', {
      data: { destination: row.destination, gateway: row.gateway, iface: row.iface },
    })
    ElMessage.success('路由已删除')
    await refreshData()
  } catch { /* cancelled */ }
}

async function switchToWan(wan) {
  try {
    await api.post('/routing/multiwan/switch', { iface: wan.iface, gateway: wan.gateway })
    ElMessage.success(`已切换到 ${wan.name}`)
    await refreshData()
  } catch (e) {
    ElMessage.error('切换失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(refreshData)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { color: #e0e0e0; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.section-card {
  background: #141414;
  border: 1px solid #222;
}
.default-route {
  display: flex;
  gap: 24px;
}
.route-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.route-row .label { font-size: 12px; color: #888; }
.route-row .value { font-size: 16px; color: #e0e0e0; }
.wan-card {
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.wan-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.wan-name {
  font-size: 14px;
  font-weight: 600;
  color: #ccc;
}
.wan-detail {
  padding-left: 4px;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 13px;
}
.detail-row .label { color: #888; }
.detail-row .value { color: #ccc; }
</style>
