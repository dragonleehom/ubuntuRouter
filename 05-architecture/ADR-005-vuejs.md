# ADR-005: Vue3 vs React vs Svelte (前端框架)

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 需要一个现代 Web GUI，用于 Dashboard、配置管理、应用市场等交互。候选方案：

- **Vue3 + Element Plus**（国内社区主流）
- **React + Ant Design**（全球最主流）
- **Svelte + Skeleton**（新兴轻量方案）

## 决策

**采用 Vue3 + Element Plus 作为前端框架。Vite 作为构建工具，Pinia 作为状态管理。**

## 理由

### 正向因素（支持 Vue3）

| 因素 | 权重 | 说明 |
|------|------|------|
| **Element Plus 管理组件** | 高 | Element Plus 的表单、表格、对话框、树控件等管理界面组件成熟完善 |
| **中文社区** | 高 | 目标用户群在中国，Vue3 中文文档和社区活跃度最高 |
| **学习曲线** | 中 | Vue3 的 `setup` 语法对中小型团队友好 |
| **性能** | 中 | Vue3 的虚拟 DOM 优化 + Vite HMR 开发体验优秀 |
| **Leaflet 集成** | 中 | Dashboard 地图组件（Leaflet.js）与 Vue3 集成良好 |
| **ECharts 集成** | 高 | 流量仪表/CPU/内存图使用 ECharts，Vue3 的 `vue-echarts` 直接可用 |

### 反向因素（不使用 React）

| 因素 | 说明 |
|------|------|
| **Ant Design Pro** | 虽然 React + Ant Design 很成熟，但路由器管理界面不需要 Pro 级的企业功能 |
| **JSX 学习曲线** | 在国内开发者群体中，Vue 的模板语法比 JSX 更容易上手 |
| **国际化需求** | Vue3 + vue-i18n 对中英文切换支持良好 |

## 影响

### 正面

- Element Plus 的 Table/Form/Dialog 组件直接匹配管理界面的 CRUD 需求
- Vue Router 的嵌套路由与侧边栏导航天然耦合
- Pinia 的 store 模式适合管理 Dashboard 的 WebSocket 实时数据状态
- Vite 的按需编译让开发体验极快

### 负面

- 如果后续需要引入复杂的拖拽编排功能，Vue3 的拖拽库（vuedraggable）成熟度略低于 React（react-dnd）
- 全球社区的组件库丰富度 React > Vue

## 组件选型矩阵

| 需求 | 选型 | 说明 |
|------|------|------|
| UI 组件库 | Element Plus | 表格/表单/对话框/页面布局 |
| 状态管理 | Pinia | WebSocket 数据流、用户 Session |
| 路由 | Vue Router | 侧边栏导航对应嵌套路由 |
| 构建工具 | Vite | HMR 速度快，打包小 |
| 图表 | ECharts (vue-echarts) | 流量折线图/饼图/柱状图 |
| 地图 | Leaflet.js | Dashboard 网络拓扑地图 |
| 拖拽 | vuedraggable | 流量编排画布 |
| HTTP 客户端 | Axios | REST API 调用 |
| WebSocket | 原生 WebSocket | 实时 Dashboard 推送 |
| i18n | vue-i18n | 中文/英文 |
| 代码检查 | ESLint + Prettier | 代码规范 |

## 实施要点

1. 目录结构：`/src/pages/`（页面）/ `/src/components/`（组件）/ `/src/stores/`（Pinia）/ `/src/api/`（Axios）
2. 主题：Element Plus 默认主题，用 CSS 变量微调配色管理器风格
3. 布局：侧边栏导航 + 顶部状态栏 + 内容区域
4. Dashboard 使用 WebSocket 接收实时数据，每 2s 推送流量更新
5. 首次加载使用 REST API 获取全量数据，之后 WebSocket 增量更新
