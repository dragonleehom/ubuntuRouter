"""DNS Manager — advanced DNS management for dnsmasq

Handles DNS forwarding rules, rewrite/hijack rules, cache management,
query log viewing, and /etc/hosts management.
"""

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────
DNSMASQ_D_DIR = Path("/etc/dnsmasq.d")
USER_CONF = DNSMASQ_D_DIR / "ubunturouter-dns.conf"
HOSTS_FILE = Path("/etc/hosts")
DNS_LOG = Path("/var/log/dnsmasq.log")
DNS_CONFIG_DIR = Path("/etc/ubunturouter/dns")


class DNSManager:
    """Manage DNS forwarding, rewriting, cache, and logging."""

    def __init__(self):
        self._conf_dir = DNS_CONFIG_DIR
        self._conf_dir.mkdir(parents=True, exist_ok=True)

    # ─── Service Status ───────────────────────────────────────────

    @staticmethod
    def _run(cmd: list, timeout: int = 10) -> dict:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception:
            return ""

    @staticmethod
    def _write_file(path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def get_status(self) -> dict:
        """Get dnsmasq service status."""
        r = self._run(["systemctl", "is-active", "dnsmasq"])
        active = r["stdout"] == "active"
        port = 53
        try:
            r2 = self._run(["ss", "-tlnp", "sport = :53"])
            if "dnsmasq" not in r2["stdout"]:
                port = None
        except Exception:
            port = None

        # Cache stats from dnsmasq stats file or SIGUSR1
        cache_stats = self._get_cache_stats()

        return {
            "running": active,
            "port": port,
            "cache": cache_stats,
        }

    def _get_cache_stats(self) -> dict:
        """Get dnsmasq cache statistics by sending SIGUSR1."""
        result = {"size": 0, "insertions": 0, "evictions": 0, "hits": 0, "misses": 0}
        try:
            subprocess.run(["killall", "-SIGUSR1", "dnsmasq"], capture_output=True, timeout=5)
            time.sleep(0.2)
            log = self._read_file(DNS_LOG)
            for line in log.split("\n"):
                m = re.search(r"cache\s+(\w+)", line)
                if m:
                    key = m.group(1).lower()
                    if "size" in line:
                        nums = re.findall(r"\d+", line)
                        if nums:
                            result["size"] = int(nums[0])
                    if "insertions" in line:
                        nums = re.findall(r"\d+", line)
                        if nums:
                            result["insertions"] = int(nums[0])
                    if "evictions" in line:
                        nums = re.findall(r"\d+", line)
                        if nums:
                            result["evictions"] = int(nums[0])
                    if "hits" in line:
                        nums = re.findall(r"\d+", line)
                        if nums:
                            result["hits"] = int(nums[0])
                    if "misses" in line:
                        nums = re.findall(r"\d+", line)
                        if nums:
                            result["misses"] = int(nums[0])
        except Exception:
            pass
        return result

    def flush_cache(self) -> dict:
        """Flush dnsmasq cache by restarting the service."""
        try:
            r = self._run(["systemctl", "restart", "dnsmasq"])
            if r["success"]:
                return {"success": True, "message": "DNS cache flushed (service restarted)"}
            return {"success": False, "message": r["stderr"]}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ─── Forwarding Rules ─────────────────────────────────────────

    def _read_config_lines(self) -> list:
        """Read DNS config file, return non-empty stripped lines."""
        content = self._read_file(USER_CONF)
        return [line.strip() for line in content.split("\n") if line.strip() and not line.strip().startswith("#")]

    def _write_config_lines(self, lines: list):
        """Write lines to DNS config file with header."""
        header = "# UbuntuRouter DNS Configuration - auto-generated\n"
        self._write_file(USER_CONF, header + "\n".join(lines) + "\n")

    def get_forwards(self) -> list:
        """Get DNS forwarding rules (server= lines)."""
        rules = []
        for line in self._read_config_lines():
            m = re.match(r"^server=/([^/]+)/(.+)$", line)
            if m:
                rules.append({
                    "id": f"fwd-{len(rules)}",
                    "domain": m.group(1),
                    "target": m.group(2),
                    "type": "forward",
                })
        return rules

    def add_forward(self, domain: str, target: str) -> dict:
        """Add a DNS forwarding rule."""
        if not domain or not target:
            return {"success": False, "message": "domain and target are required"}
        lines = self._read_config_lines()
        new_line = f"server=/{domain}/{target}"
        lines.append(new_line)
        self._write_config_lines(lines)
        self._reload_dnsmasq()
        return {"success": True, "message": f"Forward rule added: {domain} → {target}"}

    def remove_forward(self, domain: str, target: str) -> dict:
        """Remove a DNS forwarding rule."""
        lines = self._read_config_lines()
        pattern = f"server=/{domain}/{target}"
        new_lines = [l for l in lines if l != pattern]
        if len(new_lines) == len(lines):
            return {"success": False, "message": "Forward rule not found"}
        self._write_config_lines(new_lines)
        self._reload_dnsmasq()
        return {"success": True, "message": f"Forward rule removed: {domain} → {target}"}

    # ─── Rewrite Rules ────────────────────────────────────────────

    def get_rewrites(self) -> list:
        """Get DNS rewrite rules (address= lines)."""
        rules = []
        for line in self._read_config_lines():
            m = re.match(r"^address=/([^/]+)/([^\s]+)$", line)
            if m:
                rules.append({
                    "id": f"rw-{len(rules)}",
                    "domain": m.group(1),
                    "ip": m.group(2),
                    "type": "rewrite",
                })
        return rules

    def add_rewrite(self, domain: str, ip: str) -> dict:
        """Add a DNS rewrite rule (domain → IP override)."""
        if not domain or not ip:
            return {"success": False, "message": "domain and ip are required"}
        lines = self._read_config_lines()
        new_line = f"address=/{domain}/{ip}"
        lines.append(new_line)
        self._write_config_lines(lines)
        self._reload_dnsmasq()
        return {"success": True, "message": f"Rewrite rule added: {domain} → {ip}"}

    def remove_rewrite(self, domain: str, ip: str) -> dict:
        """Remove a DNS rewrite rule."""
        lines = self._read_config_lines()
        pattern = f"address=/{domain}/{ip}"
        new_lines = [l for l in lines if l != pattern]
        if len(new_lines) == len(lines):
            return {"success": False, "message": "Rewrite rule not found"}
        self._write_config_lines(new_lines)
        self._reload_dnsmasq()
        return {"success": True, "message": f"Rewrite rule removed: {domain} → {ip}"}

    # ─── /etc/hosts ───────────────────────────────────────────────

    def get_hosts(self) -> list:
        """Get entries from /etc/hosts (skip comments and localhost)."""
        entries = []
        content = self._read_file(HOSTS_FILE)
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                ip = parts[0]
                hostnames = parts[1:]
                if ip == "127.0.0.1" and "localhost" in hostnames:
                    continue
                if ip == "::1" and "localhost" in hostnames:
                    continue
                entries.append({"ip": ip, "hostnames": hostnames, "raw": line})
        return entries

    def add_host(self, ip: str, hostname: str) -> dict:
        """Add a /etc/hosts entry."""
        if not ip or not hostname:
            return {"success": False, "message": "ip and hostname are required"}
        try:
            with open(HOSTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n{ip}\t{hostname}")
            return {"success": True, "message": f"Host entry added: {ip} → {hostname}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def remove_host(self, ip: str, hostname: str) -> dict:
        """Remove a /etc/hosts entry."""
        try:
            content = self._read_file(HOSTS_FILE)
            lines = content.split("\n")
            pattern = f"{ip}\t{hostname}"
            new_lines = [l for l in lines if pattern not in l]
            if len(new_lines) == len(lines):
                return {"success": False, "message": "Host entry not found"}
            self._write_file(HOSTS_FILE, "\n".join(new_lines))
            return {"success": True, "message": f"Host entry removed: {ip} → {hostname}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ─── Query Logs ───────────────────────────────────────────────

    def get_logs(self, lines: int = 50) -> dict:
        """Get recent DNS query logs from dnsmasq log."""
        if not DNS_LOG.exists():
            return {"logs": [], "total": 0, "message": "DNS log file not found. Enable logging in dnsmasq config."}
        try:
            r = subprocess.run(
                ["tail", "-n", str(lines), str(DNS_LOG)],
                capture_output=True, text=True, timeout=5,
            )
            log_lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
            return {"logs": log_lines, "total": len(log_lines)}
        except Exception as e:
            return {"logs": [], "total": 0, "message": str(e)}

    # ─── Helper ───────────────────────────────────────────────────

    @staticmethod
    def _reload_dnsmasq():
        """Reload dnsmasq configuration without full restart."""
        try:
            subprocess.run(["killall", "-HUP", "dnsmasq"], capture_output=True, timeout=5)
        except Exception:
            pass
