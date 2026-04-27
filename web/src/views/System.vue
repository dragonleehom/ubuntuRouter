<template>
  <div class="page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：系统信息 + 编辑 -->
      <el-col :span="12">
        <el-card class="system-card">
          <template #header><span>系统信息</span></template>
          <div class="info-grid" v-if="systemInfo">
            <div class="info-row">
              <span class="label">主机名</span>
              <div class="value-row">
                <el-input
                  v-if="editing.hostname"
                  v-model="form.hostname"
                  size="small"
                  style="width: 200px"
                  placeholder="输入主机名"
                />
                <span v-else class="value">{{ systemInfo.hostname }}</span>
                <el-button
                  :type="editing.hostname ? 'primary' : 'default'"
                  size="small"
                  :icon="editing.hostname ? 'Check' : 'Edit'"
                  circle
                  @click="editing.hostname ? saveHostname() : startEdit('hostname')"
                />
              </div>
            </div>
            <div class="info-row">
              <span class="label">系统</span>
              <span class="value">{{ systemInfo.os?.distro }} {{ systemInfo.os?.version }}</span>
            </div>
            <div class="info-row">
              <span class="label">初始化状态</span>
              <el-tag :type="systemInfo.initialized ? 'success' : 'warning'" size="small">
                {{ systemInfo.initialized ? '已初始化' : '未初始化' }}
              </el-tag>
            </div>
          </div>
          <el-skeleton :rows="3" animated v-else />
        </el-card>

        <!-- 时区设置 -->
        <el-card class="system-card">
          <template #header><span>时区设置</span></template>
          <div class="info-grid" v-if="timezoneData">
            <div class="info-row">
              <span class="label">当前时区</span>
              <div class="value-row">
                <el-select
                  v-model="form.timezone"
                  size="small"
                  filterable
                  style="width: 240px"
                  :loading="tzLoading"
                >
                  <el-option
                    v-for="tz in timezoneData.timezones"
                    :key="tz"
                    :label="tz"
                    :value="tz"
                  />
                </el-select>
                <el-button
                  size="small"
                  type="primary"
                  :loading="tzSaving"
                  @click="saveTimezone"
                  style="margin-left: 8px"
                >应用</el-button>
              </div>
            </div>
          </div>
          <el-skeleton :rows="1" animated v-else />
        </el-card>

        <!-- NTP 设置 -->
        <el-card class="system-card">
          <template #header><span>NTP 时间同步</span></template>
          <div class="info-grid">
            <div class="info-row">
              <span class="label">启用 NTP</span>
              <el-switch v-model="form.ntpEnabled" @change="saveNtp" />
            </div>
            <div class="info-row" v-if="form.ntpEnabled">
              <span class="label">NTP 服务器</span>
              <div class="value-row">
                <el-input
                  v-model="form.ntpServers"
                  size="small"
                  style="width: 280px"
                  placeholder="ntp.ubuntu.com"
                />
                <el-button size="small" type="primary" @click="saveNtp">应用</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：服务状态 -->
      <el-col :span="12">
        <el-card class="system-card">
          <template #header><span>服务状态</span></template>
          <div class="service-list" v-if="systemInfo?.services">
            <div v-for="(svc, name) in systemInfo.services" :key="name" class="service-item">
              <span class="service-name">{{ name }}</span>
              <el-tag :type="svc.active ? 'success' : 'danger'" size="small">
                {{ svc.active ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </div>
          <el-skeleton :rows="3" animated v-else />
        </el-card>
      </el-col>
    </el-row>

    <el-card class="snapshot-card">
      <template #header>
        <div class="card-header">
          <span>配置快照</span>
          <el-button size="small" @click="fetchSnapshots">刷新</el-button>
        </div>
      </template>
      <el-table :data="snapshots" stripe v-loading="snapLoading" v-if="snapshots.length">
        <el-table-column prop="created_at" label="创建时间" width="200" />
        <el-table-column prop="summary" label="描述" />
        <el-table-column prop="snapshot_id" label="快照 ID" width="200" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.good" type="success" size="small">正常</el-tag>
            <el-tag v-else type="info" size="small">未知</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!snapLoading" description="暂无快照" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '@/stores'
import { ElMessage } from 'element-plus'

const systemInfo = ref(null)
const snapshots = ref([])
const snapLoading = ref(false)
const tzLoading = ref(false)
const tzSaving = ref(false)
const timezoneData = ref(null)

const editing = reactive({
  hostname: false,
})

const form = reactive({
  hostname: '',
  timezone: '',
  ntpEnabled: true,
  ntpServers: '',
})

onMounted(async () => {
  try {
    const res = await api.get('/system/status')
    systemInfo.value = res.data
    form.hostname = res.data.hostname
  } catch (e) {
    console.error('获取系统信息失败:', e)
  }
  await fetchTimezones()
  await fetchSnapshots()
})

function startEdit(field) {
  if (field === 'hostname') {
    form.hostname = systemInfo.value?.hostname || ''
    editing.hostname = true
  }
}

async function saveHostname() {
  if (!form.hostname.trim()) {
    ElMessage.warning('主机名不能为空')
    return
  }
  try {
    const res = await api.post('/system/hostname', { hostname: form.hostname.trim() })
    systemInfo.value.hostname = form.hostname.trim()
    editing.hostname = false
    ElMessage.success(res.data.message)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '设置主机名失败')
  }
}

async function fetchTimezones() {
  tzLoading.value = true
  try {
    const res = await api.get('/system/timezone')
    timezoneData.value = res.data
    form.timezone = res.data.timezone
  } catch (e) {
    console.error('获取时区列表失败:', e)
  }
  tzLoading.value = false
}

async function saveTimezone() {
  tzSaving.value = true
  try {
    const res = await api.post('/system/timezone', { timezone: form.timezone })
    ElMessage.success(res.data.message)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '设置时区失败')
  }
  tzSaving.value = false
}

async function saveNtp() {
  try {
    const res = await api.post('/system/ntp', {
      enabled: form.ntpEnabled,
      servers: form.ntpServers,
    })
    ElMessage.success(res.data.message)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '设置NTP失败')
  }
}

async function fetchSnapshots() {
  snapLoading.value = true
  try {
    const res = await api.get('/system/snapshots')
    snapshots.value = res.data.snapshots
  } catch (e) {
    console.error('获取快照列表失败:', e)
  }
  snapLoading.value = false
}
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; color: #e0e0e0; }
.system-card { margin-bottom: 20px; }
.info-grid { display: flex; flex-direction: column; gap: 12px; }
.info-row { display: flex; justify-content: space-between; align-items: center; }
.info-row .label { color: #888; font-size: 14px; flex-shrink: 0; margin-right: 12px; }
.info-row .value { color: #ccc; font-size: 14px; }
.value-row { display: flex; align-items: center; gap: 8px; }
.service-list { display: flex; flex-direction: column; gap: 8px; }
.service-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
.service-name { color: #ccc; font-size: 14px; }
.snapshot-card { margin-top: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
