// 存储管理模块路由
export default [
  {
    path: 'storage',
    meta: { title: '存储管理', icon: 'Monitor', module: 'storage' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'overview',
        name: 'StorageOverview',
        meta: { title: '磁盘概览' },
        component: () => import('@/views/storage/StorageManager.vue'),
      },
      {
        path: 'files',
        name: 'StorageFiles',
        meta: { title: '文件管理' },
        component: () => import('@/views/storage/StorageManager.vue'), // 后续拆出独立文件管理器
      },
      {
        path: 'samba',
        name: 'StorageSamba',
        meta: { title: 'Samba' },
        component: () => import('@/views/samba/SambaManager.vue'),
      },
      {
        path: 'ftp',
        name: 'StorageFtp',
        meta: { title: 'FTP' },
        component: () => import('@/views/StorageFtpPlaceholder.vue'),
      },
      {
        path: 'nfs',
        name: 'StorageNfs',
        meta: { title: 'NFS' },
        component: () => import('@/views/StorageNfsPlaceholder.vue'),
      },
      {
        path: 'disks',
        name: 'StorageDisks',
        meta: { title: '磁盘管理' },
        component: () => import('@/views/storage/StorageManager.vue'),
      },
      {
        path: 'backup',
        name: 'StorageBackup',
        meta: { title: '备份还原' },
        component: () => import('@/views/backup/SystemBackup.vue'),
      },
    ],
  },
]
