"""UbuntuRouter VPN 管理器 — PPTP 服务管理"""

import subprocess
import re
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


PPTP_CONFIG_DIR = Path("/etc/pptpd")
PPTP_CONFIG_PATH = Path("/etc/pptpd.conf")
PPTP_OPTIONS_PATH = Path("/etc/ppp/pptpd-options")
CHAP_SECRETS_PATH = Path("/etc/ppp/chap-secrets")
PPTP_SERVICE = "pptpd"


@dataclass
class PptpUser:
    """PPTP 用户"""
    username: str
    password: str
    ip: str = "*"            # 分配的 IP，* 表示任意
    enabled: bool = True


@dataclass
class PptpConfig:
    """PPTP 配置"""
    server_ip: str = "10.0.0.1"        # VPN 服务器 IP
    local_ip: str = "10.0.0.1"         # 服务器本地接口 IP
    remote_ip_range: str = "10.0.0.100-200"  # 客户端 IP 范围
    dns1: str = "8.8.8.8"
    dns2: str = "8.8.4.4"
    mppe: bool = True                   # MPPE 加密
    require_mppe: bool = True           # 强制加密
    max_connections: int = 100
    idle_timeout: int = 600             # 秒，0=不超时
    running: bool = False


@dataclass
class PptpConnection:
    """PPTP 连接状态"""
    pid: int = 0
    username: str = ""
    remote_ip: str = ""
    assigned_ip: str = ""
    connected_since: Optional[datetime] = None
    rx_bytes: int = 0
    tx_bytes: int = 0


class PptpManager:
    """PPTP VPN 管理器 — 基于 pptpd"""

    def __init__(self):
        self.config = self._load_config()

    # ─── 配置管理 ─────────────────────────────────────────

    def get_config(self) -> PptpConfig:
        """获取当前配置"""
        self.config.running = self._is_running()
        return self.config

    def update_config(self, cfg: PptpConfig) -> Tuple[bool, str]:
        """更新 PPTP 配置"""
        try:
            self._write_pptpd_conf(cfg)
            self._write_options_conf(cfg)
            self.config = cfg
            return True, "PPTP 配置已更新"
        except Exception as e:
            return False, f"配置更新失败: {str(e)}"

    def _load_config(self) -> PptpConfig:
        """从配置文件加载当前配置"""
        cfg = PptpConfig()
        cfg.running = self._is_running()

        # 解析 pptpd.conf
        if PPTP_CONFIG_PATH.exists():
            content = PPTP_CONFIG_PATH.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "=" in line:
                    key, val = [x.strip() for x in line.split("=", 1)]
                    if key == "localip":
                        cfg.local_ip = val
                        cfg.server_ip = val
                    elif key == "remoteip":
                        cfg.remote_ip_range = val
                    elif key == "option":
                        pass  # options 文件路径

        # 解析 pptpd-options
        if PPTP_OPTIONS_PATH.exists():
            content = PPTP_OPTIONS_PATH.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if line.startswith("ms-dns"):
                    parts = line.split()
                    if len(parts) >= 2:
                        if not cfg.dns1 or cfg.dns1 == "8.8.8.8":
                            cfg.dns1 = parts[1]
                        elif not cfg.dns2 or cfg.dns2 == "8.8.4.4":
                            cfg.dns2 = parts[1]
                elif line == "require-mppe-128" or line == "require-mppe":
                    cfg.require_mppe = True
                elif line == "mppe":
                    cfg.mppe = True

        return cfg

    def _write_pptpd_conf(self, cfg: PptpConfig) -> None:
        """写入 pptpd.conf"""
        content = f"""# PPTP 配置文件 — 由 UbuntuRouter 管理
option {PPTP_OPTIONS_PATH}
logwtmp
localip {cfg.local_ip}
remoteip {cfg.remote_ip_range}
connections {cfg.max_connections}
idle_timeout {cfg.idle_timeout}
"""
        PPTP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        PPTP_CONFIG_PATH.write_text(content)

    def _write_options_conf(self, cfg: PptpConfig) -> None:
        """写入 pptpd-options"""
        lines = [
            "# PPTP 选项 — 由 UbuntuRouter 管理",
            "name pptpd",
            "refuse-pap",
            "refuse-chap",
            "refuse-mschap",
            "require-mschap-v2",
            "proxyarp",
            "lock",
            "nobsdcomp",
            "nodeflate",
            f"ms-dns {cfg.dns1}",
        ]
        if cfg.dns2:
            lines.append(f"ms-dns {cfg.dns2}")

        if cfg.mppe:
            lines.append("mppe")
        if cfg.require_mppe:
            lines.append("require-mppe-128")

        lines.append("")  # trailing newline
        PPTP_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PPTP_OPTIONS_PATH.write_text("\n".join(lines))

    # ─── 服务控制 ─────────────────────────────────────────

    def start(self) -> Tuple[bool, str]:
        """启动 PPTP"""
        try:
            r = subprocess.run(
                ["systemctl", "start", PPTP_SERVICE],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "PPTP 服务已启动"
            return False, f"启动失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"启动异常: {str(e)}"

    def stop(self) -> Tuple[bool, str]:
        """停止 PPTP"""
        if not self._is_running():
            return True, "PPTP 服务未运行"
        try:
            r = subprocess.run(
                ["systemctl", "stop", PPTP_SERVICE],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "PPTP 服务已停止"
            return False, f"停止失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"停止异常: {str(e)}"

    def restart(self) -> Tuple[bool, str]:
        """重启 PPTP"""
        try:
            r = subprocess.run(
                ["systemctl", "restart", PPTP_SERVICE],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "PPTP 服务已重启"
            return False, f"重启失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"重启异常: {str(e)}"

    def _is_running(self) -> bool:
        """检查 PPTP 服务是否运行"""
        try:
            r = subprocess.run(
                ["systemctl", "is-active", PPTP_SERVICE],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip() == "active"
        except Exception:
            return False

    # ─── 用户管理 ─────────────────────────────────────────

    def list_users(self) -> List[PptpUser]:
        """列出所有 PPTP 用户"""
        users = []
        if not CHAP_SECRETS_PATH.exists():
            return users

        content = CHAP_SECRETS_PATH.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 格式: username server password ip
            parts = line.split()
            if len(parts) >= 3:
                user = PptpUser(
                    username=parts[0],
                    password=parts[2],
                    ip=parts[3] if len(parts) > 3 else "*",
                    enabled=not line.startswith("!"),
                )
                users.append(user)
        return users

    def add_user(self, user: PptpUser) -> Tuple[bool, str]:
        """添加 PPTP 用户"""
        users = self.list_users()

        # 检查是否已存在
        for existing in users:
            if existing.username == user.username:
                return False, f"用户 {user.username} 已存在"

        # 追加到文件
        server = "pptpd"
        entry = f"{user.username}\t{server}\t{user.password}\t{user.ip}\n"
        try:
            with open(CHAP_SECRETS_PATH, "a") as f:
                f.write(entry)
            CHAP_SECRETS_PATH.chmod(0o600)
            return True, f"用户 {user.username} 已添加"
        except Exception as e:
            return False, f"添加用户失败: {str(e)}"

    def update_user(self, username: str, user: PptpUser) -> Tuple[bool, str]:
        """更新 PPTP 用户"""
        users = self.list_users()
        found = False
        new_lines = []
        server = "pptpd"

        for existing in users:
            if existing.username == username:
                new_lines.append(f"{user.username}\t{server}\t{user.password}\t{user.ip}")
                found = True
            else:
                new_lines.append(f"{existing.username}\t{server}\t{existing.password}\t{existing.ip}")

        if not found:
            return False, f"用户 {username} 不存在"

        try:
            CHAP_SECRETS_PATH.write_text("\n".join(new_lines) + "\n")
            CHAP_SECRETS_PATH.chmod(0o600)
            return True, f"用户 {username} 已更新"
        except Exception as e:
            return False, f"更新用户失败: {str(e)}"

    def delete_user(self, username: str) -> Tuple[bool, str]:
        """删除 PPTP 用户"""
        users = self.list_users()
        before = len(users)
        server = "pptpd"

        users = [u for u in users if u.username != username]
        if len(users) == before:
            return False, f"用户 {username} 不存在"

        try:
            lines = [f"{u.username}\t{server}\t{u.password}\t{u.ip}" for u in users]
            CHAP_SECRETS_PATH.write_text("\n".join(lines) + "\n")
            CHAP_SECRETS_PATH.chmod(0o600)
            return True, f"用户 {username} 已删除"
        except Exception as e:
            return False, f"删除用户失败: {str(e)}"

    # ─── 连接状态 ─────────────────────────────────────────

    def get_connections(self) -> List[PptpConnection]:
        """获取当前活动连接"""
        connections = []
        try:
            # 通过 ppp 接口统计和 ps 获取 PPTP 连接
            r = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=5
            )
            pptp_pids = []
            for line in r.stdout.split("\n"):
                if "pppd" in line and "pptpd" in line.lower():
                    parts = line.split()
                    if len(parts) > 1 and parts[1].isdigit():
                        pptp_pids.append(int(parts[1]))

            # 读取 /var/run/ppp-* 状态文件
            run_dir = Path("/var/run")
            for ppp_file in sorted(run_dir.glob("ppp-*")):
                try:
                    conn = self._parse_ppp_status(ppp_file)
                    if conn:
                        connections.append(conn)
                except Exception:
                    pass

            # 也尝试通过 ifconfig 获取 ppp 接口
            r2 = subprocess.run(
                ["ip", "link", "show"],
                capture_output=True, text=True, timeout=5
            )
            for match in re.finditer(r"ppp(\d+)", r2.stdout):
                iface = f"ppp{match.group(1)}"
                conn = self._get_ppp_connection_info(iface)
                if conn:
                    # 合并已有的连接信息
                    for existing in connections:
                        if existing.assigned_ip == conn.assigned_ip:
                            conn.username = existing.username
                            break
                    connections.append(conn)

        except Exception:
            pass

        return connections

    def _parse_ppp_status(self, ppp_file: Path) -> Optional[PptpConnection]:
        """解析 ppp 状态文件"""
        try:
            content = ppp_file.read_text()
        except Exception:
            return None

        conn = PptpConnection()
        for line in content.split("\n"):
            line = line.strip()
            if "pid" in line.lower():
                try:
                    conn.pid = int(line.split()[-1])
                except (ValueError, IndexError):
                    pass
            elif "user" in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    conn.username = parts[-1]
        return conn

    def _get_ppp_connection_info(self, iface: str) -> Optional[PptpConnection]:
        """通过 ip 命令获取 ppp 连接信息"""
        try:
            r = subprocess.run(
                ["ip", "addr", "show", iface],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return None

            conn = PptpConnection()
            for line in r.stdout.split("\n"):
                line = line.strip()
                # 提取远端 IP
                m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)\s+peer\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m:
                    conn.assigned_ip = m.group(1)
                    conn.remote_ip = m.group(2)
            return conn
        except Exception:
            return None
