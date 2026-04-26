# 高阶设计文档 (HLD)

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿

## 1. 项目定位与目标

**项目名称**：UbuntuRouter — 基于 Ubuntu Linux 的现代软路由框架

**核心目标**：
1. 将 Ubuntu Server 从"能做路由"提升到"开箱即用的软路由"
2. 统一管理分散的网络子系统
3. 提供 Web GUI 降低使用门槛
4. 保持 Ubuntu 生态的全部扩展能力

**设计原则**：
- **声明式配置**：所有网络配置以 YAML 声明，Git 友好
- **不可变基础设施**：配置变更原子化，支持回滚
- **容器化服务**：DNS/DHCP/广告拦截等以容器运行，与核心路由解耦
- **模块化**：核心转发不依赖 Web UI，即使 UI 挂掉路由仍正常
- **最小权限**：各服务以独立用户运行，仅授予必要的 capabilities

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                       Web GUI (Vue3)                             │
│      Dashboard / 路由管理 / 应用市场 / VM管理 / 容器管理           │
├──────────────────────────────────────────────────────────────────┤
│                      REST API Layer (FastAPI)                     │
│          认证 / 配置CRUD / 状态查询 / WebSocket 推送              │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ Network  │ Firewall │ Routing  │  DHCP/   │   VPN    │  App     │
│ Manager  │ Manager  │ Manager  │ DNS Mgr  │  Manager │  Store   │
├──────────┴──────────┴──────────┴──────────┴──────────┤    │     │
│              Configuration Engine (Core)               │    │     │
│         声明式 YAML → 各子系统配置的转换引擎           │    │     │
│         校验 / Diff / 生成 / 原子Apply / 回滚          │    │     │
├───────────────────────────────────────────────────────┼────┼─────┤
│                    OS Abstraction Layer                │    │     │
│   netplan │ nftables │ FRR │ dnsmasq │ WireGuard     │    │     │
├───────────────────────────────────────────────────────┼────┼─────┤
│                                                       │    │     │
│              路由核心层 (转发面)                        │    │     │
│         IP Forward │ VLAN │ Bridge │ TC │ XDP         │    │     │
│                                                       │    │     │
├───────────────────────────────┬───────────────────────┼────┼─────┤
│      VM Manager               │  Container Manager    │    │     │
│   libvirt/KVM │ noVNC         │  Docker │ Compose     │    │     │
│   VFIO │ QEMU                 │  macvlan │ cgroups    │    │     │
└───────────────────────────────┴───────────────────────┴────┘     │
                                                                   │
                              ┌────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   App Store Engine  │
                    │   应用模板仓库       │
                    │   安装/更新/卸载     │
                    │   ┌──────────────┐  │
                    │   │ 容器应用模板  │  │  → Docker Compose
                    │   │ VM应用模板   │  │  → libvirt XML + cloud-init
                    │   └──────────────┘  │
                    └────────────────────┘
```

**架构分层说明**：

1. **路由核心层**：纯内核转发，与 VM/容器无关，独立运行
2. **服务管理层**：VM Manager + Container Manager 独立于路由核心
3. **应用市场**：统一编排 VM 和容器，是 VM/Container Manager 的上层抽象
4. **关键设计**：路由核心崩溃不影响已运行的 VM/容器，反之亦然

## 3. 核心模块概述

### 3.1 Configuration Engine（配置引擎）

**职责**：统一配置文件的解析、校验、转换、应用、回滚

**关键设计**：
- 单一配置源：`/etc/ubunturouter/config.yaml`
- 配置版本化：每次变更生成快照，存储于 `/var/lib/ubunturouter/snapshots/`
- 转换引擎：将统一配置翻译为各子系统的原生配置
- 原子应用：先写入所有配置文件，再统一 reload 服务
- 回滚机制：apply 后启动连通性检测定时器，超时未确认则回滚至上一快照

**默认初始配置**（由安装器/初始化器自动生成）：

```yaml
system:
  hostname: router
  timezone: Asia/Shanghai

interfaces:
  # 多网口自动检测结果示例（2口机器）
  wan0:
    type: ethernet
    device: enp1s0          # 速率最低的网口
    role: wan
    ipv4:
      method: dhcp
    firewall:
      zone: wan
  lan0:
    type: bridge
    device: br-lan
    ports: [enp2s0]         # 其余网口
    role: lan
    ipv4:
      method: static
      address: 192.168.21.1/24   # 固定默认网关
    firewall:
      zone: lan

# 单网口模式（WANLAN）自动生成配置示例：
# interfaces:
#   wanlan0:
#     type: ethernet
#     device: enp1s0
#     role: wanlan              # 特殊角色：单口模式
#     ipv4:
#       method: static
#       address: 192.168.21.1/24
#     wan_uplink:
#       method: dhcp            # 通过同一网口的上行获取WAN IP
#     firewall:
#       zone: wanlan

dhcp:
  lan:
    interface: br-lan
    range: 192.168.21.50-192.168.21.200   # 固定默认DHCP池
    gateway: 192.168.21.1
    dns: [192.168.21.1]
    lease: 86400
```

**配置转换流程**：

```
config.yaml
    │
    ▼
┌──────────────────┐
│  Validate Schema │──→ 错误：返回详细校验信息
└────────┬─────────┘
         │
    ┌────▼────┐
    │  Diff   │──→ 计算变更集（新增/修改/删除）
    └────┬────┘
         │
    ┌────▼─────────────────────────────────────┐
    │  Generate                                │
    │  ├→ /etc/netplan/01-ubunturouter.yaml    │
    │  ├→ /etc/nftables.d/ubunturouter.conf    │
    │  ├→ /etc/frr/frr.conf (delta)            │
    │  ├→ /etc/dnsmasq.d/ubunturouter.conf     │
    │  └→ /etc/wireguard/wg0.conf             │
    └────┬─────────────────────────────────────┘
         │
    ┌────▼──────────┐
    │  Apply (原子)  │──→ 失败自动回滚
    │  systemctl ... │
    └────┬──────────┘
         │
    ┌────▼──────────┐
    │  Health Check │──→ 60s内无确认 → 自动回滚
    │  (连通性检测)  │
    └───────────────┘
```

### 3.2 Network Manager（网络管理）

**职责**：接口/VLAN/桥接/Bonding 管理

- 底层使用 netplan，生成 `/etc/netplan/01-ubunturouter.yaml`
- 支持 role 语义（wan/lan/dmz/guest），自动关联防火墙 zone
- 配置变更调用 `netplan apply`
- 内置连通性检测（60s 无确认自动回滚）

### 3.3 Firewall Manager（防火墙管理）

**职责**：防火墙规则管理，Zone 模型

- 底层使用 nftables，生成 `/etc/nftables.d/ubunturouter.conf`
- Zone 模型：wan / lan / dmz / guest / management
- 自动生成：NAT 规则、forward 规则、zone 间策略
- 支持端口转发（DNAT）、端口映射、自定义规则
- 规则链所有权：ubunturouter 完全拥有其 nftables 链，不与其他工具冲突

### 3.4 Routing Manager（路由管理）

**职责**：路由策略、Multi-WAN、动态路由

- **静态路由 + Multi-WAN**：直接操作 `ip route` / `ip rule`
- **动态路由**：生成 FRR 配置并 reload
- **Multi-WAN 策略**：
  - PCC (Per-Connection Classification) — 基于流的负载均衡
  - Weighted Round-Robin — 按权重分配
  - Failover — 主备切换
- **健康检查**：ICMP/TCP/HTTP 探测，触发路由切换

### 3.5 DHCP/DNS Manager

**职责**：地址分配、DNS 解析、广告过滤

- **DHCP**：dnsmasq（默认）/ Kea（可选）
- **DNS 缓存**：Unbound（递归解析 + DNSSEC 验证）
- **广告过滤**：Docker 运行 AdGuard Home
- **数据流**：Client → Unbound(53) → AdGuard Home(5353) → 上游 DNS

### 3.6 VPN Manager

**职责**：VPN 隧道管理

- WireGuard：内核原生，生成 wg 配置
- IPSec/IKEv2：strongSwan，支持远程接入
- 支持生成客户端配置/二维码

### 3.7 VM Manager（虚拟机管理）

**职责**：虚拟机全生命周期管理

**技术栈**：
- 底层：**libvirt** + **QEMU/KVM**
- 控制台：**noVNC**（WebSocket → TCP 代理）
- 存储：**qcow2** 虚拟磁盘，存储于 `/var/lib/ubunturouter/vm/`
- 网口直通：**VFIO** + **IOMMU**

**关键能力**：
- 向导式创建 VM（选择模板 → 分配资源 → 网络配置 → 启动）
- VM 模板：预置 qcow2 云镜像 + cloud-init 注入
- 网口直通：自动检测 IOMMU 组，一键绑定 VFIO 驱动
- noVNC 代理：API Server 内嵌 WebSocket → TCP 代理
- 开机自启：通过 libvirt autostart 管理
- 状态监控：通过 libvirt API 获取 CPU/内存/磁盘/网络统计

**VM 模板格式**：
```yaml
# /var/lib/ubunturouter/vm/templates/openwrt.yaml
name: openwrt
display_name: "OpenWrt 旁路由"
description: "轻量级 Linux 路由器系统"
icon: openwrt.png
category: virtual-system
type: vm
resources:
  cpu: 2
  memory: 512MB
  disk: 100MB
source:
  type: qcow2
  url: https://downloads.openwrt.org/.../openwrt-x86-64-generic-ext4-rootfs.img
  checksum: sha256:xxx
network:
  - mode: bridge      # bridge | vfio
    bridge: br-lan
cloud_init:
  enabled: false
```

### 3.8 Container Manager（容器管理）

**职责**：Docker 容器和 Compose 项目的可视化管理

**技术栈**：
- 底层：**Docker Engine** + **Docker Compose V2**
- API：Docker Engine API (Unix Socket)
- 网络：bridge / macvlan / host
- 存储：Docker Volume + Bind Mount

**关键能力**：
- Compose 项目管理：每个应用一个 Compose 项目，独立生命周期
- 容器日志流：Docker API + WebSocket 实时推送
- 容器终端：Docker exec + WebSocket → tty
- macvlan 网络：容器获得 LAN 独立 IP，路由器自动配置
- 存储卷管理：Web 上创建/挂载/备份 Volume
- 镜像加速：支持配置国内镜像源（registry-mirrors）

**Compose 项目存储**：
```
/var/lib/ubunturouter/apps/
  └── homeassistant/
      ├── docker-compose.yml    # Compose 文件
      ├── .env                  # 环境变量
      └── data/                 # 应用数据卷
```

### 3.9 App Store Engine（应用市场引擎）

**职责**：应用模板仓库管理，统一编排容器和 VM 应用的安装/更新/卸载

**核心抽象**：应用市场是 VM Manager 和 Container Manager 的上层编排层。用户不直接操作 Docker/libvirt，而是通过"应用"这一概念与系统交互。

**应用模板规范**：

```yaml
# app-manifest.yaml — 每个应用的声明文件
id: homeassistant
name: Home Assistant
version: "2024.1.0"
category: smart-home
icon: homeassistant.png
description:
  zh: "开源智能家居平台"
  en: "Open source home automation platform"
type: container               # container | vm
install:
  container:
    compose_url: https://raw.githubusercontent.com/ubunturouter/apps/main/homeassistant/docker-compose.yml
    env:
      - key: TZ
        default: "Asia/Shanghai"
        description: "时区"
      - key: PUID
        default: "1000"
        description: "用户ID"
    volumes:
      - name: ha_config
        path: /config
        description: "配置目录"
    ports:
      - container: 8123
        host: 8123
        protocol: tcp
        description: "Web界面"
  vm:
    template: openwrt          # 引用 VM 模板名
    resources:
      cpu: 2
      memory: 512MB
update:
  strategy: pull-recreate      # pull-recreate | in-place
  backup_before_update: true
uninstall:
  remove_data: false           # 默认保留数据
  remove_volumes: false
web_url: "http://{{HOST_IP}}:{{PORT_8123}}"
screenshots:
  - ha_dashboard.png
  - ha_integrations.png
links:
  website: https://www.home-assistant.io
  docs: https://www.home-assistant.io/docs/
```

**应用仓库结构**（Git 仓库）：
```
ubunturouter-apps/                 # 官方应用仓库
├── repo-index.yaml                # 仓库索引
├── smart-home/
│   ├── homeassistant/
│   │   ├── manifest.yaml
│   │   ├── docker-compose.yml
│   │   └── icon.png
│   └── zigbee2mqtt/
│       ├── manifest.yaml
│       ├── docker-compose.yml
│       └── icon.png
├── media/
│   ├── plex/
│   └── jellyfin/
└── virtual-system/
    ├── openwrt/
    │   ├── manifest.yaml
    │   └── template.yaml         # VM 模板
    └── windows/
        ├── manifest.yaml
        └── template.yaml
```

**应用市场操作流程**：

```
用户点击"安装 Home Assistant"
    │
    ▼
┌──────────────────────┐
│ 1. 获取应用 manifest │  ← 从仓库拉取 / 本地缓存
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. 解析安装参数      │  ← 环境变量 / 端口映射 / 存储路径
│    展示配置表单       │     用户可修改默认值
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. 预检查            │
│    - 端口冲突检测     │
│    - 磁盘空间检查     │
│    - 内存是否充足     │
│    - KVM可用性(VM)    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. 执行安装          │
│    container类型:     │
│      → 生成 .env     │
│      → docker compose│
│        up -d         │
│    vm类型:           │
│      → 下载qcow2     │
│      → 生成libvirt   │
│        XML           │
│      → virsh define  │
│      → virsh start   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 5. 健康检查          │  ← HTTP/TCP 探测服务可用
│    → 标记为"运行中"   │
│    → 显示访问入口     │
└──────────────────────┘
```

**应用更新流程**：
```
定时检查 → 发现新版本 → 通知用户 → 用户确认
    → 备份数据 → 拉取新镜像/下载新qcow2
    → 停止旧实例 → 启动新实例 → 健康检查
    → 成功：清理旧版本 / 失败：回滚
```

### 3.10 Installer & Initializer（安装与初始化）

**职责**：多模式安装 + 首次启动网络自动初始化

**安装模式**：

| 模式 | 入口 | 流程 | 产出 |
|------|------|------|------|
| **裸机 ISO** | USB/光盘引导 | Subiquity → 自动分区 → 安装Ubuntu最小系统 → 安装UbuntuRouter → 重启 | 完整系统 |
| **已有系统** | `apt install` | 添加apt源 → 安装deb包 → `urctl init` | UbuntuRouter叠加安装 |
| **虚拟机镜像** | 导入qcow2/vmdk | 下载镜像 → 导入虚拟化平台 → 启动 | 预装系统 |
| **ARM镜像** | dd写入 | 下载img → dd到eMMC/SD → 启动 | 预装系统 |
| **云镜像** | cloud-init | 上传镜像 → cloud-init注入网络 → 启动 | 云端实例 |

**裸机 ISO 安装详细流程**：

```
USB 引导 → Ubuntu Live Environment
    │
    ▼
┌────────────────────────────────┐
│ 1. Subiquity 安装器            │
│    - 选择语言 (中文/English)    │
│    - 自动/手动分区              │
│    - 安装 Ubuntu Server minimal │
└────────────┬───────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ 2. UbuntuRouter 安装阶段       │
│    - 自动添加 apt 源            │
│    - 选择安装模式               │
│      [最小] [标准] [完整]       │
│    - 安装选定包                 │
│    - 安装完成后重启             │
└────────────┬───────────────────┘
             │
             ▼
       首次启动 → 进入初始化流程（见下方）
```

**首次启动网络自动初始化流程**：

```
系统首次启动 (检测到 /etc/ubunturouter/config.yaml 不存在)
    │
    ▼
┌────────────────────────────────────┐
│ 1. 网口自动探测                     │
│    - 枚举所有物理以太网口           │
│    - ethtool 获取各口速率           │
│    - 按速率排序                     │
│    - 检测是否有链路 (link up)       │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 2. WAN/LAN 自动分配                │
│                                    │
│    网口数 == 1:                    │
│      → WANLAN 模式                │
│      → 单口作 LAN (192.168.21.1)  │
│      → WAN上行: DHCP/PPPoE        │
│                                    │
│    网口数 >= 2:                    │
│      → 速率最低 = WAN             │
│      → 其余 = br-lan              │
│      → WAN: DHCP                  │
│      → LAN: 192.168.21.1/24       │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 3. 生成初始 config.yaml            │
│    - 写入网口分配结果              │
│    - LAN: 192.168.21.1/24          │
│    - DHCP: 192.168.21.50-200      │
│    - 防火墙: 默认策略              │
│    - DNS: 系统默认上游             │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 4. Apply 初始配置                  │
│    - netplan apply                 │
│    - nftables reload              │
│    - dnsmasq start                │
│    - 启动 API Server              │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ 5. 启动 Web 初始化向导             │
│    - 监听 192.168.21.1:80/443     │
│    - 等待用户访问完成向导          │
│    - 向导完成后标记已初始化        │
└────────────────────────────────────┘
```

**单网口 WANLAN 模式技术方案**：

单网口场景下，同一个物理网口需要同时承载 WAN 上行和 LAN 下行。实现方式：

```
方案A: 单口 NAT 模式（推荐，简单可靠）
────────────────────────────────────
物理网口 enp1s0
    │
    ├── IP: 192.168.21.1/24    ← LAN 侧，DHCP Server 监听
    │
    └── 上游 DHCP/PPPoE        ← WAN 侧，通过同一口获取上行IP
    
工作原理：
  - 物理口配 192.168.21.1/24 作为 LAN 网关
  - 同时通过 DHCP/PPPoE 获取上行 IP（添加为辅助地址）
  - nftables NAT：来自 LAN 的流量 masquerade 到上行 IP
  - 限制：需要上游设备（光猫/交换机）分配 IP
  
  适用：单网口设备连接光猫，光猫做 DHCP Server，
       UbuntuRouter 做旁路由/NAT 网关

方案B: VLAN 单口模式（需要 VLAN 交换机）
────────────────────────────────────
物理网口 enp1s0
    ├── enp1s0.1 (VLAN 1)  → br-lan (192.168.21.1/24)
    └── enp1s0.2 (VLAN 2)  → wan0 (DHCP)

  适用：有 VLAN 交换机，上游和下游通过 VLAN 隔离
```

**安装媒介制作**：

| 媒介 | 命令 | 说明 |
|------|------|------|
| x86 ISO | `dd if=ubunturouter-x86_64.iso of=/dev/sdX` | 包含 Ubuntu + UbuntuRouter |
| ARM img | `dd if=ubunturouter-aarch64.img of=/dev/sdX` | 写入 SD/eMMC |
| qcow2 | 直接导入 Proxmox/libvirt | 虚拟机用 |
| VMDK | 导入 VMware | VMware 用 |
| OVA | 导入 ESXi/VirtualBox | 通用虚拟化 |

### 3.11 Web GUI

**技术栈**：Vue3 + Element Plus + Vite

**核心页面**：
1. **Dashboard（三段式首页）**：
   - **网络与系统状态**：拓扑图、代理通道状态总览（Tailscale/Clash/WireGuard）、实时流量仪表、**地图组件**（链路地理位置）、conntrack
   - **设备运行状态**：CPU/内存/磁盘/网口/温度/运行时间
   - **应用与服务运营状态**：应用卡片（Docker/VM/系统服务分类）、运行状态、网络消耗排行、资源占用排行、快捷操作按钮
2. **网络向导**：首次配置引导（选WAN口、设LAN口）
3. **接口管理**：接口列表、VLAN、桥接、Bonding 可视化
4. **防火墙**：Zone 可视化、端口转发、规则管理
5. **多WAN**：线路状态、负载均衡策略、健康检查
6. **DHCP**：租约表、静态绑定、在线设备
7. **DNS/广告过滤**：查询日志、过滤统计、黑白名单
8. **VPN**：隧道状态、对端管理、客户端配置生成
9. **应用市场**：分类浏览、搜索、一键安装/更新/卸载、应用详情页
10. **我的应用**：已安装应用列表、状态、配置编辑、数据备份
11. **虚拟机**：VM 列表、创建向导、noVNC 控制台、资源监控
12. **容器**：容器/Compose 项目列表、日志、终端、网络/存储管理
13. **系统**：备份/恢复、日志、终端、固件升级
14. **流量编排**：设备识别、应用特征、可视化编排画布、通道管理、流量统计
15. **通道管理**：通道列表、状态、延迟、故障切换策略

**页面框架布局**：
```
┌──────────────────────────────────────────────┐
│  🖥 UbuntuRouter            [用户名] [⚙设置] │  ← 顶部导航栏
├──────────┬───────────────────────────────────┤
│  📊 首页  │   ← 当前选中                           │
│  🛜 网络   │                                   │
│  🔒 防火墙 │         内容区域                     │
│  📡 路由   │                                   │
│  🌐 VPN   │    （根据左侧菜单切换）              │
│  📦 应用   │                                   │
│  🐳 容器   │                                   │
│  ⚡ 流量编排│                                   │
│  ⚙ 系统   │                                   │
├──────────┴───────────────────────────────────┤
│  系统运行时间: 12d 3h | 连接数: 1,234 | CPU:12%│  ← 底部状态栏
└──────────────────────────────────────────────┘
```

**认证流程**：
```
用户访问 https://192.168.21.1
    │
    ▼
┌──────────────────────┐
│ 1. HTTP → 301 HTTPS  │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. 登录页面 (/login)  │
│    - 用户名密码输入框 │
│    - 提交 → API 验证  │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 3. PAM 认证          │
│    - python-pam 或    │
│      pam_unix.so     │
│    - 验证系统账号     │
└──────────┬───────────┘
           │ 成功
           ▼
┌──────────────────────┐
│ 4. 生成 JWT Token    │
│    - 存储:           │
│      localStorage   │
│    - 过期: 30分钟    │
│    - 每次 API 请求   │
│      带 Bearer Token│
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 5. 跳转到 Dashboard   │
│    / → 首页 / 网络状态│
└──────────────────────┘
```

**Dashboard WebSocket 推送协议**：
```
连接: ws://192.168.21.1:8080/ws/dashboard?token=xxx

服务端推送消息格式:
{
  "type": "traffic_update",       // 流量更新 (2s)
  "data": {
    "interfaces": [
      {"name": "ens3", "rx": 1234, "tx": 5678, "rx_pkts": 100, "tx_pkts": 200}
    ],
    "total_rx_rate": 1.2,        // Mbps
    "total_tx_rate": 0.8
  }
}
{
  "type": "tunnel_status",        // 隧道状态 (10s)
  "data": {
    "tailscale": {"status": "connected", "exit_nodes": [
      {"name": "us-node", "location": "Los Angeles", "latency": 32, "online": true}
    ]},
    "clash": {"status": "running", "proxies": [
      {"name": "US 01", "type": "Shadowsocks", "latency": 180, "history": [120,150,180]}
    ]},
    "wireguard": {"peers": [
      {"name": "phone", "endpoint": "1.2.3.4:51820", "transfer_rx": 100, "transfer_tx": 200}
    ]}
  }
}
{
  "type": "system_status",        // 系统状态 (30s)
  "data": {
    "cpu": {"usage": 12.5, "cores": [8, 15, 10, 5]},
    "memory": {"total": 3.3, "used": 1.2, "available": 1.8},
    "disk": [
      {"mount": "/", "total": 64, "used": 15, "avail": 46}
    ],
    "uptime": "12d 3h 45m"
  }
}
{
  "type": "app_status",            // 应用状态 (10s)
  "data": {
    "apps": [
      {"name": "Home Assistant", "type": "docker", "status": "running",
       "uptime": "12d", "cpu": 2.3, "memory_mb": 128,
       "rx_bytes": 1000000000, "tx_bytes": 2000000000,
       "web_url": "http://192.168.21.50:8123"}
    ],
    "summary": {"total": 8, "running": 6, "stopped": 1, "error": 1}
  }
}
```

**地图组件技术方案**：
- 前端：**Leaflet.js**（轻量、免费、无需 API Key）或 **MapLibre GL**
- 地图数据：OpenStreetMap 瓦片（免费，无流量限制）
- 地理定位数据流：
  ```
  Tailscale API → exit node IP → GeoIP → 城市/国家/坐标
  Clash API → 节点 IP → GeoIP → 坐标
  WireGuard peer → 端点 IP → GeoIP → 坐标
  本地公网出口 → curl ipinfo.io/json → 公网 IP + 地理信息
  ```
- 地图标注点：
  ```
  本地网关: 📍 上海 (公网IP归属地)
  直连出口: 🔵 电信出口 (当前运营商出口)
  Tailscale节点: 🟢 洛杉矶 (32ms)
  Clash节点: 🟡 东京 (120ms)
  WireGuard节点: 🟣 家庭 (通过100.x.x.1)
  ```
- 链路线条：直线带箭头，颜色按延迟分级

### 3.12 Traffic Orchestrator（流量编排引擎）

**职责**：应用流量识别、可视化编排、规则编译下发

**核心思想**：
将流量从 "所有设备所有应用走同一个出口" 升级为 **"设备A的应用X走通道Y"** 的精细化编排。

**三个核心概念**：

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│  设备    │───→│  应用    │───→│  通道    │
│ (Device) │    │ (App)    │    │ (Tunnel) │
└──────────┘    └──────────┘    └──────────┘
  iPhone          抖音           direct (直连)
  电视            Netflix        ts-exit-us (Tailscale 美国出口)
  PC              Steam          oc-jp (OpenClash 日本节点)
  NAS             Plex           wg-home (WireGuard 回家)
```

**编排实例**：

```
场景1: 电视看Netflix，走Tailscale美国出口回国
  电视 → Netflix → ts-exit-us

场景2: iPhone刷抖音，走直连
  iPhone → 抖音 → direct

场景3: PC访问OnlyFans，走OpenClash美国节点
  PC → OnlyFans → oc-us

场景4: NAS的Synology Drive远程同步，走WireGuard回家
  NAS → Synology Drive → wg-home

场景5: 异地办公室访问家庭NAS，走Tailscale Mesh
  办公室PC → NAS管理页面 → ts-mesh
```

**技术架构**：

```
┌──────────────────────────────────────────────────────────┐
│               Traffic Orchestrator (编排层)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ 设备识别  │  │ 应用识别  │  │ 可视化   │  │ 通道    │ │
│  │ Engine    │  │ Engine   │  │ 编排画布  │  │ 管理    │ │
│  └─────┬────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
└────────┼────────────┼──────────────┼─────────────┼──────┘
         │            │              │             │
         ▼            ▼              ▼             ▼
┌──────────────────────────────────────────────────────────┐
│                 Rule Compiler (规则编译器)                 │
│  编排结果 → nftables set + ip rule + 路由表               │
│  规则优先级: 最精确的设备+应用匹配优先                      │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│               Execution Layer (执行层)                    │
│  ┌────────┐┌──────────┐┌──────────┐┌──────────────────┐ │
│  │ 直连   ││ Tailscale││WireGuard ││ OpenClash/Clash  │ │
│  │ direct ││ ts-exit  ││ wg-*     ││ oc-*             │ │
│  └────────┘└──────────┘└──────────┘└──────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

#### 设备识别引擎 (Device Detection)

| 识别方式 | 数据源 | 精度 | 说明 |
|----------|--------|------|------|
| DHCP 租约 | dnsmasq lease | 高 | MAC → IP → 主机名 |
| MAC OUI 库 | 前24位MAC地址 | 中 | Apple/Samsung/Xiaomi |
| mDNS/UPnP | Avahi 网络发现 | 高 | 设备广播的型号名 |
| HTTP User-Agent | 可选端口镜像 | 高 | 浏览器指纹 |
| 用户自定义 | 手动命名 | 最高 | 用户自己确认的名称 |

**设备识别优先级**：
1. 用户手动命名的名称（最高）
2. DHCP 主机名 + mDNS 服务名称（高）
3. MAC OUI 厂商识别（中）→ "Apple设备"、"小米设备"
4. 未知设备 → "unknown-{mac最后4位}" 自动命名

#### 应用识别引擎 (App Detection)

| 识别方式 | 原理 | 识别范围 |
|----------|------|----------|
| DNS 域名 | 根据请求的目标域名判断应用 | 覆盖最广，任何有 DNS 的流量 |
| 目的IP/端口 | 知名服务的固定 IP+端口 | Netflix/CDN/游戏服务器 |
| DPI (nDPI) | 深度包检测，分析应用层协议 | QUIC/SSL SNI/HTTP Host |
| 应用特征库 | 预编译的应用→域名/IP映射表 | 定期更新，社区贡献 |

**应用特征库结构**：

```yaml
# /var/lib/ubunturouter/app-db/apps.yaml
apps:
  netflix:
    name: Netflix
    category: streaming-video
    domains:
      - "*.netflix.com"
      - "*.nflxvideo.net"
      - "*.nflxext.com"
      - "*.nflximg.net"
    ips:
      - "108.177.0.0/16"
    dpi_protocols:
      - "netflix"
    ports:
      - 443

  douyin:
    name: 抖音/TikTok
    category: streaming-video
    domains:
      - "*.douyin.com"
      - "*.tiktokv.com"
      - "musical.ly"
    dpi_protocols:
      - "tiktok"

  qqmusic:
    name: QQ音乐
    category: music
    domains:
      - "*.qqmusic.qq.com"
      - "*.y.qq.com"
      - "music.163.com"       # 网易云一并归类
    dpi_protocols:
      - "qqmusic"

  steam:
    name: Steam/游戏平台
    category: gaming
    domains:
      - "*.steampowered.com"
      - "*.steamcontent.com"
      - "*.steamstatic.com"
      - "store.steampowered.com"
    ips:
      - "103.10.124.0/24"
    dpi_protocols:
      - "steam"
    ports:
      - 27015-27030

  onlyfans:
    name: OnlyFans
    category: adult
    domains:
      - "*.onlyfans.com"
      - "*.ofsys.com"
    dpi_protocols:
      - "onlyfans"
```

#### 通道管理 (Tunnel Manager)

**通道统一抽象**：

```yaml
# 每个通道的抽象定义
tunnels:
  direct:                     # 内置通道
    type: direct
    name: 直连
    description: "默认直连出口"
    default: true              # 默认路由

  ts-exit-us:                 # Tailscale 美国 Exit Node
    type: tailscale
    name: "Tailscale 美国出口"
    exit_node: "us-node"
    priority: 100
    health_check:
      target: "8.8.8.8"

  ts-exit-cn:                 # Tailscale 国内 Exit Node
    type: tailscale
    name: "Tailscale 国内出口"
    exit_node: "cn-node"
    priority: 100

  ts-mesh:                    # Tailscale 异地组网
    type: tailscale
    name: "Tailscale Mesh 异地组网"
    subnet: "100.x.x.0/24"
    mode: mesh

  oc-us:                      # OpenClash 美国节点
    type: clash
    name: "Clash 美国节点"
    proxy_group: "美国节点"
    proxy: "US 01"

  oc-jp:                      # OpenClash 日本节点
    type: clash
    name: "Clash 日本节点"
    proxy_group: "亚洲节点"
    proxy: "JP 01"

  wg-home:                    # WireGuard 回家
    type: wireguard
    name: "WireGuard 回家"
    interface: wg0
    subnet: "10.0.1.0/24"
```

#### 规则编译器 (Rule Compiler)

将可视化编排结果编译为底层规则：

```python
# 编排规则输入示例
orchestration_rules = [
    # 设备: 电视 → 应用: Netflix → 通道: ts-exit-us
    Rule(device="电视", device_mac="aa:bb:cc:11:22:33",
         app="netflix", tunnel="ts-exit-us"),
    
    # 设备: iPhone → 应用: 抖音 → 通道: direct  
    Rule(device="iPhone", device_mac="dd:ee:ff:44:55:66",
         app="douyin", tunnel="direct"),
    
    # 全局默认 → 直连
    Rule(device="*", app="*", tunnel="direct"),
]

# 编译为 nftables 规则
编译目标 1: nftables set + mark
  → 电视的 Netflix 流量 → MARK 0x1001
  → iPhone 的抖音流量 → 不标记（走默认）

编译目标 2: ip rule
  → from MARK 0x1001 lookup 101
  → table 101: default via 100.x.x.1 dev tailscale0

# 规则优先级：
# 1. 最精确匹配（设备+应用）优先
# 2. 仅匹配应用
# 3. 仅匹配设备
# 4. 全局默认
```

**规则编译的三层架构**：

```
Layer 1: nftables mangle PREROUTING (应用标记)
Layer 2: ip rule (策略路由选择表)  
Layer 3: ip route (各通道路由表)

执行示例:
1. 包到达 → mangle PREROUTING
2. 检查 nftables set matching (device_mac + app_domain)
   → 命中: MARK = 0x1001 (ts-exit-us)
   → 未命中: 继续
3. ip rule from MARK 0x1001 lookup 101
4. table 101 → default via tailscale0
```

#### 可视化编排画布

```
┌─────────────────────────────────────────────────────┐
│  流量编排画布                                         │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    │
│  │ 📺 电视  │    │ Netflix  │───→│ Tailscale   │    │
│  │          │───→│ YouTube  │───→│ 美国出口     │    │
│  └──────────┘    └──────────┘    └─────────────┘    │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    │
│  │ 📱 iPhone│    │ 抖音      │───→│ 直连         │    │
│  │          │───→│ QQ音乐   │───→│ Tailscale   │    │
│  │          │    │          │    │ 国内出口     │    │
│  └──────────┘    └──────────┘    └─────────────┘    │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    │
│  │ 💻 PC    │    │ OnlyFans │───→│ Clash 美国   │    │
│  │          │───→│ Steam    │───→│ 直连         │    │
│  └──────────┘    └──────────┘    └─────────────┘    │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    │
│  │ 🖥 NAS   │    │ Plex     │───→│ WireGuard   │    │
│  │          │    │ Drive    │───→│ 回家隧道     │    │
│  └──────────┘    └──────────┘    └─────────────┘    │
│                                                      │
│  规则优先级: 精确匹配 > 应用匹配 > 设备匹配 > 默认     │
└─────────────────────────────────────────────────────┘
```

#### 流量统计视图

```
设备: 电视 (aa:bb:cc:11:22:33)
├── Netflix → ts-exit-us → 1.2 GB / 实时 2.3 Mbps
├── YouTube → ts-exit-cn → 856 MB / 实时 1.1 Mbps
└── 其他    → direct     → 45 MB  / 实时 0 Mbps

设备: iPhone (dd:ee:ff:44:55:66)
├── 抖音    → direct     → 2.1 GB / 实时 3.4 Mbps
├── QQ音乐  → ts-exit-cn → 380 MB / 实时 0.5 Mbps
├── Instagram→ oc-us      → 120 MB / 实时 0.2 Mbps
└── 其他    → direct     → 200 MB / 实时 0.1 Mbps

通道使用排行:
1. ts-exit-us   → 4.2 GB (电视+NAS)
2. direct       → 3.8 GB (默认流量)
3. ts-exit-cn   → 1.6 GB (QQ音乐+国内应用)
4. oc-us        → 0.5 GB (PC+iPhone)
5. wg-home      → 0.3 GB (NAS远程同步)
```

#### 故障转移

当主通道不可用时，自动切换到备用通道：

```
编排: 电视 → Netflix → ts-exit-us [主] oc-us [备]
检测到 ts-exit-us 不可用（8.8.8.8 ping 超时）
自动切换: 电视 → Netflix → oc-us

恢复后: 自动切回 ts-exit-us（可选手动确认）
```

## 4. 配置文件设计

```yaml
# /etc/ubunturouter/config.yaml
system:
  hostname: router01
  timezone: Asia/Shanghai

interfaces:
  wan0:
    type: ethernet
    device: enp1s0
    role: wan
    ipv4:
      method: dhcp
    firewall:
      zone: wan

  lan0:
    type: bridge
    device: br-lan
    ports: [enp2s0, enp3s0]
    role: lan
    ipv4:
      method: static
      address: 192.168.21.1/24
    firewall:
      zone: lan
    vlans:
      - id: 10
        name: guest
        ipv4:
          address: 192.168.10.1/24
        firewall:
          zone: guest

routing:
  multi_wan:
    enabled: true
    strategy: weighted-failover
    wan_interfaces: [wan0]
    health_check:
      target: 8.8.8.8
      interval: 5s
      timeout: 2s
  frr:
    ospf:
      enabled: false

firewall:
  default_policy:
    input: drop
    forward: drop
    output: accept
  zones:
    wan:
      masquerade: true
    lan:
      forward_to: [wan]
    guest:
      forward_to: [wan]
      isolated: true

nat:
  - source: 192.168.21.0/24
    outbound: wan0
    type: masquerade

dhcp:
  lan:
    interface: br-lan
    range: 192.168.21.50-192.168.21.200
    gateway: 192.168.21.1
    dns: [192.168.21.1]
    lease: 86400

dns:
  upstream: [223.5.5.5, 119.29.29.29]
  filtering:
    enabled: true
    blocklists:
      - https://easylist-downloads.adblockplus.org/easylistchina.txt

vpn:
  wireguard:
    enabled: true
    listen_port: 51820
    peers: []
```

## 5. 进程模型

```
PID 1: systemd
  ├─ ubunturouter-init.service       # 首次启动初始化 (oneshot, 仅首次运行)
  ├─ ubunturouter-engine.service     # 配置引擎守护进程
  ├─ ubunturouter-api.service        # REST API Server (FastAPI + uvicorn)
  ├─ nftables.service                # 防火墙
  ├─ frr.service                     # 路由协议 (可选)
  ├─ dnsmasq.service                 # DHCP + DNS (轻量模式)
  ├─ unbound.service                 # DNS 缓存
  ├─ wg-quick@wg0.service            # WireGuard
  ├─ libvirtd.service                # KVM 虚拟化 (可选，按需启用)
  ├─ docker.service                  # 容器引擎 (可选，按需启用)
  └─ ubunturouter-appstore.service   # 应用市场后台 (仓库同步、更新检查)
```

## 6. 包结构

```
ubunturouter-core          # 核心配置引擎 + CLI (Python)
ubunturouter-web           # Web GUI + API Server (Python + Vue3)
ubenturouter-appstore      # 应用市场引擎 (Python)
ubunturouter-vm            # VM Manager 依赖 (libvirt/KVM/noVNC)
ubunturouter-container     # Container Manager 依赖 (Docker/Compose)
ubunturouter-docker        # Docker Compose (AdGuard Home等路由服务)
ubunturouter-docs          # 文档
```

**安装模式**：
- **最小安装**：`ubunturouter-core` + `ubunturouter-web`（纯路由器）
- **标准安装**：最小安装 + `ubunturouter-container` + `ubunturouter-appstore`（路由+容器+应用市场）
- **完整安装**：标准安装 + `ubunturouter-vm`（路由+容器+VM+应用市场）

## 7. 迭代规划

| Phase | 内容 | 预计周期 |
|-------|------|----------|
| Phase 1 | 配置引擎 + Network Manager + Firewall Manager + DHCP/DNS Manager | 4-6 周 |
| Phase 2 | REST API + Web GUI (Dashboard/接口/防火墙/DHCP) | 6-8 周 |
| Phase 3 | Multi-WAN + VPN + 广告过滤 + QoS | 4-6 周 |
| Phase 4 | Container Manager + App Store Engine (容器应用市场) | 6-8 周 |
| Phase 5 | VM Manager + App Store VM 应用支持 | 4-6 周 |
| Phase 6 | FRR动态路由 + HA(VRRP) + IDS/IPS + XDP | 6-8 周 |

### Phase 4 详细拆分（应用市场核心迭代）

| Sprint | 内容 | 预计 |
|--------|------|------|
| 4.1 | Docker/Compose 基础管理 API | 1 周 |
| 4.2 | 容器生命周期 + 日志 + 终端 | 1 周 |
| 4.3 | App Store Engine：manifest 规范 + 仓库同步 | 1.5 周 |
| 4.4 | App Store：一键安装/卸载/更新流程 | 1.5 周 |
| 4.5 | 应用市场 Web GUI（浏览/搜索/安装页） | 1.5 周 |
| 4.6 | 我的应用 GUI（状态/配置/备份） | 1 周 |
| 4.7 | 预置首批10+容器应用模板 | 1 周 |

### Phase 5 详细拆分（VM + 应用市场 VM 支持）

| Sprint | 内容 | 预计 |
|--------|------|------|
| 5.1 | libvirt API 封装 + VM 生命周期管理 | 1.5 周 |
| 5.2 | VM 模板管理 + noVNC 集成 | 1 周 |
| 5.3 | VFIO 直通 + IOMMU 管理 | 1 周 |
| 5.4 | VM 管理 Web GUI | 1.5 周 |
| 5.5 | App Store VM 应用模板支持 | 1 周 |

## 8. 安全设计要点

1. **系统 PAM 认证**：Web GUI 和 API 使用系统账号密码登录（`python-pam` 或 `libpam`），与 SSH/控制台账号一致
2. **HTTPS 强制**：HTTP → 301 重定向到 HTTPS，安装时自动生成自签证书
3. **JWT Token**：登录成功后签发 JWT，有效期 30 分钟，每次 API 请求携带 `Authorization: Bearer <token>`
4. **登录保护**：连续 5 次失败锁定 15 分钟（基于 IP + 用户名双因子）
5. **会话管理**：用户可查看当前活跃会话列表，支持强制登出其他会话
6. **API Server** 仅监听 LAN 接口（默认 192.168.21.1:8080）
7. **TOTP 双因子**（预留）：Phase 2 支持
8. **角色权限**（预留）：admin / viewer / operator，为未来多用户做准备
9. **配置文件权限** 0600，属主 ubunturouter
10. **CLI** 需要 sudo 权限（通过 polkit 策略）
11. **nftables** 规则链以 `ubunturouter_` 前缀标识，独占管理
12. **所有配置变更**记录审计日志
