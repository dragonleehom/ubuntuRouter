<template>
  <el-container class="layout-container">
    <!-- 手机端: 遮罩层 -->
    <div v-if="isMobile && mobileMenuOpen" class="mobile-overlay" @click="mobileMenuOpen = false" />

    <!-- 侧边栏 -->
    <el-aside
      :class="['sidebar', { 'mobile-hidden': isMobile && !mobileMenuOpen, 'mobile-show': isMobile && mobileMenuOpen }]"
      :width="isMobile ? '220px' : (isCollapse ? '64px' : '220px')"
    >
      <div class="sidebar-header">
        <el-icon :size="28" color="#409EFF"><Monitor /></el-icon>
        <span v-show="!isCollapse || isMobile" class="brand">UbuntuRouter</span>
      </div>

      <el-menu
        :default-active="route.path"
        :collapse="!isMobile && isCollapse"
        :collapse-transition="false"
        background-color="#141414"
        text-color="#999"
        active-text-color="#409EFF"
        router
        @select="onMenuSelect"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/interfaces">
          <el-icon><Connection /></el-icon>
          <span>网络接口</span>
        </el-menu-item>
        <el-menu-item index="/firewall">
          <el-icon><Lock /></el-icon>
          <span>防火墙</span>
        </el-menu-item>
        <el-menu-item index="/dhcp">
          <el-icon><Connection /></el-icon>
          <span>DHCP/DNS</span>
        </el-menu-item>
        <el-menu-item index="/routing">
          <el-icon><SetUp /></el-icon>
          <span>路由</span>
        </el-menu-item>
        <el-menu-item index="/vpn">
          <el-icon><Connection /></el-icon>
          <span>VPN</span>
        </el-menu-item>
        <el-menu-item index="/multiwan">
          <el-icon><Connection /></el-icon>
          <span>多线路</span>
        </el-menu-item>
        <el-menu-item index="/containers">
          <el-icon><Monitor /></el-icon>
          <span>容器</span>
        </el-menu-item>
        <el-menu-item index="/appstore">
          <el-icon><Goods /></el-icon>
          <span>应用市场</span>
        </el-menu-item>
        <el-menu-item index="/ddns">
          <el-icon><Connection /></el-icon>
          <span>DDNS</span>
        </el-menu-item>
        <el-menu-item index="/storage">
          <el-icon><Monitor /></el-icon>
          <span>存储管理</span>
        </el-menu-item>
        <el-menu-item index="/monitor">
          <el-icon><DataBoard /></el-icon>
          <span>系统监控</span>
        </el-menu-item>
        <el-menu-item index="/samba">
          <el-icon><Connection /></el-icon>
          <span>Samba 共享</span>
        </el-menu-item>
        <el-menu-item index="/pppoe">
          <el-icon><Connection /></el-icon>
          <span>PPPoE 拨号</span>
        </el-menu-item>
        <el-menu-item index="/terminal">
          <el-icon><Monitor /></el-icon>
          <span>Web 终端</span>
        </el-menu-item>
        <el-menu-item index="/apt">
          <el-icon><Setting /></el-icon>
          <span>软件源</span>
        </el-menu-item>
        <el-menu-item index="/dns">
          <el-icon><Connection /></el-icon>
          <span>DNS 管理</span>
        </el-menu-item>
        <el-menu-item index="/diag">
          <el-icon><Connection /></el-icon>
          <span>网络诊断</span>
        </el-menu-item>
        <el-menu-item index="/backup">
          <el-icon><Setting /></el-icon>
          <span>备份恢复</span>
        </el-menu-item>
        <el-menu-item index="/orchestrator">
          <el-icon><SetUp /></el-icon>
          <span>流量编排</span>
        </el-menu-item>
        <el-menu-item index="/vm">
          <el-icon><Monitor /></el-icon>
          <span>虚拟机</span>
        </el-menu-item>
        <el-menu-item index="/system">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>

      <!-- PC端折叠按钮 -->
      <div v-if="!isMobile" class="sidebar-collapse" @click="isCollapse = !isCollapse">
        <el-icon><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部状态栏 -->
      <el-header class="topbar">
        <div class="topbar-left">
          <!-- 手机端: 汉堡菜单 -->
          <el-button v-if="isMobile" class="hamburger-btn" text @click="mobileMenuOpen = !mobileMenuOpen">
            <el-icon :size="22"><Operation /></el-icon>
          </el-button>
          <el-tag size="small" :type="connected ? 'success' : 'danger'" effect="dark">{{ connected ? '在线' : '离线' }}</el-tag>
          <span class="topbar-title">{{ pageTitle }}</span>
        </div>
        <div class="topbar-right">
          <span class="user-name">{{ authStore.user?.username || '用户' }}</span>
          <el-button text @click="authStore.logout">
            <el-icon><SwitchButton /></el-icon>
            <span class="logout-text">退出</span>
          </el-button>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'
import {
  Monitor, DataBoard, Connection, Lock, Setting,
  Fold, Expand, SwitchButton, SetUp, Goods, Operation,
} from '@element-plus/icons-vue'

const route = useRoute()
const authStore = useAuthStore()
const isCollapse = ref(false)
const connected = ref(true)
const mobileMenuOpen = ref(false)
const isMobile = ref(window.innerWidth < 768)

const pageTitle = computed(() => {
  const map = {
    '/dashboard': '仪表盘',
    '/interfaces': '网络接口',
    '/firewall': '防火墙',
    '/dhcp': 'DHCP/DNS',
    '/routing': '路由',
    '/vpn': 'VPN',
    '/multiwan': '多线路',
    '/containers': '容器',
    '/appstore': '应用市场',
    '/ddns': 'DDNS',
    '/storage': '存储管理',
    '/monitor': '系统监控',
    '/samba': 'Samba 共享',
    '/pppoe': 'PPPoE 拨号',
    '/terminal': 'Web 终端',
    '/apt': '软件源',
    '/dns': 'DNS 管理',
    '/diag': '网络诊断',
    '/backup': '备份恢复',
    '/orchestrator': '流量编排',
    '/vm': '虚拟机',
    '/system': '系统设置',
  }
  return map[route.path] || 'UbuntuRouter'
})

function onMenuSelect() {
  if (isMobile.value) {
    mobileMenuOpen.value = false
  }
}

function checkMobile() {
  isMobile.value = window.innerWidth < 768
}

let resizeHandler = null
onMounted(async () => {
  resizeHandler = () => checkMobile()
  window.addEventListener('resize', resizeHandler)
  try {
    const { api } = await import('@/stores')
    await api.get('/auth/me')
    connected.value = true
  } catch {
    connected.value = false
  }
})

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.mobile-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
}
.sidebar {
  background: #141414;
  border-right: 1px solid #222;
  display: flex;
  flex-direction: column;
  transition: width 0.3s, transform 0.3s;
  overflow: hidden;
  z-index: 1000;
}
@media (max-width: 767px) {
  .sidebar.mobile-hidden {
    transform: translateX(-100%);
    position: fixed;
    height: 100vh;
    z-index: 1000;
  }
  .sidebar.mobile-show {
    transform: translateX(0);
    position: fixed;
    height: 100vh;
    z-index: 1000;
    box-shadow: 4px 0 12px rgba(0, 0, 0, 0.4);
  }
}
.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px;
  border-bottom: 1px solid #222;
}
.brand {
  font-size: 18px;
  font-weight: 600;
  color: #e0e0e0;
  white-space: nowrap;
}
.sidebar-collapse {
  margin-top: auto;
  padding: 16px;
  text-align: center;
  cursor: pointer;
  color: #666;
  border-top: 1px solid #222;
}
.sidebar-collapse:hover {
  color: #409EFF;
}
.topbar {
  background: #141414;
  border-bottom: 1px solid #222;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 56px;
}
@media (min-width: 768px) {
  .topbar { padding: 0 24px; }
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
@media (min-width: 768px) {
  .topbar-left { gap: 12px; }
}
.hamburger-btn {
  color: #999;
  padding: 4px;
}
.topbar-title {
  font-size: 14px;
  color: #ccc;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (min-width: 768px) {
  .topbar-title { font-size: 16px; }
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
@media (min-width: 768px) {
  .topbar-right { gap: 16px; }
}
.user-name {
  color: #999;
  font-size: 13px;
  display: none;
}
@media (min-width: 768px) {
  .user-name { display: inline; font-size: 14px; }
}
.logout-text {
  display: none;
}
@media (min-width: 480px) {
  .logout-text { display: inline; }
}
.main-content {
  background: #0a0a0a;
  padding: 16px;
  overflow-y: auto;
}
@media (min-width: 768px) {
  .main-content { padding: 24px; }
}
.el-menu {
  border-right: none;
}
</style>
