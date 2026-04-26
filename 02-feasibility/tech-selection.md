# 技术选型文档

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿

## 1. 选型总览

| 模块 | 选型 | 替代方案 | 选型理由 |
|------|------|----------|----------|
| 配置后端-网络 | netplan | networkd直接配置 | Ubuntu原生，声明式YAML，生产验证 |
| 配置后端-防火墙 | nftables | iptables, ufw | 性能更优，语法统一，Ubuntu 22.04+默认 |
| 路由协议 | FRRouting | BIRD, GoBGP | 功能最全(OSPF/BGP/IS-IS)，社区活跃，VyOS也在用 |
| DHCP | Kea | dnsmasq | 高性能，ISC官方继任者，适合大规模 |
| DNS缓存 | Unbound | dnsmasq, CoreDNS | 递归解析+DNSSEC验证，性能优秀 |
| 广告过滤 | AdGuard Home (容器) | Pi-hole | 原生HTTPS管理，加密DNS，Go编写易部署 |
| VPN | WireGuard | OpenVPN, strongSwan | 内核原生，性能最优，配置极简 |
| API框架 | FastAPI (Python) | Go Gin, Rust Actix | 开发效率高，自动OpenAPI文档，async原生支持 |
| 前端框架 | Vue3 + Element Plus | React + Ant Design | 上手快，Element Plus管理界面组件成熟 |
| 包管理 | deb包 | Docker, Snap | 原生包管理，启动不依赖Docker |
| 容器运行时 | Docker (可选) | Podman, LXC | 生态最成熟，AdGuard等容器镜像丰富 |
| 配置语言 | YAML | TOML, JSON | netplan/FRR均用YAML，统一风格 |

## 2. 关键选型分析

### 2.1 netplan vs networkd 直接配置

| 维度 | netplan | networkd直接 |
|------|---------|-------------|
| 抽象层级 | 高，声明式 | 低，命令式 |
| Ubuntu集成 | 原生，开机即用 | 需手动管理 |
| 高级特性 | 部分不支持 | 完全支持 |
| 调试难度 | 需看生成结果 | 直观 |
| 回退能力 | 内置renderer回退 | 手动 |

**决策**：主路径用 netplan，遇到不支持的高级特性（如策略路由）通过 drop-in 文件补充 networkd 配置。

### 2.2 nftables vs iptables

| 维度 | nftables | iptables |
|------|----------|----------|
| 性能 | 更优（统一内核虚拟机） | 较差（多表多hook） |
| 语法 | 统一 | ipv4/ipv6分开 |
| Ubuntu支持 | 22.04+默认 | 遗留兼容 |
| 社区趋势 | 未来方向 | 逐步淘汰 |
| 规则原子更新 | 支持 | 不支持 |

**决策**：使用 nftables，不兼容 iptables。

### 2.3 FastAPI vs Go Gin

| 维度 | FastAPI | Go Gin |
|------|---------|--------|
| 开发速度 | 快 | 中等 |
| 部署 | 需Python环境 | 单二进制 |
| 性能 | 够用(异步IO) | 更高 |
| 生态 | 网络库丰富 | 标准库够用 |
| OpenAPI | 自动生成 | 需额外工具 |
| 运维脚本集成 | Python直接调用 | 需exec |

**决策**：Phase 1-3 使用 FastAPI 快速迭代。如果性能成为瓶颈，后续可将核心路径用 Go 重写。

### 2.4 Kea vs dnsmasq

| 维度 | Kea | dnsmasq |
|------|-----|---------|
| 性能 | 高（C++，多线程） | 中（单线程） |
| 功能 | DHCPv4/v6，租约数据库 | DHCPv4 + DNS 轻量合一 |
| 配置 | JSON，复杂 | 简单文本 |
| 规模 | 企业级 | 家用/SOHO |
| 依赖 | 较重（MySQL/PgSQL可选） | 极轻量 |

**决策**：默认使用 dnsmasq（轻量场景），提供 Kea 作为高性能选项。

## 3. 万兆性能路径选型

### 3.1 标准 NAT (1-5 Gbps)

- 内核 `net.ipv4.ip_forward` 转发
- RPS/RFS 多核负载均衡
- 网卡 GRO/GSO/LRO 硬件卸载
- **适用**：N100/J4125 千兆/2.5G 场景

### 3.2 优化 NAT (5-10 Gbps)

- nftables named set（O(1) 规则查找）
- conntrack 参数调优（hashsize/max）
- IRQ Affinity 绑定 CPU 核心
- TCP 缓冲区调优
- **适用**：万兆入户，i226-v/X710 网卡

### 3.3 XDP 加速 (10-40 Gbps)

- eBPF XDP 程序在网卡驱动层处理包
- XDP redirect 实现快速转发
- 仅处理简单 NAT/路由，复杂逻辑回退内核
- **适用**：万兆线速要求，X710/X550 网卡

### 3.4 DPDK (40-100 Gbps)

- 用户态轮询模式，完全绕过内核
- 需独占网卡（不能与内核共享）
- 开发复杂度高，Phase 4+ 考虑
- **适用**：数据中心/运营商场景

**决策**：Phase 1 实现标准 NAT + 优化参数；Phase 2 加入 RPS/IRQ 调优；Phase 4 可选 XDP 加速。

## 4. ARM 平台选型考量

| 维度 | x86_64 | ARM64 |
|------|--------|-------|
| 内核 | Ubuntu 原生内核 | 部分平台需 vendor 内核 |
| 网卡驱动 | 主线内核全覆盖 | 可能需 DKMS 编译 |
| AES 性能 | AES-NI | ARM CE (Cortex-A55+) |
| 万兆能力 | XDP/DPDK 可选 | 受限于 PCIe/网卡 |
| 热管理 | 不敏感 | 需温度监控+降频 |
| 存储 | SSD | eMMC/SD（减少写入） |

**决策**：ARM64 作为一等公民支持，但万兆性能目标仅对 x86_64 承诺；ARM64 目标千兆/2.5G。

## 5. 技术约束

1. **目标平台**：Ubuntu 24.04 LTS (x86_64 + aarch64)，兼容 22.04 LTS
2. **最低硬件 (x86)**：2核 CPU / 1GB RAM / 4GB 存储 / 2个网口
3. **最低硬件 (ARM)**：4核 CPU / 1GB RAM / 8GB 存储 (eMMC) / 2个网口
4. **推荐硬件 (x86 万兆)**：4核+ CPU (N100+) / 4GB RAM / 16GB SSD / 2个万兆口 (i226-v/X710)
5. **Python版本**：3.10+（Ubuntu 22.04 默认）
6. **内核版本**：5.15+（支持 WireGuard、XDP、VLAN offload）
7. **ARM 平台验证矩阵**：RK3568 (双千兆) / RK3588 (双2.5G) / RPi5 (千兆)
