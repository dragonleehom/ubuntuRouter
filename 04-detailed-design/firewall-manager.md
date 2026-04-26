# 防火墙管理模块详细设计 — Firewall Manager

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 对应 HLD 模块: 3.3 Firewall Manager
> 依赖模块: Configuration Engine, Network Manager
> 后端技术: nftables

---

## 1. 模块定位

Firewall Manager 负责基于 Zone 模型的防火墙管理，包括 Zones 定义、Zone 间转发策略、NAT (Masquerade/DNAT/SNAT)、端口转发、自定义规则。所有规则通过 nftables 实现。

**设计原则**：
- UbuntuRouter 完全拥有 `ubunturouter_` 前缀的 nftables 规则链，不与其他工具冲突
- Zone 模型清晰：每个 Zone 对应一个 nftables chain 集合
- 配置变更时只修改目标文件，而不是增量 append/delete（防止碎片化）
- 自定义规则作为原始 nftables 片段嵌入，不解析其内容

---

## 2. 数据结构

```python
# ubunturouter/firewall/models.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from enum import Enum


class FirewallPolicy(str, Enum):
    ACCEPT = "accept"
    DROP = "drop"
    REJECT = "reject"

class Protocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    TCP_UDP = "tcp_udp"
    ICMP = "icmp"
    ANY = "any"

class NATType(str, Enum):
    MASQUERADE = "masquerade"
    SNAT = "snat"
    DNAT = "dnat"


class FirewallZone(BaseModel):
    """防火墙区域定义"""
    name: str
    masquerade: bool = False          # 该 Zone 出站是否 NAT
    forward_to: List[str] = []        # 允许转发到哪些 Zone
    isolated: bool = False            # 是否隔离（同一 Zone 内设备间禁止通信）
    input: FirewallPolicy = FirewallPolicy.DROP
    forward: FirewallPolicy = FirewallPolicy.DROP
    output: FirewallPolicy = FirewallPolicy.ACCEPT


class PortForwardRule(BaseModel):
    """端口转发规则"""
    name: str
    enabled: bool = True
    protocol: Protocol = Protocol.TCP
    from_zone: str = "wan"            # 外部 Zone
    from_port: int = Field(..., ge=1, le=65535)
    to_ip: str                        # 内部 IP
    to_port: Optional[int] = None     # None = from_port
    to_zone: str = "lan"              # 内部 Zone
    description: Optional[str] = None
    log: bool = False


class FirewallRule(BaseModel):
    """自定义防火墙规则（高级）"""
    name: str
    enabled: bool = True
    action: Literal["accept", "drop", "reject", "log", "jump"] = "accept"
    protocol: Optional[Protocol] = None
    src_zone: Optional[str] = None
    dst_zone: Optional[str] = None
    src_ip: Optional[str] = None      # CIDR or IP
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    src_port_range: Optional[str] = None  # "1024-65535"
    dst_port_range: Optional[str] = None
    ct_state: Optional[str] = None    # "new", "established", "related", "invalid"
    description: Optional[str] = None
    log: bool = False


class NATRule(BaseModel):
    """NAT 规则"""
    name: str
    enabled: bool = True
    type: NATType = NATType.MASQUERADE
    source: str                       # "192.168.21.0/24"
    outbound: str                     # 出口接口名
    to_ip: Optional[str] = None
    to_port: Optional[int] = None
    protocol: Optional[Protocol] = None
    description: Optional[str] = None


class ProxyARP(BaseModel):
    """代理 ARP 配置"""
    enabled: bool = False
    interfaces: List[str] = []


class FirewallGlobalConfig(BaseModel):
    """防火墙完整配置"""
    default_policy: 'DefaultPolicy'
    zones: Dict[str, FirewallZone]
    port_forwards: List[PortForwardRule] = []
    rules: List[FirewallRule] = []
    nat_rules: List[NATRule] = []
    proxy_arp: ProxyARP = ProxyARP()
    custom_nftables: Optional[str] = None  # 原始 nftables 代码段
    enable_syn_cookies: bool = True
    enable_rp_filter: bool = True
    enable_log_martians: bool = False


class DefaultPolicy(BaseModel):
    """默认策略"""
    input: FirewallPolicy = FirewallPolicy.DROP
    forward: FirewallPolicy = FirewallPolicy.DROP
    output: FirewallPolicy = FirewallPolicy.ACCEPT
```

---

## 3. 核心接口

```python
# ubunturouter/firewall/manager.py

from typing import List, Dict, Optional


class FirewallManager:
    """
    防火墙管理模块
    所有操作通过 Configuration Engine 间接执行
    """

    # ─── Zone 管理 ──────────────────────────────────

    def list_zones(self) -> Dict[str, FirewallZone]:
        """列出所有已定义的 Zone"""

    def get_zone(self, name: str) -> Optional[FirewallZone]:
        """获取 Zone 定义"""

    def get_zone_interfaces(self, zone_name: str) -> List[str]:
        """
        获取属于指定 Zone 的接口列表
        
        实现: 遍历 config.interfaces，匹配 firewall.zone
        """

    # ─── 规则管理 ──────────────────────────────────

    def list_port_forwards(self) -> List[PortForwardRule]:
        """列出所有端口转发规则"""

    def list_firewall_rules(self) -> List[FirewallRule]:
        """列出所有自定义规则"""

    def list_nat_rules(self) -> List[NATRule]:
        """列出所有 NAT 规则"""

    def check_port_conflict(self, port: int, 
                            protocol: str = "tcp") -> List[str]:
        """
        检查端口是否已被占用（用于预检）
        检查范围: 已配置的端口转发 + 系统已在监听的端口
        """

    # ─── 状态查询 ──────────────────────────────────

    def get_conntrack_count(self) -> int:
        """
        获取当前连接跟踪数
        
        实现: cat /proc/net/nf_conntrack | wc -l
        """

    def get_conntrack_table(self, limit: int = 100) -> List[dict]:
        """
        获取连接跟踪表
        
        实现: conntrack -L -o extended | head -n {limit}
        """

    def get_rule_hit_counts(self) -> Dict[str, int]:
        """
        获取规则命中计数
        
        实现: nft list chain ip ubunturouter <chain> | grep counter
        """

    # ─── 配置 Apply ─────────────────────────────────

    def apply(self, config: UbunturouterConfig) -> None:
        """
        将 config.firewall 转换为 nftables 配置
        
        委托给 NftablesGenerator:
        1. 解析 Zone 定义
        2. 生成 nftables 规则集
        3. 写入 /etc/nftables.d/ubunturouter.conf
        4. nft -f 加载
        """
```

---

## 4. nftables 规则生成细节

```python
# ubunturouter/engine/generators/nftables.py

class NftablesGenerator(ConfigGenerator):

    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        生成 nftables 配置文件
        
        nftables 规则集结构:
        
        table ip ubunturouter {
            # ── 全局变量 ──
            set trusted_ports { ... }
            
            # ── Zone 链 ──
            chain wan_input { ... }
            chain lan_input { ... }
            chain wan_forward { ... }
            chain lan_forward { ... }
            
            # ── 转发链 ──
            chain forward {
                type filter hook forward priority 0; policy drop;
                # Zone 间转发
            }
            
            # ── 输入链 ──
            chain input {
                type filter hook input priority 0; policy drop;
                # Zone 输入
            }
            
            # ── NAT 链 ──
            chain postrouting {
                type nat hook postrouting priority srcnat;
                # Masquerade
            }
            
            chain prerouting {
                type nat hook prerouting priority dstnat;
                # DNAT/端口转发
            }
        }
        """

    def _build_table(self) -> str:
        """
        构建 nftables table
        
        table ip ubunturouter {
            # include zone chains
            # include forward rules
            # include nat rules
        }
        """

    def _build_zone_chains(self, config: FirewallConfig) -> List[str]:
        """
        为每个 Zone 生成 input/forward/output chain
        
        # Zone: wan
        chain wan_forward {
            # 允许 established
            ct state established,related accept
            # 转发到 lan
            iifname "br-lan" accept
            # 转发到 guest
            iifname "vlan10-guest" accept
            # 默认策略 (继承 forward chain 的 policy)
        }
        
        # Zone: guest (isolated)
        chain guest_forward {
            ct state established,related accept
            # isolated: 不转发到 lan
            oifname "br-lan" drop
            # 只允许出站到 wan
            oifname $WAN_IFACE accept
        }
        """

    def _build_forward_chain(self, zones: Dict[str, FirewallZone],
                            interfaces: List[InterfaceConfig]) -> str:
        """
        生成 forward 主链
        
        关键逻辑：
        · 每个 Zone 的 zone_forward chain 通过 jump 调用
        · 允许 established/related 流量回程
        · 禁止 invalid 状态（防攻击）
        · drop 默认
        
        示例:
        chain forward {
            type filter hook forward priority 0; policy drop;
            
            # 放行 established/related
            ct state established,related accept
            
            # 丢弃无效包
            ct state invalid drop
            
            # Zone 间转发
            iifname $IFACE_WAN jump wan_forward
            iifname $IFACE_LAN jump lan_forward
            iifname $IFACE_GUEST jump guest_forward
        }
        """

    def _build_input_chain(self, zones: Dict[str, FirewallZone],
                          interfaces: List[InterfaceConfig]) -> str:
        """
        生成 input 主链
        
        · ping: 允许（诊断需要）
        · DHCP: 允许 (udp 67)
        · DNS: 允许 (tcp/udp 53)
        · API Server: 允许 (tcp 8080)
        · Web GUI: 允许 (tcp 443)
        · SSH: 允许 (tcp 22, 仅 LAN)
        · WireGuard: 允许 (udp 51820)
        
        chain input {
            type filter hook input priority 0; policy drop;
            
            # 允许回环
            iif lo accept
            
            # 允许 established
            ct state established,related accept
            
            # 允许 ICMP (ping)
            ip protocol icmp accept
            
            # 允许 DHCP
            udp dport 67 accept
            
            # 允许 Web GUI (LAN only)
            iifname br-lan tcp dport { 80, 443 } accept
            
            # 允许 API (LAN only)
            iifname br-lan tcp dport 8080 accept
            
            # 允许 SSH (LAN only)
            iifname br-lan tcp dport 22 accept
            
            # 允许 WireGuard
            udp dport 51820 accept
            
            # 允许 DNS
            udp dport 53 accept
            tcp dport 53 accept
            
            # 各 Zone input chain（来自 WAN 的全部 drop）
            iifname $IFACE_WAN jump wan_input
            iifname $IFACE_LAN jump lan_input
        }
        """

    def _build_nat_chains(self, firewall: FirewallConfig,
                         interfaces: List[InterfaceConfig]) -> List[str]:
        """
        生成 NAT 链
        
        chain postrouting {
            type nat hook postrouting priority srcnat; policy accept;
            
            # Masquerade: 来自 LAN 的流量出 WAN 时 NAT
            ip saddr 192.168.0.0/16 oifname enp1s0 masquerade
        }
        
        chain prerouting {
            type nat hook prerouting priority dstnat; policy accept;
            
            # 端口转发: 外网访问 8080 → 内网 192.168.21.50:80
            iifname enp1s0 tcp dport 8080 dnat to 192.168.21.50:80
        }
        """

    def _build_port_forwards(self, rules: List[PortForwardRule],
                           interfaces: List[InterfaceConfig]) -> List[str]:
        """
        端口转发 → DNAT
        
        示例:
        # Port Forward: web (WAN 8443 → 192.168.21.50:443)
        iifname enp1s0 tcp dport 8443 dnat to 192.168.21.50:443
        
        # 同时需要在 forward chain 添加放行:
        # iifname enp1s0 oifname br-lan ip daddr 192.168.21.50 tcp dport 443 accept
        """

    def _build_custom_rules(self, custom_nftables: Optional[str],
                           zones: Dict[str, FirewallZone]) -> str:
        """
        嵌入自定义 nftables 规则
        
        用户输入的原生 nftables 语法，直接嵌入到 ubunturouter 表的对应位置。
        支持的位置标记:
        # @CUSTOM_INPUT
        # @CUSTOM_FORWARD
        # @CUSTOM_NAT_PREROUTING
        # @CUSTOM_NAT_POSTROUTING
        """
```

---

## 5. 完整 nftables 配置示例

### 5.1 标准双网口场景

```nftables
# /etc/nftables.d/ubunturouter.conf
# Generated by UbuntuRouter Config Engine
# DO NOT EDIT MANUALLY — changes will be overwritten

table ip ubunturouter {

    # ── 变量定义 ──
    define IFACE_WAN = "enp1s0"
    define IFACE_LAN = "br-lan"
    define NET_LAN  = "192.168.21.0/24"

    # ── Forward (转发) ──
    chain forward {
        type filter hook forward priority 0; policy drop;

        # 放行回程流量
        ct state established,related accept

        # 丢弃无效包
        ct state invalid drop

        # 来自 LAN → 各 zone 策略
        iifname $IFACE_LAN jump lan_forward

        # 来自 WAN → 各 zone 策略
        iifname $IFACE_WAN jump wan_forward
    }

    # ── LAN Forward ──
    chain lan_forward {
        # LAN 可以访问所有网络
        oifname $IFACE_WAN accept
    }

    # ── WAN Forward ──
    chain wan_forward {
        # WAN 进站: 只有端口转发才放行
        # 没有端口转发规则时，WAN→LAN 全部拒绝
    }

    # ── Input (入站到路由器本身) ──
    chain input {
        type filter hook input priority 0; policy drop;

        iif lo accept
        ct state established,related accept

        # ICMP
        ip protocol icmp accept

        # 服务入口 (仅允许 LAN)
        iifname $IFACE_LAN tcp dport { 80, 443 } accept
        iifname $IFACE_LAN tcp dport 8080 accept
        iifname $IFACE_LAN tcp dport 22 accept
        iifname $IFACE_LAN udp dport { 53, 67 } accept
        iifname $IFACE_LAN tcp dport 53 accept

        # WireGuard
        udp dport 51820 accept
    }

    # ── NAT ──
    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        ip saddr $NET_LAN oifname $IFACE_WAN masquerade
    }

    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        # 端口转发规则将插入此处
    }

    # ── 端口转发规则集 ──
    set port_forwards {
        type ipv4_addr . inet_service
        flags interval
        elements = {
            192.168.21.50 . 443,  # web
            192.168.21.60 . 8080, # homeassistant
        }
    }
}

# 添加回程放行规则（NftablesGenerator 自动添加）
# 挂载到 port_forwards 集合上
```

### 5.2 单网口 WANLAN 场景

```nftables
# 单网口模式下的防火墙差异：
# - 没有 WAN/LAN 接口分离
# - 所有流量经过同一网口
# - 通过 IP 地址区分 WAN/LAN

table ip ubunturouter {

    define IFACE = "ens3"
    define NET_LAN = "192.168.21.0/24"

    chain forward {
        type filter hook forward priority 0; policy drop;
        ct state established,related accept
        ct state invalid drop

        # 来自 LAN 段的流量放行
        ip saddr $NET_LAN oifname $IFACE accept

        # 非 LAN 段的流量指向 WAN（正向流量）
        ip daddr $NET_LAN iifname $IFACE accept  # 端口转发回程
    }

    chain input {
        type filter hook input priority 0; policy drop;
        iif lo accept
        ct state established,related accept

        # 从 LAN 网段访问路由器服务
        ip saddr $NET_LAN tcp dport { 80, 443, 8080, 22 } accept
        ip saddr $NET_LAN udp dport { 53, 67 } accept

        # WAN 侧只允许 WireGuard
        ip saddr != $NET_LAN udp dport 51820 accept
    }

    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        ip saddr $NET_LAN oifname $IFACE masquerade
    }
}
```

---

## 6. 特殊场景处理

### 6.1 Zone 间隔离策略

| 源 Zone → 目标 Zone | 默认行为 | 说明 |
|---------------------|----------|------|
| lan → wan | ✅ allow | 默认，用户可访问外网 |
| lan → guest | ❌ block | 内网不可访问访客网络 |
| guest → wan | ✅ allow | 访客可上网 |
| guest → lan | ❌ block | 访客不可访问内网 |
| wan → lan | ❌ block | 仅端口转发可达 |
| wan → dmz | ❌ block | 仅端口转发可达 |
| dmz → wan | ✅ allow | DMZ 可出站 |
| dmz → lan | ❌ block | 默认隔离 |

### 6.2 连接跟踪 (conntrack) 调优

```bash
# /etc/sysctl.d/99-ubunturouter-conntrack.conf

# Conntrack 最大值（根据内存自动计算）
# 每 1GB 内存 ≈ 100K 连接
net.netfilter.nf_conntrack_max = 500000

# Conntrack hash table (max 的 1/4)
net.netfilter.nf_conntrack_buckets = 125000

# 超时（秒）
net.netfilter.nf_conntrack_tcp_timeout_established = 86400
net.netfilter.nf_conntrack_tcp_timeout_time_wait = 120
net.netfilter.nf_conntrack_tcp_timeout_close_wait = 60
net.netfilter.nf_conntrack_udp_timeout = 30
net.netfilter.nf_conntrack_icmp_timeout = 30

# 万兆场景额外优化
net.core.netdev_budget = 600
net.core.netdev_budget_usecs = 4000
```

### 6.3 防止把自己锁在门外

```python
def guard_against_lockout(config: UbunturouterConfig) -> None:
    """
    Apply 前的安全检查：
    
    1. 检查 LAN 接口或 WANLAN 接口是否在 input 策略中允许
       SSH/HTTP/HTTPS 端口（当前 Web GUI 使用的端口）
    
    2. 如果没有任何允许 Web GUI 访问的规则 → 警告（不阻止 Apply）
    
    3. 检查 SSH 端口是否在 LAN zone 的 input 策略中放行
       → 如果 SSH 已禁用，且 Web GUI 也关闭 → 严重警告
    
    4. 检查至少有一个接口的 role 为 LAN 或 WANLAN
       → 如果没有 LAN 接口，用户无法访问 Web GUI
    """
```

---

## 7. 与 Network Manager 的交互

```
Firewall Manager apply()
    │
    ▼
从 config 读取 firewall.zones 和 interfaces
    │
    ▼
从 Network Manager 获取 Zone → Interface 映射表
    zone: wan → interface: enp1s0
    zone: lan → interface: br-lan
    │
    ▼
NftablesGenerator.generate()
    zone name + interface name → nftables ifname
    │
    ▼
写入 /etc/nftables.d/ubunturouter.conf
    │
    ▼
nft -f /etc/nftables.d/ubunturouter.conf
    │
    ▼
验证: nft list ruleset ip ubunturouter
```

---

## 8. 测试用例

| 测试场景 | 预期 |
|----------|------|
| LAN→WAN 出站 NAT | 客户端 web 访问正常，WAN 侧看到的是公网 IP |
| WAN→LAN 端口转发 8080→192.168.21.50:80 | 外网访问 WAN_IP:8080 到达内网 192.168.21.50:80 |
| LAN→Guest 隔离 | 内网设备 ping 不通 guest 网段的 IP |
| Guest→WAN 出站 | 访客可上网 |
| 自定义规则: 禁止 192.168.21.50 对外访问 | 该 IP 的网络访问被阻断 |
| Drop default + 未放行 SSH | SSH 连接被拒绝（预期行为） |
| 单网口 WANLAN + 端口转发 | 端口转发和 NAT 均正常工作 |
| nftables 语法错误 Apply | Apply 失败，不执行，给出错误详情 |
| conntrack 表满 | 自动调优参数在 sysctl 中生效 |
| 规则命中计数 | 每条规则有 counter，可在 Web GUI 查看 |
