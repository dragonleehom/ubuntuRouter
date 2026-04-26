"""拓扑 API 路由 — 设备发现 + 网络拓扑数据"""

import subprocess
import json
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict
from dataclasses import dataclass, field

from ..deps import require_auth

router = APIRouter()


@dataclass
class NetworkDevice:
    ip: str
    mac: str = ""
    hostname: str = ""
    vendor: str = ""
    iface: str = ""
    is_router: bool = False
    is_active: bool = True
    rssi: int = 0          # WiFi 信号强度
    online: bool = True
    last_seen: str = ""


@dataclass
class TopologyLink:
    source: str     # 设备 IP 或接口名
    target: str     # 设备 IP 或接口名
    type: str = "wired"     # wired | wireless
    speed: int = 0
    state: str = "up"


@dataclass
class TopologyData:
    nodes: List[Dict] = field(default_factory=list)
    links: List[Dict] = field(default_factory=list)


def _read_vendors() -> Dict[str, str]:
    """简化的 MAC 前缀 → 厂商映射"""
    return {
        "00:11:22": "UbuntuRouter",
        "00:50:56": "VMware",
        "00:0c:29": "VMware",
        "08:00:27": "Oracle/VirtualBox",
        "00:15:5d": "Microsoft/Hyper-V",
        "52:54:00": "QEMU/KVM",
        "bc:ae:c5": "Intel",
        "f0:1f:af": "Intel",
        "00:1a:a0": "Broadcom",
        "e0:dc:ff": "Apple",
        "b8:27:eb": "Raspberry Pi",
        "dc:a6:32": "Raspberry Pi",
        "00:1b:63": "Ralink/MediaTek",
        "cc:2d:e0": "TP-Link",
        "fc:ec:da": "TP-Link",
        "10:fe:ed": "Xiaomi",
    }


def _lookup_vendor(mac: str) -> str:
    if not mac or len(mac) < 8:
        return ""
    vendors = _read_vendors()
    prefix = mac.upper()[:8]
    if prefix in {k.upper() for k in vendors}:
        for k, v in vendors.items():
            if mac.upper().startswith(k.upper()):
                return v
    return ""


# ─── ARP 表扫描 ─────────────────────────────────────────

@router.get("/arp")
async def scan_arp(auth=Depends(require_auth)):
    """扫描 ARP 表，获取局域网设备"""
    devices = []
    try:
        r = subprocess.run(
            ["ip", "neigh", "show"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            ip = parts[0]
            state = parts[-1] if len(parts) > 3 else ""

            # 提取 MAC
            mac = ""
            for p in parts:
                if re.match(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$', p):
                    mac = p
                    break

            # 解析 hostname
            hostname = ""
            if mac:
                hostname = _lookup_vendor(mac)

            devices.append({
                "ip": ip,
                "mac": mac,
                "hostname": hostname,
                "state": state,
                "online": state in ("REACHABLE", "STALE", "DELAY"),
                "iface": parts[1] if len(parts) > 1 and parts[0] == ip else "",
            })

        return {"devices": devices, "count": len(devices)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 接口列表（含统计） ─────────────────────────────────

@router.get("/interfaces")
async def get_topology_interfaces(auth=Depends(require_auth)):
    """获取接口拓扑信息"""
    nodes = []
    links = []
    try:
        # 接口列表
        r = subprocess.run(
            ["ip", "-j", "link", "show"],
            capture_output=True, text=True, timeout=5
        )
        links_data = json.loads(r.stdout)

        r2 = subprocess.run(
            ["ip", "-j", "addr", "show"],
            capture_output=True, text=True, timeout=5
        )
        addrs_data = json.loads(r2.stdout)

        addr_map = {}
        for entry in addrs_data:
            name = entry.get("ifname", "")
            ips = [a.get("local", "") for a in entry.get("addr_info", []) if a.get("family") == "inet"]
            if ips:
                addr_map[name] = ips[0]

        for link in links_data:
            name = link.get("ifname", "")
            if name == "lo":
                continue

            # 速率
            speed = 0
            speed_file = Path(f"/sys/class/net/{name}/speed")
            if speed_file.exists():
                try:
                    speed = int(speed_file.read_text().strip())
                except Exception:
                    pass

            node = {
                "id": name,
                "name": name,
                "type": "interface",
                "ip": addr_map.get(name, ""),
                "state": link.get("operstate", "unknown"),
                "mac": link.get("address", ""),
                "speed": speed,
                "mtu": link.get("mtu", 1500),
                "group": "router",
            }
            nodes.append(node)

        # 添加路由器自身节点
        nodes.insert(0, {
            "id": "router",
            "name": "UbuntuRouter",
            "type": "router",
            "ip": "192.168.100.194",
            "state": "up",
            "group": "router",
        })

        # 链路
        for node in nodes[1:]:  # 跳过 router 自身
            links.append({
                "source": "router",
                "target": node["id"],
                "type": "internal",
                "state": node["state"],
            })

        return {"nodes": nodes, "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 完整拓扑数据 ───────────────────────────────────────

@router.get("/full")
async def get_full_topology(auth=Depends(require_auth)):
    """获取完整拓扑数据：路由器 + 接口 + ARP 设备"""
    nodes = []
    links = []

    # 1. 路由器节点
    nodes.append({
        "id": "router",
        "name": "UbuntuRouter",
        "type": "router",
        "group": "router",
        "symbolSize": 60,
    })

    # 2. 接口数据
    try:
        r = subprocess.run(
            ["ip", "-j", "link", "show"],
            capture_output=True, text=True, timeout=5
        )
        links_data = json.loads(r.stdout)
    except Exception:
        links_data = []

    for link in links_data:
        name = link.get("ifname", "")
        if name == "lo":
            continue
        speed = 0
        speed_file = Path(f"/sys/class/net/{name}/speed")
        if speed_file.exists():
            try:
                speed = int(speed_file.read_text().strip())
            except Exception:
                pass

        nodes.append({
            "id": f"iface:{name}",
            "name": name,
            "type": "interface",
            "state": link.get("operstate", "unknown"),
            "mac": link.get("address", ""),
            "speed": speed,
            "group": "interface",
            "symbolSize": 35,
        })
        links.append({
            "source": "router",
            "target": f"iface:{name}",
            "type": "internal",
        })

    # 3. ARP 设备
    try:
        r = subprocess.run(
            ["ip", "neigh", "show"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            ip = parts[0]
            mac = ""
            for p in parts:
                if re.match(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$', p):
                    mac = p
                    break

            is_reachable = "REACHABLE" in line or "STALE" in line or "DELAY" in line
            vendor = _lookup_vendor(mac) if mac else ""

            node_id = f"device:{ip}"
            nodes.append({
                "id": node_id,
                "name": vendor or ip,
                "ip": ip,
                "mac": mac,
                "type": "device",
                "online": is_reachable,
                "group": "device" if is_reachable else "offline",
                "symbolSize": 25,
            })

            # 链路: device → 接口
            for link_entry in links_data:
                name = link_entry.get("ifname", "")
                if name == "lo":
                    continue
                links.append({
                    "source": f"iface:{name}",
                    "target": node_id,
                    "type": "wired" if is_reachable else "offline",
                })
                break
    except Exception:
        pass

    return {"nodes": nodes, "links": links}
