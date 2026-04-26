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
