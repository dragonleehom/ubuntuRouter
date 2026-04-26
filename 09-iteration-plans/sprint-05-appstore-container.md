# Sprint 5: 应用市场 + 容器管理

> 周期: 第 12-14 周 | 状态: 待开始 | 负责人: TBD

---

## 范围

实现应用市场的核心功能：容器管理 API、应用仓库同步、一键安装/更新/卸载流程、应用市场和管理页面。

## 任务拆解

### Week 12: 容器管理 API

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 12.1 | Docker Engine API 封装：容器/镜像/网络/卷 CRUD | 10 | - | `ubunturouter/container/docker.py` |
| 12.2 | Compose 项目管理：compose up/down/logs/ps | 8 | 12.1 | `ubunturouter/container/compose.py` |
| 12.3 | 容器 API：列表 / 生命周期 / 日志流 / 终端 | 10 | 12.1 | `ubunturouter/api/routes/containers.py` |
| 12.4 | 容器 Web 页面：容器列表 + 启动/停止 + 日志 + 终端 | 12 | 12.3 + 6.3 | `web/src/views/containers/` |
| 12.5 | 集成测试：Docker 容器 CRUD | 6 | 12.4 | `tests/integration/test_containers.sh` |

### Week 13: 应用市场引擎

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 13.1 | App Store Engine：manifest 解析 + 应用目录树扫描 | 8 | - | `ubunturouter/appstore/engine.py` |
| 13.2 | 仓库同步：git clone/pull + 索引更新 | 6 | 13.1 | `ubunturouter/appstore/repo.py` |
| 13.3 | 应用安装编排：解析 manifest → 预检 → compose up | 10 | 13.1 + 12.2 | `ubunturouter/appstore/installer.py` |
| 13.4 | 应用更新流程：备份 → 拉取新镜像 → 重建 | 8 | 13.3 | `ubunturouter/appstore/updater.py` |
| 13.5 | 应用市场 API：apps list/detail/install/update/uninstall/repo | 12 | 13.3 | `ubunturouter/api/routes/appstore.py` |
| 13.6 | 集成测试：应用完整生命周期 (安装→更新→卸载) | 8 | 13.5 | `tests/integration/test_appstore.sh` |

### Week 14: 应用市场 Web 页面

| ID | 任务 | 预估(h) | 前置 | 产出 |
|----|------|---------|------|------|
| 14.1 | 应用市场首页：分类浏览 + 搜索 + 应用卡片 | 10 | 13.5 + 6.3 | `web/src/views/appstore/` |
| 14.2 | 应用详情页：描述 + 截图 + 配置参数 + 安装按钮 | 8 | 14.1 | `web/src/views/appstore/AppDetail.vue` |
| 14.3 | 安装配置表单：环境变量 / 端口映射 / 存储路径 | 8 | 14.2 | `web/src/views/appstore/InstallForm.vue` |
| 14.4 | 已安装应用管理页：列表 + 状态 + 配置编辑 + 备份 | 10 | 13.5 | `web/src/views/appstore/InstalledApps.vue` |
| 14.5 | 安装进度条 + 安装完成入口 | 4 | 14.3 | `web/src/components/InstallProgress.vue` |
| 14.6 | 应用市场 WebSocket：安装进度实时推送 | 6 | 14.5 + 5.2 | `web/src/stores/appstoreStore.js` |
| 14.7 | E2E 测试：应用市场完整流程 | 10 | 14.6 | `web/e2e/appstore.spec.ts` |

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S5-01 | Docker 容器启动/停止/删除 | docker ps |
| S5-02 | Compose 项目部署 | docker compose ps |
| S5-03 | 应用市场浏览/搜索 | 页面验证 |
| S5-04 | 一键安装容器应用 | 安装完成后容器运行 |
| S5-05 | 应用更新 | 版本号变化 |
| S5-06 | 应用卸载（保留数据） | 容器删除，数据目录存在 |
| S5-07 | 安装进度条 | 页面实时显示 |
| S5-08 | 第三方应用源添加 | 新源应用列表可见 |
