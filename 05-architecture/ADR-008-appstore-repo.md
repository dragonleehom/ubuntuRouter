# ADR-008: Git 仓库 vs OCI Registry vs HTTP 静态文件 (应用市场格式)

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 的应用市场需要通过一种分发机制让用户发现和安装应用。候选方案：

- **Git 仓库**: 应用模板存储在 Git 仓库中，App Store Engine 定期 git pull 同步
- **OCI Registry**: 使用容器镜像仓库（如 Docker Hub）分发应用
- **HTTP 静态文件**: 简单的 JSON/YAML 索引 + 文件下载

## 决策

**主分发机制使用 Git 仓库。每个应用是一个目录，包含 manifest.yaml + docker-compose.yml + icon 等文件。App Store Engine 通过 `git clone/pull` 同步仓库。官方仓库托管在 GitHub 上，支持第三方 Git 仓库作为额外源。**

## 理由

### 正向因素（支持 Git 仓库）

| 因素 | 权重 | 说明 |
|------|------|------|
| **版本控制** | 高 | 每次更新有 Git commit 记录，可追溯、可回滚 |
| **PR 协作** | 高 | 社区可直接提交 PR 添加新应用，审核流程自然 |
| **文件多样性** | 高 | 应用模板包含 manifest.yaml (描述) + docker-compose.yml (部署) + icon.png (图标) + .env (环境变量模板)，Git 比 Registry 更适合多文件场景 |
| **离线可用** | 高 | clone 到本地后，App Store Engine 在无网络时也可浏览已缓存的应用 |
| **分叉能力** | 中 | 用户可 fork 官方仓库并添加自己的应用 |
| **增量同步** | 中 | `git fetch` + `git diff` 比 HTTP 的完整拉取更高效 |
| **第三方源** | 高 | 用户可添加任意 Git 仓库 URL 作为第三方应用源 |

### 不使用 OCI Registry

| 因素 | 说明 |
|------|------|
| **元数据限制** | OCI Registry 的 manifest 不适合存储多文件（图标、截图、docker-compose.yml） |
| **浏览发现** | Registry 没有分类浏览、搜索等发现功能，需要额外的目录服务 |
| **社区门槛** | 提交应用需要容器镜像知识，PR 到 Git 仓库更简单 |

### 不使用 HTTP 静态文件

| 因素 | 说明 |
|------|------|
| **无版本控制** | 无法追溯变更历史 |
| **更新通知** | 需要额外的轮询逻辑检查更新 |
| **社区协作** | 没有 PR 流程 |

## 影响

### 正面

- 社区贡献者只需在 GitHub 上提 PR，门槛最低
- 第三方应用源 = Git URL，用户能用自己的 Git 仓库
- 仓库结构清晰，应用分类通过目录层级实现

### 负面

- 初次 clone 需要网络（但这是必需的）
- 大仓库（1000+ 个应用）的 `git clone` 耗时较长，可通过稀疏 checkout 优化

## 仓库结构

```
ubunturouter-apps/repo-index.yaml    # 仓库根索引（必需）
ubunturouter-apps/
├── repo-index.yaml                  # 仓库根索引
│
├── smart-home/                      # 分类目录
│   ├── homeassistant/               # 应用目录
│   │   ├── manifest.yaml            # 应用描述（必需）
│   │   ├── docker-compose.yml       # Compose 文件（容器应用必需）
│   │   ├── icon.png                 # 应用图标（推荐 256x256）
│   │   ├── screenshot-1.png         # 截图（可选）
│   │   ├── .env.example             # 环境变量模板（可选）
│   │   └── README.md                # 说明文档（可选）
│   │
│   └── zigbee2mqtt/
│       └── ...                      # 同上结构
│
├── media-center/
│   ├── plex/
│   │   └── ...
│   └── jellyfin/
│       └── ...
│
├── network-tools/
│   ├── adguardhome/
│   │   └── ...
│   ├── clash/
│   │   └── ...
│   └── frp/
│       └── ...
│
└── virtual-system/
    ├── openwrt/
    │   ├── manifest.yaml
    │   └── template.yaml            # VM 模板（VM 应用特需）
    └── windows/
        └── ...
```

## 实施要点

1. 仓库索引文件 `repo-index.yaml` 包含应用列表、分类、版本摘要，用于快速浏览
2. 首次同步使用 `git clone --depth 1`（仅最新版本）加速
3. 后续同步使用 `git fetch origin + git reset --hard origin/main`
4. 同步操作在后台异步运行（ubunturouter-appstore.service），不影响 Web GUI 响应
5. 默认官方仓库 URL 可在配置中自定义
6. 第三方仓库通过 `appstore.repositories` 配置添加
