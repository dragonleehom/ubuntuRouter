// 路由状态模块路由
export default [
  {
    path: 'status',
    meta: { title: '路由状态', icon: 'Monitor', module: 'status' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'overview',
        name: 'StatusOverview',
        meta: { title: '概览' },
        component: () => import('@/views/Dashboard.vue'), // 复用仪表盘内容作为概览页
      },
      {
        path: 'interfaces',
        name: 'StatusInterfaces',
        meta: { title: '接口总览' },
        component: () => import('@/views/Interfaces.vue'),
      },
      {
        path: 'routes',
        name: 'StatusRoutes',
        meta: { title: '路由表' },
        component: () => import('@/views/routing/RoutingTable.vue'),
      },
      {
        path: 'firewall',
        name: 'StatusFirewall',
        meta: { title: '防火墙状态' },
        component: () => import('@/views/firewall/FirewallRules.vue'),
      },
      {
        path: 'realtime',
        name: 'StatusRealtime',
        meta: { title: '实时流量' },
        component: () => import('@/views/monitor/SystemMonitor.vue'),
      },
      {
        path: 'traffic',
        name: 'StatusTraffic',
        meta: { title: '流量监控' },
        component: () => import('@/views/monitor/SystemMonitor.vue'),
      },
      {
        path: 'realtime-traffic',
        name: 'StatusRealtimeTraffic',
        meta: { title: '实时图表' },
        component: () => import('@/views/monitor/TrafficRealtime.vue'),
      },
      {
        path: 'syslog',
        name: 'StatusSyslog',
        meta: { title: '系统日志' },
        component: () => import('@/views/SyslogView.vue'),
      },
      {
        path: 'processes',
        name: 'StatusProcesses',
        meta: { title: '在线设备' },
        component: () => import('@/views/OnlineDevices.vue'),
      },
    ],
  },
]
