# 网络管理模块详细设计 — Network Manager

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 对应 HLD 模块: 3.2 Network Manager
> 依赖模块: Configuration Engine
> 后端技术: netplan + networkd

---

## 1. 模块定位

Network Manager 负责所有网络接口的声明式管理，包括物理网口、桥接、VLAN、Bonding 以及单网口 WANLAN 模式。不涉及防火墙规则和路由策略（分别由 Firewall/Routing Manager 负责）。

---

## 2. 数据结构

```python
# ubunturouter/network/models.py

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from ipaddress import IPv4Network, IPv6Network


class InterfaceType(str, Enum):
    ETHERNET = "ethernet"
    BRIDGE = "bridge"
    VLAN = "vlan"
    BOND = "bond"
    VIRTUAL = "virtual"

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


class NicInfo(BaseModel):
    """网口检测信息"""
    name: str                       # 内核接口名: ens3, enp1s0
    type: InterfaceType
    driver: Optional[str] = None    # virtio_net, i40e, r8169
    speed: Optional[int] = None     # Mbps: 10, 100, 1000, 2500, 10000
    link: bool = False              # 链路状态 (carrier)
    perm_mac: Optional[str] = None  # 永久 MAC
    pci_pci: Optional[str] = None   # PCI 地址
    is_physical: bool = False       # 是否物理网口


class IPAddress(BaseModel):
    """IP 地址信息"""
    address: str                    # "192.168.21.1/24"
    family: str = "inet"            # inet / inet6
    scope: str = "global"           # global / host / link

class InterfaceStatus(BaseModel):
    """接口运行时状态"""
    name: str
    type: InterfaceType
    operstate: str                  # UP / DOWN / UNKNOWN
    carrier: bool = False
    speed: Optional[int] = None
    ipv4: List[IPAddress] = []
    ipv6: List[IPAddress] = []
    mac: Optional[str] = None
    mtu: int = 1500
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    master: Optional[str] = None    # 所属 bridge/bond
    link_mode: str = "default"      # default / vfio (直通后)
```

---

## 3. 核心接口

```python
# ubunturouter/network/manager.py

from typing import List, Optional


class NetworkManager:
    """
    网络管理模块
    所有操作通过 Configuration Engine 提供的 UnifiedConfig 完成
    """

    # ─── 网口检测 ───────────────────────────────────

    def detect_nics(self) -> List[NicInfo]:
        """
        扫描系统所有物理网口
        返回: [{name, driver, speed, link, ...}]
        
        实现:
        1. 遍历 /sys/class/net/
        2. 排除虚拟接口 (lo, docker*, veth*, br-*, bond*, tun*, virbr*)
        3. /sys/class/net/{iface}/device/driver 存在 → 物理口
        4. ethtool {iface} → speed
        5. /sys/class/net/{iface}/carrier → link
        """

    def get_nic_info(self, name: str) -> NicInfo:
        """获取指定网口信息"""

    def detect_speed(self, iface: str) -> Optional[int]:
        """
        通过 ethtool 获取网口速率
        
        $ ethtool ens3 2>/dev/null | grep Speed
        Speed: 10000Mb/s
        
        返回: Mbps, None(失败)
        """

    # ─── 接口状态 ───────────────────────────────────

    def list_interfaces(self) -> List[InterfaceStatus]:
        """
        列出所有接口运行状态
        实现: 解析 /proc/net/dev + ip addr show 的输出
        """

    def get_interface_status(self, name: str) -> InterfaceStatus:
        """获取单个接口运行状态"""

    def get_traffic_stats(self) -> List[TrafficStat]:
        """获取各接口流量统计（增量模式）"""

    # ─── 配置 Apply ─────────────────────────────────

    def apply(self, config: UbunturouterConfig) -> None:
        """
        将配置中的 interface 段转换为 netplan 配置并 Apply
        
        委托给 NetplanGenerator (Config Engine 的一部分):
        1. 从 config.interfaces 读取接口配置
        2. 验证接口配置合法性
        3. 调用 NetplanGenerator.generate() 生成 /etc/netplan/01-ubunturouter.yaml
        4. netplan apply
        """

    # ─── VM/容器网络配置 ────────────────────────────

    def create_bridge(self, name: str, ports: List[str],
                      address: str) -> None:
        """
        创建网桥（供 VM Manager 使用）
        
        实现:
        1. 创建 bridge 接口
        2. 添加端口
        3. 配置 IP
        4. 使桥接网络可用
        注意: 需要同时更新 config.yaml 以持久化
        """

    def create_macvlan(self, name: str, parent: str,
                       ip_range: str) -> None:
        """
        创建 macvlan 网络（供 Container Manager 使用）
        
        实现:
        1. 创建 Docker macvlan 网络
        2. 配置 DHCP 转发或静态 IP 池
        """
```

---

## 4. Netplan 配置生成细节

```python
# ubunturouter/engine/generators/netplan.py

class NetplanGenerator(ConfigGenerator):

    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        将 UnifiedConfig 转换为 netplan YAML
        
        生成规则:
        """

    def _build_network_section(self, config) -> dict:
        """
        netplan 结构:
        
        network:
          version: 2
          renderer: networkd         # 使用 systemd-networkd
          ethernets: {...}           # 物理网口
          bridges: {...}             # 桥接
          bonds: {...}               # 链路聚合
          vlans: {...}               # VLAN 子接口
        
        转换逻辑:
        """

    def _build_ethernets(self, interfaces, config) -> dict:
        """
        物理网口：
        · WAN 角色: DHCP 或 静态IP
        · LAN 角色: 仅声明不配 IP（IP 在 bridge 层配）
        · WANLAN 角色: 特殊处理
        
        示例输出:
        ethernets:
          enp1s0:
            dhcp4: true
            dhcp4-overrides:
              route-metric: 100
            optional: true
          enp2s0:
            # 纯 LAN 口，不配 IP（由 bridge 管理）
          enp3s0:
            # 同上
        """

    def _build_bridges(self, interfaces, config) -> dict:
        """
        LAN 桥接：
        · 聚合所有 LAN 角色网口
        · VLAN 作为 bridge 的子接口
        
        示例输出:
        bridges:
          br-lan:
            interfaces: [enp2s0, enp3s0]
            addresses: [192.168.21.1/24]
            dhcp4: false
            parameters:
              stp: true
              forward-delay: 4
        """

    def _build_vlans(self, interfaces, config) -> dict:
        """
        VLAN 子接口：
        · 在 bridge 或物理口上创建 VLAN
        
        示例输出:
        vlans:
          vlan10-guest:
            id: 10
            link: br-lan
            addresses: [192.168.10.1/24]
        """

    def _build_bonds(self, interfaces, config) -> dict:
        """
        链路聚合：
        · 多网口绑定为逻辑接口
        
        示例输出:
        bonds:
          bond0:
            interfaces: [enp4s0, enp5s0]
            parameters:
              mode: 802.3ad
              mii-monitor-interval: 100
            addresses: [192.168.100.1/24]
        """

    def _build_wanlan(self, interface: InterfaceConfig) -> dict:
        """
        单网口 WANLAN 模式特殊处理
        
        方案A: 单口 NAT (推荐)
        ─────────────────────
        ethernets:
          ens3:
            addresses: [192.168.21.1/24]  ← LAN 侧
            dhcp4: true                   ← 同时也 DHCP 获取 WAN IP
            routes:
              - to: 0.0.0.0/0
                via: 0.0.0.0              # 默认路由由 DHCP 提供
            dhcp4-overrides:
              route-metric: 1024          # WAN 路由优先级降低
              use-routes: true            # 使用 DHCP 提供的默认路由
            # 注意: 单口上同时配静态 IP 和 DHCP，
            #       静态 IP 作为 LAN 网关，DHCP 获取 WAN 上行 IP
        """
```

---

## 5. netplan 配置示例

### 5.1 双网口场景 (1 WAN + 1 LAN)

```yaml
# /etc/netplan/01-ubunturouter.yaml
network:
  version: 2
  renderer: networkd

  ethernets:
    enp1s0:
      # WAN 口 - 1000Mbps
      dhcp4: true
      dhcp4-overrides:
        route-metric: 100
      optional: true

    enp2s0:
      # LAN 口 - 1000Mbps（纯数据口，IP 在 bridge 层）
      dhcp4: false
      optional: true

  bridges:
    br-lan:
      interfaces: [enp2s0]
      addresses: [192.168.21.1/24]
      dhcp4: false
      parameters:
        stp: true
        forward-delay: 4
```

### 5.2 单网口 WANLAN 场景

```yaml
# /etc/netplan/01-ubunturouter.yaml
network:
  version: 2
  renderer: networkd

  ethernets:
    ens3:
      dhcp4: true
      dhcp4-overrides:
        route-metric: 1024
        use-routes: true
        use-dns: true
        use-domains: true
      addresses:
        - 192.168.21.1/24
      # 注意：网口同时有静态 IP (LAN) 和 DHCP (WAN)
      # 静态 IP 配在 ens3 上，由 systemd-networkd 的 DHCP client 获取额外 IP
      optional: true
```

### 5.3 4 网口 + VLAN 场景

```yaml
# /etc/netplan/01-ubunturouter.yaml
network:
  version: 2
  renderer: networkd

  ethernets:
    enp1s0:         # 1000Mbps - WAN1
      dhcp4: true
      dhcp4-overrides:
        route-metric: 100
    enp2s0:         # 2500Mbps - WAN2 (备线)
      dhcp4: true
      dhcp4-overrides:
        route-metric: 200
    enp3s0:         # 10000Mbps - LAN1
    enp4s0:         # 10000Mbps - LAN2

  bridges:
    br-lan:
      interfaces: [enp3s0, enp4s0]
      addresses: [192.168.21.1/24]
      dhcp4: false
      parameters:
        stp: true
        forward-delay: 4

  vlans:
    vlan10-guest:
      id: 10
      link: br-lan
      addresses: [192.168.10.1/24]

    vlan20-iot:
      id: 20
      link: br-lan
      addresses: [192.168.20.1/24]
```

---

## 6. 网口检测实现

```python
# ubunturouter/network/detect.py

import os, re, subprocess

def detect_physical_nics() -> List[NicInfo]:
    """
    检测物理网口
    
    实现方式（兼容 Ubuntu 26.04）：
    """
    
    nics = []
    sys_net = Path('/sys/class/net')
    
    for iface in sorted(sys_net.iterdir()):
        name = iface.name
        
        # 排除虚拟接口
        if name == 'lo':
            continue
        if name.startswith(('docker', 'br-', 'veth', 'virbr', 'tun', 'bond')):
            continue
        
        # 判断是否物理网口（有 device/driver 符号链接）
        device_driver = iface / 'device' / 'driver'
        is_physical = device_driver.exists()
        
        if not is_physical:
            continue  # 跳过非物理口
        
        # 获取链路状态
        carrier_file = iface / 'carrier'
        link = carrier_file.read_text().strip() == '1'
        
        # 获取速率 (ethtool)
        speed = None
        if link:
            try:
                result = subprocess.run(
                    ['ethtool', name],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'Speed' in line:
                        # Speed: 10000Mb/s
                        m = re.search(r'(\d+)Mb/s', line)
                        if m:
                            speed = int(m.group(1))
            except:
                pass
        
        # 获取 MAC
        address_file = iface / 'address'
        mac = address_file.read_text().strip()
        
        # 获取驱动
        driver = None
        driver_link = iface / 'device' / 'driver'
        if driver_link.exists():
            driver = driver_link.resolve().name
        
        # 获取 PCI 地址
        pci = None
        pci_link = iface / 'device'
        if pci_link.exists():
            pci_path = pci_link.resolve()
            # 提取 PCI 地址：/sys/devices/pci0000:00/0000:00:03.0/...
            m = re.search(r'(\d{4}:\d{2}:[0-9a-f]{2}\.[0-9a-f])', str(pci_path))
            if m:
                pci = m.group(1)
        
        nics.append(NicInfo(
            name=name,
            speed=speed,
            link=link,
            perm_mac=mac,
            driver=driver,
            pci_pci=pci,
            is_physical=True
        ))
    
    return nics


def auto_assign_roles(nics: List[NicInfo], 
                      link_priority: bool = True) -> RoleAssignment:
    """
    自动分配 WAN/LAN 角色
    
    规则：
    1. 单网口 → wanlan
    2. 多网口 → 最低速率=WAN, 其余=LAN
    3. 同速率 → 接口名排序，第1个=WAN
    4. link_priority=True → 有链路的优先分配
    
    返回: RoleAssignment
    """
    if not nics:
        return RoleAssignment(mode='none')
    
    if len(nics) == 1:
        return RoleAssignment(
            mode='wanlan',
            wanlan=WANLANAssignment(device=nics[0].name)
        )
    
    # 按速率排序（有链路的优先）
    sorted_nics = sorted(nics, key=lambda n: (
        not n.link,                # link up 优先
        n.speed if n.speed else 0  # 速率升序
    ))
    
    wan = sorted_nics[0]
    lans = sorted_nics[1:]
    
    return RoleAssignment(
        mode='multi',
        wan=WANAssignment(device=wan.name),
        lans=[LANAssignment(device=l.name) for l in lans]
    )
```

---

## 7. 特殊场景处理

### 7.1 单网口 WANLAN 模式

| 场景 | 处理方式 |
|------|----------|
| 上游 DHCP 可用 | 该口同时配 192.168.21.1/24 + DHCP 获取 WAN IP |
| 上游 PPPoE | 该口配 192.168.21.1/24，WAN 上行 PPPoE |
| 上游需要静态 IP | 该口配 192.168.21.1/24，WAN 上行配静态 IP |

**限制提示（向导中显示）**：
- "单网口模式下，连接到光猫的端口即为 LAN 口。您的设备需要先连接到光猫，然后 PC/AP 连接到同一端口（通过交换机）。"
- "如需更好的网络隔离和性能，建议增加网口。"

### 7.2 虚拟化环境检测

```python
def detect_virtualized() -> bool:
    """检测是否在虚拟机中"""
    # 检查 /sys/class/dmi/id/product_name
    # System Product Name, VMware, KVM, QEMU, VirtualBox
    try:
        product = Path('/sys/class/dmi/id/product_name').read_text().strip()
        return product in ('KVM', 'KVM', 'VMware', 'VMware Virtual Platform',
                          'VirtualBox', 'QEMU Standard PC')
    except:
        return False
```

### 7.3 网口冲突检测

```python
def check_interface_conflicts(config: UbunturouterConfig) -> List[str]:
    """
    检测接口配置冲突
    · 同一物理设备被多次引用
    · bridge 引用不存在的端口
    · VLAN ID 重复
    · Bonding slave 被其他接口引用
    · 子网 IP 冲突
    """
```

---

## 8. 与 Configuration Engine 的交互

```
Network Manager apply()
    │
    ▼
从 config.interfaces 提取接口配置
    │
    ▼
验证配置 (调用 Configuration Engine)
· 物理设备存在性
· VLAN ID 范围
· Bridge 至少有 1 个端口
· Bonding 至少有 2 个 slave
· IP 子网不与其他接口冲突
    │
    ▼
NetplanGenerator.generate(config)
    │
    ▼
写入 /etc/netplan/01-ubunturouter.yaml
    │
    ▼
netplan generate → 验证语法
    │ 失败 → 返回错误，不继续
    ▼
netplan apply
    │
    ▼
配置生效
```

---

## 9. 测试用例

| 测试场景 | 预期 |
|----------|------|
| 1 个网口 ens3, 1000M | WANLAN 模式，ens3 配 192.168.21.1/24 + DHCP |
| 2 个网口: ens3(10000M), ens4(1000M) | WAN=ens4(1000M), LAN=br-lan[ens3] |
| 2 个网口: ens3(1000M), ens4(1000M) | WAN=ens3(字母序), LAN=br-lan[ens4] |
| 4 个网口: ens3~ens6, 同速率 | WAN=ens3, LAN=br-lan[ens4,ens5,ens6] |
| 无物理网口（仅 lo） | 报错，无法初始化 |
| bridge 只有一个端口 | 允许创建（后续可扩展） |
| VLAN ID = 0 | 校验失败 |
| VLAN ID = 4095 | 校验失败 |
| 虚拟化环境 | 检测到 QEMU/KVM，添加 virtio 兼容性提示 |
