# 模块概述

> 版本: v1.0 | 日期: 2026-04-25

## 模块依赖关系

```
                    ┌─────────────┐
                    │  Web GUI    │
                    └──────┬──────┘
                           │ HTTP
                    ┌──────▼──────┐
                    │  REST API   │
                    └──────┬──────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐    ┌──────▼──────┐    ┌───────▼──────┐
│  Network    │    │  Firewall   │    │  Routing     │
│  Manager    │    │  Manager    │    │  Manager     │
└──────┬──────┘    └──────┬──────┘    └──────┬───────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                   ┌──────▼──────┐
                   │  Config     │
                   │  Engine     │
                   └──────┬──────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
┌──────▼──────┐    ┌─────▼───────┐   ┌──────▼──────┐
│  DHCP/DNS   │    │    VPN      │   │  System     │
│  Manager    │    │  Manager    │   │  Monitor    │
└─────────────┘    └─────────────┘   └─────────────┘


       ┌──────────────────────────────────────────┐
       │           App Store Engine               │
       │     (应用模板仓库 / 安装/更新/卸载编排)     │
       └───────────────┬──────────────────────────┘
                       │ 调用
           ┌───────────┼───────────┐
           │                       │
    ┌──────▼──────┐        ┌──────▼──────┐
    │  Container  │        │     VM      │
    │  Manager    │        │  Manager    │
    │ (Docker/    │        │ (libvirt/   │
    │  Compose)   │        │  KVM)       │
    └──────┬──────┘        └──────┬──────┘
           │                      │
           └──────────┬───────────┘
                      │ 依赖
               ┌──────▼──────┐
               │  Network    │
               │  Manager    │
               │ (网桥/macvlan│
               │  /VFIO)     │
               └─────────────┘
```

## 各模块职责与边界

### Installer & Initializer

| 属性 | 说明 |
|------|------|
| **职责** | 多模式安装（ISO/apt/镜像）+ 首次启动网络自动初始化 |
| **触发条件** | `/etc/ubunturouter/config.yaml` 不存在时自动运行初始化 |
| **依赖** | 无（最先运行的模块） |
| **关键接口** | `detect_nics()`, `auto_assign_roles()`, `generate_initial_config()`, `apply_initial_config()` |
| **边界** | 仅在首次启动时运行，初始化完成后退出；后续配置由 Configuration Engine 管理 |

### Configuration Engine (Core)

| 属性 | 说明 |
|------|------|
| **职责** | 统一配置的解析、校验、Diff、生成、原子Apply、回滚 |
| **输入** | `/etc/ubunturouter/config.yaml` |
| **输出** | 各子系统原生配置文件 |
| **依赖** | 无（最底层模块） |
| **被依赖** | 所有 Manager 模块 |
| **关键接口** | `validate()`, `diff()`, `generate()`, `apply()`, `rollback()` |
| **数据存储** | 配置快照 `/var/lib/ubunturouter/snapshots/` |

### Network Manager

| 属性 | 说明 |
|------|------|
| **职责** | 接口/VLAN/桥接/Bonding 管理 |
| **后端** | netplan → `/etc/netplan/01-ubunturouter.yaml` |
| **依赖** | Configuration Engine |
| **关键接口** | `list_interfaces()`, `configure_interface()`, `apply_network()` |
| **边界** | 不处理防火墙规则（由 Firewall Manager 负责） |

### Firewall Manager

| 属性 | 说明 |
|------|------|
| **职责** | Zone 防火墙、NAT、端口转发、自定义规则 |
| **后端** | nftables → `/etc/nftables.d/ubunturouter.conf` |
| **依赖** | Configuration Engine, Network Manager（获取接口zone映射） |
| **关键接口** | `list_zones()`, `add_rule()`, `add_port_forward()`, `apply_firewall()` |
| **边界** | 不管理接口IP（由 Network Manager 负责） |

### Routing Manager

| 属性 | 说明 |
|------|------|
| **职责** | 静态路由、策略路由、Multi-WAN、FRR动态路由 |
| **后端** | ip route/rule + FRR |
| **依赖** | Configuration Engine, Network Manager |
| **关键接口** | `list_routes()`, `add_route()`, `configure_multiwan()`, `apply_routing()` |
| **边界** | 不管理NAT（由 Firewall Manager 负责） |

### DHCP/DNS Manager

| 属性 | 说明 |
|------|------|
| **职责** | DHCP地址分配、DNS缓存解析、广告过滤 |
| **后端** | dnsmasq/Kea + Unbound + AdGuard Home |
| **依赖** | Configuration Engine, Network Manager |
| **关键接口** | `list_leases()`, `add_static_lease()`, `configure_dns()`, `apply_dhcp_dns()` |
| **边界** | 不管理接口IP（由 Network Manager 负责） |

### VPN Manager

| 属性 | 说明 |
|------|------|
| **职责** | WireGuard/IPSec 隧道管理、客户端配置生成 |
| **后端** | WireGuard (wg-quick) + strongSwan |
| **依赖** | Configuration Engine, Firewall Manager（自动开放端口） |
| **关键接口** | `list_tunnels()`, `add_peer()`, `generate_client_config()`, `apply_vpn()` |
| **边界** | 不管理防火墙规则（由 Firewall Manager 自动处理） |

### REST API

| 属性 | 说明 |
|------|------|
| **职责** | 对外提供配置CRUD、状态查询、WebSocket推送 |
| **后端** | FastAPI + uvicorn |
| **依赖** | 所有 Manager 模块 |
| **关键接口** | RESTful CRUD endpoints, `/api/v1/...` |
| **边界** | 不直接操作系统配置，全部通过 Manager 层 |

### VM Manager

| 属性 | 说明 |
|------|------|
| **职责** | 虚拟机生命周期管理、资源分配、VFIO直通、noVNC代理 |
| **后端** | libvirt (Python bindings) + QEMU/KVM |
| **依赖** | App Store Engine (模板来源), Network Manager (网桥/vfio) |
| **关键接口** | `list_vms()`, `create_vm()`, `start_vm()`, `vm_console_url()`, `attach_vfio()` |
| **边界** | 不管理容器（由 Container Manager 负责） |
| **可选** | ARM 平台无 KVM 支持时此模块降级为不可用 |

### Container Manager

| 属性 | 说明 |
|------|------|
| **职责** | Docker 容器和 Compose 项目的可视化管理 |
| **后端** | Docker Engine API (Unix Socket) |
| **依赖** | App Store Engine (compose 文件来源), Network Manager (macvlan) |
| **关键接口** | `list_containers()`, `compose_up()`, `compose_down()`, `container_logs()`, `container_exec()` |
| **边界** | 不管理 VM（由 VM Manager 负责） |
| **存储** | `/var/lib/ubunturouter/apps/{app-name}/` |

### App Store Engine

| 属性 | 说明 |
|------|------|
| **职责** | 应用模板仓库管理，编排容器/VM 应用的安装/更新/卸载 |
| **后端** | Git (仓库同步) + YAML (manifest) |
| **依赖** | Container Manager (容器应用), VM Manager (VM应用) |
| **关键接口** | `list_apps()`, `search_apps()`, `install_app()`, `update_app()`, `uninstall_app()`, `add_repo()` |
| **边界** | 不直接操作 Docker/libvirt，通过 Container/VM Manager 执行 |
| **存储** | `/var/lib/ubunturouter/appstore/` (仓库缓存+已安装应用元数据) |

### Traffic Orchestrator

| 属性 | 说明 |
|------|------|
| **职责** | 设备识别、应用识别、可视化编排、规则编译下发到各通道 |
| **依赖** | Configuration Engine (规则)，Network Manager (设备跟踪) |
| **关键接口** | `list_devices()`, `list_apps()`, `set_orchestration()`, `get_flow_stats()`, `list_tunnels()` |
| **内部组件** | Device Detector, App Detector, Rule Compiler, Tunnel Manager |
| **边界** | 不直接管理 VPN/代理通道本身，只编排流量到已有通道 |

### Web GUI & Auth

| 属性 | 说明 |
|------|------|
| **职责** | 用户交互界面、系统 PAM 鉴权、三段式 Dashboard、实时状态展示 (WebSocket) |
| **后端** | Vue3 + Element Plus + Leaflet.js (地图) |
| **依赖** | REST API, Auth Manager (PAM), WebSocket Stream |
| **关键接口** | `/login` (POST), `/ws/dashboard` (WebSocket), `GET /api/v1/dashboard/status` |
| **认证方式** | 系统 PAM 认证 (python-pam)，JWT Token 管理 Session |
| **三个面板** | ① 网络与系统状态 (拓扑图+地图+代理通道) ② 设备运行状态 (CPU/内存/磁盘) ③ 应用与服务运营状态 (应用卡片) |
| **边界** | 不直接访问系统，所有数据通过 API/WebSocket 获取 |

### Auth Manager

| 属性 | 说明 |
|------|------|
| **职责** | 登录认证、Session 管理、登录保护、权限控制 |
| **后端** | PAM (Pluggable Authentication Modules) + JWT |
| **依赖** | 无（所有模块共用 Auth） |
| **关键接口** | `login(username, password) -> JWT`, `validate_token(token) -> user`, `logout(session_id)` |
| **Session 存储** | JWT payload 中存储 username + session_id，服务端维护 session 黑名单 |
