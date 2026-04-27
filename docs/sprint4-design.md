# Sprint 4: Docker管理增强 — 设计说明

> 日期: 2026-04-27 | 状态: 实现

## 设计原则（从业界最佳实践提炼）

1. **稳定可靠** — subprocess > docker-py（无版本兼容问题），超时保护每个操作
2. **易用性** — 容器Web终端、一键"打开"应用UI、实时日志流
3. **扩展性** — 分层设计（API→Manager→CLI），添加新docker命令只需加一行
4. **灵活** — 支持创建容器、镜像管理、Compose全生命周期

## 新增功能一览

### 后端 API 增强（在现有 containers.py + container/__init__.py 基础上增强）

| 功能 | API | 说明 |
|------|-----|------|
| 容器创建 | `POST /containers/create` | 从镜像创建容器（名称/端口映射/环境变量/挂载/网络） |
| 容器详情 | `GET /containers/{id}/inspect` | 完整 inspect 信息 |
| 容器终端 | `POST /containers/{id}/exec` | 在容器中执行命令 |
| 实时日志 | `GET /containers/{id}/logs/stream` | SSE 实时日志流 |
| 镜像删除 | `DELETE /containers/images/{id}` | 删除本地镜像 |
| 镜像详情 | `GET /containers/images/{id}/inspect` | 镜像层信息 |
| 应用打开 | `GET /containers/app-open` | 检测容器的 Web UI 地址 |
| Compose up | `POST /containers/compose/{name}/up` | 部署 Compose 项目 |
| Compose down | `POST /containers/compose/{name}/down` | 停止 Compose 项目 |
| Compose 详情 | `GET /containers/compose/{name}/inspect` | Compose 配置 |

### 前端增强

| 功能 | 位置 | 说明 |
|------|------|------|
| 镜像管理标签页 | ContainerManager.vue | 新增 Images 标签页，列表+删除+详情 |
| 容器"打开"按钮 | 容器行操作 | 检测端口一键打开 Web UI |
| 容器终端按钮 | 容器行操作 | 打开弹窗执行命令 |
| 实时日志 | 容器行操作 | 替换现有弹窗为实时流 |
| 容器创建 | 工具栏 | 从镜像创建新容器 |

## 实现清单（按顺序）

### Task 1: 后端 — ContainerManager 增强
- `container/__init__.py` — 新增方法
  - `create_container(image, name, ports, env, volumes, network)` 
  - `exec_run(container_id, cmd)` — 执行命令返回输出
  - `exec_start(container_id, exec_id)` — attach到已创建的exec（用于WebSocket终端）
  - `remove_image(image_id, force)`
  - `inspect_image(image_id)`
  - `prune_images()` — 清理无用镜像
  - `get_app_url(container_id)` — 检测容器暴露的HTTP端口

### Task 2: 后端 — API 路由增强
- `api/routes/containers.py` — 新增端点
  - `POST /containers/create`
  - `DELETE /containers/images/{image_id}`
  - `POST /containers/images/prune`
  - `GET /containers/images/{image_id}/inspect`
  - `POST /containers/{id}/exec`
  - `GET /containers/{id}/inspect`
  - `GET /containers/{id}/logs/stream` — SSE
  - `GET /containers/app-open` — 扫描可打开的 Web 应用

### Task 3: 前端 — ContainerManager 重写
- 重构为三标签页：容器列表 / 镜像管理 / Compose项目
- 新增容器创建对话框
- 每行增加：终端按钮、打开按钮、详情按钮
- 日志改为实时流

### Task 4: 前端 — 终端弹窗组件
- 简单的命令执行弹窗（非WebSocket TTY）
- 输入命令 → 执行 → 显示输出

### Task 5: 前端 — App Open 功能
- 扫描所有运行容器暴露的HTTP端口
- 显示"打开"按钮直链到容器Web UI
