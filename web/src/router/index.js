import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
      },
      {
        path: 'interfaces',
        name: 'Interfaces',
        component: () => import('@/views/Interfaces.vue'),
      },
      {
        path: 'firewall',
        name: 'Firewall',
        component: () => import('@/views/firewall/FirewallRules.vue'),
      },
      {
        path: 'dhcp',
        name: 'DHCP',
        component: () => import('@/views/dhcp/DhcpDns.vue'),
      },
      {
        path: 'routing',
        name: 'Routing',
        component: () => import('@/views/routing/RoutingTable.vue'),
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/System.vue'),
      },
      {
        path: 'vpn',
        name: 'VPN',
        component: () => import('@/views/vpn/VpnTunnels.vue'),
      },
      {
        path: 'multiwan',
        name: 'MultiWAN',
        component: () => import('@/views/multiwan/MultiWanConfig.vue'),
      },
      {
        path: 'containers',
        name: 'Containers',
        component: () => import('@/views/containers/ContainerManager.vue'),
      },
      {
        path: 'appstore',
        name: 'AppStore',
        component: () => import('@/views/appstore/AppStore.vue'),
      },
      {
        path: 'ddns',
        name: 'DDNS',
        component: () => import('@/views/ddns/DdnsConfig.vue'),
      },
      {
        path: 'storage',
        name: 'Storage',
        component: () => import('@/views/storage/StorageManager.vue'),
      },
      {
        path: 'monitor',
        name: 'Monitor',
        component: () => import('@/views/monitor/SystemMonitor.vue'),
      },
      {
        path: 'samba',
        name: 'Samba',
        component: () => import('@/views/samba/SambaManager.vue'),
      },
      {
        path: 'pppoe',
        name: 'PPPoE',
        component: () => import('@/views/pppoe/PPPoEConnection.vue'),
      },
      {
        path: 'terminal',
        name: 'Terminal',
        component: () => import('@/views/terminal/WebTerminal.vue'),
      },
      {
        path: 'apt',
        name: 'AptSources',
        component: () => import('@/views/apt/AptSources.vue'),
      },
      {
        path: 'orchestrator',
        name: 'Orchestrator',
        component: () => import('@/views/orchestrator/OrchestratorCanvas.vue'),
      },
      {
        path: 'vm',
        name: 'VM',
        component: () => import('@/views/vm/VirtualMachines.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 导航守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
