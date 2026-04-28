// 流量编排模块路由
export default [
  {
    path: 'orchestrator',
    meta: { title: '流量编排', icon: 'Switch', module: 'orchestrator' },
    component: () => import('@/layouts/ModuleLayout.vue'),
    children: [
      {
        path: 'canvas',
        name: 'OrchestratorCanvas',
        meta: { title: '编排画板' },
        component: () => import('@/views/orchestrator/OrchestratorCanvas.vue'),
      },
    ],
  },
]
