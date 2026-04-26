# ADR-004: dnsmasq vs Kea vs Unbound (DHCP/DNS 方案)

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

UbuntuRouter 需要 DHCP 地址分配和 DNS 解析转发/缓存服务。候选方案：

- **dnsmasq**: 轻量级，DHCP+DNS 一体化，OpenWrt/家用软路由标配
- **Kea**: ISC 的现代 DHCP 服务，支持多线程、数据库后端
- **Unbound**: NLnet Labs 的递归 DNS 解析器，支持 DNSSEC 验证
- **组合方案**: dnsmasq (DHCP) + Unbound (DNS 缓存/递归)

## 决策

**默认使用 dnsmasq 同时提供 DHCP+DNS（轻量一体化）。当需要高性能 DNS 递归解析时，切换到 dnsmasq (DHCP only) + Unbound (DNS 递归) 分离模式。Kea 作为 DHCP 的高性能备选，不列为默认。**

## 理由

### 正向因素（支持 dnsmasq 默认）

| 因素 | 权重 | 说明 |
|------|------|------|
| **DHCP+DNS 一体化** | 高 | 在 SOHO/家庭场景下，一个服务解决两个问题，部署简单、配置统一 |
| **成熟度** | 高 | OpenWrt 等所有开源路由器均使用 dnsmasq，经过了极其广泛的验证 |
| **资源占用** | 高 | dnsmasq 内存占用 < 10MB，对路由器这种内存敏感场景非常友好 |
| **配置简洁** | 高 | 一个配置文件覆盖 DHCP 和 DNS，维护成本低 |
| **租约文件** | 高 | 纯文本 lease 文件，Device Detector 可直接解析 |
| **DHCP 选项** | 中 | 支持 DHCP option 43/66/119/150 等常见自定义选项 |
| **PXE 启动** | 中 | 内置 PXE 支持 |

### 选择 Unbound 作为 DNS 分离方案

| 因素 | 权重 | 说明 |
|------|------|------|
| **DNSSEC 验证** | 高 | Unbound 原生 DNSSEC 验证，dnsmasq 的 DNSSEC 支持较有限 |
| **递归解析性能** | 高 | Unbound 的多线程递归解析器性能优秀 |
| **缓存能力** | 中 | 可配置 200MB+ 缓存，适合大并发查询场景 |
| **上游转发** | 中 | 支持 DoT/DoH 作为上游 |
| **API/控制** | 中 | unbound-control 提供远程管理能力 |

### 不选择 Kea 作为默认

| 因素 | 说明 |
|------|------|
| **复杂度** | Kea 需要数据库后端（MySQL/PgSQL），对于 SOHO 场景过度设计 |
| **部署方式** | 多进程架构（kea-dhcp4 / kea-dhcp6 / kea-ctrl-agent），配置管理复杂 |
| **无内置 DNS** | Kea 只做 DHCP，DNS 需要额外部署 Unbound/BIND |
| **资源占用** | Kea + 数据库的内存占用远高于 dnsmasq |
| **适用场景** | 更适合 ISP/企业级的 DHCP 部署（几十万租约），家庭网络用不上 |

## 影响

### 正面

- 默认一键部署，无需额外配置，DHCP+DNS+DNS 缓存在一个服务中
- 设备识别直接解析 `/var/lib/misc/dnsmasq.leases`，免去数据库查询
- 熟悉 OpenWrt 的用户迁移无门槛

### 负面

- dnsmasq 单线程架构，在 500+ 并发 DNS 查询场景下可能成为瓶颈（但 SOHO 场景通常 < 100）
- dnsmasq 的 DNSSEC 验证不如 Unbound 完整

## 三种部署模式

### 模式 A: 轻量集成（默认）

```
dnsmasq → 同时提供 DHCP + DNS 转发
         → 上游 DNS (223.5.5.5)
         → cache-size=10000
适用: 家庭 / SOHO，设备数 < 100
```

### 模式 B: DNS 分离（推荐高性能）

```
dnsmasq → DHCP only (port=0, DNS 功能关闭)
Unbound → DNS 递归 + DNSSEC + 缓存
         → 监听 53 端口
         → 上游转发或递归解析
适用: 设备数 100-500，需要 DNSSEC
```

### 模式 C: 全分离（最大性能 + 广告过滤）

```
dnsmasq → DHCP only
Unbound → DNS 递归 + 缓存 → 监听 53
AdGuard → 广告过滤 → 监听 5353
         → dnsmasq 的 DHCP 选项中 DNS=192.168.21.1:5353
适用: 需要广告过滤 + 高性能 DNS
```

## 实施要点

1. 默认安装 `dnsmasq`，提供 `--dns-mode=adguard` `--dns-mode=unbound` 安装选项
2. DnsmasqGenerator 负责生成 `/etc/dnsmasq.d/ubunturouter.conf`
3. UnboundGenerator 负责生成 `/etc/unbound/unbound.conf.d/ubunturouter.conf`
4. AdGuard 集成通过 Docker Compose 管理，不直接安装 deb
5. 配置中的 `dns_mode` 字段控制选择哪个模式
