# UbuntuRouter vs iStoreOS — 系统级功能缺失报告（按 iStoreOS 菜单结构）

> **分析日期**: 2026-04-27  
> **方法**: 实际登录两个系统的管理界面，逐菜单、逐功能对比  
> **优先级说明**: P1=最优先实现 / P2=重要 / P3=有价值 / P4=锦上添花 / PX=无需实现  

---

## 一、一级菜单结构对比

| 层级 | iStoreOS (一级菜单) | UbuntuRouter (一级菜单) | 匹配度 |
|------|-------------------|----------------------|--------|
| L1 | 路由状态 (Dashboard) | 仪表盘 | ✅ 有 |
| L1 | 网络配置 (向导) | 网络接口 / DHCP/DNS / DNS管理 | ⚠️ 分散 |
| L1 | 远程DDNS | DDNS | ✅ 有 |
| L1 | 存储管理 | 存储管理 | ✅ 有 |
| L1 | 功能配置 | 系统设置 | ⚠️ 部分 |
| L1 | 应用商店 | 应用市场 | ✅ 有 |
| L1 | 高级配置 (LuCI入口) | ❌ 无 | ❌ 缺失 |
| L2 | QuickStart | ❌ 无 | ❌ 缺失 |
| L2 | RouterDog | ❌ 无 (可通过App安装) | PX |
| L2 | NetworkGuide | ❌ 无 | ❌ 缺失 |
| L2 | Status | 系统监控 / 路由 / 防火墙 | ⚠️ 部分 |
| L2 | System | 系统设置 | ⚠️ 部分 |
| L2 | iStore | 应用市场 | ⚠️ 部分 |
| L2 | Docker | 容器 | ✅ 有 |
| L2 | Services | 分散（DDNS/VPN/Samba等） | ⚠️ 部分 |
| L2 | NAS | 存储管理 / Samba共享 | ⚠️ 部分 |
| L2 | Network | 网络接口 / 防火墙 / 路由 / 多线路 | ⚠️ 部分 |

---

## 二、QuickStart / 快速入门

|-| iStoreOS | UbuntuRouter | 状态 |
|--|---------|-------------|------|
| QuickStart | 首次启动配置向导 | ❌ 无 |

**缺失功能**:
1. 首次启动向导（选择上网方式 + 初始化配置） — **P2**

---

## 三、状态（Status） — 12 个子菜单

### 3.1 Overview（仪表盘/路由状态）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 实时流量曲线图 (Canvas 动画) | ❌ 无 | **P1** |
| 2 | 实时 Upload/Download 速率数值 | ❌ 无 | **P1** |
| 3 | 联网状态提示 (Connected/Disconnected) | ❌ 无 | **P3** |
| 4 | 在线设备数 + 设备列表入口 | ❌ 无 | **P2** |
| 5 | WAN IP 信息卡片 (IPv4/IPv6/DNS) | 部分有 | **P2** |
| 6 | 快捷操作按钮组（Terminal/OTA/LAN Settings/DNS Settings/Feeds Mirror/Sandbox） | ❌ 无 | **P1** |
| 7 | 磁盘信息 + 文件管理器入口 | 磁盘有，文件管理器无 | **P2** |
| 8 | Share 状态面板（LinkEase/SAMBA/WEBDAV 开启状态） | ❌ 无 | **P2** |
| 9 | Docker 状态面板（运行状态 + Docker 根目录） | ❌ 无 | **P2** |
| 10 | 下载服务状态（Aria2/qBittorrent/Transmission） | ❌ 无 | **P3** |
| 11 | DDNS 状态预览（已配置条目 + 状态标签） | ❌ 无 | **P3** |
| 12 | 系统信息卡（CPU温度/型号/固件/内核/运行时间/系统时间） | CPU/内存/磁盘有，其他无 | **P2** |
| 13 | CPU 温度显示 | ❌ 无 | **P2** |
| 14 | CPU/内存可点击展开详情 | ❌ 无 | **P3** |
| 15 | 网络拓扑 → 节点详情面板 | 有 | ✅ 已有 |

### 3.2 Routing（路由表）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | IPv4 路由表（目标/网关/掩码/设备/跃点数） | 有（RoutingTable.vue） | ✅ 已有 |
| 2 | IPv6 路由表 | ❌ 无 | **P3** |
| 3 | 路由表刷新 | 有 | ✅ 已有 |

### 3.3 Firewall（防火墙状态）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 防火墙规则列表 | 有（FirewallRules.vue） | ✅ 已有 |
| 2 | 当前连接跟踪表 (conntrack) | ❌ 无 | **P3** |
| 3 | 防火墙日志 | ❌ 无 | **P3** |

### 3.4 System Log（系统日志）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 系统日志查看（完整 journalctl 输出） | ❌ 无 | **P2** |
| 2 | 日志过滤/搜索 | ❌ 无 | **P2** |
| 3 | 日志清空 | ❌ 无 | **P3** |
| 4 | 日志自动刷新 | ❌ 无 | **P3** |

### 3.5 Processes（进程查看）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 进程列表（PID/名称/CPU/内存） | ❌ 无 | **P3** |
| 2 | 进程搜索 | ❌ 无 | **P3** |
| 3 | 进程终止 | ❌ 无 | **PX** |

### 3.6 Realtime Graphs（实时图表）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | CPU 使用率实时曲线 | 系统监控有 | ✅ 已有 |
| 2 | 内存使用率实时曲线 | 系统监控有 | ✅ 已有 |
| 3 | 网络流量实时曲线 | ❌ 无 | **P2** |
| 4 | 负载实时曲线 | ❌ 无 | **P3** |
| 5 | 无线信号实时曲线 | ❌ 无 | **PX** |

### 3.7 Realtime Bandwidth（实时带宽）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 按接口的实时带宽监控 | ❌ 无 | **P2** |
| 2 | 历史流量统计 | ❌ 无 | **P3** |

### 3.8 NetData（系统监控）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | NetData 集成入口 | 系统监控有 | ✅ 已有 |

### 3.9 WireGuard / MultiWAN Manager（已在独立页面）

- WireGuard → 已有 VPN 页面 ✅
- MultiWAN → 已有多线路页面 ✅

---

## 四、系统（System） — 15 个子菜单

### 4.1 System（系统基本设置）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 系统时间显示 + 手动设置 | ❌ 无 | **P2** |
| 2 | 与浏览器时间同步 | ❌ 无 | **P2** |
| 3 | 与 NTP 服务器同步 | ❌ 无 | **P2** |
| 4 | 主机名修改 | 只读查看 | **P2** |
| 5 | 设备描述 | ❌ 无 | **P3** |
| 6 | 时区选择（含完整时区列表） | ❌ 无 | **P2** |
| 7 | ZRam 设置 | ❌ 无 | **PX** |
| 8 | 语言和样式选择 | ❌ 无 | **P4** |

### 4.2 Administration（管理/密码/SSH）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | Web 管理界面密码修改 | ❌ 无（依赖系统PAM） | **P2** |
| 2 | SSH 访问控制（允许root密码登录/SSH密钥/端口） | ❌ 无 | **P2** |
| 3 | 管理接口绑定（只监听LAN/全部） | ❌ 无 | **P3** |
| 4 | HTTPS 证书管理 | ❌ 无 | **P3** |

### 4.3 Software（软件包管理）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 软件包列表 + 搜索 | 有（软件源页面） | ✅ 已有 |
| 2 | 软件包安装/卸载 | 有 | ✅ 已有 |

### 4.4 Startup（启动项管理）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 开机启动项列表（启用/禁用） | ❌ 无 | **P2** |
| 2 | 启动顺序管理 | ❌ 无 | **P3** |

### 4.5 Scheduled Tasks（计划任务）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | Cron 计划任务编辑 | ❌ 无 | **P2** |
| 2 | 重启/关机定时 | ❌ 无 | **P3** |

### 4.6 Mount Points（挂载点）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 文件系统挂载管理 | 有（存储管理） | ✅ 已有 |
| 2 | 自动挂载配置 | 有 | ✅ 已有 |

### 4.7 Disk Man（磁盘管理）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 磁盘列表 + 分区图表 | 磁盘列表有，图表无 | **P3** |
| 2 | 分区格式化 | ❌ 无 | **P3** |
| 3 | 磁盘健康度（SMART） | 有 | ✅ 已有 |

### 4.8 OTA（系统升级）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | OTA 在线检查更新 | ❌ 无 | **P1** |
| 2 | 一键升级固件 | ❌ 无 | **P1** |
| 3 | 版本号显示 + 更新日志 | ❌ 无 | **P2** |

### 4.9 Backup / Flash Firmware（备份/恢复/刷机）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 配置备份下载 | 有（备份恢复页面） | ✅ 已有 |
| 2 | 配置恢复上传 | 有 | ✅ 已有 |
| 3 | 系统重置为出厂 | ❌ 无 | **P3** |
| 4 | 固件刷写 | ❌ 无 | **PX** |

### 4.10 Reboot（重启）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 一键重启系统 | ❌ 无 | **P1** |
| 2 | 定时重启 | ❌ 无 | **P2** |

### 4.11 其他

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | System Convenient Tools（系统便利工具） | ❌ 无 | **P3** |
| 2 | Tuning（系统调优） | ❌ 无 | **PX** |
| 3 | LED Configuration（LED 配置） | ❌ 无 | **PX** |
| 4 | FileTransfer（文件传输） | ❌ 无 | **P4** |
| 5 | Argon Config（主题配置） | ❌ 无 | **P4** |

---

## 五、iStore（应用商店）

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 应用图标展示 | 有 | ✅ 已有 |
| 2 | 应用名称 + 版本 | 有 | ✅ 已有 |
| 3 | 应用描述 | ❌ 无 | **P3** |
| 4 | 下载量统计 | ❌ 无 | **P4** |
| 5 | 点赞/评分 | ❌ 无 | **P4** |
| 6 | 分类标签（12个实际分类） | 全"其他" | **P2** |
| 7 | 排序（下载量/评分/最近更新） | ❌ 无 | **P3** |
| 8 | "打开"按钮（直接跳转应用Web UI） | ❌ 无 | **P2** |
| 9 | 安装/更新/卸载/打开 状态自动切换 | 有 | ✅ 已有 |
| 10 | 应用详情弹窗 | ❌ 无 | **P3** |

---

## 六、Docker（容器管理） — 7 个子菜单

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | Docker 全局配置（Root Dir/Registry Mirrors/日志级别/远程Endpoint） | ❌ 无 | **P2** |
| 2 | Docker 概述（容器/镜像/网络/卷 数量统计） | ❌ 无 | **P2** |
| 3 | 容器列表（状态/创建/端口/操作：启动/停止/重启/删除/终端/日志） | 有（ContainerManager.vue） | ✅ 已有 |
| 4 | 镜像列表（拉取/删除/导入/导出） | ❌ 无 | **P2** |
| 5 | Docker 网络管理 | ❌ 无 | **P3** |
| 6 | Docker 卷管理 | ❌ 无 | **P3** |
| 7 | Docker 事件日志 | ❌ 无 | **P4** |
| 8 | 容器终端直连 | ❌ 无 | **P2** |
| 9 | 容器日志查看 | ❌ 无 | **P2** |

---

## 七、Services（服务管理） — 24 个服务集成

以下服务在 iStoreOS 中通过应用安装后在 Services 菜单注册入口，UbuntuRouter 可通过类似机制实现：

| # | 服务名称 | 说明 | UbuntuRouter | 优先级 |
|---|---------|------|-------------|--------|
| 1 | PassWall（科学上网） | ❌ 无 | **PX** |
| 2 | App Filter（应用过滤） | ❌ 无 | **PX** |
| 3 | DDNSTO 远程控制 | 有（DDNS 页面） | ✅ 已有 |
| 4 | LinkEase | ❌ 无（可通过App安装） | **PX** |
| 5 | Tailscale | ❌ 无（可通过App安装） | **P2** |保留并入VPN |
| 6 | ChineseSubFinder | ❌ 无（可通过App安装） | **PX** |
| 7 | CodeServer | ❌ 无（可通过App安装） | **PX** |
| 8 | Heimdall | ❌ 无（可通过App安装） | **PX** |
| 9 | Home Assistant | ❌ 无（可通过App安装） | **PX** |
| 10 | ITTools | ❌ 无（可通过App安装） | **PX** |
| 11 | PhotoPrism | ❌ 无（可通过App安装） | **PX** |
| 12 | Plex | ❌ 无（可通过App安装） | **PX** |
| 13 | PVE | ❌ 无（可通过App安装） | **PX** |
| 14 | Xteve | ❌ 无（可通过App安装） | **PX** |
| 15 | Xunlei | ❌ 无（可通过App安装） | **PX** |
| 16 | OpenClash | ❌ 无 | **PX** |
| 17 | Dynamic DNS | 有（DDNS 页面） | ✅ 已有 |
| 18 | HDD Idle（硬盘休眠） | ❌ 无 | **P3** |
| 19 | Bandwidth Monitor（带宽监控） | 系统监控有流量模块 | ⚠️ 部分 |
| 20 | Wake on LAN（网络唤醒） | ❌ 无 | **P2** |
| 21 | MWAN3 Helper（多线辅助） | 有多线路页面 | ⚠️ 部分 |
| 22 | Network Shares（网络共享） | 有 Samba 页面 | ✅ 已有 |
| 23 | Terminal（Web 终端） | 有（ttyd） | ✅ 已有 |
| 24 | UPnP IGD & PCP（UPnP 端口转发） | ❌ 无 | **P2** |

> **关键机制**: iStoreOS 的 Services 菜单中大部分是通过应用商店安装后自动注册到 LuCI 菜单的。UbuntuRouter 需要实现 **应用安装后自动注册服务入口** 的机制。

---

## 八、NAS（存储与共享） — 7 个子菜单

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | **UniShare（统一共享管理）** — Samba + WebDAV 同页面管理 | Samba有独立页面，WebDAV无 | **P2** |
| 2 | UniShare 共享用户管理（添加/删除/权限） | ❌ 无 | **P2** |
| 3 | NFS 管理 | ❌ 无 | **P3** |
| 4 | RAID 管理 | ❌ 无 | **P3** |
| 5 | S.M.A.R.T. 硬盘健康 | 有 | ✅ 已有 |
| 6 | qBittorrent EE（下载服务集成） | ❌ 无（可通过App安装） | **PX** |
| 7 | Mount NetShare（挂载网络共享：NFS/SMB/CIFS） | ❌ 无 | **P2** |
| 8 | MergerFS（文件系统合并） | ❌ 无 | **PX** |

---

## 九、Network（网络） — 9 个子菜单

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | **Interfaces（接口配置）** — 完整编辑（协议/IP/网关/DNS/防火墙区域） | 只有"编辑IP"按钮 | **P1** |
| 2 | **NetworkPort（网络端口）** — 物理端口信息 | ❌ 无 | **P1** |
| 3 | **Wireless（无线配置）** | ❌ 无（Ubuntu限制） | **P1** |
| 4 | **Routing（路由）** — 静态路由增删改 | 有（RoutingTable.vue） | ✅ 已有 |
| 5 | **DHCP and DNS（DHCP/DNS服务配置）** | 有（DhcpDns.vue + DnsConfig.vue） | ✅ 已有 |
| 6 | **Diagnostics（网络诊断）** — Ping/Traceroute/Nslookup/Dig | 有（NetworkDiag.vue） | ✅ 已有 |
| 7 | **Firewall（防火墙）** — 区域/规则/转发/NAT | 有（FirewallRules.vue） | ✅ 已有 |
| 8 | **多线多拨** — MACVLAN 虚拟WAN口 + 并发多拨 | ❌ 无 | **PX** |
| 9 | **MultiWAN Manager** — 多WAN负载均衡 + 健康检查 | 有（MultiWanConfig.vue） | ✅ 已有 |

### Interfaces（接口配置）详细缺失

| # | iStoreOS 功能 | UbuntuRouter | 优先级 |
|---|--------------|-------------|--------|
| 1 | 接口列表（名称/状态/MAC/IP/协议/速率/已接收/已发送） | 有，缺收发统计 | **P2** |
| 2 | 接口编辑（协议选择：静态IP/DHCP客户端/PPPoE） | ❌ 无 | **P1** |
| 3 | 接口编辑（IPv4/IPv6 地址设置） | 只有"编辑IP"按钮 | **P1** |
| 4 | 接口编辑（DNS 设置） | ❌ 无 | **P1** |
| 5 | 接口编辑（防火墙区域分配) | ❌ 无 | **P2** |
| 6 | 接口编辑（MTU/跃点数设置） | ❌ 无 | **P2** |
| 7 | 接口编辑（DHCP 客户端选项） | ❌ 无 | **P3** |
| 8 | 接口新建（添加新接口/新协议） | ❌ 无 | **P2** |
| 9 | 物理端口状态（Link/速率/双工/错包） | ❌ 无 | **P3** |
| 10 | 物理端口 LED 控制 | ❌ 无 | **PX** |

---

## 十、UbuntuRouter 已有功能（按 iStoreOS 无对应项）

| 功能 | 说明 |
|------|------|
| 配置编辑（ConfigEditor.vue） | YAML 编辑器 + Save & Apply |
| 系统监控（SystemMonitor.vue） | CPU/内存/网络/磁盘图表 |
| Samba 共享（SambaManager.vue） | Samba 配置页面 |
| PPPoE 拨号（PPPoEConnection.vue） | PPPoE 连接管理 |
| 容器管理（ContainerManager.vue） | Docker 容器管理 |
| 软件源（AptSources.vue） | APT 包管理 |
| DNS 管理（DnsConfig.vue） | DNS 转发规则 |
| 网络诊断（NetworkDiag.vue） | Ping/Traceroute |
| 备份恢复（SystemBackup.vue） | 配置备份 |
| 流量编排（OrchestratorCanvas.vue） | 流量编排 |
| 虚拟机（VirtualMachines.vue） | QEMU/KVM 虚拟机管理 |
| 配置编辑（ConfigEditor.vue） | 统一配置编辑 |
| PendingChangesBar | 待应用变更浮动条 |
| 仓库管理 | App 源管理 |

---

## 十一、系统级缺失功能汇总（按优先级排序）

### P1 — 最关键，用户体感最明显
| # | 功能 | 所属菜单 | 原因 |
|---|------|---------|------|
| 1 | **实时流量曲线图 + 速率数值** | 仪表盘 | 用户第一眼看到，最基本的路由器运营数据 |
| 2 | **快捷操作面板**（Terminal/OTA/LAN/DNS等） | 仪表盘 | 提供快速进入常用功能的入口 |
| 3 | **接口编辑（协议/IP/DNS/MTU 完整表单）** | Network → Interfaces | 网络配置的核心操作，当前只有只读列表 |
| 4 | **OTA 在线升级** | System → OTA | 没有升级渠道意味着产品停滞 |
| 5 | **一键重启系统** | System → Reboot | 软路由需要远程重启能力 |
| 6 | **网络配置向导**（拨号/DHCP/旁路由/内网） | 独立体验 | 新用户第一次使用必须的流程 |
| 7 | **NetworkPort（物理端口信息）** | Network → 端口 | 基础网络信息 |
| 8 | **Wireless（无线配置）** | Network → 无线 | 无线网络管理 |
| 9 | **接口编辑 - 协议选择** | Network → Interfaces | 接口配置核心 |
| 10 | **接口编辑 - 地址设置** | Network → Interfaces | 接口配置核心 |
| 11 | **接口编辑 - DNS设置** | Network → Interfaces | 接口配置核心 |

### P2 — 重要，补齐核心功能缺口
| # | 功能 | 所属菜单 |
|---|------|---------|
| 12 | 系统日志查看器（含筛选/搜索） | Status → System Log |
| 13 | 密码/SSH密钥管理 | System → Administration |
| 14 | 主机名/时区/NTP设置 | System → System |
| 15 | 计划任务编辑 | System → Scheduled Tasks |
| 16 | 开机启动项管理 | System → Startup |
| 17 | 文件管理器 | 仪表盘入口 |
| 18 | Docker 全局配置 + 镜像管理 | Docker |
| 19 | 应用"打开"按钮（跳转Web UI） | iStore |
| 20 | 应用分类标签修正（12个实际分类） | iStore |
| 21 | 在线设备列表 | 仪表盘 |
| 22 | CPU 温度显示 | 仪表盘 |
| 23 | UniShare（Samba+WebDAV统一管理） | NAS |
| 24 | 网络共享挂载（NFS/SMB/CIFS） | NAS |
| 25 | Wake on LAN（网络唤醒） | Services |
| 26 | UPnP IGD & PCP（端口转发） | Services |
| 27 | 接口收发流量统计 | Network → Interfaces |
| 28 | 接口防火墙区域分配 | Network → Interfaces |
| 29 | 新建接口 | Network → Interfaces |
| 30 | 容器终端/日志查看 | Docker |
| 31 | Tailscale（合并入VPN） | VPN |
| 32 | 系统信息卡增强 | 仪表盘 |
| 33 | 首次启动向导 | QuickStart |

### P3 — 有价值，锦上添花
| # | 功能 | 所属菜单 |
|---|------|---------|
| 34 | 应用详情弹窗 | iStore |
| 35 | 应用排序（下载量/评分/更新） | iStore |
| 36 | 实时带宽监控（按接口） | Status |
| 37 | 带宽历史统计 | Status |
| 38 | 进程列表/搜索 | Status → Processes |
| 39 | 防火墙连接跟踪表 | Status → Firewall |
| 40 | 分区图表/格式化 | System → Disk Man |
| 41 | HTTPS 证书管理 | System → Administration |
| 42 | HDD 硬盘休眠 | Services |
| 43 | NFS 管理 | NAS |
| 44 | Docker 网络管理 | Docker |
| 45 | Docker 卷管理 | Docker |
| 46 | 系统重置 | System → Backup |
| 47 | 系统便利工具 | System → Convenient Tools |
| 48 | 接口编辑 - DHCP客户端选项 | Network → Interfaces |
| 49 | 物理端口状态详情 | Network → 端口 |

### P4 — 长期优化
| # | 功能 | 所属菜单 |
|---|------|---------|
| 50 | 主题/样式选择（多配色） | System → Language and Style |
| 51 | Argon 风格主题配置 | System → Argon Config |
| 52 | 应用下载量/评分统计体系 | iStore |
| 53 | Docker 事件日志 | Docker → Events |
| 54 | 语言切换（中/英） | System → Language and Style |

### PX — 无需实现（技术路线不兼容/无必要）
| # | 功能 | 原因 |
|---|------|------|
| 1 | 无线配置（Wireless） | 保持P1，需要实现 |
| 2 | 多线多拨（MACVLAN并发拨号） | 功能极端小众 |
| 3 | PassWall / OpenClash | 法律/政策原因 |
| 4 | LED 配置 | 硬件不兼容 |
| 5 | 固件刷写（Flash Firmware） | 不同发行版 |
| 6 | ZRam / System Tuning | 过于技术细节，可用默认 |
| 7 | qBittorrent EE | 可通过App安装 |
| 8 | 物理端口LED控制 | 硬件不兼容 |

---

## 十二、关键缺失功能个数统计

| 优先级 | 数量 | 说明 |
|--------|------|------|
| P1 | 11 | 用户体感最核心的缺失 |
| P2 | 22 | 重要功能补齐 |
| P3 | 16 | 有价值的功能增强 |
| P4 | 5 | 长期优化项 |
| PX | 8 | 无需实现 |
| **总计** | **62** | **完整的缺失功能列表** |
| ✅ 已有 | ~20 | UbuntuRouter 已实现且匹配的功能 |

---

## 十三、UbuntuRouter 的独特优势（iStoreOS 没有的）

| 功能 | 说明 | 保留价值 |
|------|------|---------|
| 流量编排（Orchestrator） | 按设备/应用维度的流量引导 | ✅ 保留并完善 |
| 虚拟机管理（KVM/QEMU） | 完整的虚拟机生命周期管理 | ✅ 保留 |
| 配置编辑 + Save & Apply | YAML 编辑 + 差异对比 + 回滚 | ✅ 保留 |
| PendingChangesBar | 待应用变更管理 | ✅ 保留 |
| 多线路健康检查 | Multi-WAN 链路健康检测 | ✅ 保留 |
| 配置快照回滚 | 自动生成快照 + Rollback | ✅ 保留 |

---

*本文档按 iStoreOS 24.10.2 的 LuCI 菜单结构组织，UbuntuRouter 对应的功能已标记。优先级标记 P1-P4 为建议值，可调整为 PX 表示不需要实现。*
