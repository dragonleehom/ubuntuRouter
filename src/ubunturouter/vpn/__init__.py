"""UbuntuRouter VPN 管理器 — WireGuard 隧道 CRUD + 运行时状态"""

import subprocess
import json
import re
import ipaddress
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime


WG_CONFIG_DIR = Path("/etc/wireguard")
WG_BINARY = "/usr/bin/wg"
WG_QUICK_BINARY = "/usr/bin/wg-quick"


@dataclass
class WireGuardPeer:
    """WireGuard Peer 信息"""
    public_key: str
    preshared_key: str = ""
    endpoint: str = ""          # host:port
    allowed_ips: List[str] = field(default_factory=list)
    latest_handshake: int = 0
    transfer_rx: int = 0       # 接收字节
    transfer_tx: int = 0       # 发送字节
    persistent_keepalive: int = 0
    enabled: bool = True


@dataclass
class WireGuardTunnel:
    """WireGuard 隧道"""
    name: str                   # 接口名，如 wg0
    private_key: str = ""
    public_key: str = ""
    listen_port: int = 51820
    address: str = ""           # 隧道 IP，如 10.0.0.1/24
    dns: str = ""
    mtu: int = 1420
    table: str = "auto"
    fwmark: str = ""
    peers: List[WireGuardPeer] = field(default_factory=list)
    running: bool = False
    config_path: str = ""       # 配置文件路径


@dataclass
class VpnStats:
    """VPN 统计"""
    tunnels_count: int = 0
    active_tunnels: int = 0
    total_peers: int = 0
    total_rx_bytes: int = 0
    total_tx_bytes: int = 0


class VpnManager:
    """WireGuard VPN 管理器 — 配置文件 + 运行时操作"""

    def __init__(self, config_dir: Path = WG_CONFIG_DIR):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

    # ─── 隧道 CRUD ─────────────────────────────────────────

    def list_tunnels(self) -> List[WireGuardTunnel]:
        """列出所有 WireGuard 隧道"""
        tunnels = []
        for conf_file in sorted(self.config_dir.glob("*.conf")):
            tunnel = self._parse_config(conf_file)
            if tunnel:
                tunnel.running = self._is_interface_up(tunnel.name)
                tunnels.append(tunnel)
        return tunnels

    def get_tunnel(self, name: str) -> Optional[WireGuardTunnel]:
        """获取单个隧道详情"""
        conf_path = self.config_dir / f"{name}.conf"
        if not conf_path.exists():
            return None
        tunnel = self._parse_config(conf_path)
        if tunnel:
            tunnel.running = self._is_interface_up(tunnel.name)
            # 如果运行中，合并运行时状态
            if tunnel.running:
                runtime_info = self._get_runtime_tunnel(name)
                if runtime_info:
                    tunnel.public_key = runtime_info.get("public_key", tunnel.public_key)
                    tunnel.listen_port = runtime_info.get("listen_port", tunnel.listen_port)
                    # 合并 peer 运行时数据
                    runtime_peers = runtime_info.get("peers", [])
                    for rp in runtime_peers:
                        for tp in tunnel.peers:
                            if tp.public_key == rp.get("public_key"):
                                tp.latest_handshake = rp.get("latest_handshake", 0)
                                tp.transfer_rx = rp.get("transfer_rx", 0)
                                tp.transfer_tx = rp.get("transfer_tx", 0)
                                tp.endpoint = rp.get("endpoint", tp.endpoint)
        return tunnel

    def create_tunnel(self, tunnel: WireGuardTunnel) -> Tuple[bool, str]:
        """创建 WireGuard 隧道（生成配置 + 密钥）"""
        # 生成密钥对
        if not tunnel.private_key:
            privkey = self._generate_private_key()
            if not privkey:
                return False, "无法生成私钥"
            tunnel.private_key = privkey
            tunnel.public_key = self._derive_public_key(privkey)

        # 写入配置文件
        config = self._generate_config(tunnel)
        conf_path = self.config_dir / f"{tunnel.name}.conf"
        try:
            conf_path.write_text(config)
            conf_path.chmod(0o600)
            return True, f"隧道 {tunnel.name} 已创建"
        except Exception as e:
            return False, f"写入配置失败: {str(e)}"

    def delete_tunnel(self, name: str) -> Tuple[bool, str]:
        """删除隧道"""
        # 先停止
        if self._is_interface_up(name):
            self.stop_tunnel(name)
        conf_path = self.config_dir / f"{name}.conf"
        if conf_path.exists():
            try:
                conf_path.unlink()
                return True, f"隧道 {name} 已删除"
            except Exception as e:
                return False, f"删除失败: {str(e)}"
        return False, f"隧道 {name} 不存在"

    # ─── 隧道启停 ─────────────────────────────────────────

    def start_tunnel(self, name: str) -> Tuple[bool, str]:
        """启动 WireGuard 隧道"""
        conf_path = self.config_dir / f"{name}.conf"
        if not conf_path.exists():
            return False, f"隧道 {name} 的配置文件不存在"
        try:
            r = subprocess.run(
                [WG_QUICK_BINARY, "up", name],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, f"隧道 {name} 已启动"
            return False, f"启动失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"启动异常: {str(e)}"

    def stop_tunnel(self, name: str) -> Tuple[bool, str]:
        """停止 WireGuard 隧道"""
        if not self._is_interface_up(name):
            return True, f"隧道 {name} 未运行"
        try:
            r = subprocess.run(
                [WG_QUICK_BINARY, "down", name],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, f"隧道 {name} 已停止"
            return False, f"停止失败: {r.stderr.strip()}"
        except Exception as e:
            return False, f"停止异常: {str(e)}"

    def restart_tunnel(self, name: str) -> Tuple[bool, str]:
        """重启隧道"""
        self.stop_tunnel(name)
        return self.start_tunnel(name)

    # ─── Peer 管理 ─────────────────────────────────────────

    def add_peer(self, tunnel_name: str, peer: WireGuardPeer) -> Tuple[bool, str]:
        """添加 Peer 到隧道"""
        tunnel = self.get_tunnel(tunnel_name)
        if not tunnel:
            return False, f"隧道 {tunnel_name} 不存在"

        # 检查公钥是否已存在
        for existing in tunnel.peers:
            if existing.public_key == peer.public_key:
                return False, f"Peer 公钥 {peer.public_key[:16]}... 已存在"

        tunnel.peers.append(peer)
        # 重新生成配置
        config = self._generate_config(tunnel)
        conf_path = self.config_dir / f"{tunnel_name}.conf"
        try:
            conf_path.write_text(config)
            # 如果隧道在运行中，同步添加 peer
            if tunnel.running:
                cmd = [WG_BINARY, "set", tunnel_name,
                       "peer", peer.public_key]
                if peer.endpoint:
                    cmd += ["endpoint", peer.endpoint]
                if peer.allowed_ips:
                    cmd += ["allowed-ips", ",".join(peer.allowed_ips)]
                if peer.persistent_keepalive > 0:
                    cmd += ["persistent-keepalive", str(peer.persistent_keepalive)]
                subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return True, f"Peer {peer.public_key[:16]}... 已添加"
        except Exception as e:
            return False, f"添加 Peer 失败: {str(e)}"

    def remove_peer(self, tunnel_name: str, public_key: str) -> Tuple[bool, str]:
        """从隧道移除 Peer"""
        tunnel = self.get_tunnel(tunnel_name)
        if not tunnel:
            return False, f"隧道 {tunnel_name} 不存在"

        before = len(tunnel.peers)
        tunnel.peers = [p for p in tunnel.peers if p.public_key != public_key]
        if len(tunnel.peers) == before:
            return False, f"未找到公钥 {public_key[:16]}..."

        # 重新生成配置
        config = self._generate_config(tunnel)
        conf_path = self.config_dir / f"{tunnel_name}.conf"
        try:
            conf_path.write_text(config)
            # 如果隧道在运行中，同步移除 peer
            if tunnel.running:
                subprocess.run(
                    [WG_BINARY, "set", tunnel_name, "peer", public_key, "remove"],
                    capture_output=True, text=True, timeout=10
                )
            return True, f"Peer 已移除"
        except Exception as e:
            return False, f"移除 Peer 失败: {str(e)}"

    # ─── 统计 ──────────────────────────────────────────────

    def get_stats(self) -> VpnStats:
        """获取 VPN 全局统计"""
        tunnels = self.list_tunnels()
        stats = VpnStats()
        stats.tunnels_count = len(tunnels)
        stats.active_tunnels = sum(1 for t in tunnels if t.running)
        for t in tunnels:
            stats.total_peers += len(t.peers)
            for p in t.peers:
                stats.total_rx_bytes += p.transfer_rx
                stats.total_tx_bytes += p.transfer_tx
        return stats

    def get_dump(self) -> List[Dict]:
        """获取 wg show 原始 JSON dump"""
        try:
            r = subprocess.run(
                [WG_BINARY, "show", "dump"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return []
            return self._parse_dump(r.stdout)
        except Exception:
            return []

    # ─── 内部辅助 ──────────────────────────────────────────

    def _is_interface_up(self, name: str) -> bool:
        """检测接口是否 up"""
        try:
            r = subprocess.run(
                ["ip", "link", "show", name],
                capture_output=True, text=True, timeout=5
            )
            return "state UP" in r.stdout
        except Exception:
            return False

    def _generate_private_key(self) -> str:
        """生成 WireGuard 私钥"""
        try:
            r = subprocess.run(
                [WG_BINARY, "genkey"],
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip()
        except Exception:
            return ""

    def _derive_public_key(self, private_key: str) -> str:
        """从私钥派生公钥"""
        try:
            r = subprocess.run(
                [WG_BINARY, "pubkey"],
                input=private_key,
                capture_output=True, text=True, timeout=5
            )
            return r.stdout.strip()
        except Exception:
            return ""

    def _parse_config(self, conf_path: Path) -> Optional[WireGuardTunnel]:
        """解析 WireGuard 配置文件"""
        try:
            content = conf_path.read_text()
        except Exception:
            return None

        tunnel = WireGuardTunnel(name="")
        tunnel.name = conf_path.stem
        tunnel.config_path = str(conf_path)

        current_peer = None
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('[Interface]'):
                current_peer = None
                continue
            elif line.startswith('[Peer]'):
                if current_peer is not None:
                    tunnel.peers.append(current_peer)
                current_peer = WireGuardPeer()
                continue

            if current_peer is None:
                # Interface 部分
                if '=' in line:
                    key, val = [x.strip() for x in line.split('=', 1)]
                    if key == 'PrivateKey':
                        tunnel.private_key = val
                    elif key == 'ListenPort':
                        try:
                            tunnel.listen_port = int(val)
                        except ValueError:
                            pass
                    elif key == 'Address':
                        tunnel.address = val
                    elif key == 'DNS':
                        tunnel.dns = val
                    elif key == 'MTU':
                        try:
                            tunnel.mtu = int(val)
                        except ValueError:
                            pass
                    elif key == 'Table':
                        tunnel.table = val
                    elif key == 'FwMark':
                        tunnel.fwmark = val
            else:
                # Peer 部分
                if '=' in line:
                    key, val = [x.strip() for x in line.split('=', 1)]
                    if key == 'PublicKey':
                        current_peer.public_key = val
                    elif key == 'PresharedKey':
                        current_peer.preshared_key = val
                    elif key == 'Endpoint':
                        current_peer.endpoint = val
                    elif key == 'AllowedIPs':
                        current_peer.allowed_ips = [x.strip() for x in val.split(',')]
                    elif key == 'PersistentKeepalive':
                        try:
                            current_peer.persistent_keepalive = int(val)
                        except ValueError:
                            pass

        if current_peer is not None:
            tunnel.peers.append(current_peer)

        # 从私钥推导公钥
        if tunnel.private_key:
            tunnel.public_key = self._derive_public_key(tunnel.private_key)

        return tunnel

    def _generate_config(self, tunnel: WireGuardTunnel) -> str:
        """生成 WireGuard 配置文件内容"""
        lines = ["[Interface]"]
        if tunnel.private_key:
            lines.append(f"PrivateKey = {tunnel.private_key}")
        lines.append(f"ListenPort = {tunnel.listen_port}")
        if tunnel.address:
            lines.append(f"Address = {tunnel.address}")
        if tunnel.dns:
            lines.append(f"DNS = {tunnel.dns}")
        if tunnel.mtu:
            lines.append(f"MTU = {tunnel.mtu}")
        if tunnel.table != "auto":
            lines.append(f"Table = {tunnel.table}")

        for peer in tunnel.peers:
            lines.extend(["", "[Peer]"])
            lines.append(f"PublicKey = {peer.public_key}")
            if peer.preshared_key:
                lines.append(f"PresharedKey = {peer.preshared_key}")
            if peer.endpoint:
                lines.append(f"Endpoint = {peer.endpoint}")
            if peer.allowed_ips:
                lines.append(f"AllowedIPs = {', '.join(peer.allowed_ips)}")
            if peer.persistent_keepalive > 0:
                lines.append(f"PersistentKeepalive = {peer.persistent_keepalive}")

        return '\n'.join(lines) + '\n'

    def _get_runtime_tunnel(self, name: str) -> Optional[Dict]:
        """获取运行时隧道状态"""
        try:
            r = subprocess.run(
                [WG_BINARY, "show", name, "dump"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return None
            return self._parse_tunnel_dump(name, r.stdout)
        except Exception:
            return None

    def _parse_tunnel_dump(self, name: str, dump: str) -> Dict:
        """解析 wg show dump 输出"""
        result = {"name": name, "public_key": "", "listen_port": 0, "peers": []}
        lines = dump.strip().split('\n')
        if not lines:
            return result

        # 第一行是接口信息: private_key public_key listen_port fwmark
        parts = lines[0].split('\t')
        if len(parts) >= 3:
            result["private_key"] = parts[0]
            result["public_key"] = parts[1]
            try:
                result["listen_port"] = int(parts[2])
            except ValueError:
                pass

        # 后续行是 peer 信息
        for line in lines[1:]:
            parts = line.split('\t')
            if len(parts) >= 7:
                peer = {
                    "public_key": parts[0],
                    "preshared_key": parts[1],
                    "endpoint": parts[2],
                    "allowed_ips": parts[3].split(',') if parts[3] else [],
                    "latest_handshake": int(parts[4]) if parts[4].isdigit() else 0,
                    "transfer_rx": int(parts[5]) if parts[5].isdigit() else 0,
                    "transfer_tx": int(parts[6]) if parts[6].isdigit() else 0,
                    "persistent_keepalive": int(parts[7]) if len(parts) > 7 and parts[7].isdigit() else 0,
                }
                result["peers"].append(peer)

        return result

    def _parse_dump(self, dump: str) -> List[Dict]:
        """解析全局 wg show dump"""
        tunnels = []
        current = None
        for line in dump.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) < 3:
                continue
            # 接口行: private_key public_key listen_port
            if current is None or parts[0] != current.get("_privkey"):
                current = {
                    "_privkey": parts[0],
                    "public_key": parts[1],
                    "listen_port": int(parts[2]) if parts[2].isdigit() else 0,
                    "peers": [],
                }
                tunnels.append(current)
            else:
                # Peer 行
                if len(parts) >= 7:
                    peer = {
                        "public_key": parts[0],
                        "endpoint": parts[2],
                        "allowed_ips": parts[3].split(',') if parts[3] else [],
                        "latest_handshake": int(parts[4]),
                        "transfer_rx": int(parts[5]),
                        "transfer_tx": int(parts[6]),
                    }
                    current["peers"].append(peer)
        return tunnels
