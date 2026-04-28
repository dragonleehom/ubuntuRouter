<template>
  <div class="page">
    <div class="page-header">
      <h2>SNMP 配置</h2>
      <div class="header-actions">
        <el-button size="small" @click="fetchStatus">刷新</el-button>
        <el-button v-if="!enabled" type="success" size="small" @click="snmpEnable">启用</el-button>
        <el-button v-else type="danger" size="small" @click="snmpDisable">禁用</el-button>
        <el-button type="primary" size="small" @click="showConfig=true" :loading="configLoading">配置</el-button>
      </div>
    </div>
    <el-card shadow="never" class="section-card">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="状态"><el-tag :type="enabled?'success':'info'">{{ enabled?'运行中':'已停止' }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="端口">{{ port }}</el-descriptions-item>
        <el-descriptions-item label="Community">{{ community }}</el-descriptions-item>
        <el-descriptions-item label="位置">{{ location || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ contact || '-' }}</el-descriptions-item>
        <el-descriptions-item label="允许网段">{{ (allowedNetworks || []).join(', ') }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    <el-dialog v-model="showConfig" title="SNMP 配置" width="450px">
      <el-form :model="form" label-width="120px" size="small">
        <el-form-item label="Community"><el-input v-model="form.community" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="form.location" /></el-form-item>
        <el-form-item label="联系人"><el-input v-model="form.contact" /></el-form-item>
        <el-form-item label="允许网段"><el-input v-model="form.allowed" placeholder="多个用空格分隔" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showConfig=false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/stores'
const enabled = ref(false); const port = ref(161); const community = ref('public')
const location = ref(''); const contact = ref(''); const allowedNetworks = ref(['127.0.0.1'])
const showConfig = ref(false); const configLoading = ref(false)
const form = reactive({ community: 'public', location: '', contact: '', allowed: '' })
async function fetchStatus() {
  try {
    const res = await api.get('/system/snmp/status')
    enabled.value = res.data.enabled; community.value = res.data.community || 'public'
    location.value = res.data.location || ''; contact.value = res.data.contact || ''
    allowedNetworks.value = res.data.allowed_networks || ['127.0.0.1']
    port.value = res.data.port || 161
    Object.assign(form, { community: community.value, location: location.value, contact: contact.value, allowed: (allowedNetworks.value || []).join(' ') })
  } catch { /* ignore */ }
}
async function snmpEnable() { try { await api.post('/system/snmp/enable'); ElMessage.success('SNMP 已启用'); await fetchStatus() } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') } }
async function snmpDisable() { try { await api.post('/system/snmp/disable'); ElMessage.success('SNMP 已禁用'); await fetchStatus() } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') } }
async function saveConfig() {
  configLoading.value = true
  try {
    await api.post('/system/snmp/config', { community: form.community, location: form.location, contact: form.contact, allowed_networks: form.allowed.split(/\s+/) })
    ElMessage.success('配置已保存'); showConfig.value = false; await fetchStatus()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  configLoading.value = false
}
onMounted(fetchStatus)
</script>
<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { color: #e0e0e0; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.section-card { background: #141414; border: 1px solid #222; }
</style>
