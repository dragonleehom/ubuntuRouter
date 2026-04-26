"""Netplan 配置生成器 — 将统一配置中的网络接口信息生成 netplan YAML

迁移自 ubunturouter/generators/netplan.py。
使用 EventBus + BaseGenerator 模式，响应 "interfaces" 配置节变更。
"""

import yaml
import logging
from pathlib import Path
from typing import List, Dict, Optional

from ubunturouter.config.models import (
    UbunturouterConfig, InterfaceConfig, InterfaceRole, InterfaceType,
    IPConfig, IPMethod, VlanConfig, BondConfig, BondMode,
)
from ubunturouter.engine.events import GeneratorResult
from ubunturouter.engine.generators.base import BaseGenerator, register_generator

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("/etc/netplan/01-ubunturouter.yaml")


@register_generator
class NetplanGenerator(BaseGenerator):
    """生成 /etc/netplan/01-ubunturouter.yaml"""
    SECTION = "interfaces"

    def generate(self, config: UbunturouterConfig) -> GeneratorResult:
        files_modified = []
        ifaces = self._build_all_interfaces(config)
        netplan_config = {
            "network": {
                "version": 2,
                "renderer": "networkd",
            }
        }

        # Only add non-empty sections
        for key, val in ifaces.items():
            if val:
                netplan_config["network"][key] = val

        yaml_str = yaml.dump(
            netplan_config,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            indent=2,
        )

        if self.write_file(OUTPUT_PATH, yaml_str):
            files_modified.append(str(OUTPUT_PATH))
        else:
            return self.fail(f"Failed to write {OUTPUT_PATH}")

        # Apply netplan
        result = self.run_cmd(["netplan", "apply"])
        if result["success"]:
            return self.ok(
                f"netplan generated and applied ({len(ifaces.get('ethernets', {})) + len(ifaces.get('bridges', {})) + len(ifaces.get('vlans', {}))} interfaces)",
                files_modified,
            )
        else:
            return self.fail(f"netplan apply failed: {result['stderr']}")

    # ─── 内部方法（迁移自 generators/netplan.py）─────────────

    def _build_all_interfaces(self, config: UbunturouterConfig) -> Dict:
        ethernets = {}
        bonds = {}
        bridges = {}
        vlans = {}

        for iface in config.interfaces:
            if iface.type == InterfaceType.ETHERNET:
                if iface.role == InterfaceRole.WANLAN:
                    ethernets[iface.device] = self._build_phy_iface(iface)
                    bridge_name = f"br-{iface.name}"
                    bridges[bridge_name] = self._build_wanlan_bridge(iface, bridge_name)
                elif iface.role in (InterfaceRole.LAN, InterfaceRole.GUEST, InterfaceRole.DMZ):
                    bridge_name = iface.ports[0] if iface.ports else f"br-{iface.name}"
                    ethernets[iface.device] = self._build_phy_iface_no_ip(iface)
                    if iface.ports and len(iface.ports) > 0:
                        pass
                else:
                    ethernets[iface.device] = self._build_phy_iface(iface)

            elif iface.type == InterfaceType.BOND:
                bonds[iface.name] = self._build_bond(iface)
            elif iface.type == InterfaceType.BRIDGE:
                bridges[iface.name] = self._build_bridge(iface)

            if iface.vlans:
                for vlan in iface.vlans:
                    vlan_name = vlan.name or f"{iface.name}.{vlan.id}"
                    vlan_config = self._build_vlan(vlan, iface.name)
                    if vlan_config:
                        vlans[vlan_name] = vlan_config

        lan_ifaces = [i for i in config.interfaces
                      if i.role == InterfaceRole.LAN and i.type == InterfaceType.ETHERNET]
        if len(lan_ifaces) > 1:
            bridge_ports = [i.device for i in lan_ifaces if i.device]
            br_lan_name = "br-lan"
            lan0 = lan_ifaces[0]
            br_config = {
                "interfaces": bridge_ports,
                "dhcp4": False,
                "optional": True,
            }
            if lan0.ipv4 and lan0.ipv4.method == IPMethod.STATIC and lan0.ipv4.address:
                br_config["addresses"] = [lan0.ipv4.address]
            bridges[br_lan_name] = br_config
            for i_face in lan_ifaces:
                if i_face.device in ethernets:
                    eth_config = ethernets[i_face.device]
                    eth_config.pop("addresses", None)
                    eth_config.pop("dhcp4", None)
                    eth_config["optional"] = True
        elif len(lan_ifaces) == 1:
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
