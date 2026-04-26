# Sprint 5: 应用市场 + 容器管理

> 周期: 当前迭代 | 状态: 进行中 | 负责人: Profile Tech

---

## 范围

UbuntuRouter 应用市场核心功能：Docker 容器管理 API、Compose 项目管理、应用仓库同步、一键安装/更新/卸载流程、应用市场前端页面。

## 模块结构

```
ubunturouter/
├── container/          ← NEW: Docker/Compose 管理器
│   ├── __init__.py
│   ├── docker.py       # Docker Engine API 封装
│   └── compose.py      # Compose 项目管理
├── appstore/           ← NEW: 应用市场引擎
│   ├── __init__.py
│   ├── engine.py       # Manifest 解析 + 应用目录树
│   ├── repo.py         # 仓库同步 (git)
│   ├── installer.py    # 安装编排
│   └── updater.py      # 更新/卸载
├── api/routes/
│   ├── containers.py   ← NEW: 容器 API
│   └── appstore.py     ← NEW: 应用市场 API
└── web/src/views/
    ├── containers/      ← NEW: 容器管理页面
    └── appstore/        ← NEW: 应用市场页面
```

## 技术架构

```
┌─────────────────────────────┐
│  App Store Engine           │
│  ┌──────────┐ ┌──────────┐  │
│  │ repo.py  │ │engine.py │  │  Manifest: app.yaml
│  │ 同步仓库 │ │解析manifest│  │  ├── name/version
│  └────┬─────┘ └────┬─────┘  │  ├── compose: docker-compose.yml
│       │            │        │  ├── env_vars
│       ▼            ▼        │  ├── ports
│  ┌──────────────────────┐   │  ├── volumes
│  │    installer.py      │   │  └── icon/screenshots
│  │  预检→compose up     │   │
│  └──────────┬───────────┘   │  应用仓库结构:
│             │               │  /opt/ubunturouter/apps/
│             ▼               │  ├── repos/          ← git clone 的仓库
│  ┌──────────────────────┐   │  │   └── official/
│  │ Container Manager    │   │  │       ├── adguard-home/
│  │ docker.py/compose.py │   │  │       │   ├── app.yaml
│  │                      │   │  │       │   └── docker-compose.yml
│  │  docker SDK → Docker │   │  │       └── ...
│  │  compose → subprocess│   │  └── installed/      ← 软链接到安装的应用
│  └──────────────────────┘   │      ├── adguard-home -> ../repos/official/adguard-home
└─────────────────────────────┘
```

## API 设计

### 容器管理 (`/api/v1/containers`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 容器列表 |
| GET | `/{id}` | 容器详情 |
| POST | `/{id}/start` | 启动容器 |
| POST | `/{id}/stop` | 停止容器 |
| POST | `/{id}/restart` | 重启容器 |
| DELETE | `/{id}` | 删除容器 |
| GET | `/{id}/logs` | 获取日志 |
| GET | `/compose` | Compose 项目列表 |
| POST | `/compose/up` | 部署 Compose 项目 |
| POST | `/compose/{name}/down` | 停止 Compose 项目 |
| GET | `/compose/{name}/logs` | Compose 项目日志 |

### 应用市场 (`/api/v1/appstore`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/apps` | 应用列表（支持搜索/分类筛选） |
| GET | `/apps/{id}` | 应用详情 |
| POST | `/apps/{id}/install` | 安装应用 |
| POST | `/apps/{id}/update` | 更新应用 |
| POST | `/apps/{id}/uninstall` | 卸载应用 |
| GET | `/installed` | 已安装应用列表 |
| POST | `/repo/sync` | 同步仓库 |
| GET | `/repo/status` | 同步状态 |
| POST | `/repo/add` | 添加第三方仓库 |

## 数据流: 应用安装

```
用户点击"安装" 
  → POST /appstore/apps/{id}/install
  → installer.precheck()  # 检查端口/目录冲突
  → installer.install()   # create symlink → compose up -d
  → WebSocket 推送进度    # 步骤: 拉镜像→创建网络→启动→健康检查
  → 返回 200 + installed 状态
```

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| S5-01 | Docker 容器启动/停止/删除 | docker ps + API |
| S5-02 | Compose 项目部署 | docker compose ps |
| S5-03 | 应用市场浏览/搜索 | 页面验证 |
| S5-04 | 一键安装容器应用 | 安装完成后容器运行 |
| S5-05 | 应用更新 | 版本号变化 |
| S5-06 | 应用卸载（保留数据） | 容器删除，数据目录存在 |
| S5-07 | 安装进度条 | 页面实时显示 |
| S5-08 | 第三方应用源添加 | 新源应用列表可见 |
