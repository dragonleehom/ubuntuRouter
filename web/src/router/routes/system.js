// 系统设置模块路由
export default [
  {
    path: 'system',
    meta: { title: '系统设置', icon: 'Setting', module: 'system' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'settings',
        name: 'SystemSettings',
        meta: { title: '系统' },
        component: () => import('@/views/System.vue'),
      },
      {
        path: 'users',
        name: 'SystemUsers',
        meta: { title: '用户管理' },
        component: () => import('@/views/System.vue'),
      },
      {
        path: 'ssh-keys',
        name: 'SystemSshKeys',
        meta: { title: 'SSH 密钥' },
        component: () => import('@/views/SystemSshKeys.vue'),
      },
      {
        path: 'software',
        name: 'SystemSoftware',
        meta: { title: '软件包' },
        component: () => import('@/views/apt/AptSources.vue'),
      },
      {
        path: 'startup',
        name: 'SystemStartup',
        meta: { title: '启动项' },
        component: () => import('@/views/SystemStartup.vue'),
      },
      {
        path: 'scheduled-tasks',
        name: 'SystemScheduledTasks',
        meta: { title: '定时任务' },
        component: () => import('@/views/SystemScheduledTasks.vue'),
      },
      {
        path: 'led',
        name: 'SystemLed',
        meta: { title: 'LED 配置' },
        component: () => import('@/views/SystemLedPlaceholder.vue'),
      },
      {
        path: 'snmp',
        name: 'SystemSnmp',
        meta: { title: 'SNMP' },
        component: () => import('@/views/SystemSnmpPlaceholder.vue'),
      },
      {
        path: 'ttyd',
        name: 'SystemTtyd',
        meta: { title: 'TTYD 终端' },
        component: () => import('@/views/terminal/WebTerminal.vue'),
      },
      {
        path: 'devices',
        name: 'SystemDevices',
        meta: { title: '设备管理' },
        component: () => import('@/views/monitor/SystemMonitor.vue'),
      },
      {
        path: 'config',
        name: 'SystemConfig',
        meta: { title: '配置编辑' },
        component: () => import('@/views/ConfigEditor.vue'),
      },
      {
        path: 'timed-reboot',
        name: 'SystemTimedReboot',
        meta: { title: '定时重启' },
        component: () => import('@/views/SystemTimedRebootPlaceholder.vue'),
      },
      {
        path: 'upgrade',
        name: 'SystemUpgrade',
        meta: { title: '系统升级' },
        component: () => import('@/views/SystemUpdate.vue'),
      },
      {
        path: 'tls',
        name: 'SystemTls',
        meta: { title: 'HTTPS 证书' },
        component: () => import('@/views/tls/TlsManager.vue'),
      },
    ],
  },
]
