# ADR-001: nftables vs iptables

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 需要一套防火墙系统来支持 Zone 模型、NAT、端口转发、自定义规则等功能。Linux 内核提供了两代防火墙框架：

- **iptables**: 传统方案，自 Linux 2.4 起存在，社区经验丰富
- **nftables**: 新一代方案，自 Linux 3.13 起，Ubuntu 22.04+ 默认

## 决策

**使用 nftables 作为 UbuntuRouter 的唯一防火墙后端。不兼容 iptables。**

## 理由

### 正向因素（支持 nftables）

| 因素 | 权重 | 说明 |
|------|------|------|
| **Ubuntu 默认** | 高 | Ubuntu 22.04+ 默认使用 nftables，iptables 仅为兼容层 |
| **性能** | 高 | nftables 使用统一的内核虚拟机，规则匹配 O(1)；iptables 多表多 Hook 有性能损耗 |
| **规则原子性** | 高 | nftables 支持原子更新，避免 iptables 的批量操作中间状态 |
| **语法统一** | 中 | IPv4/IPv6 使用同一语法，iptables 需 iptables+ip6tables 两套 |
| **集合/映射** | 高 | nftables 的 named set/map 支持 O(1) 查找，适合万兆场景的 IP 集合匹配 |
| **调试工具** | 中 | `nft monitor` 实时追踪规则变更，`nft list ruleset` 查看完整规则集 |
| **未来方向** | 高 | iptables 已被标记为遗留，nftables 是 Linux 网络的发展方向 |

### 反向因素（不选择 iptables）

| 因素 | 说明 |
|------|------|
| **社区熟悉度** | iptables 语法在中文社区更常见，但迁移成本仅限初始团队 |
| **成熟工具链** | 如 ufw/firewalld 均基于 nftables，iptables 的兼容性工具链已停止改进 |
| **用户自定义** | 用户从 OpenWrt 迁移过来可能熟悉 iptables，但 nftables 语法更清晰，学习曲线平缓 |

## 影响

### 正面

- 万兆场景下 nftables named set 提供 O(1) 匹配，显著提升性能
- 原子规则更新避免 Apply 时出现规则中间态导致的安全漏洞
- NftablesGenerator 只需输出一个 nft 文件，无需处理 iptables-save/restore 的格式拼接
- 与 Ubuntu 26.04 默认配置一致，无需额外安装兼容层

### 负面

- 团队需要掌握 nftables 语法（与 iptables 差异大）
- 部分老旧教程和社区脚本基于 iptables，不能直接使用
- Ubuntu 24.04+ 仍保留 `iptables-legacy` 兼容层，核心路由场景仍需注意避免规则冲突

## 备选方案

### iptables (legacy)
- 被 Ubuntu 标记为 deprecated
- 没有集合机制，规则逐条匹配，万兆场景性能瓶颈明显
- **结论**: 不适合

### iptables-nft (兼容层)
- 使用 iptables 语法但底层走 nftables 内核
- 语法兼容但功能受限（不支持 nftables 的集合、映射等高级特性）
- **结论**: 作为过渡方案可以，但限制了 nftables 的高级能力

## 实施要点

1. 所有 nftables 规则链以 `ubunturouter_` 前缀命名，确保唯一性
2. NftablesGenerator 输出的配置文件位于 `/etc/nftables.d/ubunturouter.conf`
3. 通过 `nft -f` 加载，使用 `nft -c -f` 做语法预检
4. 在 Ubuntu 24.04+ 上禁用 iptables-legacy，确保没有规则冲突
5. 提供迁移工具：`urctl doctor` 检测残留 iptables 规则并警告
