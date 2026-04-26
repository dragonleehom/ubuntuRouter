// 网络配置模块路由
export default [
  {
    path: 'network',
    meta: { title: '网络配置', icon: 'Connection', module: 'network' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'interfaces',
        name: 'NetworkInterfaces',
        meta: { title: '接口' },
        component: () => import('@/views/Interfaces.vue'),
      },
      {
        path: 'wireless',
        name: 'NetworkWireless',
        meta: { title: 'WiFi' },
        component: () => import('@/views/NetworkWirelessPlaceholder.vue'),
      },
      {
        path: 'dhcp',
        name: 'NetworkDhcp',
        meta: { title: 'DHCP 服务器' },
        component: () => import('@/views/dhcp/DhcpDns.vue'),
      },
      {
        path: 'hostnames',
        name: 'NetworkHostnames',
        meta: { title: '主机名映射' },
        component: () => import('@/views/NetworkHostnamesPlaceholder.vue'),
      },
      {
        path: 'dns',
        name: 'NetworkDns',
        meta: { title: 'DNS 设置' },
        component: () => import('@/views/dns/DnsConfig.vue'),
      },
      {
        path: 'static-routes',
        name: 'NetworkStaticRoutes',
        meta: { title: '静态路由' },
        component: () => import('@/views/routing/RoutingTable.vue'),
      },
      {
        path: 'firewall',
        name: 'NetworkFirewall',
        meta: { title: '防火墙规则' },
        component: () => import('@/views/firewall/FirewallRules.vue'),
      },
      {
        path: 'port-forward',
        name: 'NetworkPortForward',
        meta: { title: '端口转发' },
        component: () => import('@/views/firewall/FirewallRules.vue'), // 复用到后续重写
      },
      {
        path: 'qos',
        name: 'NetworkQos',
        meta: { title: 'SQM QoS' },
        component: () => import('@/views/NetworkQosPlaceholder.vue'),
      },
      {
        path: 'turbo-acc',
        name: 'NetworkTurboAcc',
        meta: { title: 'Turbo ACC' },
        component: () => import('@/views/NetworkTurboAccPlaceholder.vue'),
      },
      {
        path: 'diagnostics',
        name: 'NetworkDiagnostics',
        meta: { title: '网络诊断' },
        component: () => import('@/views/diag/NetworkDiag.vue'),
      },
      {
        path: 'upnp',
        name: 'NetworkUpnp',
        meta: { title: 'UPnP' },
        component: () => import('@/views/NetworkUpnpPlaceholder.vue'),
      },
    ],
  },
]
