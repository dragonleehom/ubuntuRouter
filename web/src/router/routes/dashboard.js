// 仪表盘路由
export default [
  {
    path: '',
    redirect: '/dashboard',
  },
  {
    path: 'dashboard',
    name: 'Dashboard',
    meta: { title: '仪表盘', icon: 'DataBoard', module: 'dashboard' },
    component: () => import('@/views/Dashboard.vue'),
  },
]
