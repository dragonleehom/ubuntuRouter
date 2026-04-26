# 路由管理模块详细设计 — Routing Manager

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 对应 HLD 模块: 3.4 Routing Manager
> 依赖模块: Configuration Engine, Network Manager
> 后端技术: ip route/rule + FRR (动态路由)

---

## 1. 模块定位

Routing Manager 负责所有路由策略的管理，包括静态路由、策略路由（多路由表）、Multi-WAN 负载均衡与故障切换、线路健康检查、以及可选的 FRR 动态路由（OSPF/BGP）。

**设计原则**：
- 静态路由和多 WAN 策略通过 `ip route` / `ip rule` 直接操作内核路由表
- 动态路由通过 FRR (Free Range Routing) 管理
- Multi-WAN 健康检查独立于路由规则，避免假死导致路由震荡
- 每条 WAN 线路使用独立的路由表，主路由表仅包含默认路由指向 Metric 最小的 WAN

---

## 2. 数据结构

```python
# ubunturouter/routing/models.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from enum import Enum


class MultiWanStrategy(str, Enum):
    """多 WAN 负载均衡策略"""
    FAILOVER = "failover"            # 主备切换（默认）
    WEIGHTED_RR = "weighted-rr"     # 按权重轮询
    PCC = "pcc"                     # 按源IP/目的IP/端口哈希
    BALANCE = "balance"             # 按比率分配


class HealthCheckType(str, Enum):
    ICMP = "icmp"
    TCP = "tcp"
    HTTP = "http"
    DNS = "dns"
    SCRIPT = "script"               # 自定义脚本


class RouteSource(str, Enum):
    STATIC = "static"                # 静态路由
    MULTIWAN = "multiwan"            # Multi-WAN 策略生成
    FRR = "frr"                      # FRR 动态路由
    SYSTEM = "system"                # 系统自动（DHCP等）


class StaticRoute(BaseModel):
    """静态路由"""
    target: str                      # 目标网段: "0.0.0.0/0", "10.0.0.0/24"
    via: str                         # 下一跳: "192.168.1.1"
    metric: int = 100
    table: Optional[int] = None      # 路由表 ID，None=主表
    dev: Optional[str] = None        # 出接口名，可选（与 via 二选一）
    comment: Optional[str] = None
    enabled: bool = True


class PolicyRule(BaseModel):
    """策略路由规则 (ip rule)"""
    priority: int = 10000            # 优先级，数值越小越优先
    from_ip: Optional[str] = None    # 源 IP/网段
    to_ip: Optional[str] = None      # 目的 IP/网段
    iif: Optional[str] = None        # 入接口
    oif: Optional[str] = None        # 出接口
    fwmark: Optional[int] = None     # nftables 标记
    fwmask: Optional[str] = None     # 标记掩码
    table: int = Field(..., ge=1, le=32765)
    comment: Optional[str] = None
    enabled: bool = True


class HealthCheck(BaseModel):
    """线路健康检查"""
    type: HealthCheckType = HealthCheckType.ICMP
    target: str = "8.8.8.8"
    interval: int = 5                # 探测间隔（秒）
    timeout: int = 2                 # 单次超时（秒）
    count: int = 3                   # 失败次数触发切换
    success_count: int = 2           # 成功次数触发恢复
    port: Optional[int] = None       # TCP/HTTP 端口
    http_url: Optional[str] = None   # HTTP 检查路径
    expected_code: int = 200         # HTTP 期望状态码
    script_path: Optional[str] = None # 自定义脚本路径


class WanInterface(BaseModel):
    """WAN 接口路由配置"""
    name: str                        # 逻辑名: wan0
    device: str                      # 物理设备: enp1s0
    table_id: int                    # 路由表 ID (e.g., 101)
    metric: int = 100                # 主路由表默认路由 Metric
    weight: int = 1                  # 负载均衡权重
    health_check: HealthCheck = HealthCheck()
    enabled: bool = True


class MultiWanConfig(BaseModel):
    """多 WAN 配置"""
    enabled: bool = False
    strategy: MultiWanStrategy = MultiWanStrategy.FAILOVER
    wans: List[WanInterface] = []
    health_check_global: bool = True  # 全局启用健康检查
    sticky_connections: bool = True   # 同一流的包走同一个 WAN (PCC)
    reconnect_delay: int = 5          # 切换后的延迟补偿（秒）


class OSPFConfig(BaseModel):
    enabled: bool = False
    router_id: str
    networks: List[Dict[str, str]] = []   # [{network: "192.168.21.0/24", area: "0.0.0.0"}]
    interfaces: List[str] = []           # 参与 OSPF 的接口
    redistribute_connected: bool = True
    redistribute_static: bool = False
    metric: int = 10


class BGPConfig(BaseModel):
    enabled: bool = False
    as_number: int = 64512
    router_id: str
    neighbors: List[Dict[str, str]] = [] # [{ip: "10.0.0.2", remote_as: 64513}]
    networks: List[str] = []             # 宣告的网段
    redistribute_connected: bool = True
    redistribute_static: bool = False


class FRRConfig(BaseModel):
    """FRR 路由套件配置"""
    enabled: bool = False
    ospf: OSPFConfig = OSPFConfig()
    bgp: BGPConfig = BGPConfig()
    # 预留: rip, isis


class RoutingConfig(BaseModel):
    """路由完整配置"""
    static_routes: List[StaticRoute] = []
    policy_rules: List[PolicyRule] = []
    multi_wan: MultiWanConfig = MultiWanConfig()
    frr: FRRConfig = FRRConfig()
    # 内核参数
    ip_forward: bool = True
    rp_filter: Literal[0, 1, 2] = 1   # 反向路径过滤（1=strict, 2=loose）
    arp_ignore: int = 0
    arp_announce: int = 0


# ─── 运行时状态 ──────────────────────────────────────

class RouteEntry(BaseModel):
    """路由条目（运行状态）"""
    target: str
    via: Optional[str] = None
    dev: Optional[str] = None
    metric: int
    table: int = 254                  # 254=main
    proto: str = "static"             # static / kernel / dhcp / frr
    source: RouteSource


class WanStatus(BaseModel):
    """WAN 线路状态"""
    name: str
    device: str
    table_id: int
    gateway: Optional[str] = None     # 当前网关
    ip: Optional[str] = None          # WAN IP
    health: Literal["healthy", "degraded", "dead"] = "healthy"
    last_checked: str = ""
    last_healthy: str = ""
    latency_ms: Optional[float] = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    failover_count: int = 0
```

---

## 3. 核心接口

```python
# ubunturouter/routing/manager.py

from typing import List, Optional, Dict


class RoutingManager:
    """
    路由管理模块
    """

    # 路由表 ID 分配
    TABLE_MAIN = 254
    TABLE_LOCAL = 255
    TABLE_BASE_MULTIWAN = 100        # Multi-WAN 从 100 开始分配
    TABLE_BASE_CUSTOM = 200          # 自定义策略路由从 200 开始

    # ─── 路由查询 ───────────────────────────────────

    def list_routes(self, table: Optional[int] = None) -> List[RouteEntry]:
        """
        列出路由表
        
        实现: ip route show [table <id>]
        返回所有或指定路由表的路由条目
        """

    def list_policy_rules(self) -> List[PolicyRule]:
        """
        列出策略路由规则
        
        实现: ip rule show
        """

    # ─── WAN 状态 ──────────────────────────────────

    def list_wan_status(self) -> List[WanStatus]:
        """
        获取所有 WAN 线路状态
        
        实现:
        1. 从 config.routing.multi_wan.wans 读取 WAN 列表
        2. 对每条 WAN:
           - ip route show table {table_id} → 获取网关/IP
           - ping 健康检查目标 → 延迟/状态
           - ip addr show {device} → 获取 WAN IP
        """

    def get_active_wan(self) -> Optional[str]:
        """
        获取当前活跃的 WAN 线路名
        
        实现: 检查主路由表 (table main) 中 metric 最小的默认路由
        """

    # ─── 配置 Apply ─────────────────────────────────

    def apply(self, config: UbunturouterConfig) -> None:
        """
        应用路由配置
        
        委托给 RouteGenerator:
        1. 静态路由 → ip route add/replace
        2. 策略路由 → ip rule add/replace
        3. Multi-WAN → 分配路由表 + ip rule + 健康检查线程
        4. FRR → 生成 frr.conf → vtysh reload
        """


class HealthCheckEngine:
    """
    健康检查引擎（独立线程）
    
    职责：持续监控各 WAN 线路状态，故障时触发切换
    """

    def start(self):
        """
        启动健康检查循环
        
        流程:
        while True:
            for each WAN in config:
                status = check(wan.health_check)
                if status changed:
                    on_status_change(wan, status)
            sleep(min_interval_across_all_wans)
        """

    def check(self, hc: HealthCheck, device: str) -> dict:
        """
        执行单次健康检查
        
        ICMP: ping -c {count} -W {timeout} {target}
        TCP:  nc -zv -w {timeout} {target} {port}
        HTTP: curl -o /dev/null -s -w %{http_code} {url}
        DNS:  dig @{target} google.com +short
        """

    def on_status_change(self, wan: WanInterface, status: dict):
        """
        健康状态变化时触发
        
        健康→不健康: 计数, count >= threshold → failover
        不健康→健康: 计数, success >= threshold → restore
        
        failover:
        1. 将故障 WAN 的路由表规则优先级降低
        2. 将备用 WAN 的默认路由插入主表
        3. 更新 conntrack（可选，保持现有连接）
        """
```

---

## 4. Multi-WAN 实现细节

### 4.1 路由表规划

```
table main (254)：
  默认路由 → 当前活跃的 WAN（metric 最小）
  直连路由（系统自动配置）

table 101 (wan0):
  默认路由 → wan0 网关 (192.168.1.1)
  直连路由

table 102 (wan1):
  默认路由 → wan1 网关 (10.0.0.1)
  直连路由

ip rule:
  from all fwmark 0x1001 lookup 101  # 流量编排标记
  from all fwmark 0x1002 lookup 102
  iif wan0 lookup 101                 # WAN0 回程
  iif wan1 lookup 102                 # WAN1 回程
  from all lookup 101 priority 1000   # WAN0 默认
  from all lookup 102 priority 2000   # WAN1 备用
```

### 4.2 多 WAN 策略实现

**Failover（主备切换）**：
```
配置: wan0 (M=100, 主), wan1 (M=200, 备)

正常: 主表默认路由 → wan0 网关 (metric=100)
wan0 故障:
  1. 删除主表默认路由
  2. 添加主表默认路由 → wan1 网关 (metric=200)
  3. conntrack 更新（标记从 wan0 出去的流重新路由）
wan0 恢复:
  1. 恢复主表默认路由 → wan0 网关 (metric=100)
  2. 删除主表 wan1 默认路由（备用状态）
```

**Weighted-RR（按权重轮询）**：
```
配置: wan0 (weight=3), wan1 (weight=1)

创建 nftables set:
  set wan_pool {
    type mark
    flags interval
    elements = {
      0x1001 . 0x1002,    # 3份 wan0
      0x1003,             # 1份 wan1
    }
  }

ip rule:
  from all fwmark 0x1001 lookup 101  # wan0 路径 1
  from all fwmark 0x1002 lookup 101  # wan0 路径 2
  from all fwmark 0x1003 lookup 102  # wan1

新建连接:
  nft add rule ip ubunturouter mangle_PREROUTING \
    ct state new numgen random mod 4 \
    @wan_pool mark set
```

**PCC (Per-Connection Classification)**：
```
基于流的哈希确保同一连接走同一 WAN:
  src_ip, dst_ip, src_port, dst_port, proto
    
  nft add rule ip ubunturouter mangle_PREROUTING \
    ct state new mark set \
    jhash ip saddr . ip daddr . tcp sport . tcp dport mod 2 mark
  # 0 → table 101, 1 → table 102
```

### 4.3 健康检查实现

```python
# ubunturouter/routing/healthcheck.py

import subprocess, asyncio
from typing import Optional


class HealthChecker:
    """线路健康检查器"""

    async def check_icmp(self, target: str, count: int = 3,
                         timeout: int = 2) -> Optional[float]:
        """
        ICMP ping 检查
        
        返回: 平均延迟 (ms) 或 None（超时/失败）
        """
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', str(timeout), target],
            capture_output=True, text=True, timeout=timeout * count + 2
        )
        if result.returncode != 0:
            return None
        
        # 提取延迟: rtt min/avg/max/mdev = 12.345/15.678/18.901/2.345 ms
        import re
        match = re.search(r'rtt.*?= [\d.]+/([\d.]+)/', result.stdout)
        return float(match.group(1)) if match else None

    async def check_tcp(self, target: str, port: int,
                        timeout: int = 2) -> Optional[float]:
        """
        TCP 端口检查
        """
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((target, port))
            return (time.time() - start) * 1000
        except:
            return None
        finally:
            sock.close()

    async def check_http(self, url: str, timeout: int = 5,
                         expected_code: int = 200) -> bool:
        """
        HTTP 响应检查
        """
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as resp:
                    return resp.status == expected_code
        except:
            return False

    async def check_wan(self, wan: WanInterface) -> dict:
        """
        对一条 WAN 执行完整健康检查
        """
        hc = wan.health_check
        
        if hc.type == "icmp":
            latency = await self.check_icmp(hc.target, hc.count, hc.timeout)
            return {"healthy": latency is not None, "latency_ms": latency}
        
        elif hc.type == "tcp":
            latency = await self.check_tcp(hc.target, hc.port or 80, hc.timeout)
            return {"healthy": latency is not None, "latency_ms": latency}
        
        elif hc.type == "http":
            ok = await self.check_http(
                f"http://{hc.target}:{hc.port or 80}{hc.http_url or '/'}",
                hc.timeout,
                hc.expected_code or 200
            )
            return {"healthy": ok, "latency_ms": None}
        
        else:
            return {"healthy": True, "latency_ms": None}
```

---

## 5. FRR 动态路由集成

### 5.1 FRR 配置生成

```
# /etc/frr/frr.conf
# 由 UbuntuRouter Routing Manager 管理，请勿手动编辑

frr version 8.4
frr defaults traditional

hostname router
log syslog informational

! OSPF
router ospf
  router-id 192.168.21.1
  redistribute connected
  network 192.168.21.0/24 area 0.0.0.0
  network 10.0.0.0/24 area 0.0.0.0
  default-information originate
!

! BGP
router bgp 64512
  bgp router-id 192.168.21.1
  neighbor 10.0.0.2 remote-as 64513
  neighbor 10.0.0.2 description site-to-site-01
  !
  address-family ipv4 unicast
    network 192.168.21.0/24
    network 10.0.0.0/24
    neighbor 10.0.0.2 activate
  exit-address-family
!
```

### 5.2 FRR 管理

```python
# ubunturouter/engine/generators/frr.py

class FRRGenerator(ConfigGenerator):

    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        生成 frr.conf
        
        只处理 frr.enabled=True 的情况
        否则不生成/清空文件
        """
        frr = config.routing.frr
        if not frr.enabled:
            return {"/etc/frr/frr.conf": "# FRR disabled by UbuntuRouter"}

    def reload_command(self) -> List[str]:
        return ["vtysh", "-f", "/etc/frr/frr.conf"]

    def verify(self, config: UbunturouterConfig) -> bool:
        """验证: vtysh -c 'show running-config' 正常"""
```

### 5.3 FRR 与 Multi-WAN 共存

```
FRR 动态路由和 Multi-WAN 策略路由是两套独立系统：

┌─────────────────┐        ┌─────────────────┐
│  Multi-WAN      │        │  FRR OSPF/BGP   │
│  ─────────      │        │  ──────────────  │
│  策略路由层面    │        │  动态路由协议层面 │
│  ip rule        │        │  交换路由信息     │
│  ip route table │        │  注入到内核路由表  │
└────────┬────────┘        └────────┬────────┘
         │                         │
         ▼                         ▼
    ┌─────────────────────────────────┐
    │        Linux 内核路由表          │
    │  table main (254) + 自定义表    │
    │  FRR 注入的动态路由              │
    |  Multi-WAN 注入的策略路由        │
    |  用户配置的静态路由               │
    └─────────────────────────────────┘

限制: FRR 的动态路由和 Multi-WAN 故障切换不联动
如果使用 BGP/OSPF，FRR 的 metric 优先级高于 Multi-WAN 的切换逻辑。
此时需关闭 Multi-WAN 的健康检查切换（frr 接管路由决策）。
```

---

## 6. 完整路由表生成逻辑

```python
def generate_all_routes(config: UbunturouterConfig) -> dict:
    """
    生成所有路由相关命令
    
    返回: {
        "ip_route_add": [...],   # ip route add/replace
        "ip_rule_add": [...],    # ip rule add/replace
        "ip_route_del": [...],   # ip route del
        "ip_rule_del": [...],    # ip rule del
    }
    """
    commands = {"add": [], "del": [], "rules_add": [], "rules_del": []}
    
    # 1. 静态路由
    for route in config.routing.static_routes:
        if not route.enabled:
            continue
        target = route.target
        via = f"via {route.via}" if route.via else ""
        dev = f"dev {route.dev}" if route.dev else ""
        table = f"table {route.table}" if route.table else ""
        metric = f"metric {route.metric}"
        commands["add"].append(f"ip route add {target} {via} {dev} {metric} {table}")
    
    # 2. Multi-WAN 路由表
    if config.routing.multi_wan.enabled:
        for wan in config.routing.multi_wan.wans:
            if not wan.enabled:
                continue
            tid = wan.table_id
            # 各 WAN 的独立路由表 (通过 DHCP 或静态)
            # 由 NetplanGenerator 生成 WAN 口的单独路由表
            # 这里只维护策略规则
            commands["rules_add"].append(
                f"ip rule add from all table {tid} priority {60000 - wan.metric}"
            )
    
    # 3. 流编排规则 (由 Traffic Orchestrator 生成)
    #    放在这里生成对应的 ip rule
    
    # 4. 清理旧规则 (diff 后删除不再需要的)
    #    ... 
    
    return commands
```

---

## 7. 服务 Reload 顺序

```
Routing Manager apply()
    │
    ▼
┌──────────────────────┐
│ 1. 静态路由           │
│    ip route add ...  │  ← 不会影响现有连接
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. 策略路由规则       │
│    ip rule add ...   │  ← 新连接走新规则
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 3. FRR (如果启用)     │
│    vtysh -f ...      │  ← 如改变 OSPF/BGP，邻居会震荡
│    需 graceful restart│
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 4. 健康检查启动/重启  │
│    现有的检查线程停止  │
│    新线程启动         │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 5. 连通性检测         │
│    验证: WAN 可 ping │
│    外网, LAN 子网可达 │
└──────────────────────┘
```

---

## 8. 测试用例

| 测试场景 | 预期 |
|----------|------|
| 单 WAN 直连上网 | 主表默认路由指向 DHCP 网关，互联网可达 |
| 静态路由: 10.0.0.0/24 via 192.168.21.2 | 目标网段的流量走指定下一跳 |
| Multi-WAN Failover: wan0 断线 | 10s 内自动切换到 wan1 |
| Multi-WAN Failover: wan0 恢复 | 自动切回 wan0（或等待用户确认） |
| Weighted-RR: wan0(3) wan1(1) | 新建连接按 3:1 分配 |
| PCC: 流的连续性 | 同一连接始终走一个 WAN |
| 健康检查: TCP 端口 80 不可用 | 对应 WAN 标记为 degraded |
| 健康检查: ICMP timeout 3次 | 对应 WAN 标记为 dead，触发切换 |
| FRR OSPF 邻居建立 | 邻居表显示 Established |
| FRR BGP 路由宣告 | 邻居收到宣告的路由前缀 |
| 策略路由: from 192.168.21.100 table 200 | 该 IP 流量走独立路由表 |
