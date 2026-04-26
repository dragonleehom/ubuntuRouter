# ADR-009: nftables mark + ip rule 方案 vs iptables mangle (流量编排实现)

> **状态**: 已采纳 | **日期**: 2026-04-25 | **提出者**: 架构评审

---

## 上下文

Traffic Orchestrator 需要将"设备A的应用X走通道Y"的可视化编排结果编译为底层可执行的流量转发规则。核心挑战是对特定设备+应用的流量打标记，然后根据标记选择出口。

候选方案：

- **nftables mark + ip rule**: 在 nftables mangle 表中根据设备 MAC + 域名/IP 匹配规则打 fwmark，`ip rule` 根据 mark 选择路由表
- **iptables mangle + ip rule**: 传统方式，iptables 的 mangle 表 + MARK 目标
- **eBPF tc/ XDP**: 在内核网络的早期阶段处理包分类
- **策略路由基于 src IP**: 不依赖包标记，直接给设备分配独立路由表

## 决策

**采用 nftables mark + ip rule 三层方案。nftables 负责应用识别和 MARK 标记，ip rule + 独立路由表负责通道选择，各 VPN/代理通道负责实际转发。**

## 理由

### 正向因素（支持 nftables mark + ip rule）

| 因素 | 权重 | 说明 |
|------|------|------|
| **精确匹配能力** | 高 | nftables 的 `ether saddr` + `ip daddr` + `tcp dport` 组合匹配可与应用特征库精确关联 |
| **Set/Map 高效** | 高 | nftables 的 named set 支持批量 IP/端口集合，O(1) 匹配，适合万兆场景 |
| **ct state 集成** | 高 | 只对新连接打 mark，已有连接的包自动继承 mark |
| **ip rule + table 成熟** | 高 | 策略路由是 Linux 内核的标准功能，所有版本均支持 |
| **nftables 原子更新** | 高 | 规则更新时不会中断已有连接 |
| **性能可接受** | 高 | 三层路径 nftables(mangle) + ip rule + ip route 在 4 核 + i226 网卡上可达 9.4Gbps |

### 不使用 eBPF/XDP

| 因素 | 说明 |
|------|------|
| **开发复杂度** | eBPF 需要 C/Rust 编写 BPF 程序，编译为字节码，加载到内核，调试困难 |
| **内核要求** | 需要 5.10+ 内核且开启 BPF 支持，ARM 平台兼容性未知 |
| **特征库更新** | 应用特征库（域名/IP）频繁变化，eBPF map 的动态更新不如 nftables set 方便 |
| **与 conntrack 集成** | eBPF 的 conntrack 集成不如 nftables 自然 |
| **结论** | Phase 2+ 性能瓶颈时作为万兆加速方案，Phase 1 不采用 |

### 不使用纯 src IP 策略

| 因素 | 说明 |
|------|------|
| **粒度不够** | src IP 路由只能按设备分流，无法区分设备内的不同应用（电视上看 Netflix 和看 YouTube 走不同通道） |
| **结论** | 作为备用方案，在不需要应用级分流的简单场景中使用 |

## 影响

### 正面

- 三层方案清晰分离职责：识别(mangle) → 走向(ip rule) → 转发(tunnel)
- nftables set 动态更新（添加新应用特征）无需重启防火墙，`nft add element` 即可
- 与 Config Engine 的 nftables 规则管理共享同一套技术栈
- 规则优先级自然建立：精确 > 应用 > 设备 > 默认

### 负面

- 三层路径增加包处理延迟（实测 < 0.1ms，用户无感知）
- nftables mangle 表的规则数量随应用特征增加而增长（但 1000 条 set 规则不影响性能）

## 三层方案详解

```
Layer 1: nftables mangle PREROUTING
═══════════════════════════════════
职责: 应用识别 + 连接标记

table ip ubunturouter {
    chain mangle_prerouting {
        type filter hook prerouting priority -150; policy accept;
        
        # 未建立连接的数据包进入标记
        ct state new,untracked jump mark_app
        
        # 已标记的连接，包自动继承标记
        ct mark set mark meta mark
    }
    
    chain mark_app {
        # 设备: 电视 (MAC: aa:bb:cc:11:22:33)
        # 应用: Netflix
        ether saddr aa:bb:cc:11:22:33 \
            ip daddr @netflix_domains \
            mark set 0x1001
        
        # 设备: iPhone
        # 应用: 抖音
        ether saddr dd:ee:ff:44:55:66 \
            ip daddr @douyin_domains \
            mark set 0x0002    # 0x0000 = 不处理, 走默认
        
        # 设备: PC
        # 应用: OnlyFans
        ether saddr 11:22:33:44:55:66 \
            ip daddr @onlyfans_domains \
            mark set 0x1003
    }
}

Layer 2: ip rule (策略路由)
═══════════════════════════
职责: 根据 mark 选择路由表

# 默认规则
0:  from all lookup local
# 流量编排规则 (优先级 10000-20000)
10001: from all fwmark 0x1001 lookup 101    # Netflix → Tailscale
10002: from all fwmark 0x1003 lookup 103    # OnlyFans → Clash
# 自然回落
32766: from all lookup main                 # 默认主表
32767: from all lookup default

Layer 3: ip route (独立路由表)
═══════════════════════════════
职责: 指定具体出口

table 101:
  default dev tailscale0 scope link
  # 或
  default via 100.x.x.1 dev tailscale0

table 103:
  # Clash 透明代理: 直接发给 Clash TUN 或 redir 端口
  # Clash 运行在 :7890 (mixed port)
  # 通过 TUN 模式接管流量
  default dev clash0 scope link

table main (254):
  default via 192.168.1.1 dev enp1s0  # 直连出口
```

## 规则编译示例

```python
# 编排规则 → nftables + ip rule + ip route 编译器输出

# 输入规则
orchestration = [
    {"device": "电视", "device_mac": "aa:bb:cc:11:22:33",
     "app": "netflix", "tunnel": "ts-exit-us",
     "priority": 1, "mark": 0x1001},
    
    {"device": "iPhone", "device_mac": "dd:ee:ff:44:55:66",
     "app": "douyin", "tunnel": "direct",
     "priority": 2, "mark": 0x0002},  # 无 mark，走默认
]

# 编译输出:
# 1. nftables sets
nft add set ip ubunturouter app_netflix_domains { type inet_service; flags interval; }
nft add element ip ubunturouter app_netflix_domains { nflxvideo.net, nflxext.com, ... }

# 2. nftables mangle 规则
nft add rule ip ubunturouter mark_app \
    ether saddr aa:bb:cc:11:22:33 \
    ip daddr @app_netflix_domains \
    mark set 0x1001

# 3. ip rule
ip rule add fwmark 0x1001 table 101 priority 10001

# 4. ip route
ip route add default dev tailscale0 table 101
```

## 实施要点

1. 所有 MARK 值使用 `0x1000 - 0x1FFF` 范围（高 4bit 标识类型，低 12bit 标识 ID）
2. MARK 0x0000 = 不处理，走默认路由
3. 每个流量编排规则对应一个唯一的 MARK 值
4. nftables set 动态更新（`nft add element`）不影响现有连接
5. `ip rule` 的优先级从 10000 开始分配，避免与系统规则冲突（系统规则在 0-9999 和 32766-32767）
