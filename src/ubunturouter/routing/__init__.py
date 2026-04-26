"""路由运行时管理器 — 读取/操作 Linux 路由表"""
import subprocess
import json
import re
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
import ipaddress


@dataclass
class RouteEntry:
    destination: str
    gateway: str
    netmask: str
    iface: str
    metric: int = 0
    table: int = 254  # 254 = main
    proto: str = ""
    is_default: bool = False
    flags: List[str] = field(default_factory=list)


@dataclass
class RoutingTable:
    table_id: int
    table_name: str = ""
    routes: List[RouteEntry] = field(default_factory=list)


@dataclass
class MultiWANStatus:
    wan_name: str
    iface: str
    gateway: str
    online: bool
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    is_active: bool = False  # 当前是否为默认路由出口


class RoutingManager:
    """Linux 路由管理器 — 操作 ip route / ip rule"""

    def __init__(self):
        pass

    # ─── 路由表读取 ────────────────────────────────────────

    def get_routes(self, table: str = "main") -> List[RouteEntry]:
        """读取指定路由表"""
        routes = []
        try:
            r = subprocess.run(
                ["ip", "-j", "route", "show", "table", table],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0:
                return routes
            data = json.loads(r.stdout)
            for entry in data:
                dst = entry.get("dst", "")
                is_default = dst == "default"
                route = RouteEntry(
                    destination=dst,
                    gateway=entry.get("gateway", ""),
                    netmask=entry.get("prefsrc", ""),
                    iface=entry.get("dev", ""),
                    metric=int(entry.get("metric", 0)),
                    table=int(entry.get("table", 254)),
                    proto=entry.get("protocol", ""),
                    is_default=is_default,
                )
                routes.append(route)
        except Exception:
            pass
        return routes

    def get_all_routing_tables(self) -> List[RoutingTable]:
        """读取所有路由表"""
        tables = []
        # 获取已知表名
        table_names = self._get_table_names()

        for table_id_str, table_name in table_names.items():
            table_id = int(table_id_str)
            routes = self.get_routes(str(table_id))
            tables.append(RoutingTable(
                table_id=table_id,
                table_name=table_name,
                routes=routes,
            ))

        return tables

    def get_default_route(self) -> Optional[RouteEntry]:
        """获取默认路由"""
        routes = self.get_routes("main")
        for r in routes:
            if r.is_default:
                return r
        return None

    def get_routing_rules(self) -> List[Dict]:
        """获取策略路由规则 (ip rule)"""
        rules = []
        try:
            r = subprocess.run(
                ["ip", "-j", "rule", "show"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return rules
            data = json.loads(r.stdout)
            for entry in data:
                rule = {
                    "priority": entry.get("priority", 0),
                    "from": entry.get("from", "all"),
                    "to": entry.get("to", "all"),
                    "table": entry.get("table", 254),
                    "fwmark": entry.get("fwmark", ""),
                    "iif": entry.get("iif", ""),
                    "oif": entry.get("oif", ""),
                }
                rules.append(rule)
        except Exception:
            pass
        return rules

    # ─── 静态路由 CRUD ────────────────────────────────────

    def add_static_route(self, destination: str, gateway: str,
                         iface: str = "", metric: int = 0,
                         table: str = "main") -> bool:
        """添加静态路由"""
        cmd = ["ip", "route", "add", destination]
        if gateway:
            cmd += ["via", gateway]
        if iface:
            cmd += ["dev", iface]
        if metric > 0:
            cmd += ["metric", str(metric)]
        if table != "main":
            cmd += ["table", table]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    def delete_static_route(self, destination: str, gateway: str = "",
                            iface: str = "", table: str = "main") -> bool:
        """删除静态路由"""
        cmd = ["ip", "route", "delete", destination]
        if gateway:
            cmd += ["via", gateway]
        if iface:
            cmd += ["dev", iface]
        if table != "main":
            cmd += ["table", table]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    def replace_default_route(self, gateway: str, iface: str,
                              metric: int = 100) -> bool:
        """替换默认路由"""
        # 先删现有的默认路由
        self.delete_static_route("default", table="main")
        # 添加新的
        return self.add_static_route("default", gateway, iface, metric)

    # ─── Multi-WAN 健康检测 ───────────────────────────────

    def get_multiwan_status(self) -> List[MultiWANStatus]:
        """检测所有 WAN 口状态"""
        wans = []
        try:
            r = subprocess.run(
                ["ip", "-j", "addr", "show"],
                capture_output=True, text=True, timeout=5
            )
            ifaces = json.loads(r.stdout)

            # 获取默认路由的接口
            default_route = self.get_default_route()
            active_iface = default_route.iface if default_route else ""

            for iface in ifaces:
                name = iface.get("ifname", "")
                if name == "lo":
                    continue
                # 获取该接口的网关
                gateway = self._get_iface_gateway(name)
                if not gateway:
                    continue

                # 检测连通性
                latency, loss = self._ping_test(gateway)

                wans.append(MultiWANStatus(
                    wan_name=name,
                    iface=name,
                    gateway=gateway,
                    online=loss < 100,
                    latency_ms=latency,
                    packet_loss=loss,
                    is_active=(name == active_iface),
                ))
        except Exception:
            pass
        return wans

    def switch_default_gateway(self, iface: str, gateway: str) -> bool:
        """手动切换默认路由到指定接口"""
        return self.replace_default_route(gateway, iface, metric=100)

    # ─── 辅助 ──────────────────────────────────────────────

    def _get_iface_gateway(self, iface: str) -> str:
        """获取接口的网关地址（从路由表反向查找）"""
        routes = self.get_routes("main")
        for route in routes:
            if route.iface == iface and route.is_default:
                return route.gateway
        return ""

    def _ping_test(self, target: str, count: int = 2) -> tuple:
        """ping 检测延迟和丢包率"""
        try:
            r = subprocess.run(
                ["ping", "-c", str(count), "-W", "2", target],
                capture_output=True, text=True, timeout=10
            )
            output = r.stdout

            # 解析延迟
            avg_latency = 0.0
            match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/', output)
            if match:
                avg_latency = float(match.group(1))

            # 解析丢包率
            loss = 100.0
            match = re.search(r'(\d+)% packet loss', output)
            if match:
                loss = float(match.group(1))

            return avg_latency, loss
        except Exception:
            return 0.0, 100.0

    def _get_table_names(self) -> Dict[str, str]:
        """获取路由表 ID 到名称的映射"""
        names = {"255": "local", "254": "main", "253": "default", "0": "unspec"}
        try:
            r = subprocess.run(
                ["cat", "/etc/iproute2/rt_tables"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].isdigit():
                        names[parts[0]] = parts[1]
        except Exception:
            pass
        return names
