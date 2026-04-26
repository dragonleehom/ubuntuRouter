// 重启关机模块路由
export default [
  {
    path: 'power',
    meta: { title: '重启关机', icon: 'SwitchButton', module: 'power' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'reboot',
        name: 'PowerReboot',
        meta: { title: '重启' },
        component: () => import('@/views/PowerRebootPlaceholder.vue'),
      },
      {
        path: 'shutdown',
        name: 'PowerShutdown',
        meta: { title: '关机' },
        component: () => import('@/views/PowerShutdownPlaceholder.vue'),
      },
    ],
  },
]
