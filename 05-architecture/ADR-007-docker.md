# ADR-007: Docker vs Podman vs LXC (容器运行时)

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 的应用市场需要容器运行时来部署 AdGuard Home、Home Assistant 等容器化应用。候选方案：

- **Docker Engine + Docker Compose**: 最成熟的容器方案
- **Podman + Podman Compose**: 无守护进程，Rootless
- **LXC/LXD**: 系统容器，更接近 VM

## 决策

**主容器运行时使用 Docker Engine + Docker Compose。AdGuard Home 等内置路由服务也通过 Docker Compose 管理。**

## 理由

### 正向因素（支持 Docker）

| 因素 | 权重 | 说明 |
|------|------|------|
| **生态成熟** | 高 | 应用市场要安装的应用（Home Assistant, Plex, Pi-hole 等）官方镜像均为 Docker 格式 |
| **Compose 规范** | 高 | Docker Compose 是事实上的容器编排标准，应用市场模板直接使用 `docker-compose.yml` |
| **Docker API** | 高 | Python 通过 `docker-py` 直接操作 Docker API，Container Manager 无需封装子进程 |
| **日志流** | 高 | `docker logs --follow` 的 WebSocket 转发实现简单 |
| **macvlan 支持** | 高 | Docker 的 macvlan 网络驱动使容器获得 LAN 独立 IP |
| **社区镜像** | 高 | 大部分镜像的 Dockerfile 格式成熟，部署文档随处可见 |

### 不使用 Podman

| 因素 | 说明 |
|------|------|
| **Compose 成熟度** | Podman Compose 仍不如 Docker Compose 稳定 |
| **macvlan 支持** | Podman 的 macvlan 网络配置不如 Docker 直观 |
| **生态兼容性** | 某些 Docker-only 镜像（需 `--privileged` 或特定 `cap_add`）在 Podman 下有兼容问题 |
| **API 兼容** | Docker API 是标准，但 Podman 的兼容层有细微差异 |

### 不使用 LXC

| 因素 | 说明 |
|------|------|
| **应用市场适配** | LXC 需要单独的 image 管理（非 Docker Hub），应用市场模板需要额外适配 |
| **密度** | LXC 系统容器 vs Docker 应用容器，Docker 更适合"一个应用一个容器"的模式 |
| **网络集成** | Docker 的 macvlan/bridge 网络与 UbuntuRouter 的网络模型更易集成 |

## 影响

### 正面

- 应用市场模板直接使用标准 `docker-compose.yml`，开发者无需学习新格式
- Container Manager 通过 `docker-py` 调用 Docker API，代码简洁
- Docker Hub 的镜像可用性最广

### 负面

- Docker 守护进程占用 ~100MB 内存（但路由器内存充裕 + 仅按需启动）
- Docker 守护进程以 root 运行（与容器逃逸风险相关，但路由器本就是单用户系统）
- 系统升级时需注意 Docker 的版本兼容性

## 关于 Docker 在软路由上的讨论

```
"Docker 占资源" 的担忧:
  - Docker daemon idle: ~60MB RAM（可通过 `docker system prune` 优化）
  - 比裸机跑服务多 ~5% 的 CPU 开销（网络层多一层 bridge）
  - 但换取的是：应用独立的更新/回滚/隔离能力

"路由器上不需要 Docker" 的观点:
  - 传统路由器（OpenWrt）确实不需要 Docker
  - 但 UbuntuRouter 的定位是"全能路由平台"，不是纯路由器
  - Docker 是扩展能力的基石

结论:
  - Docker 不是必须安装的（安装模式可选）
  - 当用户需要应用市场功能时，Docker 是最合适的选择
  - 纯路由模式可以完全不用 Docker
```

## 实施要点

1. Docker 不作为硬依赖：最小安装模式不安装 Docker
2. 标准/完整安装模式自动安装 Docker Engine（来自 Ubuntu 官方源）
3. 应用市场已安装的应用存储在 `/var/lib/ubunturouter/apps/{app-name}/docker-compose.yml`
4. 内置路由服务（AdGuard Home）也走 Docker Compose
5. 提供镜像加速源配置（registry-mirrors），解决国内拉取慢的问题
6. `docker compose` CLI 使用 Compose V2 插件
