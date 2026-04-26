# Sprint 2: REST API + Auth + Dashboard 基础

> 周期: 第 4-6 周 | 状态: 待开始 | 负责人: TBD

---

## 范围

在配置引擎之上搭建 REST API 服务，实现系统 PAM 鉴权，以及 Dashboard 基础的三面板展示。

## 任务拆解

### Week 4: FastAPI 骨架 + Auth

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 4.1 | FastAPI 应用骨架：uvicorn + 路由注册 + 中间件 | 4 | Sprint 1 | `ubunturouter/api/main.py` |
| 4.2 | PAM 认证模块：Python PAM 绑定 | 6 | 4.1 | `ubunturouter/api/auth/pam.py` |
| 4.3 | JWT Token 签发/验证/刷新 | 6 | 4.2 | `ubunturouter/api/auth/jwt.py` |
| 4.4 | 登录保护模块：失败计数 + IP 锁定 | 4 | 4.3 | `ubunturouter/api/auth/ratelimit.py` |
| 4.5 | Auth API 端点：login/logout/sessions/强制登出 | 8 | 4.3 | `ubunturouter/api/routes/auth.py` |
| 4.6 | HTTPS 支持：自签证书生成 + HTTP→301 重定向 | 4 | 4.1 | `ubunturouter/api/tls.py` |
| 4.7 | 单元测试：Auth 流程 | 6 | 4.5 | `tests/test_auth.py` |

### Week 5: Dashboard API + WebSocket

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 5.1 | Dashboard 全量状态 API：接口/WAN/系统/应用统计聚合 | 8 | 4.1 | `ubunturouter/api/routes/dashboard.py` |
| 5.2 | WebSocket 推送框架：4 种消息类型 + 频率控制 | 8 | 5.1 | `ubunturouter/api/ws/dashboard.py` |
| 5.3 | 接口 API：list/detect/status | 6 | Sprint 1 | `ubunturouter/api/routes/interfaces.py` |
| 5.4 | 系统 API：status/logs/backup/snapshots/upgrade | 12 | Sprint 1 | `ubunturouter/api/routes/system.py` |
| 5.5 | 配置 API：apply/rollback/list-snapshots | 6 | Sprint 1 | `ubunturouter/api/routes/config.py` |
| 5.6 | 集成测试：curl 验证所有 API 端点 | 8 | 5.5 | `tests/integration/test_api.sh` |

### Week 6: 前端 Dashboard 三面板

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 6.1 | Vue3 项目初始化：Vite + Vue Router + Pinia + Element Plus | 4 | - | `web/` 目录 |
| 6.2 | 登录页面 + JWT 存储 + Axios 拦截器 | 8 | 6.1 + Auth API | `web/src/views/Login.vue` |
| 6.3 | 页面框架: 侧边栏 + 顶部状态栏 + 内容区 | 6 | 6.2 | `web/src/layouts/MainLayout.vue` |
| 6.4 | Dashboard 面板一: 网络拓扑 + 通道状态 + 流量仪表 | 12 | 6.3 + Dashboard API | `web/src/views/dashboard/NetworkPanel.vue` |
| 6.5 | Dashboard 面板二: CPU/内存/磁盘/网口/运行时间 | 8 | 6.3 | `web/src/views/dashboard/SystemPanel.vue` |
| 6.6 | Dashboard 面板三: 应用卡片 + 状态/流量/快捷操作 | 10 | 6.3 | `web/src/views/dashboard/AppPanel.vue` |
| 6.7 | WebSocket 集成：实时数据推送→Pinia store→组件更新 | 8 | 6.4 + WS API | `web/src/stores/dashboardStore.js` |
| 6.8 | E2E 测试：Playwright 验证 Dashboard 加载和实时更新 | 8 | 6.7 | `web/e2e/dashboard.spec.ts` |

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S2-01 | HTTP 自动重定向到 HTTPS | curl -L http://... |
| S2-02 | 系统账号登录 Web GUI 成功 | 浏览器/curl |
| S2-03 | 错误密码 5 次后锁定 | curl 连续请求 |
| S2-04 | JWT 过期后自动跳转登录 | 手动修改 Token |
| S2-05 | Dashboard 三面板完整加载 | Playwright screenshot |
| S2-06 | WebSocket 实时推送 2s/10s/30s | 开发者工具 WS 验证 |
| S2-07 | 接口 API 返回实时状态 | curl 验证 |
| S2-08 | 系统 API 返回配置/日志/快照 | curl 验证 |
| S2-09 | 配置 API apply 后系统变更 | curl + 命令行验证 |
