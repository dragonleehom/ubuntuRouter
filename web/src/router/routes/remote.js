// 远程服务模块路由
export default [
  {
    path: 'remote',
    meta: { title: '远程服务', icon: 'Connection', module: 'remote' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'ddns',
        name: 'RemoteDdns',
        meta: { title: '动态域名' },
        component: () => import('@/views/ddns/DdnsConfig.vue'),
      },
      {
        path: 'vpn',
        name: 'RemoteVpn',
        meta: { title: 'VPN 设置' },
        component: () => import('@/views/vpn/VpnTunnels.vue'),
      },
      {
        path: 'vpn/tailscale',
        name: 'RemoteVpnTailscale',
        meta: { title: 'Tailscale' },
        component: () => import('@/views/vpn/VpnTunnels.vue'), // 后续拆分出独立 Tailscale 页
      },
      {
        path: 'frp-client',
        name: 'RemoteFrpClient',
        meta: { title: 'FRP 客户端' },
        component: () => import('@/views/RemoteFrpClientPlaceholder.vue'),
      },
      {
        path: 'frp-server',
        name: 'RemoteFrpServer',
        meta: { title: 'FRP 服务端' },
        component: () => import('@/views/RemoteFrpServerPlaceholder.vue'),
      },
      {
        path: 'socat',
        name: 'RemoteSocat',
        meta: { title: 'Socat' },
        component: () => import('@/views/RemoteSocatPlaceholder.vue'),
      },
      {
        path: 'webdav',
        name: 'RemoteWebdav',
        meta: { title: 'WebDAV' },
        component: () => import('@/views/RemoteWebdavPlaceholder.vue'),
      },
    ],
  },
]
