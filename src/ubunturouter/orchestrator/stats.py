"""流量统计聚合 — 从 conntrack 和 nftables counter 读取统计"""
import json
import logging
import re
import subprocess
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger("ubunturouter.orchestrator.stats")


class TrafficStats:
    """流量统计聚合

    从 conntrack、nftables counter 和系统接口读取流量统计数据，
    按设备、应用和通道维度聚合。
    """

    def __init__(self):
        pass

    # ─── 设备统计 ──────────────────────────────────────────────

    def get_device_stats(self) -> Dict[str, Dict[str, int]]:
        """获取各设备的流量统计

        Returns:
            {mac: {rx_bytes, tx_bytes, rx_packets, tx_packets}}
        """
        stats: Dict[str, Dict[str, int]] = {}

        # 从 conntrack 获取按源 MAC 的流量
        conntrack_data = self._get_conntrack_stats()
        for entry in conntrack_data:
            mac = entry.get("src_mac", "").upper()
            if not mac:
                continue
            if mac not in stats:
                stats[mac] = {
                    "rx_bytes": 0,
                    "tx_bytes": 0,
                    "rx_packets": 0,
                    "tx_packets": 0,
                }

            # conntrack 的 src 是内部设备，dst 是外部
            # tx: 设备发送, rx: 设备接收
            bytes_in = entry.get("bytes", 0)
            packets_in = entry.get("packets", 0)
            # 注意: conntrack -L 通常不区分方向统计
            stats[mac]["tx_bytes"] += bytes_in
            stats[mac]["tx_packets"] += packets_in

        # 补充来自接口的统计（如果设备有对应接口）
        iface_stats = self._get_iface_stats()
        for mac, data in stats.items():
            # 尝试通过 ARP 找到对应接口
            iface = self._mac_to_iface(mac)
            if iface and iface in iface_stats:
                data["rx_bytes"] = iface_stats[iface].get("rx_bytes", 0)
                data["rx_packets"] = iface_stats[iface].get("rx_packets", 0)

        return stats

    # ─── 应用统计 ──────────────────────────────────────────────

    def get_app_stats(self) -> Dict[str, Dict[str, int]]:
        """获取按应用分类的流量统计

        Returns:
            {app_name: {bytes, connections}}
        """
        stats: Dict[str, Dict[str, int]] = {}

        # 从 nftables counter 获取
        nft_stats = self._get_nftables_counter_stats()
        for app_name, data in nft_stats.items():
            stats[app_name] = {
                "bytes": data.get("bytes", 0),
                "connections": data.get("connections", 0),
            }

        # 从 conntrack 按目标 IP/端口推断应用
        conntrack_data = self._get_conntrack_stats()
        # 使用简单端口映射推断
        port_app_map = {
            443: "HTTPS",
            80: "HTTP",
            53: "DNS",
            22: "SSH",
        }
        for entry in conntrack_data:
            dst_port = entry.get("dst_port", 0)
            app_name = port_app_map.get(dst_port)
            if app_name:
                if app_name not in stats:
                    stats[app_name] = {"bytes": 0, "connections": 0}
                stats[app_name]["bytes"] += entry.get("bytes", 0)
                stats[app_name]["connections"] += 1

        return stats

    # ─── 通道统计 ──────────────────────────────────────────────

    def get_channel_stats(self) -> Dict[str, Dict[str, int]]:
        """获取各 WAN/通道的流量统计

        Returns:
            {channel_name: {rx_bytes, tx_bytes}}
        """
        stats: Dict[str, Dict[str, int]] = {}

        # 从接口统计获取
        iface_stats = self._get_iface_stats()
        for iface, data in iface_stats.items():
            # 映射到通道名
            channel = self._iface_to_channel(iface)
            if channel:
                stats[channel] = {
                    "rx_bytes": data.get("rx_bytes", 0),
                    "tx_bytes": data.get("tx_bytes", 0),
                }

        return stats

    # ─── 全量统计 ──────────────────────────────────────────────

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有维度的统计"""
        return {
            "devices": self.get_device_stats(),
            "apps": self.get_app_stats(),
            "channels": self.get_channel_stats(),
        }

    # ─── 内部方法 ──────────────────────────────────────────────

    def _get_conntrack_stats(self) -> List[Dict[str, Any]]:
        """从 conntrack 获取连接跟踪统计"""
        entries: List[Dict[str, Any]] = []
        try:
            r = subprocess.run(
                ["conntrack", "-L", "-o", "json"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                if isinstance(data, list):
                    for entry in data:
                        conntrack_entry = {
                            "src": entry.get("src", ""),
                            "dst": entry.get("dst", ""),
                            "dst_port": entry.get("dst_port", 0),
                            "bytes": entry.get("bytes", 0),
                            "packets": entry.get("packets", 0),
                            "proto": entry.get("proto", ""),
                        }
                        # 尝试从 /proc/net/arp 获取 MAC
                        conntrack_entry["src_mac"] = self._ip_to_mac(
                            conntrack_entry["src"]
                        )
                        entries.append(conntrack_entry)
        except FileNotFoundError:
            # conntrack 工具未安装
            logger.debug("conntrack tool not available")
        except json.JSONDecodeError:
            logger.debug("Failed to parse conntrack JSON output")
        except Exception as e:
            logger.debug("conntrack stats failed: %s", e)

        # fallback: 尝试用 nf_conntrack 接口读取
        if not entries:
            entries = self._get_conntrack_from_proc()

        return entries

    def _get_conntrack_from_proc(self) -> List[Dict[str, Any]]:
        """从 /proc/net/nf_conntrack 读取连接跟踪"""
        entries: List[Dict[str, Any]] = []
        conntrack_path = Path("/proc/net/nf_conntrack")
        if not conntrack_path.exists():
            return entries

        try:
            content = conntrack_path.read_text(encoding="utf-8", errors="replace")
            for line in content.strip().split("\n"):
                if not line:
                    continue
                # 解析 nf_conntrack 行格式
                match = re.search(
                    r"src=(\S+)\s+dst=(\S+)\s+"
                    r"dport=(\d+)",
                    line,
                )
                if match:
                    src = match.group(1)
                    dst = match.group(2)
                    dport = int(match.group(3))
                    entries.append({
                        "src": src,
                        "dst": dst,
                        "dst_port": dport,
                        "bytes": 0,
                        "packets": 0,
                        "proto": "",
                        "src_mac": self._ip_to_mac(src),
                    })
        except Exception as e:
            logger.debug("Failed to read /proc/net/nf_conntrack: %s", e)

        return entries

    def _get_nftables_counter_stats(self) -> Dict[str, Dict[str, int]]:
        """从 nftables counter 获取统计"""
        stats: Dict[str, Dict[str, int]] = {}
        try:
            r = subprocess.run(
                ["nft", "-j", "list", "counters"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                # nftables JSON 格式: { "nftables": [{"counter": {...}}] }
                nftables = data.get("nftables", []) if isinstance(data, dict) else data
                for item in nftables:
                    if isinstance(item, dict) and "counter" in item:
                        counter = item["counter"]
                        name = counter.get("name", counter.get("handle", "unknown"))
                        bytes_val = counter.get("bytes", 0)
                        packets = counter.get("packets", 0)
                        stats[name] = {
                            "bytes": int(bytes_val),
                            "connections": int(packets),
                        }
        except FileNotFoundError:
            logger.debug("nftables tool not available")
        except (json.JSONDecodeError, Exception) as e:
            logger.debug("nftables counter stats failed: %s", e)

        return stats

    def _get_iface_stats(self) -> Dict[str, Dict[str, int]]:
        """从 /sys/class/net/ 读取接口流量统计"""
        stats: Dict[str, Dict[str, int]] = {}
        sys_net = Path("/sys/class/net")
        if not sys_net.exists():
            return stats

        try:
            for iface_dir in sys_net.iterdir():
                iface = iface_dir.name
                if iface == "lo":
                    continue

                rx_bytes = self._read_sys_stat(iface_dir / "statistics" / "rx_bytes")
                tx_bytes = self._read_sys_stat(iface_dir / "statistics" / "tx_bytes")
                rx_packets = self._read_sys_stat(iface_dir / "statistics" / "rx_packets")
                tx_packets = self._read_sys_stat(iface_dir / "statistics" / "tx_packets")

                stats[iface] = {
                    "rx_bytes": rx_bytes,
                    "tx_bytes": tx_bytes,
                    "rx_packets": rx_packets,
                    "tx_packets": tx_packets,
                }
        except OSError as e:
            logger.debug("Failed to read /sys/class/net: %s", e)

        return stats

    @staticmethod
    def _read_sys_stat(path: Path) -> int:
        """读取 sysfs 统计文件"""
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return 0

    def _ip_to_mac(self, ip: str) -> str:
        """从 ARP 表查询 IP 对应的 MAC"""
        if not ip:
            return ""
        try:
            r = subprocess.run(
                ["ip", "neigh", "show", ip],
                capture_output=True, text=True, timeout=5,
            )
            match = re.search(r"lladdr\s+(\S+)", r.stdout)
            if match:
                return match.group(1).upper()
        except Exception:
            pass
        return ""

    def _mac_to_iface(self, mac: str) -> str:
        """根据 MAC 查找对应接口"""
        mac = mac.upper().replace("-", ":")
        try:
            r = subprocess.run(
                ["ip", "-j", "neigh", "show"],
                capture_output=True, text=True, timeout=5,
            )
            data = json.loads(r.stdout)
            for entry in data:
                if "lladdr" in entry and entry["lladdr"].upper() == mac:
                    return entry.get("dev", "")
        except Exception:
            pass
        # 尝试从 /proc/net/arp 查找
        try:
            content = Path("/proc/net/arp").read_text(encoding="utf-8")
            for line in content.strip().split("\n")[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 4 and parts[3].upper() == mac:
                    return parts[1]  # device
        except Exception:
            pass
        return ""

    @staticmethod
    def _iface_to_channel(iface: str) -> str:
        """将接口名映射到通道名"""
        mapping = {
            "eth0": "wan1",
            "eth1": "wan2",
            "wg0": "vpn",
            "wg1": "vpn2",
        }
        return mapping.get(iface, iface)
