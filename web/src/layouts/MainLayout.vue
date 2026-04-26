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
        <!-- 仪表盘（独立项，不折叠） -->
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>

        <!-- 2. 路由状态 -->
        <el-sub-menu index="/status">
          <template #title>
            <el-icon><Monitor /></el-icon>
            <span>路由状态</span>
          </template>
          <el-menu-item index="/status/overview">概览</el-menu-item>
          <el-menu-item index="/status/interfaces">接口总览</el-menu-item>
          <el-menu-item index="/status/routes">路由表</el-menu-item>
          <el-menu-item index="/status/firewall">防火墙状态</el-menu-item>
          <el-menu-item index="/status/realtime">实时流量</el-menu-item>
          <el-menu-item index="/status/traffic">流量监控</el-menu-item>
          <el-menu-item index="/status/syslog">系统日志</el-menu-item>
          <el-menu-item index="/status/processes">进程管理</el-menu-item>
        </el-sub-menu>

        <!-- 3. 网络配置 -->
        <el-sub-menu index="/network">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>网络配置</span>
          </template>
          <el-menu-item index="/network/interfaces">接口</el-menu-item>
          <el-menu-item index="/network/wizard">联网向导</el-menu-item>
          <el-menu-item index="/network/wireless">无线</el-menu-item>
          <el-menu-item index="/network/dhcp">DHCP 服务器</el-menu-item>
          <el-menu-item index="/network/hostnames">主机名映射</el-menu-item>
          <el-menu-item index="/network/dns">DNS 设置</el-menu-item>
          <el-menu-item index="/network/static-routes">静态路由</el-menu-item>
          <el-menu-item index="/network/firewall">防火墙规则</el-menu-item>
          <el-menu-item index="/network/port-forward">端口转发</el-menu-item>
          <el-menu-item index="/network/qos">SQM QoS</el-menu-item>
          <el-menu-item index="/network/turbo-acc">Turbo ACC</el-menu-item>
          <el-menu-item index="/network/diagnostics">网络诊断</el-menu-item>
          <el-menu-item index="/network/upnp">UPnP</el-menu-item>
        </el-sub-menu>

        <!-- 4. 远程服务 -->
        <el-sub-menu index="/remote">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>远程服务</span>
          </template>
          <el-menu-item index="/remote/ddns">动态域名</el-menu-item>
          <!-- VPN 带三级子菜单 -->
          <el-sub-menu index="/remote/vpn">
            <template #title><span>VPN 设置</span></template>
            <el-menu-item index="/remote/vpn">概览</el-menu-item>
            <el-menu-item index="/remote/vpn/tailscale">Tailscale</el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/remote/frp-client">FRP 客户端</el-menu-item>
          <el-menu-item index="/remote/frp-server">FRP 服务端</el-menu-item>
          <el-menu-item index="/remote/socat">Socat</el-menu-item>
          <el-menu-item index="/remote/webdav">WebDAV</el-menu-item>
        </el-sub-menu>

        <!-- 5. 存储管理 -->
        <el-sub-menu index="/storage">
          <template #title>
            <el-icon><Monitor /></el-icon>
            <span>存储管理</span>
          </template>
          <el-menu-item index="/storage/overview">磁盘概览</el-menu-item>
          <el-menu-item index="/storage/files">文件管理</el-menu-item>
          <el-menu-item index="/storage/samba">Samba</el-menu-item>
          <el-menu-item index="/storage/ftp">FTP</el-menu-item>
          <el-menu-item index="/storage/nfs">NFS</el-menu-item>
          <el-menu-item index="/storage/disks">磁盘管理</el-menu-item>
          <el-menu-item index="/storage/backup">备份还原</el-menu-item>
        </el-sub-menu>

        <!-- 6. 应用管理 -->
        <el-sub-menu index="/apps">
          <template #title>
            <el-icon><Goods /></el-icon>
            <span>应用管理</span>
          </template>
          <el-menu-item index="/apps/market">应用市场</el-menu-item>
          <el-menu-item index="/apps/installed">已安装应用</el-menu-item>
          <!-- Docker 带三级子菜单 -->
          <el-sub-menu index="/apps/docker">
            <template #title><span>Docker</span></template>
            <el-menu-item index="/apps/docker">概览</el-menu-item>
            <el-menu-item index="/apps/docker/containers">容器</el-menu-item>
            <el-menu-item index="/apps/docker/images">镜像</el-menu-item>
            <el-menu-item index="/apps/docker/networks">网络</el-menu-item>
            <el-menu-item index="/apps/docker/volumes">存储卷</el-menu-item>
          </el-sub-menu>
        </el-sub-menu>

        <!-- 7. 系统设置 -->
        <el-sub-menu index="/system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item index="/system/settings">系统</el-menu-item>
          <el-menu-item index="/system/users">用户管理</el-menu-item>
          <el-menu-item index="/system/ssh-keys">SSH 密钥</el-menu-item>
          <el-menu-item index="/system/software">软件包</el-menu-item>
          <el-menu-item index="/system/upgrade">系统升级</el-menu-item>
          <el-menu-item index="/system/startup">启动项</el-menu-item>
          <el-menu-item index="/system/scheduled-tasks">定时任务</el-menu-item>
          <el-menu-item index="/system/led">LED 配置</el-menu-item>
          <el-menu-item index="/system/snmp">SNMP</el-menu-item>
          <el-menu-item index="/system/ttyd">TTYD 终端</el-menu-item>
          <el-menu-item index="/system/devices">设备管理</el-menu-item>
          <el-menu-item index="/system/config">配置编辑</el-menu-item>
          <el-menu-item index="/system/timed-reboot">定时重启</el-menu-item>
        </el-sub-menu>

        <!-- 8. 重启关机 -->
        <el-sub-menu index="/power">
          <template #title>
            <el-icon><SwitchButton /></el-icon>
            <span>重启关机</span>
          </template>
          <el-menu-item index="/power/reboot">重启</el-menu-item>
          <el-menu-item index="/power/shutdown">关机</el-menu-item>
        </el-sub-menu>
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
        <PendingChangesBar />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'
import PendingChangesBar from '@/components/PendingChangesBar.vue'
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

// 根据路由的 meta.title 动态获取页面标题
const pageTitle = computed(() => {
  return route.meta?.title || 'UbuntuRouter'
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
  padding-bottom: 80px;
}
@media (min-width: 768px) {
  .main-content { padding: 24px; }
}
.el-menu {
  border-right: none;
}
/* 子菜单样式：缩进三级菜单 */
.el-sub-menu .el-sub-menu .el-menu-item {
  padding-left: 56px !important;
}
</style>
