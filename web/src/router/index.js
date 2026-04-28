import { createRouter, createWebHistory } from 'vue-router'
import dashboardRoutes from './routes/dashboard.js'
import statusRoutes from './routes/status.js'
import networkRoutes from './routes/network.js'
import remoteRoutes from './routes/remote.js'
import storageRoutes from './routes/storage.js'
import appsRoutes from './routes/apps.js'
import systemRoutes from './routes/system.js'
import powerRoutes from './routes/power.js'
import orchestratorRoutes from './routes/orchestrator.js'

// 旧路径到新路径的重定向映射
const redirectMap = {
  '/interfaces': '/status/interfaces',
  '/firewall': '/network/firewall',
  '/dhcp': '/network/dhcp',
  '/routing': '/status/routes',
  '/vpn': '/remote/vpn',
  '/multiwan': '/network/interfaces',
  '/containers': '/apps/docker',
  '/appstore': '/apps/market',
  '/ddns': '/remote/ddns',
  '/storage': '/storage/overview',
  '/monitor': '/system/devices',
  '/samba': '/storage/samba',
  '/pppoe': '/network/interfaces',
  '/terminal': '/system/ttyd',
  '/apt': '/system/software',
  '/dns': '/network/dns',
  '/diag': '/network/diagnostics',
  '/backup': '/storage/backup',
  '/config': '/system/config',
  '/vm': '/apps/docker',
  '/system': '/system/settings',
}

// 批量生成重定向路由
const redirectRoutes = Object.entries(redirectMap).map(([oldPath, newPath]) => ({
  path: oldPath.substring(1), // 去掉开头的 /
  redirect: newPath,
}))

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
      // 仪表盘（根目录的子路由）
      ...dashboardRoutes,
      // 各模块路由
      ...statusRoutes,
      ...networkRoutes,
      ...remoteRoutes,
      ...storageRoutes,
      ...appsRoutes,
      ...systemRoutes,
      ...powerRoutes,
      // 编排模块
      ...orchestratorRoutes,
      // 旧路径重定向
      ...redirectRoutes,
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
