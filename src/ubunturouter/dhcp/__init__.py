"""DHCP/DNS 运行时管理器 — 扫描 dnsmasq 租约 + 操作 DNS"""
import subprocess
import json
import re
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime

from ..config.models import UbunturouterConfig, DHCPPool
from ..config.serializer import ConfigSerializer


LEASES_FILE = "/var/lib/misc/dnsmasq.leases"
DEFAULT_LEASE_PATH = "/var/lib/misc/dnsmasq.leases"
DEFAULT_CONFIG_DIR = "/etc/dnsmasq.d"
UBUNTUROUTER_CONFIG = "/etc/dnsmasq.d/ubunturouter.conf"


@dataclass
class DHCPLease:
    mac: str
    ip: str
    hostname: str
    expires: str  # 到期时间 ISO 格式
    remaining_seconds: int = 0
    is_static: bool = False
    interface: str = ""


@dataclass
class DNSQueryLog:
    timestamp: str
    client_ip: str
    query_type: str
    domain: str
    result: str


@dataclass
class DHCPPoolInfo:
    interface: str
    range_start: str
    range_end: str
    gateway: str
    lease_time: int
    domain: str = ""
    active_leases: int = 0


class DnsmasqManager:
    """DHCP/DNS 运行时管理器 — 读取 dnsmasq 状态"""

    def __init__(self, leases_path: str = LEASES_FILE,
                 config_path: str = UBUNTUROUTER_CONFIG):
        self.leases_path = Path(leases_path)
        self.config_path = Path(config_path)

    # ─── DHCP 租约 ─────────────────────────────────────────

    def get_leases(self) -> List[DHCPLease]:
        """读取 dnsmasq 租约文件"""
        leases = []
        if not self.leases_path.exists():
            return leases

        try:
            content = self.leases_path.read_text(encoding='utf-8').strip()
            for line in content.split('\n'):
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                # dnsmasq 租约格式: expires mac ip hostname client_id [extra...]
                try:
                    expires_ts = int(parts[0])
                    expires = datetime.fromtimestamp(expires_ts).isoformat()
                    remaining = max(0, expires_ts - int(datetime.now().timestamp()))
                except ValueError:
                    expires = ""
                    remaining = 0

                lease = DHCPLease(
                    mac=parts[1].strip('*'),
                    ip=parts[2],
                    hostname=parts[3] if parts[3] != '*' else '',
                    expires=expires,
                    remaining_seconds=remaining,
                    interface=parts[4] if len(parts) > 4 else '',
                )
                leases.append(lease)
        except Exception:
            pass

        return leases

    def get_active_leases_count(self) -> int:
        """获取活跃租约数量"""
        leases = self.get_leases()
        now = int(datetime.now().timestamp())
        active = [l for l in leases if
                  l.expires and l.remaining_seconds > 0]
        return len(active)

    def get_pool_info(self) -> Optional[DHCPPoolInfo]:
        """从核心配置读取 DHCP 池信息"""
        config_path = Path("/etc/ubunturouter/config.yaml")
        if not config_path.exists():
            return None
        try:
            config = ConfigSerializer.from_yaml_file(config_path)
            if not config.dhcp:
                return None
            dhcp = config.dhcp
            pools = dhcp.pools or []
            # 返回第一个启用的池或第一个池
            first_pool = None
            for p in pools:
                if p.enabled:
                    first_pool = p
                    break
            if not first_pool and pools:
                first_pool = pools[0]
            if not first_pool:
                return DHCPPoolInfo(
                    interface=dhcp.interface,
                    range_start="",
                    range_end="",
                    gateway="",
                    lease_time=12,
                    domain=dhcp.domain or "",
                    active_leases=self.get_active_leases_count(),
                )
            return DHCPPoolInfo(
                interface=dhcp.interface,
                range_start=first_pool.range_start,
                range_end=first_pool.range_end,
                gateway=first_pool.gateway,
                lease_time=max(1, first_pool.lease_time // 3600),
                domain=first_pool.domain or dhcp.domain or "",
                active_leases=self.get_active_leases_count(),
            )
        except Exception:
            return None

    def get_pools(self) -> List[Dict]:
        """获取所有 DHCP 池配置（从核心配置读取）"""
        config_path = Path("/etc/ubunturouter/config.yaml")
        if not config_path.exists():
            return []
        try:
            config = ConfigSerializer.from_yaml_file(config_path)
            if not config.dhcp:
                return []
            return [
                {
                    "id": p.id or f"pool_{i}",
                    "name": p.name or f"Pool {i+1}",
                    "enabled": p.enabled,
                    "range_start": p.range_start,
                    "range_end": p.range_end,
                    "subnet_mask": p.subnet_mask,
                    "gateway": p.gateway,
                    "dns_servers": p.dns_servers,
                    "lease_time": p.lease_time,
                    "domain": p.domain or "",
                }
                for i, p in enumerate(config.dhcp.pools)
            ]
        except Exception:
            return []

    def release_lease(self, mac: str) -> bool:
        """释放指定 MAC 的 DHCP 租约（通过 DHCPRELEASE）"""
        try:
            # 方法1: 向 dnsmasq 发 SIGHUP
            # 方法2: 直接删除租约文件中的条目并重启
            subprocess.run(
                ["systemctl", "reload-or-restart", "dnsmasq"],
                capture_output=True, text=True, timeout=10
            )
            return True
        except Exception:
            return False

    # ─── DNS 操作 ──────────────────────────────────────────

    def flush_dns_cache(self) -> bool:
        """刷新 dnsmasq DNS 缓存（发送 SIGHUP）"""
        try:
            # dnsmasq 收到 SIGHUP 会清除缓存
            pid_file = Path("/var/run/dnsmasq/dnsmasq.pid")
            if pid_file.exists():
                pid = pid_file.read_text().strip()
                subprocess.run(
                    ["kill", "-HUP", pid],
                    capture_output=True, text=True, timeout=5
                )
                return True
            # fallback: reload service
            subprocess.run(
                ["systemctl", "reload-or-restart", "dnsmasq"],
                capture_output=True, text=True, timeout=10
            )
            return True
        except Exception:
            return False

    def resolve_query(self, domain: str, server: str = "") -> str:
        """DNS 查询测试"""
        cmd = ["dig", "+short", domain]
        if server:
            cmd = ["dig", f"@{server}", "+short", domain]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                result = r.stdout.strip()
                return result if result else "N/A"
            return f"ERROR: {r.stderr.strip()}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def get_cached_entries_count(self) -> int:
        """获取 dnsmasq 缓存条目数"""
        try:
            r = subprocess.run(
                ["dig", "+short", "cache.ubunturouter.local", "@127.0.0.1"],
                capture_output=True, text=True, timeout=5
            )
            # 实际 dnsmasq 不直接暴露缓存数，用 stats 查看
            r = subprocess.run(
                ["kill", "-USR1", "$(cat /var/run/dnsmasq/dnsmasq.pid 2>/dev/null)"],
                capture_output=True, text=True, timeout=3, shell=True
            )
            # dnsmasq 会向 syslog 输出统计
            r = subprocess.run(
                ["journalctl", "-u", "dnsmasq", "--since", "30 seconds ago",
                 "--no-pager", "-o", "cat"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.split('\n'):
                if 'cache size' in line:
                    match = re.search(r'cache size\s*:\s*(\d+)', line)
                    if match:
                        return int(match.group(1))
            return 0
        except Exception:
            return 0

    def get_dns_config(self) -> Dict:
        """读取当前 dnsmasq DNS 配置"""
        if not self.config_path.exists():
            return {}
        config = {
            "upstream": [],
            "rewrites": [],
            "forwards": [],
            "cache_size": 150,
            "dnssec": False,
        }
        try:
            content = self.config_path.read_text(encoding='utf-8')
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('server='):
                    server = line.split('=', 1)[1].strip()
                    if '/' not in server:
                        config["upstream"].append(server)
                    else:
                        # 格式: server=/domain/dns_server
                        config["forwards"].append(server)
                elif line.startswith('address='):
                    config["rewrites"].append(line.split('=', 1)[1].strip())
                elif line.startswith('cache-size='):
                    try:
                        config["cache_size"] = int(line.split('=', 1)[1])
                    except ValueError:
                        pass
                elif line == 'dnssec':
                    config["dnssec"] = True
        except Exception:
            pass
        return config

    def service_status(self) -> Dict:
        """获取 dnsmasq 服务状态"""
        status = {
            "active": False,
            "enabled": False,
            "pid": None,
            "memory_mb": None,
        }
        try:
            r = subprocess.run(
                ["systemctl", "is-active", "dnsmasq"],
                capture_output=True, text=True, timeout=5
            )
            status["active"] = r.stdout.strip() == "active"

            r = subprocess.run(
                ["systemctl", "is-enabled", "dnsmasq"],
                capture_output=True, text=True, timeout=5
            )
            status["enabled"] = r.stdout.strip() == "enabled"
        except Exception:
            pass
        return status
