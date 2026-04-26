<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-header">
        <el-icon :size="28" color="#409EFF"><Monitor /></el-icon>
        <span v-show="!isCollapse" class="brand">UbuntuRouter</span>
      </div>

      <el-menu
        :default-active="route.path"
        :collapse="isCollapse"
        :collapse-transition="false"
        background-color="#141414"
        text-color="#999"
        active-text-color="#409EFF"
        router
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

      <div class="sidebar-collapse" @click="isCollapse = !isCollapse">
        <el-icon><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部状态栏 -->
      <el-header class="topbar">
        <div class="topbar-left">
          <el-tag size="small" type="success" effect="dark" v-if="connected">在线</el-tag>
          <el-tag size="small" type="danger" effect="dark" v-else>离线</el-tag>
          <span class="topbar-title">仪表盘</span>
        </div>
        <div class="topbar-right">
          <span class="user-name">{{ authStore.user?.username || '用户' }}</span>
          <el-button text @click="authStore.logout">
            <el-icon><SwitchButton /></el-icon>
            退出
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
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'
import {
  Monitor, DataBoard, Connection, Lock, Setting,
  Fold, Expand, SwitchButton, SetUp, Goods,
} from '@element-plus/icons-vue'

const route = useRoute()
const authStore = useAuthStore()
const isCollapse = ref(false)
const connected = ref(true)

onMounted(async () => {
  try {
    const { api } = await import('@/stores')
    await api.get('/auth/me')
    connected.value = true
  } catch {
    connected.value = false
  }
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.sidebar {
  background: #141414;
  border-right: 1px solid #222;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  overflow: hidden;
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
  padding: 0 24px;
  height: 56px;
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.topbar-title {
  font-size: 16px;
  color: #ccc;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.user-name {
  color: #999;
  font-size: 14px;
}
.main-content {
  background: #0a0a0a;
  padding: 24px;
  overflow-y: auto;
}
.el-menu {
  border-right: none;
}
</style>
