"""首次启动初始化器 — 网口检测 + 角色自动分配 + 初始配置生成"""

import os
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from ..config.models import (
    UbunturouterConfig, InterfaceConfig, InterfaceConfig as IntfCfg,
    InterfaceRole, InterfaceType, IPConfig, IPMethod,
    DHCPPoolConfig, DNSConfig, FirewallConfig, FirewallZoneConfig,
    FirewallPolicy, PortForwardRule, FirewallRule,
    RoutingConfig, SystemConfig,
)
from ..engine.engine import ConfigEngine
from ..engine.applier import ConfigApplier
from ..generators.base import GeneratorRegistry
from ..generators.netplan import NetplanGenerator
from ..generators.nftables import NftablesGenerator
from ..generators.dnsmasq import DnsmasqGenerator


@dataclass
class NicInfo:
    name: str
    speed: int = 0        # Mbps
    link: bool = False    # carrier 状态
    driver: str = ""
    permanent_mac: str = ""


@dataclass
class RoleAssignment:
    nics: List[NicInfo] = field(default_factory=list)
    wan: Optional[NicInfo] = None
    lans: List[NicInfo] = field(default_factory=list)
    wanlan: Optional[NicInfo] = None  # 单网口
    gateway: str = "192.168.21.1"


INITIALIZED_FLAG = Path("/etc/ubunturouter/initialized.flag")


class Initializer:
    """首次启动初始化器"""

    def __init__(self, engine: ConfigEngine):
        self.engine = engine

    def should_init(self) -> bool:
        """是否需要进行初始化"""
        return not self.engine.exists() and not INITIALIZED_FLAG.exists()

    def detect_physical_nics(self) -> List[NicInfo]:
        """检测物理网口"""
        nics = []
        sys_net = Path("/sys/class/net")

        for entry in sys_net.iterdir():
            ifname = entry.name
            # 排除虚拟接口
            if ifname == "lo":
                continue
            if ifname.startswith(("docker", "br-", "veth", "virbr", "tun", "tap", "bond")):
                continue

            nic = NicInfo(name=ifname)

            # 检查是否为物理设备（有 device/driver 目录）
            device_dir = entry / "device"
            if not device_dir.exists():
                continue  # 跳过虚拟设备

            # 驱动名称
            driver_link = device_dir / "driver"
            if driver_link.exists():
                nic.driver = os.path.basename(os.readlink(str(driver_link)))

            # 网口速率（ethtool）
            try:
                r = subprocess.run(
                    ["ethtool", ifname],
                    capture_output=True, text=True, timeout=5
                )
                for line in r.stdout.split("\n"):
                    line = line.strip()
                    if "Speed:" in line:
                        m = re.search(r"(\d+)", line)
                        if m:
                            nic.speed = int(m.group(1))
                    if "Link detected:" in line:
                        nic.link = "yes" in line.lower()
            except Exception:
                # 虚拟环境可能没有 ethtool，从 speed 文件读取
                nic.speed = 1000  # 默认 1G
                nic.link = True
                # 尝试从 /sys 读取速度
                speed_file = entry / "speed"
                if speed_file.exists():
                    try:
                        speed_val = speed_file.read_text().strip()
                        if speed_val.isdigit():
                            nic.speed = int(speed_val)
                    except Exception:
                        pass

            # 载波状态（无条件 fallback）
            carrier_file = entry / "carrier"
            if carrier_file.exists():
                try:
                    nic.link = carrier_file.read_text().strip() == "1"
                except Exception:
                    pass

            nics.append(nic)

        # 按接口名排序
        nics.sort(key=lambda n: n.name)
        return nics

    def auto_assign_roles(self, nics: List[NicInfo]) -> RoleAssignment:
        """自动分配 WAN/LAN 角色"""
        ra = RoleAssignment(nics=nics)

        if not nics:
            return ra

        if len(nics) == 1:
            ra.wanlan = nics[0]
            return ra

        # 按速率排序（低速=WAN）
        sorted_nics = sorted(nics, key=lambda n: n.speed)

        # 无链接的优先排除出 WAN
        linked = [n for n in sorted_nics if n.link]
        unlinked = [n for n in sorted_nics if not n.link]

        if len(nics) == 2:
            # 2口：低速=WAN
            if linked and not unlinked:
                ra.wan = sorted_nics[0]
                ra.lans = sorted_nics[1:]
            elif len(linked) == 1:
                ra.wan = linked[0]
                ra.lans = [n for n in nics if n != linked[0]]
            else:
                # 只有一个 link 或多个 link，按排序
                ra.wan = linked[0] if linked else nics[0]
                ra.lans = [n for n in nics if n != ra.wan]
        else:
            # 3+口：最低速率=WAN，其余桥接
            if linked:
                ra.wan = linked[0]
                ra.lans = [n for n in nics if n != ra.wan]
            else:
                ra.wan = nics[0]
                ra.lans = nics[1:]

        return ra

    def generate_initial_config(self, assignment: RoleAssignment) -> UbunturouterConfig:
        """生成初始配置"""
        interfaces = []
        firewall_zones = []
        dhcp = None
        dns = DNSConfig()

        if assignment.wanlan:
            # 单网口 WANLAN 模式
            interfaces.append(InterfaceConfig(
                name=assignment.wanlan.name,
                device=assignment.wanlan.name,
                type=InterfaceType.ETHERNET,
                role=InterfaceRole.WANLAN,
                ipv4=IPConfig(method=IPMethod.DHCP),
                firewall_zone="wan",
            ))
            # WANLAN 的 LAN 地址池
            dhcp = DHCPPoolConfig(
                interface=assignment.wanlan.name,
                range_start="192.168.21.50",
                range_end="192.168.21.200",
                gateway="192.168.21.1",
                lease_time=86400,
                domain="lan",
            )
        else:
            # WAN 接口
            if assignment.wan:
                wan_ip = IPConfig(method=IPMethod.DHCP) if len(assignment.nics) >= 1 else \
                         IPConfig(method=IPMethod.STATIC, address="192.168.21.1/24",
                                  gateway="192.168.21.1")
                interfaces.append(InterfaceConfig(
                    name=assignment.wan.name,
                    device=assignment.wan.name,
                    type=InterfaceType.ETHERNET,
                    role=InterfaceRole.WAN,
                    ipv4=wan_ip,
                    firewall_zone="wan",
                ))

            # LAN 接口
            if assignment.lans:
                for idx, lan in enumerate(assignment.lans):
                    if idx == 0:
                        # 第一个 LAN 口作为网关
                        interfaces.append(InterfaceConfig(
                            name=lan.name,
                            device=lan.name,
                            type=InterfaceType.ETHERNET,
                            role=InterfaceRole.LAN,
                            ipv4=IPConfig(
                                method=IPMethod.STATIC,
                                address=assignment.gateway + "/24",
                            ),
                            ports=[lan.name],
                            firewall_zone="lan",
                        ))
                        dhcp = DHCPPoolConfig(
                            interface=lan.name,
                            range_start="192.168.21.50",
                            range_end="192.168.21.200",
                            gateway=assignment.gateway,
                            lease_time=86400,
                            domain="lan",
                        )
                    else:
                        # 后续 LAN 口桥接
                        interfaces.append(InterfaceConfig(
                            name=lan.name,
                            device=lan.name,
                            type=InterfaceType.ETHERNET,
                            role=InterfaceRole.LAN,
                            firewall_zone="lan",
                        ))

        # 防火墙 zone
        firewall_zones = {
            "wan": FirewallZoneConfig(
                name="wan",
                masquerade=True,
                input=FirewallPolicy.DROP,
                forward_to=["lan"],
            ),
            "lan": FirewallZoneConfig(
                name="lan",
                masquerade=False,
                input=FirewallPolicy.ACCEPT,
                forward_to=["wan"],
            ),
        }

        config = UbunturouterConfig(
            system=SystemConfig(hostname="ubunturouter"),
            interfaces=interfaces,
            firewall=FirewallConfig(
                zones=firewall_zones,
            ),
            routing=RoutingConfig(),
            dhcp=dhcp,
            dns=dns,
        )

        return config

    def apply_and_start_wizard(self) -> bool:
        """
        Apply 初始配置 → 标记已初始化
        返回 True=初始化成功
        """
        if not self.should_init():
            return True  # 已经初始化

        # 检测网口
        nics = self.detect_physical_nics()
        if not nics:
            raise RuntimeError("未检测到物理网口")

        # 分配角色
        assignment = self.auto_assign_roles(nics)

        # 生成初始配置
        config = self.generate_initial_config(assignment)

        # 注册生成器并 Apply
        registry = GeneratorRegistry()
        registry.register("netplan", NetplanGenerator())
        registry.register("nftables", NftablesGenerator())
        registry.register("dnsmasq", DnsmasqGenerator())

        applier = ConfigApplier(self.engine, registry)
        result = applier.apply_atomic(config, auto_rollback=True)

        if result.success:
            # 标记已初始化
            INITIALIZED_FLAG.parent.mkdir(parents=True, exist_ok=True)
            INITIALIZED_FLAG.touch()
            return True

        raise RuntimeError(f"初始化 Apply 失败: {result.error}")
