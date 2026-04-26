"""PPPoE Manager — PPPoE dial-up connection management for UbuntuRouter

Manages PPPoE configuration, connection lifecycle, and status monitoring.
Uses pon/poff for connection control and reads /proc/net/dev for traffic stats.
"""

import logging
import os
import re
import subprocess
import time
import yaml
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────
CONFIG_DIR = Path("/etc/ubunturouter")
CONFIG_PATH = CONFIG_DIR / "pppoe.yaml"
PPP_PEERS_DIR = Path("/etc/ppp/peers")
INTERFACE_NAME = "ppp0"
PROVIDER_NAME = "ubunturouter"


class PPPoEManager:
    """Manage PPPoE connection lifecycle and configuration."""

    def __init__(self):
        self._config_path = CONFIG_PATH
        self._peers_path = PPP_PEERS_DIR / PROVIDER_NAME
        self._peers_backup_path = PPP_PEERS_DIR / f"{PROVIDER_NAME}.bak"

    # ─── Configuration I/O ────────────────────────────────────────

    def _load_config(self) -> dict:
        """Load PPPoE configuration from YAML."""
        if not self._config_path.exists():
            return {
                "username": "",
                "password": "",
                "mtu": 1492,
                "auto_reconnect": True,
                "enabled": False,
            }
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict):
                return {}
            return cfg
        except Exception as e:
            logger.error("Failed to load PPPoE config: %s", e)
            return {}

    def _save_config(self, cfg: dict):
        """Save PPPoE configuration to YAML."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._config_path.with_suffix(".yaml.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, default_flow_style=False)
            tmp.replace(self._config_path)
        except Exception as e:
            logger.error("Failed to save PPPoE config: %s", e)
            raise

    # ─── PPP Peers Config ─────────────────────────────────────────

    def _write_peers_file(self, username: str, password: str, mtu: int):
        """Write /etc/ppp/peers/ubunturouter configuration file."""
        content = f"""# UbuntuRouter PPPoE configuration - auto-generated
plugin rp-pppoe.so
nic eth1  # Default WAN interface - adjust as needed
name "{username}"
password "{password}"
mtu {mtu}
mru {mtu}
persist
maxfail 0
holdoff 10
lcp-echo-interval 10
lcp-echo-failure 5
usepeerdns
defaultroute
noauth
noipdefault
"""
        self._peers_path.parent.mkdir(parents=True, exist_ok=True)
        # Backup existing if present
        if self._peers_path.exists():
            try:
                import shutil
                shutil.copy2(self._peers_path, self._peers_backup_path)
            except Exception:
                pass
        try:
            with open(self._peers_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(self._peers_path, 0o600)
        except Exception as e:
            logger.error("Failed to write PPP peers file: %s", e)
            raise

    def _get_peers_file_content(self) -> Optional[str]:
        """Read current PPP peers file content."""
        if not self._peers_path.exists():
            return None
        try:
            return self._peers_path.read_text(encoding="utf-8")
        except Exception:
            return None

    # ─── Connection Control ───────────────────────────────────────

    def _run(self, cmd: list, timeout: int = 15) -> dict:
        """Run a command and return result dict."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "success": r.returncode == 0,
                "stdout": r.stdout.strip(),
                "stderr": r.stderr.strip(),
                "returncode": r.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out", "returncode": -1}
        except FileNotFoundError:
            return {"success": False, "stdout": "", "stderr": "Command not found - is ppp installed?", "returncode": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def connect(self) -> dict:
        """Dial PPPoE connection."""
        cfg = self._load_config()
        username = cfg.get("username", "")
        password = cfg.get("password", "")
        mtu = cfg.get("mtu", 1492)

        if not username or not password:
            return {"success": False, "message": "PPPoE username and password not configured"}

        # Write peers file
        try:
            self._write_peers_file(username, password, mtu)
        except Exception as e:
            return {"success": False, "message": f"Failed to write config: {e}"}

        # Call pon
        result = self._run(["pon", PROVIDER_NAME])

        # Update config
        cfg["enabled"] = True
        self._save_config(cfg)

        if result["success"]:
            return {"success": True, "message": "PPPoE dial-up initiated"}
        else:
            error_msg = result["stderr"] or "pon failed"
            # Check if already connected
            if self._is_connected():
                return {"success": True, "message": "PPPoE already connected"}
            return {"success": False, "message": error_msg}

    def disconnect(self) -> dict:
        """Hang up PPPoE connection."""
        result = self._run(["poff", PROVIDER_NAME])
        cfg = self._load_config()
        if result["success"] or "not running" in result.get("stderr", "").lower():
            cfg["enabled"] = False
            self._save_config(cfg)
            return {"success": True, "message": "PPPoE disconnected"}
        return {"success": False, "message": result.get("stderr", "poff failed")}

    def reconnect(self) -> dict:
        """Reconnect PPPoE (disconnect + connect)."""
        self.disconnect()
        time.sleep(1)
        return self.connect()

    # ─── Status ───────────────────────────────────────────────────

    def _is_connected(self) -> bool:
        """Check if PPPoE interface exists and is up."""
        try:
            r = subprocess.run(
                ["ip", "addr", "show", INTERFACE_NAME],
                capture_output=True, text=True, timeout=5,
            )
            return "state UP" in r.stdout or "state UNKNOWN" in r.stdout
        except Exception:
            return False

    def _get_interface_stats(self) -> dict:
        """Get traffic stats for ppp0 from /proc/net/dev."""
        try:
            data = Path("/proc/net/dev").read_text()
            for line in data.strip().split("\n")[2:]:
                parts = line.split()
                if len(parts) >= 10 and parts[0].rstrip(":") == INTERFACE_NAME:
                    return {
                        "rx_bytes": int(parts[1]),
                        "tx_bytes": int(parts[9]),
                        "rx_packets": int(parts[2]),
                        "tx_packets": int(parts[10]),
                        "rx_errors": int(parts[3]),
                        "tx_errors": int(parts[11]),
                    }
        except Exception:
            pass
        return {"rx_bytes": 0, "tx_bytes": 0, "rx_packets": 0, "tx_packets": 0, "rx_errors": 0, "tx_errors": 0}

    def _get_ip_address(self) -> Optional[str]:
        """Get the IPv4 address assigned to ppp0."""
        try:
            r = subprocess.run(
                ["ip", "-4", "addr", "show", INTERFACE_NAME],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.split("\n"):
                m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return None

    def _get_uptime(self) -> Optional[float]:
        """Get PPPoE connection uptime in seconds from /proc/net/pppoe or iface stats."""
        try:
            r = subprocess.run(
                ["ip", "link", "show", INTERFACE_NAME],
                capture_output=True, text=True, timeout=5,
            )
            # Not accurate but available - we'll rely on plog for real uptime
            return None
        except Exception:
            return None

    def get_status(self) -> dict:
        """Get full PPPoE connection status."""
        connected = self._is_connected()
        stats = self._get_interface_stats() if connected else {}
        ip = self._get_ip_address() if connected else None
        cfg = self._load_config()

        return {
            "connected": connected,
            "interface": INTERFACE_NAME,
            "ip_address": ip,
            "traffic": stats,
            "config": {
                "username": cfg.get("username", ""),
                "password": "******" if cfg.get("password") else "",
                "mtu": cfg.get("mtu", 1492),
                "auto_reconnect": cfg.get("auto_reconnect", True),
                "enabled": cfg.get("enabled", False),
            },
            "peers_file": self._get_peers_file_content(),
        }

    def get_config(self) -> dict:
        """Get PPPoE configuration."""
        cfg = self._load_config()
        return {
            "username": cfg.get("username", ""),
            "password": cfg.get("password", ""),
            "mtu": cfg.get("mtu", 1492),
            "auto_reconnect": cfg.get("auto_reconnect", True),
            "enabled": cfg.get("enabled", False),
        }

    def update_config(self, new_cfg: dict) -> dict:
        """Update PPPoE configuration. Only sets provided fields."""
        cfg = self._load_config()
        for key in ["username", "password", "mtu", "auto_reconnect", "enabled"]:
            if key in new_cfg:
                cfg[key] = new_cfg[key]
        self._save_config(cfg)
        return {"success": True, "message": "PPPoE configuration updated", "config": self.get_config()}
