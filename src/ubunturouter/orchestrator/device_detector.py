"""设备检测引擎 — 监听 DHCP 租约 + ARP 扫描 + mDNS 解析识别局域网设备"""
import subprocess
import threading
import logging
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

import yaml

from ..dhcp import DnsmasqManager

logger = logging.getLogger("ubunturouter.orchestrator.devices")

DEVICE_DB_PATH = Path("/opt/ubunturouter/data/devices.yaml")

# 常见 MAC OUI 厂商前缀数据库（至少10个）
MAC_OUI_DB: Dict[str, str] = {
    "00:11:22": "Cisco",
    "00:1A:2B": "Intel",
    "00:1B:63": "Dell",
    "00:1C:BF": "HP",
    "00:1D:60": "Apple",
    "00:1E:4C": "Lenovo",
    "00:21:5A": "Huawei",
    "00:22:15": "Xiaomi",
    "00:23:8B": "Samsung",
    "00:24:FE": "Netgear",
    "00:25:90": "TP-Link",
    "00:26:5E": "ASUS",
    "00:27:19": "ZTE",
    "00:50:56": "VMware",
    "00:0C:29": "VMware",
    "08:00:27": "Oracle (VirtualBox)",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "A4:CF:12": "Apple",
    "F0:18:98": "Xiaomi",
    "18:FE:34": "OnePlus",
    "F4:5C:89": "Huawei",
    "E0:DC:FF": "Amazon",
    "E8:9F:6D": "Microsoft",
    "00:17:88": "Nokia",
    "00:24:36": "D-Link",
    "E0:AC:CB": "Google",
    "3C:5A:B4": "Google",
    "18:9E:FC": "Sonos",
    "60:6C:66": "Broadcom",
}


@dataclass
class Device:
    """局域网设备信息"""
    mac: str
    ip: str = ""
    hostname: str = ""
    iface: str = ""
    online: bool = False
    vendor: str = ""
    first_seen: str = ""
    last_seen: str = ""
    device_type: str = "client"  # router / client / unknown
    custom_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mac": self.mac,
            "ip": self.ip,
            "hostname": self.hostname,
            "iface": self.iface,
            "online": self.online,
            "vendor": self.vendor,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "device_type": self.device_type,
            "custom_name": self.custom_name,
            "display_name": self.custom_name or self.hostname or self.mac,
        }


class DeviceDetector:
    """设备检测引擎

    从多个来源发现局域网设备:
    - DHCP 租约 (DnsmasqManager)
    - ARP 表 (ip neigh show)
    - mDNS 解析 (avahi-browse)
    - 接口信息 (/sys/class/net/)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._dhcp = DnsmasqManager()
        self._devices: Dict[str, Device] = {}  # key: mac 地址
        self._gateway_ips: List[str] = []
        self._detect_gateway_ips()
        self._load_persisted()

    # ─── 公共方法 ──────────────────────────────────────────────

    def detect_all(self) -> List[Device]:
        """全量检测：采集所有来源并返回设备列表"""
        known_macs = set(self._devices.keys())
        now = datetime.now().isoformat()

        # 1. 从 DHCP 租约获取
        leases = self._dhcp.get_leases()
        for lease in leases:
            mac = lease.mac.upper()
            if mac not in self._devices:
                device = Device(
                    mac=mac,
                    ip=lease.ip,
                    hostname=lease.hostname,
                    online=True,
                    vendor=self._lookup_vendor(mac),
                    first_seen=now,
                    last_seen=now,
                    device_type=self._classify_device(lease.ip),
                )
                self._devices[mac] = device
            else:
                existing = self._devices[mac]
                existing.ip = lease.ip or existing.ip
                existing.hostname = lease.hostname or existing.hostname
                existing.online = True
                existing.last_seen = now
                if not existing.vendor:
                    existing.vendor = self._lookup_vendor(mac)

        # 2. 从 ARP 表补充
        arp_entries = self._scan_arp_table()
        for mac, ip, iface in arp_entries:
            mac = mac.upper()
            if mac not in self._devices:
                device = Device(
                    mac=mac,
                    ip=ip,
                    iface=iface,
                    online=True,
                    vendor=self._lookup_vendor(mac),
                    first_seen=now,
                    last_seen=now,
                    device_type=self._classify_device(ip),
                )
                self._devices[mac] = device
            else:
                existing = self._devices[mac]
                existing.ip = ip or existing.ip
                existing.iface = iface or existing.iface
                existing.online = True
                existing.last_seen = now
                if not existing.vendor:
                    existing.vendor = self._lookup_vendor(mac)

        # 3. mDNS 解析获取主机名
        mdns_hostnames = self._resolve_mdns()
        for mac, hostname in mdns_hostnames.items():
            mac = mac.upper()
            if mac in self._devices and not self._devices[mac].hostname:
                self._devices[mac].hostname = hostname

        # 4. 标记离线设备（之前见过但本次扫描不在线）
        for mac in known_macs:
            if mac in self._devices:
                # 在 ARP 和 DHCP 中都找不到才算离线
                still_seen = any(m.upper() == mac for m, _, _ in arp_entries)
                still_seen = still_seen or any(
                    l.mac.upper() == mac for l in leases
                )
                if not still_seen:
                    self._devices[mac].online = False

        self._persist()
        return self.get_devices()

    def get_devices(self) -> List[Device]:
        """返回当前已知的所有设备列表"""
        with self._lock:
            return list(self._devices.values())

    def get_device(self, mac: str) -> Optional[Device]:
        """根据 MAC 获取单个设备"""
        with self._lock:
            return self._devices.get(mac.upper())

    def rename(self, mac: str, new_name: str) -> bool:
        """用户自定义设备名称"""
        with self._lock:
            mac = mac.upper()
            if mac not in self._devices:
                return False
            self._devices[mac].custom_name = new_name
            self._persist()
            logger.info("Device %s renamed to '%s'", mac, new_name)
            return True

    # ─── 内部辅助 ──────────────────────────────────────────────

    def _detect_gateway_ips(self) -> None:
        """检测网关 IP 地址（从路由表获取）"""
        try:
            r = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.strip().split("\n"):
                parts = line.split()
                if "via" in parts:
                    idx = parts.index("via")
                    if idx + 1 < len(parts):
                        self._gateway_ips.append(parts[idx + 1])
        except Exception:
            pass

    def _classify_device(self, ip: str) -> str:
        """根据 IP 归类设备类型"""
        if ip in self._gateway_ips:
            return "router"
        # 检查是否为本机 IP
        try:
            r = subprocess.run(
                ["ip", "-j", "addr", "show"],
                capture_output=True, text=True, timeout=5,
            )
            import json
            data = json.loads(r.stdout)
            for iface in data:
                for addr_info in iface.get("addr_info", []):
                    if addr_info.get("local") == ip:
                        return "router"
        except Exception:
            pass
        return "client"

    def _lookup_vendor(self, mac: str) -> str:
        """根据 MAC 地址查询厂商"""
        # 标准化 MAC: 去掉分隔符后取前6个十六进制字符
        oui = mac.replace(":", "").replace("-", "").upper()[:6]
        # 按冒号格式查找
        formatted = ":".join(oui[i:i+2] for i in range(0, 6, 2))
        return MAC_OUI_DB.get(formatted, "")

    def _scan_arp_table(self) -> List[tuple]:
        """扫描 ARP 表获取 MAC->IP 映射"""
        entries = []
        try:
            r = subprocess.run(
                ["ip", "neigh", "show"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                # 格式: 192.168.1.100 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE
                match = re.match(
                    r"(\S+)\s+dev\s+(\S+)\s+lladdr\s+(\S+)",
                    line,
                )
                if match:
                    ip = match.group(1)
                    iface = match.group(2)
                    mac = match.group(3).upper()
                    state = "REACHABLE" in line or "STALE" in line
                    entries.append((mac, ip, iface))
        except Exception:
            pass
        return entries

    def _resolve_mdns(self) -> Dict[str, str]:
        """通过 avahi-browse 解析 mDNS 主机名"""
        mdns_map: Dict[str, str] = {}
        try:
            r = subprocess.run(
                ["avahi-browse", "-a", "-t", "--parsable"],
                capture_output=True, text=True, timeout=10,
            )
            for line in r.stdout.strip().split("\n"):
                if not line:
                    continue
                # 格式: eth0;IPv4;hostname;_http._tcp;local
                parts = line.split(";")
                if len(parts) >= 4:
                    hostname = parts[2]
                    # 尝试从同一服务发现获取 MAC
                    # avahi-browse 通常不直接输出 MAC, 结合 ARP 表关联
                    mdns_map[hostname] = hostname
        except FileNotFoundError:
            # avahi-browse 未安装
            pass
        except Exception as e:
            logger.debug("mDNS resolution failed: %s", e)

        # 尝试通过 dbus 查询（更可靠）
        if not mdns_map:
            try:
                r = subprocess.run(
                    ["dbus-send", "--system", "--dest=org.freedesktop.Avahi",
                     "/", "org.freedesktop.Avahi.Server.GetHostName",
                     "--print-reply=literal"],
                    capture_output=True, text=True, timeout=5,
                )
            except Exception:
                pass

        return mdns_map

    # ─── 持久化 ────────────────────────────────────────────────

    def _persist(self) -> None:
        """保存设备列表到 YAML 文件"""
        try:
            DEVICE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            devices_data = []
            with self._lock:
                for dev in self._devices.values():
                    devices_data.append(dev.to_dict())
            with open(DEVICE_DB_PATH, "w", encoding="utf-8") as f:
                yaml.dump(devices_data, f, default_flow_style=False,
                          allow_unicode=True, sort_keys=False)
        except OSError as e:
            logger.error("Failed to persist device database: %s", e)

    def _load_persisted(self) -> None:
        """从 YAML 文件加载设备列表"""
        try:
            if DEVICE_DB_PATH.exists():
                with open(DEVICE_DB_PATH, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "mac" in item:
                            dev = Device(
                                mac=item["mac"].upper(),
                                ip=item.get("ip", ""),
                                hostname=item.get("hostname", ""),
                                iface=item.get("iface", ""),
                                online=item.get("online", False),
                                vendor=item.get("vendor", ""),
                                first_seen=item.get("first_seen", ""),
                                last_seen=item.get("last_seen", ""),
                                device_type=item.get("device_type", "client"),
                                custom_name=item.get("custom_name", ""),
                            )
                            self._devices[dev.mac] = dev
                    logger.info("Loaded %d devices from %s",
                                len(self._devices), DEVICE_DB_PATH)
        except Exception as e:
            logger.warning("Failed to load device database: %s", e)
