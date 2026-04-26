import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API_BASE = '/api/v1'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

// 请求拦截器：自动添加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 自动跳转登录
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isAuthenticated = computed(() => !!localStorage.getItem('access_token'))

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
    // 获取用户信息
    const me = await api.get('/auth/me')
    user.value = me.data
    return me.data
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
    window.location.href = '/login'
  }

  return { user, isAuthenticated, login, logout }
})

export const useDashboardStore = defineStore('dashboard', () => {
  const status = ref(null)
  const loading = ref(false)

  async function fetchStatus() {
    loading.value = true
    try {
      const res = await api.get('/dashboard/status')
      status.value = res.data
    } catch (e) {
      console.error('获取 Dashboard 状态失败:', e)
    }
    loading.value = false
  }

  return { status, loading, fetchStatus }
})

export { api }

/**
 * 配置管理 Store — 保存待应用配置、差分状态
 * 
 * 所有编辑页面的修改都暂存到此 store，
 * 用户确认后通过 Apply 按钮统一触发配置生效。
 */
export const useConfigStore = defineStore('config', () => {
  const currentConfig = ref(null)        // 当前线上配置（完整 YAML）
  const pendingConfig = ref(null)        // 待应用的配置（完整 YAML）
  const pendingChanges = ref([])         // 待应用变更的 diff_items
  const pendingSectionCount = ref(0)     // 变更的配置节数
  const diffResult = ref(null)           // 最近一次 diff 结果
  const loading = ref(false)

  /** 加载当前配置 */
  async function loadCurrent() {
    loading.value = true
    try {
      const res = await api.get('/config/view')
      currentConfig.value = res.data.config_yaml
      return res.data
    } finally {
      loading.value = false
    }
  }

  /** 暂存一份新配置（用户保存时调用） */
  async function stageConfig(yaml) {
    pendingConfig.value = yaml
    // 调用 diff API 获取变更预览
    try {
      const res = await api.post('/config/diff', { config_yaml: yaml })
      diffResult.value = res.data
      pendingChanges.value = res.data.diff_items || []
      pendingSectionCount.value = (res.data.changed_sections || []).length
      return res.data
    } catch (e) {
      console.error('Diff failed:', e)
      // 如果 diff 失败（如首次配置），仍然允许 Apply
      pendingChanges.value = []
      pendingSectionCount.value = 0
      return null
    }
  }

  /** 应用暂存的配置 */
  async function applyPending() {
    if (!pendingConfig.value) return null
    try {
      const res = await api.post('/config/apply', {
        config_yaml: pendingConfig.value,
        auto_rollback: true,
      })
      if (res.data.success) {
        // 成功后清空暂存
        pendingConfig.value = null
        pendingChanges.value = []
        pendingSectionCount.value = 0
        diffResult.value = null
        // 重新加载当前配置
        await loadCurrent()
      }
      return res.data
    } catch (e) {
      console.error('Apply failed:', e)
      throw e
    }
  }

  /** 丢弃暂存配置 */
  function discardPending() {
    pendingConfig.value = null
    pendingChanges.value = []
    pendingSectionCount.value = 0
    diffResult.value = null
  }

  /** 是否有待应用的变更 */
  const hasPending = computed(() => pendingConfig.value !== null && pendingSectionCount.value > 0)

  return {
    currentConfig, pendingConfig, pendingChanges,
    pendingSectionCount, diffResult, loading, hasPending,
    loadCurrent, stageConfig, applyPending, discardPending,
  }
})
