# Ubuntu Linux 软路由可行性报告

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 已通过

## 1. 概述

评估将 Ubuntu Linux 作为软件路由器运行的可行性，覆盖家庭/SOHO及中小型企业场景，并与主流软路由方案对比。

## 2. 核心能力评估

### 2.1 数据转发能力

| 能力 | 支持情况 | 说明 |
|------|----------|------|
| IP 转发 | ✅ 原生支持 | `net.ipv4.ip_forward=1`，内核级线速转发 |
| NAT/SNAT/DNAT | ✅ 原生支持 | nftables/iptables，masquerade 完备 |
| VLAN (802.1Q) | ✅ 原生支持 | `ip link add link eth0 name eth0.10 type vlan id 10` |
| 网桥/Bridge | ✅ 原生支持 | bridge + STP，可替代硬件交换 |
| Bonding/LAG | ✅ 原生支持 | LACP (802.3ad) 等多种模式 |
| 策略路由 | ✅ 原生支持 | 多路由表 + ip rule，支持 Multi-WAN |
| QoS/TC | ✅ 原生支持 | tc + fq_codel/CAKE，流量整形完备 |

### 2.2 路由协议

| 协议 | 方案 | 说明 |
|------|------|------|
| 静态路由 | ✅ 内核原生 | ip route / netplan |
| OSPF/BGP/EIGRP | ✅ FRRouting | 生产级路由协议栈，Ubuntu 官方源直接安装 |
| RIP/IS-IS | ✅ FRRouting | 同上 |
| MPLS | ✅ 内核+FRR | Linux 4.x+ 内核 MPLS 支持 |

### 2.3 防火墙与安全

| 能力 | 方案 | 说明 |
|------|------|------|
| 状态防火墙 | ✅ nftables | Ubuntu 22.04+ 默认，替代 iptables |
| UFW 前端 | ✅ ufw | 简化配置，底层 nftables |
| IDS/IPS | ✅ Suricata | 入侵检测/防御，可集成 nftables |
| 区域隔离 | ✅ firewalld | zone 模型，适合多接口场景 |

### 2.4 VPN 网关

| 协议 | 方案 | 典型吞吐 |
|------|------|----------|
| WireGuard | ✅ 内核原生 | 1Gbps+ (AES-NI) |
| IPSec/IKEv2 | ✅ strongSwan | 500Mbps+ |
| OpenVPN | ✅ openvpn | 200-400Mbps |
| VXLAN/GRE | ✅ 内核原生 | 隧道互联 |

### 2.5 DNS/DHCP 服务

| 服务 | 方案 | 说明 |
|------|------|------|
| DNS 缓存/递归 | Unbound / CoreDNS | 高性能递归解析 |
| DNS 过滤/广告拦截 | Pi-hole / AdGuard Home | 家庭场景刚需 |
| DHCP | Kea / dnsmasq | Kea 高性能，dnsmasq 轻量 |
| DDNS | ddclient / Cloudflare API | 动态 DNS |

### 2.6 高性能转发（进阶）

| 技术 | 吞吐 | 说明 |
|------|------|------|
| 内核转发 (标准) | 1-5 Gbps | 取决于 CPU/网卡 |
| XDP (eBPF) | 10-40 Gbps | 内核快速路径，包处理不经过协议栈 |
| DPDK | 40-100 Gbps | 用户态轮询，完全绕过内核 |
| VPP (FD.io) | 40-80 Gbps | Cisco 开源矢量包处理器 |

## 3. 与主流软路由方案对比

| 维度 | Ubuntu | OpenWrt | pfSense | VyOS |
|------|--------|---------|---------|------|
| **定位** | 通用服务器OS | 嵌入式路由OS | 防火墙/路由专用 | 路由器专用OS |
| **包管理** | apt（极丰富） | opkg（有限） | FreeBSD ports | apt（有限） |
| **Web UI** | 需自建/Cockpit | LuCI（成熟） | 原生WebGUI | 原生WebGUI |
| **资源占用** | 较高(512MB+) | 极低(64MB) | 中等(1GB+) | 中等(512MB+) |
| **启动速度** | 30-60s | 10-30s | 30-60s | 30-60s |
| **扩展性** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Docker支持** | 原生 | 有限 | 无 | 无 |
| **企业路由协议** | FRR（完整） | 有限 | FRR（有限） | FRR（完整） |
| **SDN/云集成** | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ |
| **社区规模** | 极大 | 大（中国社区强） | 大 | 中等 |
| **学习曲线** | 中等 | 低 | 低 | 低 |

## 4. 优势分析

1. **生态最强**：apt 仓库数万软件包，任何网络服务一键安装
2. **Docker 原生**：可容器化运行 Pi-hole、AdGuard Home、Clash、Suricata 等，互不干扰
3. **高性能潜力**：支持 XDP/DPDK/VPP，可达到专业路由器性能级别
4. **完整路由协议栈**：FRRouting 支持 OSPF/BGP/IS-IS/MPLS，企业级能力
5. **SDN/云原生**：OVS、Kubernetes CNI、Terraform 等无缝集成
6. **长期支持**：Ubuntu LTS 5年支持周期，安全更新有保障
7. **硬件兼容性广**：几乎所有 x86 网卡、USB 网卡即插即用
8. **脚本化/自动化**：netplan YAML 声明式配置，Ansible 友好

## 5. 劣势与挑战

1. **无原生 Web 管理界面**：需自行开发或集成 Cockpit/Webmin
2. **非路由专用**：默认配置需大量调优才适合路由场景
3. **资源占用较高**：最低 512MB RAM，不如 OpenWrt 轻量
4. **配置碎片化**：netplan / networkd / NetworkManager / nftables / tc 多套子系统，需统一管理
5. **缺乏一键式路由方案**：不像 OpenWrt 开箱即用，需自行组合
6. **安全加固需手动**：默认安装包含不必要的服务，需做最小化裁剪
7. **启动较慢**：相比嵌入式路由OS，启动时间偏长

## 6. 适用场景判定

| 场景 | 适合度 | 说明 |
|------|--------|------|
| **家庭软路由** | ⭐⭐⭐⭐ | 功能远超需求，但配置复杂度也高 |
| **SOHO 多WAN** | ⭐⭐⭐⭐⭐ | 多线负载均衡+VPN+DNS过滤，Ubuntu 强项 |
| **中小企业边缘路由** | ⭐⭐⭐⭐⭐ | FRR+BGP/OSPF+防火墙，完全可以替代商业方案 |
| **SD-WAN 节点** | ⭐⭐⭐⭐⭐ | Docker+VXLAN+WireGuard，天然优势 |
| **云路由/虚拟化** | ⭐⭐⭐⭐⭐ | Proxmox/ESXi/KVM 中运行，性能损失小 |
| **10Gbps+ 高性能网关** | ⭐⭐⭐⭐ | 需要 XDP/DPDK 加持，技术门槛高 |

## 7. 可行性结论

**结论：完全可行，且在扩展性和企业级能力上优于多数专用软路由方案。**

核心依据：
- Linux 内核本身就是全球部署最广的路由转发引擎
- Ubuntu 提供最完整的用户态工具链和包生态
- 性能从百兆到百 G 均有对应方案
- 唯一核心短板——**缺乏统一的 Web 管理界面**——可通过开发解决

**建议**：开发一套面向 Ubuntu 的软路由管理框架，将分散的子系统（netplan/nftables/FRR/DHCP/DNS）统一到声明式配置+Web GUI 之下，即可形成媲美 OpenWrt/VyOS 但扩展性更强的软路由方案。

## 8. 技术风险与缓解

| 风险 | 影响 | 缓解方案 |
|------|------|----------|
| netplan 不支持某些高级配置 | 中 | 回退到 networkd 直接配置 |
| nftables 规则冲突 | 中 | 拥有规则链的所有权，不允许外部工具修改 |
| 配置变更导致断网 | 高 | 连通性检测 + 自动回滚 + 60s 定时器 |
| Web UI 性能 | 低 | 前端独立于核心路由，挂掉不影响转发 |
| Ubuntu 升级兼容性 | 中 | 锁定 LTS 版本，充分测试后再支持新版 |
