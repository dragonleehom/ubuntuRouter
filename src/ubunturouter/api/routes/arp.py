"""ARP 扫描 API — 获取在线设备列表

通过读取 /proc/net/arp 获取 ARP 表中的在线设备，并尝试
通过 DHCP 租约文件获取主机名。
"""

import subprocess
import re
import logging
from pathlib import Path
from fastapi import APIRouter, Depends

from ..deps import require_auth

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_arp_table() -> list[dict]:
    """读取 /proc/net/arp 解析在线设备"""
    devices = []
    try:
        with open("/proc/net/arp") as f:
            lines = f.readlines()[1:]  # 跳过标题行
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 4:
                    ip = parts[0]
                    hw_type = parts[1]
                    flags = parts[2]
                    mac = parts[3]

                    # 只取完整条目 (flags != 0x00)
                    if flags == "0x00":
                        continue
                    # 跳过不完整条目
                    if mac == "00:00:00:00:00:00" or mac.count(":") != 5:
                        continue

                    devices.append({
                        "ip": ip,
                        "mac": mac.upper(),
                        "interface": parts[5] if len(parts) > 5 else "",
                    })
    except Exception as e:
        logger.error(f"读取 ARP 表失败: {e}")
    return devices


def _resolve_hostnames(devices: list[dict]) -> dict:
    """尝试通过 DHCP 租约和反向 DNS 解析主机名"""
    # 从 dnsmasq 租约文件读取
    hostname_map = {}
    lease_paths = [
        "/var/lib/misc/dnsmasq.leases",
        "/var/lib/dhcp/dhcpd.leases",
        "/var/lib/dnsmasq/dnsmasq.leases",
        "/tmp/dnsmasq.leases",
    ]
    for lp in lease_paths:
        p = Path(lp)
        if p.exists():
            try:
                for line in p.read_text().splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        mac = parts[1].upper()
                        hostname = parts[3]
                        if hostname and hostname != "*":
                            hostname_map[mac] = hostname
            except Exception:
                pass

    # 尝试 hosts 文件
    try:
        with open("/etc/hosts") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        hostname = parts[1]
                        for dev in devices:
                            if dev["ip"] == ip and dev["mac"] not in hostname_map:
                                hostname_map[dev["mac"]] = hostname
    except Exception:
        pass

    return hostname_map


def _get_vendor(mac: str) -> str:
    """通过 MAC 前 3 字节判断厂商 (OUI 前缀)"""
    prefix = mac[:8]  # XX:XX:XX
    oui_db = {
        "00:11:22": "DD-WRT",
        "00:1A:2B": "Intel",
        "00:1B:21": "Intel",
        "00:1C:BF": "Intel",
        "00:1E:8C": "Intel",
        "00:1F:29": "Intel",
        "00:21:6A": "Intel",
        "00:23:14": "Intel",
        "00:24:D6": "Intel",
        "00:25:56": "Intel",
        "00:26:AB": "Intel",
        "00:27:10": "Intel",
        "00:50:56": "VMware",
        "00:0C:29": "VMware",
        "00:05:69": "VMware",
        "00:1C:42": "Parallels",
        "00:15:5D": "Hyper-V",
        "00:1A:4A": "Broadcom",
        "00:12:37": "Cisco",
        "00:1A:A1": "Cisco",
        "00:24:97": "Apple",
        "00:25:00": "Apple",
        "00:26:08": "Apple",
        "00:26:B0": "Apple",
        "00:50:56": "VMware",
        "B8:27:EB": "Raspberry Pi",
        "DC:A6:32": "Raspberry Pi",
        "E4:5F:01": "Raspberry Pi",
        "00:0E:C6": "Nokia",
        "00:23:47": "Samsung",
        "00:26:37": "Samsung",
        "00:1E:DF": "Huawei",
        "00:25:9E": "Huawei",
        "A0:04:60": "Xiaomi",
        "40:31:3C": "Xiaomi",
        "DC:0B:1A": "Xiaomi",
        "00:26:47": "TP-Link",
        "00:27:19": "TP-Link",
        "00:1A:79": "ASUS",
        "00:26:56": "ASUS",
        "1C:87:2C": "ASUS",
        "34:29:8F": "Hikvision",
        "00:19:07": "Linksys",
        "00:1A:70": "Netgear",
        "00:23:DF": "Netgear",
        "D4:6E:0E": "Ubiquiti",
        "E0:B9:BA": "Ubiquiti",
        "00:0F:B5": "D-Link",
        "00:1B:11": "D-Link",
    }
    return oui_db.get(prefix, "未知")


@router.get("/list")
async def list_devices(auth=Depends(require_auth)):
    """获取在线设备列表"""
    devices = _parse_arp_table()
    hostnames = _resolve_hostnames(devices)

    result = []
    for dev in devices:
        mac = dev["mac"]
        result.append({
            "ip": dev["ip"],
            "mac": mac,
            "interface": dev["interface"],
            "hostname": hostnames.get(mac, ""),
            "vendor": _get_vendor(mac),
        })

    return {
        "success": True,
        "count": len(result),
        "devices": result,
    }


@router.get("/count")
async def device_count(auth=Depends(require_auth)):
    """仅获取在线设备数量"""
    devices = _parse_arp_table()
    return {"success": True, "count": len(devices)}
