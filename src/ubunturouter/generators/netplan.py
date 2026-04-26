"""Netplan 配置生成器 — 物理口/VLAN/Bridge/Bonding/WANLAN"""

import yaml
from typing import Dict, List, Optional
from ..config.models import (
    UbunturouterConfig, InterfaceConfig, InterfaceRole, InterfaceType,
    IPConfig, IPMethod, VlanConfig, BondConfig, BondMode,
)
from .base import ConfigGenerator


OUTPUT_PATH = "/etc/netplan/01-ubunturouter.yaml"


class NetplanGenerator(ConfigGenerator):
    """将统一配置中的网络接口信息生成 netplan 配置"""

    def __init__(self):
        self.output_path = OUTPUT_PATH

    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        ifaces = self._build_all_interfaces(config)
        netplan_config = {
            "network": {
                "version": 2,
                "renderer": "networkd",
                "ethernets": ifaces.get("ethernets", {}),
                "bonds": ifaces.get("bonds", {}),
                "bridges": ifaces.get("bridges", {}),
                "vlans": ifaces.get("vlans", {}),
            }
        }

        yaml_str = yaml.dump(
            netplan_config,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            indent=2,
        )
        return {self.output_path: yaml_str}

    def validate_generated(self, content: str) -> Optional[str]:
        return None  # netplan generate 会在 apply 时自动校验

    def reload_command(self) -> List[str]:
        return ["netplan", "apply"]

    def reload_delay(self) -> int:
        return 0

    # ─── 内部方法 ────────────────────────────────────────

    def _build_all_interfaces(self, config: UbunturouterConfig) -> Dict:
        ethernets = {}
        bonds = {}
        bridges = {}
        vlans = {}

        for iface in config.interfaces:
            if iface.type == InterfaceType.ETHERNET:
                # WANLAN：特殊处理，单个网口同时做 WAN+LAN
                if iface.role == InterfaceRole.WANLAN:
                    ethernets[iface.device] = self._build_phy_iface(iface)
                    # WANLAN 创建一个 br-wanlan bridge
                    bridge_name = f"br-{iface.name}"
                    bridges[bridge_name] = self._build_wanlan_bridge(
                        iface, bridge_name
                    )
                elif iface.role in (InterfaceRole.LAN, InterfaceRole.GUEST, InterfaceRole.DMZ):
                    # LAN 口桥接到 br-lan
                    bridge_name = iface.ports[0] if iface.ports else f"br-{iface.name}"
                    ethernets[iface.device] = self._build_phy_iface_no_ip(iface)
                    # 如果是第一个 LAN 口或已指定，创建 bridge
                    if iface.ports and len(iface.ports) > 0:
                        # 多 LAN 口共享一个 bridge
                        pass  # 在 _build_brlan_bridge 中处理
                else:
                    # WAN 直连
                    ethernets[iface.device] = self._build_phy_iface(iface)

            elif iface.type == InterfaceType.BOND:
                bonds[iface.name] = self._build_bond(iface)

            elif iface.type == InterfaceType.BRIDGE:
                bridges[iface.name] = self._build_bridge(iface)

            # VLAN 从接口配置中展开
            if iface.vlans:
                for vlan in iface.vlans:
                    vlan_name = vlan.name or f"{iface.name}.{vlan.id}"
                    vlan_config = self._build_vlan(vlan, iface.name)
                    if vlan_config:
                        vlans[vlan_name] = vlan_config

        # 构建单一 LAN bridge（如果有多 LAN 口）
        lan_ifaces = [i for i in config.interfaces
                      if i.role == InterfaceRole.LAN and i.type == InterfaceType.ETHERNET]
        if len(lan_ifaces) > 1:
            # 自动桥接多 LAN 口
            bridge_ports = [i.device for i in lan_ifaces if i.device]
            br_lan_name = "br-lan"
            # 第一个 LAN 口的 IP 配置作为 bridge IP
            lan0 = lan_ifaces[0]
            br_config = {
                "interfaces": bridge_ports,
                "dhcp4": False,
                "optional": True,
            }
            if lan0.ipv4 and lan0.ipv4.method == IPMethod.STATIC and lan0.ipv4.address:
                br_config["addresses"] = [lan0.ipv4.address]
            bridges[br_lan_name] = br_config
            # 把各 LAN 口的 ipv4 移除（已转到 bridge）
            for i_face in lan_ifaces:
                if i_face.device in ethernets:
                    eth_config = ethernets[i_face.device]
                    eth_config.pop("addresses", None)
                    eth_config.pop("dhcp4", None)
                    eth_config["optional"] = True
        elif len(lan_ifaces) == 1:
            # 单 LAN 口，直接使用其配置
            lan0 = lan_ifaces[0]
            ethernets[lan0.device] = self._build_phy_iface(lan0)

        return {
            "ethernets": ethernets or None,
            "bonds": bonds or None,
            "bridges": bridges or None,
            "vlans": vlans or None,
        }

    def _build_phy_iface(self, iface: InterfaceConfig) -> Dict:
        cfg = {"dhcp4": False}
        if iface.ipv4 and iface.ipv4.method == IPMethod.DHCP:
            cfg["dhcp4"] = True
        elif iface.ipv4 and iface.ipv4.method == IPMethod.STATIC and iface.ipv4.address:
            cfg["addresses"] = [iface.ipv4.address]
            if iface.ipv4.gateway:
                cfg["routes"] = [{"to": "default", "via": iface.ipv4.gateway}]
            if iface.ipv4.dns:
                cfg["nameservers"] = {"addresses": iface.ipv4.dns}
        if iface.mtu:
            cfg["mtu"] = iface.mtu
        if iface.mac:
            cfg["match"] = {"macaddress": iface.mac}
        cfg["optional"] = True
        return cfg

    def _build_phy_iface_no_ip(self, iface: InterfaceConfig) -> Dict:
        cfg = {"dhcp4": False, "optional": True}
        if iface.mtu:
            cfg["mtu"] = iface.mtu
        return cfg

    def _build_wanlan_bridge(self, iface: InterfaceConfig, bridge_name: str) -> Dict:
        cfg = {
            "interfaces": [iface.device],
            "dhcp4": False,
            "optional": True,
        }
        if iface.ipv4 and iface.ipv4.method == IPMethod.STATIC and iface.ipv4.address:
            cfg["addresses"] = [iface.ipv4.address]
            if iface.ipv4.gateway:
                cfg["routes"] = [{"to": "default", "via": iface.ipv4.gateway}]
            if iface.ipv4.dns:
                cfg["nameservers"] = {"addresses": iface.ipv4.dns}
        return cfg

    def _build_bond(self, iface: InterfaceConfig) -> Dict:
        if not iface.bond:
            return {}
        cfg = {
            "interfaces": iface.bond.slaves,
            "parameters": {
                "mode": iface.bond.mode.value,
                "mii-monitor-interval": iface.bond.mii_monitor_interval,
            },
            "dhcp4": False,
            "optional": True,
        }
        if iface.ipv4 and iface.ipv4.method == IPMethod.STATIC and iface.ipv4.address:
            cfg["addresses"] = [iface.ipv4.address]
        elif iface.ipv4 and iface.ipv4.method == IPMethod.DHCP:
            cfg["dhcp4"] = True
        return cfg

    def _build_bridge(self, iface: InterfaceConfig) -> Dict:
        ports = iface.ports or []
        cfg = {
            "interfaces": ports,
            "dhcp4": False,
            "optional": True,
        }
        if iface.ipv4 and iface.ipv4.method == IPMethod.STATIC and iface.ipv4.address:
            cfg["addresses"] = [iface.ipv4.address]
        elif iface.ipv4 and iface.ipv4.method == IPMethod.DHCP:
            cfg["dhcp4"] = True
        return cfg

    def _build_vlan(self, vlan: VlanConfig, parent: str) -> Optional[Dict]:
        vlan_name = vlan.name or f"{parent}.{vlan.id}"
        cfg = {
            "id": vlan.id,
            "link": parent,
            "dhcp4": False,
            "optional": True,
        }
        if vlan.ipv4 and vlan.ipv4.method == IPMethod.STATIC and vlan.ipv4.address:
            cfg["addresses"] = [vlan.ipv4.address]
        elif vlan.ipv4 and vlan.ipv4.method == IPMethod.DHCP:
            cfg["dhcp4"] = True
        return cfg
