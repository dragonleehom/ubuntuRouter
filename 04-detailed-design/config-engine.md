# 配置引擎详细设计 — Configuration Engine

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 对应 HLD 模块: 3.1 Configuration Engine (Core)
> 依赖性: 无（最底层模块，所有 Manager 依赖此模块）

---

## 1. 模块定位

Configuration Engine 是整个 UbuntuRouter 的核心底层模块，负责：

1. **统一配置源**：以单一 YAML 文件 `config.yaml` 作为所有配置的权威来源
2. **配置校验**：Schema 校验 + 语义校验，确保配置合法
3. **Diff 计算**：对比新旧配置，生成最小变更集
4. **配置生成**：将统一配置翻译为各子系统的原生配置文件
5. **原子 Apply**：按正确顺序写入配置文件并 reload 服务
6. **回滚机制**：连通性检测失败时自动恢复上一快照
7. **快照管理**：每次变更自动创建快照，支持手动回滚

---

## 2. 数据结构定义

### 2.1 核心配置模型 (Pydantic)

```python
# ubunturouter/config/models.py

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Literal
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from enum import Enum


# ─── 枚举 ─────────────────────────────────────────────

class InterfaceRole(str, Enum):
    WAN = "wan"
    LAN = "lan"
    DMZ = "dmz"
    GUEST = "guest"
    MANAGEMENT = "management"
    WANLAN = "wanlan"  # 单网口模式
    BOND = "bond"

class IPMethod(str, Enum):
    DHCP = "dhcp"
    STATIC = "static"
    PPPOE = "pppoe"
    DISABLED = "disabled"

class BondMode(str, Enum):
    BALANCE_RR = "balance-rr"
    ACTIVE_BACKUP = "active-backup"
    BALANCE_XOR = "balance-xor"
    BROADCAST = "broadcast"
    LACP_8023AD = "802.3ad"
    BALANCE_TLB = "balance-tlb"
    BALANCE_ALB = "balance-alb"

class FirewallPolicy(str, Enum):
    ACCEPT = "accept"
    DROP = "drop"
    REJECT = "reject"

class MultiWanStrategy(str, Enum):
    FAILOVER = "failover"
    WEIGHTED_RR = "weighted-rr"
    WEIGHTED_FAILOVER = "weighted-failover"
    PCC = "pcc"

class AppType(str, Enum):
    CONTAINER = "container"
    VM = "vm"


# ─── 网络接口 ─────────────────────────────────────────

class VlanConfig(BaseModel):
    id: int = Field(..., ge=1, le=4094)
    name: Optional[str] = None
    ipv4: Optional['IPConfig'] = None
    ipv6: Optional['IPConfig'] = None
    firewall: Optional['FirewallZoneRef'] = None
    dhcp: Optional['DHCPConfig'] = None

class BondConfig(BaseModel):
    mode: BondMode = BondMode.LACP_8023AD
    slaves: List[str] = Field(..., min_length=2)
    mii_monitor_interval: int = 100  # ms
    ipv4: Optional['IPConfig'] = None
    ipv6: Optional['IPConfig'] = None

class IPConfig(BaseModel):
    method: IPMethod = IPMethod.DHCP
    address: Optional[str] = None       # "192.168.21.1/24"
    gateway: Optional[str] = None       # "192.168.21.1"
    dns: Optional[List[str]] = None     # ["223.5.5.5"]
    mtu: Optional[int] = None           # 1500

class WanUplink(BaseModel):
    """单网口 WANLAN 模式下，WAN 上行配置"""
    method: IPMethod = IPMethod.DHCP
    username: Optional[str] = None
    password: Optional[str] = None

class InterfaceConfig(BaseModel):
    name: str                           # 逻辑名: wan0, lan0
    type: Literal["ethernet", "bridge", "vlan", "bond", "wireless"]
    device: Optional[str] = None        # 物理设备: enp1s0
    role: InterfaceRole = InterfaceRole.LAN
    ports: Optional[List[str]] = None   # bridge member ports
    vlans: Optional[List[VlanConfig]] = None
    bond: Optional[BondConfig] = None
    ipv4: Optional[IPConfig] = None
    ipv6: Optional[IPConfig] = None
    firewall: Optional['FirewallZoneRef'] = None
    wan_uplink: Optional[WanUplink] = None  # 仅 WANLAN 模式
    mtu: Optional[int] = None
    mac: Optional[str] = None           # MAC 地址覆盖
    dhcp: Optional['DHCPConfig'] = None
    enabled: bool = True

    @model_validator(mode='after')
    def validate_interface(self):
        # WANLAN 模式必须有 wan_uplink
        if self.role == InterfaceRole.WANLAN and not self.wan_uplink:
            raise ValueError("WANLAN mode requires wan_uplink config")
        # bridge 必须有 ports
        if self.type == "bridge" and not self.ports:
            raise ValueError("Bridge interface must have at least one port")
        # ethernet 必须有 device
        if self.type == "ethernet" and not self.device:
            raise ValueError("Ethernet interface must have a device")
        return self


# ─── 防火墙 ───────────────────────────────────────────

class FirewallZoneRef(BaseModel):
    zone: str

class FirewallZone(BaseModel):
    name: str
    masquerade: bool = False
    forward_to: List[str] = []
    isolated: bool = False
    input: FirewallPolicy = FirewallPolicy.DROP
    forward: FirewallPolicy = FirewallPolicy.DROP
    output: FirewallPolicy = FirewallPolicy.ACCEPT

class PortForwardRule(BaseModel):
    name: str
    enabled: bool = True
    protocol: Literal["tcp", "udp", "tcp_udp"] = "tcp"
    from_zone: str = "wan"
    from_port: int = Field(..., ge=1, le=65535)
    to_ip: str
    to_port: Optional[int] = None  # None = same as from_port
    to_zone: str = "lan"
    description: Optional[str] = None

class FirewallRule(BaseModel):
    name: str
    enabled: bool = True
    action: Literal["accept", "drop", "reject"] = "accept"
    protocol: Optional[Literal["tcp", "udp", "tcp_udp", "icmp"]] = None
    src_zone: Optional[str] = None
    dst_zone: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    description: Optional[str] = None

class NATRule(BaseModel):
    source: str
    outbound: str
    type: Literal["masquerade", "snat", "dnat"] = "masquerade"
    to_ip: Optional[str] = None
    enabled: bool = True

class FirewallConfig(BaseModel):
    default_policy: 'DefaultPolicy'
    zones: Dict[str, FirewallZone]
    port_forwards: List[PortForwardRule] = []
    rules: List[FirewallRule] = []
    custom_nftables: Optional[str] = None  # 原始 nftables 片段


# ─── 路由 ─────────────────────────────────────────────

class StaticRoute(BaseModel):
    target: str
    via: str
    metric: Optional[int] = None
    table: Optional[int] = None
    comment: Optional[str] = None

class HealthCheck(BaseModel):
    target: str = "8.8.8.8"
    interval: int = 5  # seconds
    timeout: int = 2   # seconds
    count: int = 3

class MultiWanConfig(BaseModel):
    enabled: bool = False
    strategy: MultiWanStrategy = MultiWanStrategy.FAILOVER
    wan_interfaces: List[str] = []
    health_check: HealthCheck = HealthCheck()
    weights: Optional[Dict[str, int]] = None  # interface_name -> weight

class FRROption(BaseModel):
    enabled: bool = False
    router_id: Optional[str] = None
    ospf: Optional['OSPFConfig'] = None
    bgp: Optional['BGPConfig'] = None

class OSPFConfig(BaseModel):
    networks: List[str] = []

class BGPConfig(BaseModel):
    as_number: int = 64512
    neighbors: List[dict] = []

class RoutingConfig(BaseModel):
    multi_wan: MultiWanConfig = MultiWanConfig()
    static_routes: List[StaticRoute] = []
    frr: FRROption = FRROption()
    policy_rules: List[dict] = []


# ─── DHCP ─────────────────────────────────────────────

class StaticLease(BaseModel):
    mac: str
    ip: str
    hostname: Optional[str] = None

class DHCPConfig(BaseModel):
    interface: str
    enabled: bool = True
    range_start: str = "192.168.21.50"
    range_end: str = "192.168.21.200"
    gateway: str = "192.168.21.1"
    dns: List[str] = ["192.168.21.1"]
    lease_time: int = 86400  # seconds
    domain: Optional[str] = "lan"
    static_leases: List[StaticLease] = []
    options: Dict[str, str] = {}  # 自定义 DHCP 选项


# ─── DNS ─────────────────────────────────────────────

class DNSConfig(BaseModel):
    upstream: List[str] = ["223.5.5.5", "119.29.29.29"]
    doh_upstream: Optional[List[str]] = None
    blocking: bool = False
    blocklists: List[str] = []
    whitelist: List[str] = []
    rewrite: Dict[str, str] = {}  # domain -> ip
    enable_dnssec: bool = True
    cache_size: int = 10000
    custom_dnsmasq: Optional[str] = None


# ─── VPN ─────────────────────────────────────────────

class WireguardPeer(BaseModel):
    name: str
    public_key: str
    preshared_key: Optional[str] = None
    allowed_ips: List[str] = ["0.0.0.0/0"]
    endpoint: Optional[str] = None
    persistent_keepalive: int = 25
    enabled: bool = True

class WireguardConfig(BaseModel):
    enabled: bool = False
    interface: str = "wg0"
    listen_port: int = 51820
    private_key: Optional[str] = None
    address: str = "10.0.0.1/24"
    mtu: int = 1420
    peers: List[WireguardPeer] = []

class VPNConfig(BaseModel):
    wireguard: WireguardConfig = WireguardConfig()
    ipsec: Optional[dict] = None


# ─── 系统 ─────────────────────────────────────────────

class SystemConfig(BaseModel):
    hostname: str = "router"
    timezone: str = "Asia/Shanghai"
    password_hash: Optional[str] = None
    ntp_servers: List[str] = ["ntp.aliyun.com", "ntp.ubuntu.com"]
    api_port: int = 8080
    web_port: int = 443
    ssh_port: int = 22


# ─── 顶级配置 ─────────────────────────────────────────

class UbunturouterConfig(BaseModel):
    """顶层配置模型"""
    format_version: str = "1.0"
    system: SystemConfig = SystemConfig()
    interfaces: List[InterfaceConfig] = []
    routing: RoutingConfig = RoutingConfig()
    firewall: FirewallConfig
    dhcp: DHCPConfig
    dns: DNSConfig = DNSConfig()
    vpn: Optional[VPNConfig] = None

    class Config:
        extra = "forbid"  # 禁止未定义的字段
```

---

## 3. 核心引擎接口

```python
# ubunturouter/engine/engine.py

from pathlib import Path
from typing import Optional, List, Tuple

class ConfigEngine:
    """
    配置引擎核心类
    线程安全：所有公开方法使用文件锁保护
    """

    CONFIG_PATH = Path("/etc/ubunturouter/config.yaml")
    SNAPSHOT_DIR = Path("/var/lib/ubunturouter/snapshots")
    LOCK_PATH = Path("/var/run/ubunturouter/engine.lock")

    # ─── 公开接口 ─────────────────────────────────

    def load(self) -> UbunturouterConfig:
        """
        从 CONFIG_PATH 加载配置
        返回: 解析后的配置对象
        异常: ConfigNotFoundError (文件不存在),
              ConfigValidationError (校验失败)
        """

    def save(self, config: UbunturouterConfig) -> None:
        """
        将配置写入 CONFIG_PATH
        使用原子写入：写入临时文件 → fsync → rename
        """

    def validate(self, config: UbunturouterConfig) -> ValidationResult:
        """
        校验配置合法性
        返回: ValidationResult(is_valid: bool, errors: List[ValidationError])
        校验内容:
          - Pydantic Schema 校验
          - 语义校验（IP冲突、端口冲突、接口引用存在性）
          - 冲突检测（多WAN接口名不重复）
        """

    def diff(self, new_config: UbunturouterConfig) -> ConfigDiff:
        """
        计算新旧配置差异
        输入: new_config (待生效)
        内部: 对比 self.load() 获取当前生效配置
        返回: ConfigDiff
        """

    def apply(self, new_config: UbunturouterConfig,
              auto_rollback: bool = True) -> ApplyResult:
        """
        应用配置变更
        流程:
          1. 校验 → 2. 创建快照 → 3. Diff → 4. 生成子系统配置
          → 5. 原子写入 → 6. Reload 服务 → 7. 连通性检测
          → 8. 成功/回滚
        参数:
          auto_rollback: 是否启用自动回滚
        返回: ApplyResult(success, message, snapshot_id)
        """

    def rollback(self, snapshot_id: str) -> ApplyResult:
        """
        回滚到指定快照
        snapshot_id: 'latest' 或 快照 ID
        """

    def list_snapshots(self) -> List[SnapshotInfo]:
        """列出所有可用快照"""

    def get_snapshot(self, snapshot_id: str) -> UbunturouterConfig:
        """读取指定快照的配置"""


# ─── 辅助值对象 ──────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

@dataclass
class ConfigDiff:
    """配置变更摘要"""
    has_changes: bool
    summary: str                  # 人类可读变更摘要
    changed_sections: List[str]   # 变更的配置节
    generated_files: List[str]    # 将生成的文件
    services_to_reload: List[str] # 将 reload 的服务

@dataclass
class ApplyResult:
    success: bool
    message: str
    snapshot_id: Optional[str]
    rollback_to: Optional[str]
    execution_time_ms: int

@dataclass
class SnapshotInfo:
    id: str
    timestamp: datetime
    summary: str
    file_size: int
```

---

## 4. 配置转换引擎

```python
# ubunturouter/engine/generators/

# 目录结构：
# generators/
# ├── __init__.py
# ├── base.py          # 基类 Generator
# ├── netplan.py       # → netplan YAML
# ├── nftables.py      # → nftables conf
# ├── dnsmasq.py       # → dnsmasq conf
# ├── frr.py           # → FRR conf
# └── wireguard.py     # → wg-quick conf

class ConfigGenerator(ABC):
    """配置生成器基类"""

    @abstractmethod
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        生成子系统配置
        返回: {file_path: file_content}
        """
    @abstractmethod
    def reload_command(self) -> List[str]:
        """生成 reload 命令列表"""
    @abstractmethod
    def verify(self, config: UbunturouterConfig) -> bool:
        """验证生成的配置是否合法"""


class NetplanGenerator(ConfigGenerator):
    """网络配置生成器 → /etc/netplan/01-ubunturouter.yaml"""
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        转换逻辑：
        1. 物理网口 → ethernets 段
        2. bridge → bridges 段
        3. bond → bonds 段
        4. VLAN → vlans 段
        5. WANLAN → 特殊处理（单口+上行）
        """
    def reload_command(self) -> List[str]:
        return ["netplan", "apply"]
    def verify(self, config: UbunturouterConfig) -> bool:
        # `netplan generate` 无报错
        pass


class NftablesGenerator(ConfigGenerator):
    """防火墙配置生成器 → /etc/nftables.d/ubunturouter.conf"""
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        转换逻辑：
        1. 创建 table ip ubunturouter
        2. 每个 zone 创建 chain (input/forward/output)
        3. 自动生成 forward 规则（zone→zone）
        4. NAT 规则
        5. 端口转发 DNAT 规则
        6. 自定义规则
        7. 单网口 WANLAN 特殊处理
        """
    def reload_command(self) -> List[str]:
        return ["nft", "-f", "/etc/nftables.d/ubunturouter.conf"]
    def verify(self, config: UbunturouterConfig) -> bool:
        # `nft -c -f <file>` 语法检查
        pass


class DnsmasqGenerator(ConfigGenerator):
    """DHCP+DNS 配置生成器 → /etc/dnsmasq.d/ubunturouter.conf"""
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        转换逻辑：
        1. DHCP 池配置
        2. 静态租约
        3. DNS 上游
        4. DNS 重写
        5. 自定义选项
        """
    def reload_command(self) -> List[str]:
        return ["systemctl", "reload-or-restart", "dnsmasq"]
    def verify(self, config: UbunturouterConfig) -> bool:
        # dnsmasq --test
        pass


class UnboundGenerator(ConfigGenerator):
    """DNS 缓存配置生成器 → /etc/unbound/unbound.conf.d/ubunturouter.conf"""
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        转换逻辑：
        1. 上游 DNS 配置
        2. DNSSEC 设置
        3. 缓存大小
        4. 访问控制（允许 LAN 网段）
        """
    def reload_command(self) -> List[str]:
        return ["systemctl", "reload-or-restart", "unbound"]
    def verify(self, config: UbunturouterConfig) -> bool:
        # unbound-checkconf
        pass


class FRRGenerator(ConfigGenerator):
    """路由协议配置生成器 → /etc/frr/frr.conf"""
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        转换逻辑：
        1. 静态路由
        2. 策略路由 (ip rule)
        3. OSPF 配置
        4. BGP 配置
        """
    def reload_command(self) -> List[str]:
        return ["vtysh", "-f", "/etc/frr/frr.conf"]
    def verify(self, config: UbunturouterConfig) -> bool:
        # vtysh -c 'show running-config' 无异常
        pass


class WireGuardGenerator(ConfigGenerator):
    """VPN 配置生成器 → /etc/wireguard/wg0.conf"""
    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        转换逻辑：
        1. 接口配置
        2. Peer 列表
        3. 私有密钥（加密存储）
        """
    def reload_command(self) -> List[str]:
        return ["wg-quick", "strip", "wg0"]  # 验证用
    def verify(self, config: UbunturouterConfig) -> bool:
        # `wg show` 无错误
        pass
```

---

## 5. 配置 Apply 完整流程

```python
# ubunturouter/engine/applier.py

class ConfigApplier:
    """
    配置应用器
    职责：按正确顺序执行配置变更
    """

    # 服务依赖顺序
    SERVICE_ORDER = [
        # (generator, service_name, reload_delay_ms)
        ("netplan", "networking", 0),       # 网络先就绪
        ("nftables", "nftables", 500),      # 防火墙
        ("frr", "frr", 500),                # 路由
        ("dnsmasq", "dnsmasq", 200),        # DHCP+DNS
        ("unbound", "unbound", 200),        # DNS 缓存
        ("wireguard", "wg-quick@wg0", 300), # VPN
    ]

    TIMEOUT_HEALTH_CHECK = 60  # 秒
    TIMEOUT_SERVICE = 30       # 秒

    def apply_atomic(self, config: UbunturouterConfig,
                     auto_rollback: bool = True) -> ApplyResult:
        """
        原子 Apply — 完整流程：
        
        1. 校验配置 ← ConfigEngine.validate()
        
        2. 创建快照
           · 保存当前 config.yaml → snapshot_{timestamp}.yaml
           · 保存当前所有子系统配置 → snapshot_{timestamp}/ 目录
        
        3. 计算 diff
           · 仅处理有变更的 section
           · 无变更的 section 跳过 reload
        
        4. 生成子系统配置
           · 遍历 SERVICE_ORDER，调用对应 generator.generate()
           · 写入临时文件
        
        5. 原子写入（全或无）
           · 校验所有 generated 文件：
             - netplan generate → 无错误
             - nft -c → 无错误
             - dnsmasq --test → 无错误
             - unbound-checkconf → 无错误
           · 校验通过 → rename 临时文件到正式路径
           · 校验失败 → 不写入，返回错误
        
        6. 按序 reload 服务
           · 按 SERVICE_ORDER 顺序
           · 每个 service reload 后等待 delay 毫秒
           · 异常：记录失败服务，继续后续
        
        7. 连通性检测（仅 auto_rollback=True）
           · 检测条件：
             a) LAN IP 可 ping 通 (127.0.0.1/32)
             b) DNS 可解析 (dig @192.168.21.1 ubunturouter.local)
             c) API Server 可达 (curl localhost:8080/health)
             d) WAN 出口可达 (ping 8.8.8.8, 仅 WAN 有 IP 时)
           · 60 秒内轮询，任意条件满足即标记成功
           · 超时未满足 → 自动回滚
        
        8. 返回结果
           · 成功：ApplyResult(success=True, snapshot_id=xxx)
           · 回滚：ApplyResult(success=False, rollback_to=xxx)
        """
```

**服务 Reload 顺序说明**：

```
 顺序  │ 服务名           │ 前置依赖
───────┼──────────────────┼───────────
  1    │ netplan apply     │ 无（网络基础）
  2    │ nftables reload   │ 网口已配置（zone 引用接口名）
  3    │ vtysh -f         │ 网口已配置（FRR 引用接口 IP）
  4    │ dnsmasq reload    │ 网口已配置（DHCP 监听接口）
  5    │ unbound reload    │ 无（独立服务）
  6    │ wg-quick reload   │ 网口已配置（WG 接口）
```

---

## 6. 回滚机制实现

```python
# ubunturouter/engine/rollback.py

class RollbackManager:
    """
    回滚管理器
    """

    SNAPSHOT_DIR = Path("/var/lib/ubunturouter/snapshots")
    MAX_SNAPSHOTS = 50  # 保留最近 50 个快照

    def create_snapshot(self, config: UbunturouterConfig,
                        summary: str) -> str:
        """
        创建配置快照
        
        存储结构：
        /var/lib/ubunturouter/snapshots/
        ├── 20260425_120000_abc123/     # 快照 ID = timestamp_hash
        │   ├── config.yaml             # 主配置
        │   ├── meta.yaml               # 元数据（时间、摘要、触发者）
        │   └── systemd/                # 子系统当前配置副本
        │       ├── 01-netplan.yaml
        │       ├── nftables.conf
        │       ├── dnsmasq.conf
        │       └── frr.conf
        ├── 20260425_110000_def456/
        └── latest -> 20260425_120000_abc123/  # 符号链接
        """

    def auto_rollback(self, snapshot_id: str) -> ApplyResult:
        """
        自动回滚流程：
        1. 停止本次配置的连通性检测定时器
        2. 读取快照中的子系统配置文件
        3. 原子恢复（写入 + reload）
        4. 连通性检测（60s）
        5. 如果回滚也失败 → 严重错误，报警
        """

    def cleanup_old_snapshots(self):
        """删除超过 MAX_SNAPSHOTS 的旧快照"""

    def mark_snapshot_good(self, snapshot_id: str):
        """标记快照为已验证成功（不会被回滚时覆盖）"""
```

---

## 7. 首次启动初始化模块

```python
# ubunturouter/engine/initializer.py

class Initializer:
    """
    首次启动初始化器
    触发条件：检测 /etc/ubunturouter/config.yaml 不存在
    仅在首次启动时运行一次
    """

    def should_init(self) -> bool:
        """是否需要进行初始化"""
        return not ConfigEngine.CONFIG_PATH.exists()

    def detect_physical_nics(self) -> List[NicInfo]:
        """
        检测物理网口
        
        返回: [{name: "ens3", speed: 10000, link: True, driver: "virtio_net"}]
        
        实现：
        1. 遍历 /sys/class/net/
        2. 排除: lo, docker*, br-*, veth*, virbr*, tun*
        3. 检查 /sys/class/net/{iface}/device/driver 是否存在（物理口）
        4. ethtool {iface} 获取 speed
        5. cat /sys/class/net/{iface}/carrier 获取 link 状态
        """

    def auto_assign_roles(self, nics: List[NicInfo]) -> RoleAssignment:
        """
        自动分配 WAN/LAN 角色
        
        规则：
        · 1口 → wanlan (WANLAN 模式)
        · 2口 → 低速率=WAN, 高速率=LAN
        · 3+口 → 最低速率=WAN, 其余桥接=br-lan
        · 同速率 → 按接口名排序 (enp1s0 < enp2s0)
        · 无链路(link=1)的网口优先排除出 WAN
        """

    def generate_initial_config(self, assignment: RoleAssignment) -> UbunturouterConfig:
        """
        生成初始配置
        
        固定默认值：
        · LAN 网关: 192.168.21.1/24
        · DHCP 池: 192.168.21.50 - 192.168.21.200
        · WAN: DHCP
        · 上游 DNS: 223.5.5.5, 119.29.29.29
        · 防火墙: 默认 drop
        · NAT: masquerade
        """

    def apply_and_start_wizard(self):
        """
        Apply 初始配置 → 标记已初始化 → 启动 Web 向导
        """
```

---

## 8. 文件锁定与并发保护

```python
# ubunturouter/engine/lock.py

import fcntl
from pathlib import Path

class EngineLock:
    """
    文件锁，确保同一时刻只有一个 Apply 操作在进行
    """

    LOCK_PATH = Path("/var/run/ubunturouter/engine.lock")

    def __enter__(self):
        self.lock = self.LOCK_PATH.open('w')
        fcntl.flock(self.lock, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        fcntl.flock(self.lock, fcntl.LOCK_UN)
        self.lock.close()
```

---

## 9. 配置文件路径汇总

| 路径 | 用途 |
|------|------|
| `/etc/ubunturouter/config.yaml` | 统一配置文件（权威源） |
| `/var/lib/ubunturouter/snapshots/` | 配置快照目录 |
| `/var/run/ubunturouter/engine.lock` | 并发锁文件 |
| `/etc/netplan/01-ubunturouter.yaml` | netplan 生成的网络配置 |
| `/etc/nftables.d/ubunturouter.conf` | nftables 防火墙规则 |
| `/etc/dnsmasq.d/ubunturouter.conf` | dnsmasq DHCP+DNS 配置 |
| `/etc/unbound/unbound.conf.d/ubunturouter.conf` | Unbound DNS 缓存配置 |
| `/etc/frr/frr.conf` | FRR 路由配置 |
| `/etc/wireguard/wg0.conf` | WireGuard VPN 配置 |
| `/etc/ubunturouter/initialized.flag` | 初始化完成标记 |

---

## 10. 错误处理策略

| 错误类型 | 行为 | 用户可见性 |
|----------|------|-----------|
| Schema 校验失败 | 拒绝 Apply，返回错误列表 | ✅ Web GUI 显示每个字段错误 |
| 语义校验失败（端口冲突等） | 拒绝 Apply，返回冲突详情 | ✅ Web GUI 显示冲突 |
| 配置生成校验失败 | 拒绝写入，子系统报告失败原因 | ✅ Web GUI 显示详细错误 |
| 服务 Reload 失败 | 记录失败服务，继续后续；最终视为 Apply 失败触发回滚 | ✅ 回滚通知 |
| 连通性检测失败 | 自动回滚（auto_rollback=true） | ✅ 回滚通知+回滚后配置摘要 |
| 回滚也失败 | 严重错误，邮件/Webhook 告警，保留现场 | ❌ 需要运维介入 |
| 文件写入失败（磁盘满） | 拒绝 Apply，报错 | ✅ 磁盘空间告警 |
| 并发 Apply 冲突 | 后到的 Apply 被拒绝，等待前次完成 | ✅ 提示"正在处理其他配置变更" |
