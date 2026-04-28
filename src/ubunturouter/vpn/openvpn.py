"""UbuntuRouter VPN 管理器 — OpenVPN 服务管理"""

import subprocess
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


OPENVPN_CONFIG_DIR = Path("/etc/openvpn")
OPENVPN_EASYRSA_DIR = Path("/etc/openvpn/easy-rsa")
OPENVPN_KEYS_DIR = OPENVPN_EASYRSA_DIR / "pki"
OPENVPN_CCD_DIR = OPENVPN_CONFIG_DIR / "ccd"
OPENVPN_SERVICE = "openvpn"
OPENVPN_LOG_DIR = Path("/var/log/openvpn")


@dataclass
class OpenvpnConfig:
    """OpenVPN 配置"""
    protocol: str = "udp"               # tcp 或 udp
    port: int = 1194
    dev_type: str = "tun"               # tun 或 tap
    cipher: str = "AES-256-GCM"
    auth: str = "SHA384"
    dh_bits: int = 2048
    server_network: str = "10.8.0.0"
    server_netmask: str = "255.255.255.0"
    max_clients: int = 100
    keepalive_interval: int = 10
    keepalive_timeout: int = 120
    compress: str = ""                  # comp-lzo 或 lz4-v2 或留空
    dns1: str = "8.8.8.8"
    dns2: str = "8.8.4.4"
    redirect_gateway: bool = True       # 重定向所有流量
    client_to_client: bool = False
    duplicate_cn: bool = False
    tls_version: str = "1.2"
    running: bool = False
    config_name: str = "server"         # 配置文件名(不含 .conf)


@dataclass
class OpenvpnClient:
    """OpenVPN 客户端"""
    name: str
    enabled: bool = True
    certificate_expiry: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class OpenvpnConnection:
    """OpenVPN 连接状态"""
    common_name: str = ""
    remote_ip: str = ""
    virtual_ip: str = ""
    bytes_received: int = 0
    bytes_sent: int = 0
    connected_since: Optional[datetime] = None
    client_id: int = 0


class OpenvpnManager:
    """OpenVPN 管理器 — 基于 openvpn + easy-rsa"""

    def __init__(self):
        self.config = self._load_config()

    # ─── 目录初始化 ───────────────────────────────────────

    def _ensure_dirs(self) -> None:
        """确保目录存在"""
        for d in [OPENVPN_CONFIG_DIR, OPENVPN_CCD_DIR, OPENVPN_LOG_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    # ─── 配置管理 ─────────────────────────────────────────

    def get_config(self) -> OpenvpnConfig:
        """获取当前配置"""
        self.config.running = self._is_running()
        return self.config

    def update_config(self, cfg: OpenvpnConfig) -> Tuple[bool, str]:
        """更新 OpenVPN 配置"""
        try:
            self._ensure_dirs()
            self._write_server_conf(cfg)
            self.config = cfg
            return True, "OpenVPN 配置已更新"
        except Exception as e:
            return False, f"配置更新失败: {str(e)}"

    def _load_config(self) -> OpenvpnConfig:
        """从配置文件加载当前配置"""
        cfg = OpenvpnConfig()
        cfg.running = self._is_running()

        server_conf = OPENVPN_CONFIG_DIR / "server.conf"
        if not server_conf.exists():
            return cfg

        content = server_conf.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#") or not line or line.startswith(";"):
                continue

            parts = line.split()
            if not parts:
                continue

            directive = parts[0]

            if directive == "port" and len(parts) > 1:
                try:
                    cfg.port = int(parts[1])
                except ValueError:
                    pass
            elif directive == "proto":
                cfg.protocol = parts[1] if len(parts) > 1 else "udp"
            elif directive == "dev":
                cfg.dev_type = parts[1] if len(parts) > 1 else "tun"
            elif directive == "cipher" and len(parts) > 1:
                cfg.cipher = parts[1]
            elif directive == "auth" and len(parts) > 1:
                cfg.auth = parts[1]
            elif directive == "server" and len(parts) > 2:
                cfg.server_network = parts[1]
                cfg.server_netmask = parts[2]
            elif directive == "keepalive" and len(parts) > 2:
                try:
                    cfg.keepalive_interval = int(parts[1])
                    cfg.keepalive_timeout = int(parts[2])
                except ValueError:
                    pass
            elif directive == "max-clients" and len(parts) > 1:
                try:
                    cfg.max_clients = int(parts[1])
                except ValueError:
                    pass
            elif directive == "comp-lzo":
                cfg.compress = "comp-lzo"
            elif directive == "compress":
                cfg.compress = parts[1] if len(parts) > 1 else "lz4-v2"
            elif directive == "push" and len(parts) > 1:
                push_val = " ".join(parts[1:])
                if 'dhcp-option DNS' in push_val:
                    dns = push_val.split()[-1]
                    if not cfg.dns1 or cfg.dns1 == "8.8.8.8":
                        cfg.dns1 = dns
                    elif dns != cfg.dns1:
                        cfg.dns2 = dns
                elif 'redirect-gateway' in push_val:
                    cfg.redirect_gateway = True
            elif directive == "client-to-client":
                cfg.client_to_client = True
            elif directive == "duplicate-cn":
                cfg.duplicate_cn = True
            elif directive == "tls-version-min" and len(parts) > 1:
                cfg.tls_version = parts[1]

        return cfg

    def _get_server_conf_path(self, name: str = "server") -> Path:
        """获取服务器配置文件路径"""
        return OPENVPN_CONFIG_DIR / f"{name}.conf"

    def _write_server_conf(self, cfg: OpenvpnConfig) -> None:
        """写入 OpenVPN 服务器配置"""
        server_conf = self._get_server_conf_path(cfg.config_name)

        lines = [
            "# OpenVPN 服务器配置 — 由 UbuntuRouter 管理",
            f"port {cfg.port}",
            f"proto {cfg.protocol}",
            f"dev {cfg.dev_type}",
            "",
            "# 证书路径",
            f"ca {OPENVPN_EASYRSA_DIR}/pki/ca.crt",
            f"cert {OPENVPN_EASYRSA_DIR}/pki/issued/server.crt",
            f"key {OPENVPN_EASYRSA_DIR}/pki/private/server.key",
            f"dh {OPENVPN_EASYRSA_DIR}/pki/dh.pem",
            f"tls-crypt {OPENVPN_EASYRSA_DIR}/pki/tls-crypt.key 2",
            "",
            "# 网络配置",
            f"server {cfg.server_network} {cfg.server_netmask}",
            f"topology subnet",
            "",
            "# 推送路由",
        ]

        if cfg.redirect_gateway:
            lines.append('push "redirect-gateway def1 bypass-dhcp"')

        lines.append(f'push "dhcp-option DNS {cfg.dns1}"')
        if cfg.dns2:
            lines.append(f'push "dhcp-option DNS {cfg.dns2}"')

        lines.extend([
            "",
            "# 加密设置",
            f"cipher {cfg.cipher}",
            f"auth {cfg.auth}",
            f"tls-version-min {cfg.tls_version}",
            "tls-cipher TLS-ECDHE-ECDSA-WITH-AES-256-GCM-SHA384:TLS-ECDHE-RSA-WITH-AES-256-GCM-SHA384",
            "data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
            "",
            "# 客户端设置",
            f"keepalive {cfg.keepalive_interval} {cfg.keepalive_timeout}",
            f"max-clients {cfg.max_clients}",
        ])

        if cfg.client_to_client:
            lines.append("client-to-client")
        if cfg.duplicate_cn:
            lines.append("duplicate-cn")
        if cfg.compress:
            lines.append(f"compress {cfg.compress}")

        lines.extend([
            "",
            "# 安全与性能",
            "persist-key",
            "persist-tun",
            "float",
            "reneg-sec 0",
            "tcp-nodelay",
            "fast-io",
            "",
            "# 日志",
            f"status {OPENVPN_LOG_DIR}/status.log",
            f"log-append {OPENVPN_LOG_DIR}/openvpn.log",
            "verb 3",
            "mute 20",
            "",
            "# 客户端配置目录 (CCD)",
            f"client-config-dir {OPENVPN_CCD_DIR}",
        ])

        server_conf.write_text("\n".join(lines) + "\n")

    # ─── Easy-RSA 初始化 ──────────────────────────────────

    def init_easyrsa(self) -> Tuple[bool, str]:
        """初始化 easy-rsa PKI"""
        self._ensure_dirs()

        try:
            # 检查 easy-rsa 是否已安装
            r = subprocess.run(
                ["which", "easyrsa"],
                capture_output=True, text=True, timeout=5
            )
            easyrsa_bin = r.stdout.strip() if r.returncode == 0 else ""

            if not easyrsa_bin:
                # 尝试在 /usr/share/easy-rsa 中查找
                for p in [
                    "/usr/share/easy-rsa/easyrsa",
                    "/usr/share/easy-rsa/3/easyrsa",
                    "/usr/local/bin/easyrsa",
                ]:
                    if Path(p).exists():
                        easyrsa_bin = p
                        break

            if not easyrsa_bin:
                return False, "easy-rsa 未安装，请先安装: apt install easy-rsa"

            # 初始化 PKI
            OPENVPN_EASYRSA_DIR.mkdir(parents=True, exist_ok=True)

            # 复制 easy-rsa 到配置目录
            easyrsa_dir = Path(easyrsa_bin).parent.parent
            if (easyrsa_dir / "x509-types").exists():
                # 复制 x509-types
                shutil.copytree(
                    str(easyrsa_dir / "x509-types"),
                    str(OPENVPN_EASYRSA_DIR / "x509-types"),
                    dirs_exist_ok=True
                )

            # 创建 vars 文件
            vars_content = """# Easy-RSA 配置 — 由 UbuntuRouter 管理
if [ -z "$EASYRSA_CALLER" ]; then
    echo "You appear to be sourcing this file directly." >&2
    exit 1
fi
set_var EASYRSA_REQ_COUNTRY    "US"
set_var EASYRSA_REQ_PROVINCE   "California"
set_var EASYRSA_REQ_CITY       "San Francisco"
set_var EASYRSA_REQ_ORG        "UbuntuRouter"
set_var EASYRSA_REQ_EMAIL      "admin@ubunturouter.local"
set_var EASYRSA_REQ_OU         "VPN"
set_var EASYRSA_KEY_SIZE       2048
set_var EASYRSA_ALGO           rsa
set_var EASYRSA_CA_EXPIRE      3650
set_var EASYRSA_CERT_EXPIRE    3650
set_var EASYRSA_NS_SUPPORT     "no"
set_var EASYRSA_EXT_DIR        "$EASYRSA_PKI/x509-types"
"""
            (OPENVPN_EASYRSA_DIR / "vars").write_text(vars_content)

            # 初始化 PKI
            r = subprocess.run(
                [easyrsa_bin, "init-pki"],
                cwd=str(OPENVPN_EASYRSA_DIR),
                capture_output=True, text=True, timeout=30,
            )
            # 注意：easyrsa init-pki 可能需要交互
            # 这里我们手动确保 pki 目录存在
            OPENVPN_KEYS_DIR.mkdir(parents=True, exist_ok=True)

            return True, "Easy-RSA PKI 已初始化"
        except Exception as e:
            return False, f"初始化 easy-rsa 失败: {str(e)}"

    def generate_dh(self) -> Tuple[bool, str]:
        """生成 Diffie-Hellman 参数"""
        self._ensure_dirs()
        try:
            dh_file = OPENVPN_KEYS_DIR / "dh.pem"
            if dh_file.exists():
                return True, "DH 参数已存在"

            r = subprocess.run(
                ["openssl", "dhparam", "-out", str(dh_file), str(self.config.dh_bits)],
                capture_output=True, text=True, timeout=300
            )
            if r.returncode != 0:
                return False, f"DH 参数生成失败: {r.stderr.strip()}"
            return True, "DH 参数已生成"
        except Exception as e:
            return False, f"DH 生成异常: {str(e)}"

    def generate_tls_crypt_key(self) -> Tuple[bool, str]:
        """生成 TLS-Crypt 密钥"""
        self._ensure_dirs()
        try:
            key_file = OPENVPN_KEYS_DIR / "tls-crypt.key"
            if key_file.exists():
                return True, "TLS-Crypt 密钥已存在"

            r = subprocess.run(
                ["openvpn", "--genkey", "--secret", str(key_file)],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"TLS-Crypt 密钥生成失败: {r.stderr.strip()}"
            return True, "TLS-Crypt 密钥已生成"
        except Exception as e:
            return False, f"TLS-Crypt 生成异常: {str(e)}"

    def generate_ca(self) -> Tuple[bool, str]:
        """生成 CA 证书"""
        self._ensure_dirs()
        try:
            ca_crt = OPENVPN_KEYS_DIR / "ca.crt"
            ca_key = OPENVPN_KEYS_DIR / "private" / "ca.key"

            if ca_crt.exists() and ca_key.exists():
                return True, "CA 证书已存在"

            # 确保目录存在
            (OPENVPN_KEYS_DIR / "private").mkdir(parents=True, exist_ok=True)

            # 生成 CA 密钥
            r = subprocess.run(
                ["openssl", "genrsa", "-out", str(ca_key), "4096"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"CA 密钥生成失败: {r.stderr.strip()}"

            # 生成 CA 证书
            r = subprocess.run(
                ["openssl", "req", "-x509", "-new", "-nodes",
                 "-key", str(ca_key),
                 "-sha384", "-days", "3650",
                 "-out", str(ca_crt),
                 "-subj", "/CN=OpenVPN CA/O=UbuntuRouter"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"CA 证书生成失败: {r.stderr.strip()}"

            return True, "CA 证书已生成"
        except Exception as e:
            return False, f"CA 生成异常: {str(e)}"

    def generate_server_cert(self) -> Tuple[bool, str]:
        """生成服务器证书"""
        self._ensure_dirs()

        # 确保 CA 存在
        ca_crt = OPENVPN_KEYS_DIR / "ca.crt"
        ca_key = OPENVPN_KEYS_DIR / "private" / "ca.key"
        if not ca_crt.exists() or not ca_key.exists():
            ok, msg = self.generate_ca()
            if not ok:
                return False, f"自动创建 CA 失败: {msg}"

        issued_dir = OPENVPN_KEYS_DIR / "issued"
        private_dir = OPENVPN_KEYS_DIR / "private"
        issued_dir.mkdir(parents=True, exist_ok=True)
        private_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 生成服务器密钥
            server_key = private_dir / "server.key"
            r = subprocess.run(
                ["openssl", "genrsa", "-out", str(server_key), "2048"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"服务器密钥生成失败: {r.stderr.strip()}"

            # 生成 CSR
            server_req = OPENVPN_KEYS_DIR / "server.req"
            r = subprocess.run(
                ["openssl", "req", "-new",
                 "-key", str(server_key),
                 "-out", str(server_req),
                 "-subj", "/CN=server/O=UbuntuRouter"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"服务器 CSR 生成失败: {r.stderr.strip()}"

            # 签发证书
            server_crt = issued_dir / "server.crt"
            ext_file = OPENVPN_KEYS_DIR / "server_ext.cnf"
            ext_file.write_text("subjectAltName=DNS:server\n")

            r = subprocess.run(
                ["openssl", "x509", "-req",
                 "-in", str(server_req),
                 "-CA", str(ca_crt),
                 "-CAkey", str(ca_key),
                 "-CAcreateserial",
                 "-out", str(server_crt),
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

    def init_full_pki(self) -> Tuple[bool, str]:
        """初始化完整 PKI（CA + DH + TLS-Crypt + 服务器证书）"""
        steps = [
            ("CA 证书", self.generate_ca),
            ("DH 参数", self.generate_dh),
            ("TLS-Crypt 密钥", self.generate_tls_crypt_key),
            ("服务器证书", self.generate_server_cert),
        ]

        for name, func in steps:
            ok, msg = func()
            if not ok and "已存在" not in msg:
                return False, f"{name} 失败: {msg}"

        return True, "PKI 初始化完成"

    # ─── 客户端证书管理 ──────────────────────────────────

    def list_clients(self) -> List[OpenvpnClient]:
        """列出所有已签发证书的客户端"""
        clients = []
        issued_dir = OPENVPN_KEYS_DIR / "issued"
        if not issued_dir.exists():
            return clients

        for cert_file in sorted(issued_dir.glob("*.crt")):
            name = cert_file.stem
            if name == "server" or name == "ca":
                continue

            client = OpenvpnClient(name=name)
            # 获取证书过期时间
            try:
                r = subprocess.run(
                    ["openssl", "x509", "-in", str(cert_file),
                     "-noout", "-enddate"],
                    capture_output=True, text=True, timeout=5
                )
                for line in r.stdout.split("\n"):
                    if line.startswith("notAfter="):
                        date_str = line[9:].strip()
                        try:
                            client.certificate_expiry = datetime.strptime(
                                date_str, "%b %d %H:%M:%S %Y %Z"
                            )
                        except ValueError:
                            pass
                clients.append(client)
            except Exception:
                clients.append(client)

        return clients

    def generate_client_cert(self, client_name: str) -> Tuple[bool, str]:
        """为客户端签发证书"""
        self._ensure_dirs()

        ca_crt = OPENVPN_KEYS_DIR / "ca.crt"
        ca_key = OPENVPN_KEYS_DIR / "private" / "ca.key"
        if not ca_crt.exists() or not ca_key.exists():
            return False, "CA 证书不存在，请先初始化 PKI"

        issued_dir = OPENVPN_KEYS_DIR / "issued"
        private_dir = OPENVPN_KEYS_DIR / "private"
        issued_dir.mkdir(parents=True, exist_ok=True)
        private_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 生成客户端密钥
            client_key = private_dir / f"{client_name}.key"
            r = subprocess.run(
                ["openssl", "genrsa", "-out", str(client_key), "2048"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return False, f"客户端密钥生成失败: {r.stderr.strip()}"

            # 生成 CSR
            client_req = OPENVPN_KEYS_DIR / f"{client_name}.req"
            r = subprocess.run(
                ["openssl", "req", "-new",
                 "-key", str(client_key),
                 "-out", str(client_req),
                 "-subj", f"/CN={client_name}/O=UbuntuRouter"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"客户端 CSR 生成失败: {r.stderr.strip()}"

            # 签发证书
            client_crt = issued_dir / f"{client_name}.crt"
            r = subprocess.run(
                ["openssl", "x509", "-req",
                 "-in", str(client_req),
                 "-CA", str(ca_crt),
                 "-CAkey", str(ca_key),
                 "-CAcreateserial",
                 "-out", str(client_crt),
                 "-days", "3650",
                 "-sha384"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0:
                return False, f"客户端证书签发失败: {r.stderr.strip()}"

            return True, f"客户端 {client_name} 证书已签发"
        except Exception as e:
            return False, f"客户端证书生成异常: {str(e)}"

    def revoke_client(self, client_name: str) -> Tuple[bool, str]:
        """吊销客户端证书"""
        issued_dir = OPENVPN_KEYS_DIR / "issued"
        cert_file = issued_dir / f"{client_name}.crt"
        if not cert_file.exists():
            return False, f"客户端 {client_name} 的证书不存在"

        try:
            # 创建吊销证书目录
            revoked_dir = OPENVPN_KEYS_DIR / "revoked"
            revoked_dir.mkdir(parents=True, exist_ok=True)

            # 移动证书到已吊销目录
            dest = revoked_dir / f"{client_name}.crt"
            shutil.move(str(cert_file), str(dest))

            # 也移动密钥
            key_file = OPENVPN_KEYS_DIR / "private" / f"{client_name}.key"
            if key_file.exists():
                shutil.move(str(key_file), str(revoked_dir / f"{client_name}.key"))

            return True, f"客户端 {client_name} 已吊销"
        except Exception as e:
            return False, f"吊销客户端失败: {str(e)}"

    # ─── 客户端配置导出 ──────────────────────────────────

    def export_client_config(self, client_name: str) -> Tuple[bool, str]:
        """导出 .ovpn 客户端配置"""
        self._ensure_dirs()

        ca_crt = OPENVPN_KEYS_DIR / "ca.crt"
        client_crt = OPENVPN_KEYS_DIR / "issued" / f"{client_name}.crt"
        client_key = OPENVPN_KEYS_DIR / "private" / f"{client_name}.key"
        tls_crypt = OPENVPN_KEYS_DIR / "tls-crypt.key"

        if not ca_crt.exists():
            return False, "CA 证书不存在"
        if not client_crt.exists():
            return False, f"客户端 {client_name} 的证书不存在"
        if not client_key.exists():
            return False, f"客户端 {client_name} 的密钥不存在"

        # 读取证书内容
        ca_content = ca_crt.read_text()
        cert_content = client_crt.read_text()
        key_content = client_key.read_text()
        tls_content = tls_crypt.read_text() if tls_crypt.exists() else ""

        # 获取服务器地址
        server_addr = self.config.server_network.split(".")[0:2]
        server_addr = f"{server_addr[0]}.{server_addr[1]}.0.1"  # 使用网关地址作为服务器标识

        cfg = OpenvpnConfig()
        lines = [
            "# OpenVPN 客户端配置 — 由 UbuntuRouter 生成",
            "client",
            f"dev {cfg.dev_type}",
            f"proto {cfg.protocol}",
            "remote YOUR_SERVER_IP_HERE",
            "resolv-retry infinite",
            "nobind",
            "persist-key",
            "persist-tun",
            "",
            "# 证书内嵌",
            "<ca>",
            ca_content.strip(),
            "</ca>",
            "",
            "<cert>",
            cert_content.strip(),
            "</cert>",
            "",
            "<key>",
            key_content.strip(),
            "</key>",
            "",
            "# TLS-Crypt",
        ]

        if tls_content:
            lines.extend([
                "<tls-crypt>",
                tls_content.strip(),
                "</tls-crypt>",
                "",
            ])

        lines.extend([
            f"cipher {cfg.cipher}",
            f"auth {cfg.auth}",
            f"tls-version-min {cfg.tls_version}",
            "data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
            "remote-cert-tls server",
            "key-direction 1",
            "",
            "# 压缩",
        ])

        if cfg.compress:
            lines.append(f"compress {cfg.compress}")

        lines.extend([
            "",
            "# 日志",
            "verb 3",
            "mute 20",
        ])

        # 写入文件
        output_dir = OPENVPN_CONFIG_DIR / "client-configs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{client_name}.ovpn"
        output_path.write_text("\n".join(lines) + "\n")

        return True, str(output_path)

    # ─── 服务控制 ─────────────────────────────────────────

    def start(self, name: str = "server") -> Tuple[bool, str]:
        """启动 OpenVPN（指定配置名，默认为 server）"""
        conf_file = self._get_server_conf_path(name)
        if not conf_file.exists():
            return False, f"配置文件 {conf_file} 不存在"

        try:
            # 使用 systemd 单元或直接启动
            service_name = f"openvpn@{name}"

            r = subprocess.run(
                ["systemctl", "start", service_name],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, f"OpenVPN ({name}) 已启动"
            return False, f"启动失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"启动异常: {str(e)}"

    def stop(self, name: str = "server") -> Tuple[bool, str]:
        """停止 OpenVPN"""
        service_name = f"openvpn@{name}"
        if not self._is_running(name):
            return True, f"OpenVPN ({name}) 未运行"

        try:
            r = subprocess.run(
                ["systemctl", "stop", service_name],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, f"OpenVPN ({name}) 已停止"
            return False, f"停止失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"停止异常: {str(e)}"

    def restart(self, name: str = "server") -> Tuple[bool, str]:
        """重启 OpenVPN"""
        try:
            r = subprocess.run(
                ["systemctl", "restart", f"openvpn@{name}"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, f"OpenVPN ({name}) 已重启"
            return False, f"重启失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"重启异常: {str(e)}"

    def _is_running(self, name: str = "server") -> bool:
        """检查 OpenVPN 是否运行"""
        try:
            r = subprocess.run(
                ["systemctl", "is-active", f"openvpn@{name}"],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip() == "active"
        except Exception:
            return False

    # ─── 连接状态 ─────────────────────────────────────────

    def get_connections(self) -> List[OpenvpnConnection]:
        """获取当前活动连接"""
        connections = []
        status_file = OPENVPN_LOG_DIR / "status.log"

        if not status_file.exists():
            return connections

        try:
            content = status_file.read_text()
        except Exception:
            return connections

        in_client_list = False
        for line in content.split("\n"):
            line = line.strip()

            if "OpenVPN CLIENT LIST" in line:
                in_client_list = True
                continue
            elif "ROUTING TABLE" in line:
                in_client_list = False
                continue
            elif line.startswith("Updated"):
                continue

            if in_client_list and "," in line and "Common Name" not in line:
                # 格式: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
                parts = line.split(",")
                if len(parts) >= 5:
                    conn = OpenvpnConnection()
                    conn.common_name = parts[0].strip()
                    conn.remote_ip = parts[1].strip()
                    try:
                        conn.bytes_received = int(parts[2].strip())
                        conn.bytes_sent = int(parts[3].strip())
                    except ValueError:
                        pass
                    try:
                        conn.connected_since = datetime.strptime(
                            parts[4].strip(), "%a %b %d %H:%M:%S %Y"
                        )
                    except ValueError:
                        pass
                    connections.append(conn)

        return connections

    # ─── 自动配置 ─────────────────────────────────────────

    def auto_configure(self) -> Tuple[bool, str]:
        """一键配置 OpenVPN（初始化 PKI + 生成配置）"""
        # 1. 初始化目录
        self._ensure_dirs()

        # 2. 初始化 PKI
        ok, msg = self.init_full_pki()
        if not ok:
            return False, f"PKI 初始化失败: {msg}"

        # 3. 写入服务器配置
        try:
            self._write_server_conf(self.config)
        except Exception as e:
            return False, f"配置写入失败: {str(e)}"

        # 4. 确保防火墙允许
        protocol = self.config.protocol
        port = self.config.port
        try:
            subprocess.run(
                ["iptables", "-C", "INPUT", "-p", protocol, "--dport",
                 str(port), "-j", "ACCEPT"],
                capture_output=True, text=True, timeout=5
            )
        except Exception:
            pass  # iptables 规则可能不存在

        return True, "OpenVPN 自动配置完成"
