"""UbuntuRouter VPN 管理器 — IPSec/IKEv2 服务管理 (strongSwan)"""

import subprocess
import json
import re
import tempfile
import os
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


IPSEC_CONFIG_DIR = Path("/etc/ipsec.d")
IPSEC_CONF_PATH = Path("/etc/ipsec.conf")
IPSEC_SECRETS_PATH = Path("/etc/ipsec.secrets")
IPSEC_STRONGSWAN_CONF = Path("/etc/strongswan.conf")
IPSEC_SERVICE = "strongswan-starter"
IPSEC_CERTS_DIR = IPSEC_CONFIG_DIR / "certs"
IPSEC_PRIVATE_DIR = IPSEC_CONFIG_DIR / "private"
IPSEC_CACERTS_DIR = IPSEC_CONFIG_DIR / "cacerts"


@dataclass
class IpsecConfig:
    """IPSec/IKEv2 配置"""
    server_ip: str = ""                 # 服务器公网 IP
    server_domain: str = ""             # 服务器域名（用于证书）
    psk: str = ""                       # 预共享密钥
    ike_port: int = 500
    nat_t_port: int = 4500
    dns1: str = "8.8.8.8"
    dns2: str = "8.8.4.4"
    left_subnet: str = "0.0.0.0/0"     # 服务端子网
    right_subnet: str = "0.0.0.0/0"    # 客户端子网
    enforce_server_cert: bool = True    # 强制服务端证书验证
    lifetime: int = 28800               # SA 生命周期(秒)
    running: bool = False


@dataclass
class IpsecUser:
    """IKEv2 用户 (用户名/密码认证)"""
    username: str
    password: str
    enabled: bool = True


@dataclass
class IpsecConnection:
    """IPSec 连接状态"""
    name: str = ""
    username: str = ""
    remote_ip: str = ""
    virtual_ip: str = ""
    established_since: Optional[datetime] = None
    bytes_in: int = 0
    bytes_out: int = 0


class IpsecManager:
    """IPSec/IKEv2 VPN 管理器 — 基于 strongSwan"""

    def __init__(self):
        self.config = self._load_config()

    # ─── 目录初始化 ───────────────────────────────────────

    def _ensure_dirs(self) -> None:
        """确保配置目录存在"""
        for d in [IPSEC_CONFIG_DIR, IPSEC_CERTS_DIR, IPSEC_PRIVATE_DIR,
                  IPSEC_CACERTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    # ─── 配置管理 ─────────────────────────────────────────

    def get_config(self) -> IpsecConfig:
        """获取当前配置"""
        self.config.running = self._is_running()
        return self.config

    def update_config(self, cfg: IpsecConfig) -> Tuple[bool, str]:
        """更新 IPSec 配置"""
        try:
            self._ensure_dirs()
            self._write_ipsec_conf(cfg)

            # 如果提供了 PSK，更新 secrets
            if cfg.psk:
                self._write_secrets(cfg)

            self.config = cfg
            return True, "IPSec 配置已更新"
        except Exception as e:
            return False, f"配置更新失败: {str(e)}"

    def _load_config(self) -> IpsecConfig:
        """从配置文件加载当前配置"""
        cfg = IpsecConfig()
        cfg.running = self._is_running()

        # 解析 ipsec.conf
        if IPSEC_CONF_PATH.exists():
            content = IPSEC_CONF_PATH.read_text()
            current_section = None
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if line.startswith("config setup"):
                    current_section = "config"
                    continue
                elif line.startswith("conn "):
                    current_section = "conn"
                    continue

                if "=" in line:
                    key, val = [x.strip().strip('"') for x in line.split("=", 1)]
                    if current_section == "config" and key == "charon.port":
                        try:
                            cfg.ike_port = int(val.split("=")[-1].strip() if "=" in val else val)
                        except ValueError:
                            pass
                    elif current_section == "conn":
                        if key == "left":
                            cfg.server_ip = val
                        elif key == "leftcert":
                            cfg.enforce_server_cert = True
                        elif key == "lifetime":
                            try:
                                cfg.lifetime = int(re.sub(r"[^\d]", "", val))
                            except ValueError:
                                pass

        # 读取 PSK
        if IPSEC_SECRETS_PATH.exists():
            content = IPSEC_SECRETS_PATH.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                # PSK 格式: %any %any : PSK "secret"
                m = re.search(r'PSK\s+"([^"]+)"', line)
                if m:
                    cfg.psk = m.group(1)

        return cfg

    def _write_ipsec_conf(self, cfg: IpsecConfig) -> None:
        """生成 ipsec.conf"""
        server_id = cfg.server_domain if cfg.server_domain else cfg.server_ip

        content = f"""# IPSec 配置文件 — 由 UbuntuRouter 管理
config setup
    charondebug="ike 2, knl 2, cfg 2, net 2, esp 2, dmn 2, mgr 2"
    uniqueids=no
    strictcrlpolicy=no

conn %default
    ikelifetime=24h
    lifetime={cfg.lifetime}s
    rekeymargin=3m
    keyingtries=1
    keyexchange=ikev2
    authby=secret
    mobike=yes

conn ikev2-psk
    auto=add
    compress=no
    type=tunnel
    keyexchange=ikev2
    fragmentation=yes
    forceencaps=yes
    dpdaction=clear
    dpddelay=300s
    dpdtimeout=150s
    left={cfg.server_ip}
    leftid=@{server_id}
    leftsubnet={cfg.left_subnet}
    leftfirewall=yes
    right=%any
    rightid=%any
    rightsubnet={cfg.right_subnet}
    rightsourceip=%virtual
    rightsendcert=never
"""
        if cfg.enforce_server_cert:
            content += "    leftcert=serverCert.pem\n"

        IPSEC_CONF_PATH.write_text(content)

    def _write_secrets(self, cfg: IpsecConfig) -> None:
        """写入 ipsec.secrets"""
        server_id = cfg.server_domain if cfg.server_domain else cfg.server_ip

        # PSK 条目
        psk_line = f"@server_id %any : PSK \"{cfg.psk}\"\n"

        # EAP 用户名/密码 (IKEv2 用户名密码认证)
        eap_lines = []

        content = f"# IPSec Secrets — 由 UbuntuRouter 管理\n{psk_line}"
        for eap in eap_lines:
            content += eap

        IPSEC_SECRETS_PATH.write_text(content)
        IPSEC_SECRETS_PATH.chmod(0o600)

    def _update_secrets_with_users(self, users: List[IpsecUser],
                                    psk: str, server_id: str) -> None:
        """用用户列表更新 secrets"""
        lines = ["# IPSec Secrets — 由 UbuntuRouter 管理"]

        # PSK
        lines.append(f"@server_id %any : PSK \"{psk}\"")

        # EAP 用户
        for user in users:
            if user.enabled:
                lines.append(f"%any %any : EAP \"{user.password}\"")

        content = "\n".join(lines) + "\n"
        IPSEC_SECRETS_PATH.write_text(content)
        IPSEC_SECRETS_PATH.chmod(0o600)

    # ─── 证书管理 ─────────────────────────────────────────

    def generate_ca_cert(self, subject: str = "CN=IKEv2 VPN CA") -> Tuple[bool, str]:
        """生成 CA 证书"""
        self._ensure_dirs()
        try:
            # 生成 CA 密钥
            r = subprocess.run(
                ["openssl", "genrsa", "-out",
                 str(IPSEC_PRIVATE_DIR / "caKey.pem"), "4096"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"CA 密钥生成失败: {r.stderr.strip()}"

            # 生成 CA 证书
            r = subprocess.run(
                ["openssl", "req", "-x509", "-new", "-nodes",
                 "-key", str(IPSEC_PRIVATE_DIR / "caKey.pem"),
                 "-sha384", "-days", "3650",
                 "-out", str(IPSEC_CACERTS_DIR / "caCert.pem"),
                 "-subj", f"/{subject}"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"CA 证书生成失败: {r.stderr.strip()}"

            return True, "CA 证书已生成"
        except Exception as e:
            return False, f"CA 证书生成异常: {str(e)}"

    def generate_server_cert(self, subject: str = "") -> Tuple[bool, str]:
        """生成服务器证书"""
        self._ensure_dirs()

        # 如果没有 CA，先创建
        if not (IPSEC_CACERTS_DIR / "caCert.pem").exists():
            ok, msg = self.generate_ca_cert()
            if not ok:
                return False, f"自动创建 CA 失败: {msg}"

        server_id = self.config.server_domain if self.config.server_domain else self.config.server_ip
        subj = subject or f"CN={server_id}"

        try:
            # 生成服务器密钥
            r = subprocess.run(
                ["openssl", "genrsa", "-out",
                 str(IPSEC_PRIVATE_DIR / "serverKey.pem"), "4096"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"服务器密钥生成失败: {r.stderr.strip()}"

            # 生成 CSR
            r = subprocess.run(
                ["openssl", "req", "-new",
                 "-key", str(IPSEC_PRIVATE_DIR / "serverKey.pem"),
                 "-out", str(IPSEC_CONFIG_DIR / "serverReq.pem"),
                 "-subj", f"/{subj}"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"CSR 生成失败: {r.stderr.strip()}"

            # 用 CA 签发证书
            extfile_content = f"subjectAltName=DNS:{server_id},IP:{self.config.server_ip}\n"
            ext_file = IPSEC_CONFIG_DIR / "server_ext.cnf"
            ext_file.write_text(extfile_content)

            r = subprocess.run(
                ["openssl", "x509", "-req",
                 "-in", str(IPSEC_CONFIG_DIR / "serverReq.pem"),
                 "-CA", str(IPSEC_CACERTS_DIR / "caCert.pem"),
                 "-CAkey", str(IPSEC_PRIVATE_DIR / "caKey.pem"),
                 "-CAcreateserial",
                 "-out", str(IPSEC_CERTS_DIR / "serverCert.pem"),
                 "-days", "3650",
                 "-sha384",
                 "-extfile", str(ext_file)],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"服务器证书签发失败: {r.stderr.strip()}"

            return True, "服务器证书已生成"
        except Exception as e:
            return False, f"服务器证书生成异常: {str(e)}"

    def generate_client_cert(self, client_name: str) -> Tuple[bool, str]:
        """生成客户端证书"""
        self._ensure_dirs()

        if not (IPSEC_CACERTS_DIR / "caCert.pem").exists():
            return False, "CA 证书不存在，请先生成 CA"

        try:
            # 生成客户端密钥
            client_key = IPSEC_PRIVATE_DIR / f"{client_name}Key.pem"
            r = subprocess.run(
                ["openssl", "genrsa", "-out", str(client_key), "4096"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"客户端密钥生成失败: {r.stderr.strip()}"

            # 生成 CSR
            client_req = IPSEC_CONFIG_DIR / f"{client_name}Req.pem"
            r = subprocess.run(
                ["openssl", "req", "-new",
                 "-key", str(client_key),
                 "-out", str(client_req),
                 "-subj", f"/CN={client_name}"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"客户端 CSR 生成失败: {r.stderr.strip()}"

            # 签发证书
            client_cert = IPSEC_CERTS_DIR / f"{client_name}Cert.pem"
            r = subprocess.run(
                ["openssl", "x509", "-req",
                 "-in", str(client_req),
                 "-CA", str(IPSEC_CACERTS_DIR / "caCert.pem"),
                 "-CAkey", str(IPSEC_PRIVATE_DIR / "caKey.pem"),
                 "-CAcreateserial",
                 "-out", str(client_cert),
                 "-days", "3650",
                 "-sha384"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"客户端证书签发失败: {r.stderr.strip()}"

            return True, f"客户端 {client_name} 证书已生成"
        except Exception as e:
            return False, f"客户端证书生成异常: {str(e)}"

    def list_certs(self) -> List[dict]:
        """列出所有证书"""
        certs = []
        try:
            # 服务器证书
            if (IPSEC_CERTS_DIR / "serverCert.pem").exists():
                info = self._get_cert_info(IPSEC_CERTS_DIR / "serverCert.pem")
                if info:
                    info["type"] = "server"
                    certs.append(info)

            # CA 证书
            if (IPSEC_CACERTS_DIR / "caCert.pem").exists():
                info = self._get_cert_info(IPSEC_CACERTS_DIR / "caCert.pem")
                if info:
                    info["type"] = "ca"
                    certs.append(info)

            # 客户端证书
            for cert_file in sorted(IPSEC_CERTS_DIR.glob("*Cert.pem")):
                if cert_file.name not in ("serverCert.pem",):
                    info = self._get_cert_info(cert_file)
                    if info:
                        info["type"] = "client"
                        info["name"] = cert_file.stem.replace("Cert", "")
                        certs.append(info)
        except Exception:
            pass

        return certs

    def _get_cert_info(self, cert_path: Path) -> Optional[dict]:
        """获取证书信息"""
        try:
            r = subprocess.run(
                ["openssl", "x509", "-in", str(cert_path),
                 "-noout", "-subject", "-issuer", "-dates"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return None

            info = {
                "path": str(cert_path),
                "subject": "",
                "issuer": "",
                "not_before": "",
                "not_after": "",
            }
            for line in r.stdout.split("\n"):
                line = line.strip()
                if line.startswith("subject="):
                    info["subject"] = line[8:]
                elif line.startswith("issuer="):
                    info["issuer"] = line[7:]
                elif line.startswith("notBefore="):
                    info["not_before"] = line[10:]
                elif line.startswith("notAfter="):
                    info["not_after"] = line[9:]

            return info
        except Exception:
            return None

    # ─── 用户管理 (EAP 用户名/密码) ──────────────────────

    def list_users(self) -> List[IpsecUser]:
        """列出所有 IKEv2 用户"""
        users = []
        if not IPSEC_SECRETS_PATH.exists():
            return users

        content = IPSEC_SECRETS_PATH.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            # EAP 条目: %any %any : EAP "password"
            m = re.search(r':\s+EAP\s+"([^"]+)"', line)
            if m:
                # 用户名在左边
                parts = line.split(":")
                if len(parts) >= 1:
                    user_parts = parts[0].strip().split()
                    if len(user_parts) >= 1:
                        username = user_parts[0] if user_parts[0] != "%any" else ""
                    else:
                        username = ""
                else:
                    username = ""
                users.append(IpsecUser(
                    username=username,
                    password=m.group(1),
                ))

        return users

    def add_user(self, user: IpsecUser) -> Tuple[bool, str]:
        """添加 IKEv2 用户"""
        users = self.list_users()

        for existing in users:
            if existing.username == user.username:
                return False, f"用户 {user.username} 已存在"

        # 追加到 secrets 文件
        try:
            with open(IPSEC_SECRETS_PATH, "a") as f:
                f.write(f"%any %any : EAP \"{user.password}\"\n")
            IPSEC_SECRETS_PATH.chmod(0o600)
            return True, f"用户 {user.username} 已添加"
        except Exception as e:
            return False, f"添加用户失败: {str(e)}"

    def update_user(self, username: str, user: IpsecUser) -> Tuple[bool, str]:
        """更新 IKEv2 用户"""
        users = self.list_users()
        found = False
        new_lines = []

        content = IPSEC_SECRETS_PATH.read_text()
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                new_lines.append(line)
                continue

            m = re.search(r':\s+EAP\s+"([^"]+)"', stripped)
            if m:
                parts = stripped.split(":")
                user_parts = parts[0].strip().split() if len(parts) >= 1 else []
                existing_user = user_parts[0] if len(user_parts) >= 1 and user_parts[0] != "%any" else ""

                if existing_user == username:
                    new_lines.append(f"%any %any : EAP \"{user.password}\"")
                    found = True
                else:
                    new_lines.append(stripped)
            else:
                new_lines.append(stripped)

        if not found:
            return False, f"用户 {username} 不存在"

        try:
            IPSEC_SECRETS_PATH.write_text("\n".join(new_lines) + "\n")
            IPSEC_SECRETS_PATH.chmod(0o600)
            return True, f"用户 {username} 已更新"
        except Exception as e:
            return False, f"更新用户失败: {str(e)}"

    def delete_user(self, username: str) -> Tuple[bool, str]:
        """删除 IKEv2 用户"""
        users = self.list_users()
        before = len(users)

        new_lines = []
        content = IPSEC_SECRETS_PATH.read_text()
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                new_lines.append(line)
                continue

            m = re.search(r':\s+EAP\s+"([^"]+)"', stripped)
            if m:
                parts = stripped.split(":")
                user_parts = parts[0].strip().split() if len(parts) >= 1 else []
                existing_user = user_parts[0] if len(user_parts) >= 1 and user_parts[0] != "%any" else ""

                if existing_user != username:
                    new_lines.append(stripped)
            else:
                new_lines.append(stripped)

        if len(new_lines) == before + sum(1 for l in content.split("\n") if l.strip().startswith("#") or not l.strip()):
            return False, f"用户 {username} 不存在"

        try:
            IPSEC_SECRETS_PATH.write_text("\n".join(new_lines) + "\n")
            IPSEC_SECRETS_PATH.chmod(0o600)
            return True, f"用户 {username} 已删除"
        except Exception as e:
            return False, f"删除用户失败: {str(e)}"

    # ─── 服务控制 ─────────────────────────────────────────

    def start(self) -> Tuple[bool, str]:
        """启动 strongSwan"""
        try:
            r = subprocess.run(
                ["systemctl", "start", IPSEC_SERVICE],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "IPSec 服务已启动"
            return False, f"启动失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"启动异常: {str(e)}"

    def stop(self) -> Tuple[bool, str]:
        """停止 strongSwan"""
        if not self._is_running():
            return True, "IPSec 服务未运行"
        try:
            r = subprocess.run(
                ["systemctl", "stop", IPSEC_SERVICE],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "IPSec 服务已停止"
            return False, f"停止失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"停止异常: {str(e)}"

    def restart(self) -> Tuple[bool, str]:
        """重启 strongSwan"""
        try:
            r = subprocess.run(
                ["systemctl", "restart", IPSEC_SERVICE],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "IPSec 服务已重启"
            return False, f"重启失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"重启异常: {str(e)}"

    def reload(self) -> Tuple[bool, str]:
        """重新加载 strongSwan 配置"""
        try:
            r = subprocess.run(
                ["ipsec", "reload"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "IPSec 配置已重新加载"
            return False, f"重载失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"重载异常: {str(e)}"

    def _is_running(self) -> bool:
        """检查 strongSwan 是否运行"""
        try:
            r = subprocess.run(
                ["systemctl", "is-active", IPSEC_SERVICE],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip() == "active"
        except Exception:
            return False

    # ─── 连接状态 ─────────────────────────────────────────

    def get_connections(self) -> List[IpsecConnection]:
        """获取当前活动连接"""
        connections = []

        try:
            # 使用 ipsec statusall 获取连接信息
            r = subprocess.run(
                ["ipsec", "statusall"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                connections = self._parse_statusall(r.stdout)
        except Exception:
            pass

        return connections

    def _parse_statusall(self, output: str) -> List[IpsecConnection]:
        """解析 ipsec statusall 输出"""
        connections = []
        current_conn = None

        for line in output.split("\n"):
            line = line.strip()

            # 匹配连接状态: "Connection: ikev2-psk[1]: state: ESTABLISHED"
            m = re.search(r'Connection:\s+(\S+)\[(\d+)\]:\s+state:\s+(\S+)', line)
            if m and m.group(3).upper() == "ESTABLISHED":
                current_conn = IpsecConnection()
                current_conn.name = m.group(1)
                continue

            # 匹配远端 IP: "remote host: 1.2.3.4[4500]"
            if current_conn:
                m = re.search(r'remote\s+host:\s+([0-9.]+)', line)
                if m:
                    current_conn.remote_ip = m.group(1)

                # 匹配虚拟 IP: "virtual IP: 10.0.0.2"
                m = re.search(r'virtual\s+IP:\s+([0-9.]+)', line)
                if m:
                    current_conn.virtual_ip = m.group(1)

                # 标记连接结束
                if line.startswith("Security Associations") or line.startswith("Runtime"):
                    if current_conn and current_conn.remote_ip:
                        connections.append(current_conn)
                    current_conn = None

        # 最后一段
        if current_conn and current_conn.remote_ip:
            connections.append(current_conn)

        return connections

    def get_status(self) -> dict:
        """获取完整状态摘要"""
        status = {
            "running": self._is_running(),
            "version": "",
            "connections": [],
        }

        try:
            r = subprocess.run(
                ["ipsec", "version"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                status["version"] = r.stdout.strip()
        except Exception:
            pass

        status["connections"] = [
            {
                "name": c.name,
                "remote_ip": c.remote_ip,
                "virtual_ip": c.virtual_ip,
            }
            for c in self.get_connections()
        ]
        status["active_connections"] = len(status["connections"])

        return status

    # ─── 客户端配置导出 ──────────────────────────────────

    def export_mobileconfig(self, client_name: str = "client") -> Tuple[bool, str]:
        """导出 iOS/macOS .mobileconfig 配置"""
        server_id = self.config.server_domain if self.config.server_domain else self.config.server_ip

        if not (IPSEC_CACERTS_DIR / "caCert.pem").exists():
            return False, "CA 证书不存在，请先生成证书"

        # 读取 CA 证书内容 (Base64)
        r = subprocess.run(
            ["openssl", "x509", "-in", str(IPSEC_CACERTS_DIR / "caCert.pem"),
             "-outform", "DER"],
            capture_output=True, text=False, timeout=10
        )
        if r.returncode != 0:
            return False, "无法读取 CA 证书"
        ca_der_b64 = subprocess.run(
            ["openssl", "base64"], input=r.stdout, capture_output=True,
            text=False, timeout=5
        ).stdout.decode().strip()

        mobileconfig = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>IKEv2</key>
            <dict>
                <key>AuthenticationMethod</key>
                <string>SharedSecret</string>
                <key>ChildSecurityAssociationParameters</key>
                <dict>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256-GCM</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-384</string>
                    <key>LifeTimeInMinutes</key>
                    <integer>480</integer>
                </dict>
                <key>DeadPeerDetectionRate</key>
                <string>Medium</string>
                <key>DisableMOBIKE</key>
                <integer>0</integer>
                <key>EnablePFS</key>
                <integer>0</integer>
                <key>IKESecurityAssociationParameters</key>
                <dict>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256-GCM</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-384</string>
                    <key>LifeTimeInMinutes</key>
                    <integer>1440</integer>
                </dict>
                <key>LocalIdentifier</key>
                <string>{client_name}</string>
                <key>RemoteAddress</key>
                <string>{server_id}</string>
                <key>RemoteIdentifier</key>
                <string>{server_id}</string>
                <key>ServerCertificateIssuerCommonName</key>
                <string>IKEv2 VPN CA</string>
                <key>ServerCertificateCommonName</key>
                <string>{server_id}</string>
                <key>SharedSecret</key>
                <string>{self.config.psk}</string>
                <key>UseConfigurationAttributeInternalIPSubnet</key>
                <integer>0</integer>
            </dict>
            <key>IPv4</key>
            <dict>
                <key>OverridePrimary</key>
                <integer>1</integer>
            </dict>
            <key>PayloadDescription</key>
            <string>Configures VPN settings</string>
            <key>PayloadDisplayName</key>
            <string>IKEv2 VPN</string>
            <key>PayloadIdentifier</key>
            <string>com.ubunturouter.vpn.ikev2.{client_name}</string>
            <key>PayloadType</key>
            <string>com.apple.vpn.managed</string>
            <key>PayloadUUID</key>
            <string>{self._uuid()}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>Proxies</key>
            <dict>
                <key>HTTPEnable</key>
                <integer>0</integer>
                <key>HTTPSEnable</key>
                <integer>0</integer>
            </dict>
            <key>UserDefinedName</key>
            <string>IKEv2 VPN</string>
            <key>VPNType</key>
            <string>IKEv2</string>
        </dict>
        <dict>
            <key>PayloadCertificateFileName</key>
            <string>caCert</string>
            <key>PayloadContent</key>
            <data>
{ca_der_b64}
            </data>
            <key>PayloadDescription</key>
            <string>CA 证书</string>
            <key>PayloadDisplayName</key>
            <string>CA Certificate</string>
            <key>PayloadIdentifier</key>
            <string>com.ubunturouter.vpn.ikev2.ca</string>
            <key>PayloadType</key>
            <string>com.apple.security.root</string>
            <key>PayloadUUID</key>
            <string>{self._uuid()}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
        </dict>
    </array>
    <key>PayloadDescription</key>
    <string>IKEv2 VPN configuration for UbuntuRouter</string>
    <key>PayloadDisplayName</key>
    <string>IKEv2 VPN</string>
    <key>PayloadIdentifier</key>
    <string>com.ubunturouter.vpn.ikev2</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{self._uuid()}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
"""
        output_path = IPSEC_CONFIG_DIR / f"{client_name}.mobileconfig"
        output_path.write_text(mobileconfig)
        return True, str(output_path)

    @staticmethod
    def _uuid() -> str:
        """生成随机 UUID"""
        import uuid
        return str(uuid.uuid4())
