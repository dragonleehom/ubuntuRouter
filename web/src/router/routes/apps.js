// 应用管理模块路由
export default [
  {
    path: 'apps',
    meta: { title: '应用管理', icon: 'Goods', module: 'apps' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'market',
        name: 'AppsMarket',
        meta: { title: '应用市场' },
        component: () => import('@/views/appstore/AppStore.vue'),
      },
      {
        path: 'installed',
        name: 'AppsInstalled',
        meta: { title: '已安装应用' },
        component: () => import('@/views/appstore/AppStore.vue'),
      },
      {
        path: 'docker',
        name: 'AppsDocker',
        meta: { title: 'Docker 概览' },
        component: () => import('@/views/containers/ContainerManager.vue'),
      },
      {
        path: 'docker/containers',
        name: 'AppsDockerContainers',
        meta: { title: 'Docker > 容器' },
        component: () => import('@/views/containers/ContainerManager.vue'),
      },
      {
        path: 'docker/images',
        name: 'AppsDockerImages',
        meta: { title: 'Docker > 镜像' },
        component: () => import('@/views/containers/ContainerManager.vue'),
      },
      {
        path: 'docker/networks',
        name: 'AppsDockerNetworks',
        meta: { title: 'Docker > 网络' },
        component: () => import('@/views/containers/ContainerManager.vue'),
      },
      {
        path: 'docker/volumes',
        name: 'AppsDockerVolumes',
        meta: { title: 'Docker > 存储卷' },
        component: () => import('@/views/containers/ContainerManager.vue'),
      },
    ],
  },
]
