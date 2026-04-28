"""UbuntuRouter 统一配置模型

所有配置的权威数据模型。使用 Pydantic v2 进行类型校验和序列化。
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Literal
from enum import Enum
import re


# ═══════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════

class InterfaceRole(str, Enum):
    WAN = "wan"
    LAN = "lan"
    DMZ = "dmz"
    GUEST = "guest"
    MANAGEMENT = "management"
    WANLAN = "wanlan"

class IPMethod(str, Enum):
    DHCP = "dhcp"
    STATIC = "static"
    PPPOE = "pppoe"
    DISABLED = "disabled"

class FirewallPolicy(str, Enum):
    ACCEPT = "accept"
    DROP = "drop"
    REJECT = "reject"

class BondMode(str, Enum):
    BALANCE_RR = "balance-rr"
    ACTIVE_BACKUP = "active-backup"
    BALANCE_XOR = "balance-xor"
    BROADCAST = "broadcast"
    LACP_8023AD = "802.3ad"
    BALANCE_TLB = "balance-tlb"
    BALANCE_ALB = "balance-alb"

class MultiWanStrategy(str, Enum):
    FAILOVER = "failover"
    WEIGHTED_RR = "weighted-rr"
    BALANCE = "balance"

class InterfaceType(str, Enum):
    ETHERNET = "ethernet"
    BRIDGE = "bridge"
    VLAN = "vlan"
    BOND = "bond"


# ═══════════════════════════════════════════════════════
# 网络接口
# ═══════════════════════════════════════════════════════

class IPConfig(BaseModel):
    """IP 地址配置"""
    method: IPMethod = IPMethod.DHCP
    address: Optional[str] = None       # "192.168.21.1/24"
    gateway: Optional[str] = None
    dns: Optional[List[str]] = None

    @field_validator('address')
    @classmethod
    def validate_cidr(cls, v):
        if v is not None:
            parts = v.split('/')
            if len(parts) != 2:
                raise ValueError(f'地址格式错误，需要 CIDR 格式: {v}')
            ip_parts = parts[0].split('.')
            if len(ip_parts) != 4 or not all(
                p.isdigit() and 0 <= int(p) <= 255 for p in ip_parts
            ):
                raise ValueError(f'IP 地址格式错误: {parts[0]}')
            prefix = int(parts[1])
            if not 0 <= prefix <= 32:
                raise ValueError(f'子网前缀长度不合法: {prefix}')
        return v

    @field_validator('gateway')
    @classmethod
    def validate_gateway(cls, v):
        if v is not None:
            parts = v.split('.')
            if len(parts) != 4 or not all(
                p.isdigit() and 0 <= int(p) <= 255 for p in parts
            ):
                raise ValueError(f'网关地址格式错误: {v}')
        return v


class WanUplinkConfig(BaseModel):
    """单网口 WANLAN 模式的上行配置"""
    method: IPMethod = IPMethod.DHCP
    username: Optional[str] = None
    password: Optional[str] = None


class VlanConfig(BaseModel):
    """VLAN 子接口"""
    id: int = Field(..., ge=1, le=4094)
    name: Optional[str] = None
    ipv4: Optional[IPConfig] = None
    firewall_zone: Optional[str] = None
    dhcp: Optional['DHCPPoolConfig'] = None


class BondConfig(BaseModel):
    """Bonding 配置"""
    mode: BondMode = BondMode.LACP_8023AD
    slaves: List[str] = Field(..., min_length=2)
    mii_monitor_interval: int = 100
    ipv4: Optional[IPConfig] = None


class InterfaceConfig(BaseModel):
    """网络接口配置"""
    name: str
    type: InterfaceType = InterfaceType.ETHERNET
    device: Optional[str] = None
    role: InterfaceRole = InterfaceRole.LAN
    ports: Optional[List[str]] = None
    vlans: Optional[List[VlanConfig]] = None
    bond: Optional[BondConfig] = None
    ipv4: Optional[IPConfig] = None
    firewall_zone: Optional[str] = None
    wan_uplink: Optional[WanUplinkConfig] = None
    mtu: Optional[int] = None
    mac: Optional[str] = None
    enabled: bool = True

    @model_validator(mode='after')
    def validate_interface(self):
        # Bridge 必须有 ports
        if self.type == InterfaceType.BRIDGE and (not self.ports or len(self.ports) < 1):
            raise ValueError(f'Bridge 接口 {self.name} 必须至少包含一个端口')
        # Ethernet 必须有 device
        if self.type == InterfaceType.ETHERNET and not self.device:
            raise ValueError(f'Ethernet 接口 {self.name} 必须指定 device')
        # Bond 必须有 slaves
        if self.type == InterfaceType.BOND and (not self.bond):
            raise ValueError(f'Bond 接口 {self.name} 必须配置 bond 参数')
        # WANLAN 必须有 wan_uplink
        if self.role == InterfaceRole.WANLAN and not self.wan_uplink:
            raise ValueError(f'WANLAN 接口 {self.name} 必须配置 wan_uplink')
        return self


class FirewallZoneConfig(BaseModel):
    """防火墙区域"""
    name: str
    masquerade: bool = False
    forward_to: List[str] = []
    isolated: bool = False
    input: FirewallPolicy = FirewallPolicy.DROP
    forward: FirewallPolicy = FirewallPolicy.DROP
    output: FirewallPolicy = FirewallPolicy.ACCEPT


class PortForwardRule(BaseModel):
    """端口转发规则"""
    name: str
    enabled: bool = True
    protocol: Literal["tcp", "udp", "tcp_udp"] = "tcp"
    from_port: int = Field(..., ge=1, le=65535)
    to_ip: str
    to_port: Optional[int] = None
    from_zone: str = "wan"
    to_zone: str = "lan"
    description: Optional[str] = None

    @field_validator('to_ip')
    @classmethod
    def validate_ip(cls, v):
        parts = v.split('.')
        if len(parts) != 4 or not all(
            p.isdigit() and 0 <= int(p) <= 255 for p in parts
        ):
            raise ValueError(f'IP 地址格式错误: {v}')
        return v


class FirewallRule(BaseModel):
    """自定义防火墙规则"""
    name: str
    enabled: bool = True
    action: Literal["accept", "drop", "reject", "log"] = "accept"
    protocol: Optional[Literal["tcp", "udp", "tcp_udp", "icmp"]] = None
    src_zone: Optional[str] = None
    dst_zone: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    description: Optional[str] = None


class FirewallConfig(BaseModel):
    """防火墙完整配置"""
    default_policy: Optional[dict] = Field(
        default_factory=lambda: {"input": "drop", "forward": "drop", "output": "accept"}
    )
    zones: Dict[str, FirewallZoneConfig] = {}
    port_forwards: List[PortForwardRule] = []
    rules: List[FirewallRule] = []


class StaticRoute(BaseModel):
    """静态路由"""
    target: str
    via: str
    metric: int = 100
    table: Optional[int] = None
    comment: Optional[str] = None
    enabled: bool = True


class HealthCheckConfig(BaseModel):
    """健康检查"""
    target: str = "8.8.8.8"
    interval: int = 5
    timeout: int = 2
    count: int = 3


class WanInterfaceConfig(BaseModel):
    """WAN 接口配置"""
    name: str
    device: str
    table_id: int = 101
    metric: int = 100
    weight: int = 1
    health_check: HealthCheckConfig = HealthCheckConfig()
    enabled: bool = True


class MultiWanConfig(BaseModel):
    """多 WAN 配置"""
    enabled: bool = False
    strategy: MultiWanStrategy = MultiWanStrategy.FAILOVER
    wans: List[WanInterfaceConfig] = []


class RoutingConfig(BaseModel):
    """路由配置"""
    static_routes: List[StaticRoute] = []
    multi_wan: MultiWanConfig = MultiWanConfig()
    frr_enabled: bool = False


class StaticLease(BaseModel):
    """静态 DHCP 租约"""
    mac: str
    ip: str
    hostname: Optional[str] = None

    @field_validator('mac')
    @classmethod
    def validate_mac(cls, v):
        if not re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', v):
            raise ValueError(f'MAC 地址格式错误: {v}')
        return v.lower()

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v):
        parts = v.split('.')
        if len(parts) != 4 or not all(
            p.isdigit() and 0 <= int(p) <= 255 for p in parts
        ):
            raise ValueError(f'IP 地址格式错误: {v}')
        return v


class DHCPPool(BaseModel):
    """单个 DHCP 地址池"""
    id: str = ""
    name: str = ""
    enabled: bool = True
    range_start: str = "192.168.21.50"
    range_end: str = "192.168.21.200"
    subnet_mask: str = "255.255.255.0"
    gateway: str = "192.168.21.1"
    dns_servers: List[str] = ["192.168.21.1"]
    lease_time: int = 86400  # seconds
    domain: Optional[str] = None

    @field_validator('range_start', 'range_end', 'gateway')
    @classmethod
    def validate_ip(cls, v):
        parts = v.split('.')
        if len(parts) != 4 or not all(
            p.isdigit() and 0 <= int(p) <= 255 for p in parts
        ):
            raise ValueError(f'IP 地址格式错误: {v}')
        return v

    @field_validator('subnet_mask')
    @classmethod
    def validate_netmask(cls, v):
        parts = v.split('.')
        if len(parts) != 4 or not all(
            p.isdigit() and 0 <= int(p) <= 255 for p in parts
        ):
            raise ValueError(f'子网掩码格式错误: {v}')
        # 验证连续1+连续0
        binary = ''.join(f'{int(p):08b}' for p in parts)
        if '01' in binary.rstrip('0'):
            raise ValueError(f'子网掩码不合法: {v}')
        return v

    @field_validator('dns_servers')
    @classmethod
    def validate_dns_list(cls, v):
        for dns in v:
            parts = dns.split('.')
            if len(parts) != 4 or not all(
                p.isdigit() and 0 <= int(p) <= 255 for p in parts
            ):
                raise ValueError(f'DNS 地址格式错误: {dns}')
        return v


class DHCPPoolConfig(BaseModel):
    """DHCP 配置（支持多池）"""
    interface: str
    enabled: bool = True
    domain: Optional[str] = "lan"
    pools: List[DHCPPool] = []
    static_leases: List[StaticLease] = []


class DNSConfig(BaseModel):
    """DNS 配置"""
    upstream: List[str] = Field(
        default_factory=lambda: ["223.5.5.5", "119.29.29.29"]
    )
    enable_dnssec: bool = True
    cache_size: int = 10000
    blocking: bool = False
    blocklists: List[str] = []


class SystemConfig(BaseModel):
    """系统配置"""
    hostname: str = "router"
    timezone: str = "Asia/Shanghai"
    api_port: int = 8080
    web_port: int = 443


# ═══════════════════════════════════════════════════════
# PPPoE
# ═══════════════════════════════════════════════════════

class PPPoEConfig(BaseModel):
    """PPPoE 拨号配置"""
    enabled: bool = False
    username: str = ""
    password: str = ""
    interface: str = "wan"
    mtu: int = 1492
    auto_reconnect: bool = True


# ═══════════════════════════════════════════════════════
# Samba
# ═══════════════════════════════════════════════════════

class SambaShareConfig(BaseModel):
    """Samba 共享目录"""
    name: str
    path: str
    writable: bool = True
    guest_ok: bool = False
    valid_users: str = ""
    browsable: bool = True
    enabled: bool = True


class SambaConfig(BaseModel):
    """Samba 服务配置"""
    enabled: bool = False
    workgroup: str = "WORKGROUP"
    server_string: str = "UbuntuRouter"
    shares: List[SambaShareConfig] = []


# ═══════════════════════════════════════════════════════
# DDNS
# ═══════════════════════════════════════════════════════

class DDNSRecordConfig(BaseModel):
    """DDNS 记录"""
    id: str = ""
    type: str  # cloudflare, duckdns, alidns, dnspod
    domain: str
    subdomain: str = ""
    ttl: int = 120
    enabled: bool = True
    # Provider-specific credentials
    api_token: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class DDNSConfig(BaseModel):
    """DDNS 配置"""
    enabled: bool = False
    records: List[DDNSRecordConfig] = []


# ═══════════════════════════════════════════════════════
# 顶级配置
# ═══════════════════════════════════════════════════════

class UbunturouterConfig(BaseModel):
    """UbuntuRouter 顶级配置"""
    format_version: str = "1.0"
    system: SystemConfig = SystemConfig()
    interfaces: List[InterfaceConfig] = []
    firewall: FirewallConfig = FirewallConfig()
    routing: RoutingConfig = RoutingConfig()
    dhcp: Optional[DHCPPoolConfig] = None
    dns: Optional[DNSConfig] = None
    pppoe: Optional[PPPoEConfig] = None
    samba: Optional[SambaConfig] = None
    ddns: Optional[DDNSConfig] = None

    class Config:
        extra = "forbid"  # 禁止未定义的字段

    @model_validator(mode='after')
    def validate_config(self):
        # 检查至少有一个接口配置了 LAN 或 WANLAN
        has_lan = any(
            i.role in (InterfaceRole.LAN, InterfaceRole.WANLAN) for i in self.interfaces
        )
        has_wan = any(
            i.role == InterfaceRole.WAN for i in self.interfaces
        ) or any(
            i.role == InterfaceRole.WANLAN for i in self.interfaces
        )
        if not has_lan:
            raise ValueError('至少需要一个 LAN 或 WANLAN 接口')
        # 如果没有 WAN 但 WANLAN 存在，是合法的
        if not has_wan and not has_lan:
            raise ValueError('至少需要一个 WAN 或 WANLAN 接口')

        # 检查 DHCP 配置对应的接口是否存在
        if self.dhcp and self.dhcp.interface:
            iface_names = [i.name for i in self.interfaces]
            if self.dhcp.interface not in iface_names:
                # 可能是 bridge 名（如 br-lan），这是允许的
                pass

        return self
