# VPN 管理模块详细设计 — VPN Manager

> 版本: v1.0 | 日期: 2026-04-25 | 状态: 初稿
> 对应 HLD 模块: 3.6 VPN Manager
> 依赖模块: Configuration Engine, Firewall Manager
> 后端技术: WireGuard (内核原生) + strongSwan (IPSec) + Tailscale (可选集成)

---

## 1. 模块定位

VPN Manager 负责 VPN 隧道和代理通道的统一管理。支持三种类型：

1. **WireGuard** — 内核原生 VPN，高性能、配置简单。用于远程接入、站点互联、回家
2. **IPSec/IKEv2** — strongSwan 驱动，兼容性好，适合移动设备远程接入
3. **Tailscale 集成** — 基于 WireGuard 的零配置 Mesh VPN，负责状态监控和 Exit Node 管理
4. **OpenClash 集成** — 代理客户端管理，负责节点状态监控和切换

核心设计原则：VPN Manager 不直接管理 Tailscale/Clash 本身（它们是独立安装的应用），但其状态监控和通道编排集成在 Dashboard 和 Traffic Orchestrator 中。

---

## 2. 数据结构

```python
# ubunturouter/vpn/models.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from enum import Enum


class TunnelType(str, Enum):
    WIREGUARD = "wireguard"
    IPSEC = "ipsec"
    TAILSCALE = "tailscale"
    CLASH = "clash"
    DIRECT = "direct"               # 内置，非 VPN


class TunnelStatus(str, Enum):
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DEGRADED = "degraded"


# ─── WireGuard ─────────────────────────────────────

class WireGuardPeer(BaseModel):
    name: str
    public_key: str
    preshared_key: Optional[str] = None
    allowed_ips: List[str] = ["0.0.0.0/0"]
    endpoint: Optional[str] = None     # "domain.com:51820" 或 "1.2.3.4:51820"
    persistent_keepalive: int = 25
    enabled: bool = True
    description: Optional[str] = None


class WireGuardConfig(BaseModel):
    enabled: bool = False
    interface: str = "wg0"
    listen_port: int = 51820
    private_key: Optional[str] = None  # 自动生成或用户提供
    address: str = "10.0.1.1/24"
    mtu: int = 1420
    table: str = "auto"                # "auto" / "off" / 数字
    fwmark: Optional[int] = None
    dns: Optional[List[str]] = None    # ["192.168.21.1"]
    peers: List[WireGuardPeer] = []


# ─── IPSec / IKEv2 ────────────────────────────────

class IPsecPeer(BaseModel):
    name: str
    endpoint: str
    auth_method: str = "psk"
    psk: Optional[str] = None
    local_id: Optional[str] = None
    remote_id: Optional[str] = None
    local_subnet: str = "192.168.21.0/24"
    remote_subnet: str = "10.0.0.0/24"
    ike_version: Literal["ikev1", "ikev2"] = "ikev2"
    enabled: bool = True


class IPsecConfig(BaseModel):
    enabled: bool = False
    # IKEv2 远程接入（移动客户端）
    mobile_clients: bool = False
    virtual_pool: str = "10.0.100.0/24"
    dns_servers: List[str] = ["192.168.21.1"]
    server_cert: Optional[str] = None
    server_key: Optional[str] = None
    ca_cert: Optional[str] = None
    # 站点互联
    peers: List[IPsecPeer] = []


# ─── Tailscale 集成 ───────────────────────────────

class TailscaleNode(BaseModel):
    """Tailscale 节点信息"""
    name: str
    ip: str                          # Tailscale 分配的 IP (100.x.x.x)
    public_ip: Optional[str] = None
    is_exit_node: bool = False
    is_online: bool = False
    latency_ms: Optional[float] = None
    location: Optional[str] = None   # 地理位置（从公网IP推算）
    last_seen: Optional[str] = None


class TailscaleStatus(BaseModel):
    enabled: bool = False
    status: TunnelStatus = TunnelStatus.DISCONNECTED
    self_ip: Optional[str] = None
    exit_nodes: List[TailscaleNode] = []
    mesh_peers: List[TailscaleNode] = []
    dns_enabled: bool = False


# ─── Clash 代理集成 ───────────────────────────────

class ClashProxy(BaseModel):
    """Clash 代理节点"""
    name: str
    type: str = "Shadowsocks"        # Shadowsocks / VMess / Trojan / Hysteria2
    server: str
    port: int
    latency_ms: Optional[float] = None
    status: Literal["alive", "dead", "untested"] = "untested"
    location: Optional[str] = None
    # 历史延迟
    history: List[float] = []


class ClashProxyGroup(BaseModel):
    name: str                        # "美国节点", "亚洲节点", "自动选择"
    type: str = "select"             # select / url-test / fallback / load-balance
    proxies: List[str] = []
    now: Optional[str] = None        # 当前选中的代理


class ClashConfig(BaseModel):
    enabled: bool = False
    api_port: int = 9090
    api_secret: Optional[str] = None
    mixed_port: int = 7890
    proxies: List[ClashProxy] = []
    proxy_groups: List[ClashProxyGroup] = []


# ─── 统一通道抽象（供 Traffic Orchestrator 使用）───

class Tunnel(BaseModel):
    """统一通道抽象"""
    id: str                             # "ts-exit-us", "wg-home", "oc-us"
    name: str
    type: TunnelType
    status: TunnelStatus
    latency_ms: Optional[float] = None
    location: Optional[str] = None
    is_exit_node: bool = False          # 能否作为流量出口
    is_mesh: bool = False               # 是否站点互联
    traffic_rx: int = 0
    traffic_tx: int = 0
    peers_online: int = 0
    health: Literal["healthy", "degraded", "dead"] = "healthy"
    backup_of: Optional[str] = None     # 备用通道指向


# ─── 运行时状态 ─────────────────────────────────────

class VPNStats(BaseModel):
    tunnels: List[Tunnel] = []
    total_traffic_rx: int = 0
    total_traffic_tx: int = 0
    active_connections: int = 0
```

---

## 3. 核心接口

```python
# ubunturouter/vpn/manager.py

from typing import List, Optional


class VPNManager:
    """VPN 管理模块"""

    # ─── 统一通道列表 ──────────────────────────────

    def list_tunnels(self) -> List[Tunnel]:
        """
        列出所有可用通道
        
        合并:
        1. WireGuard 接口状态 (wg show)
        2. Tailscale 状态 (tailscale status --json)
        3. Clash 代理组状态 (Clash API /proxies)
        4. IPSec 连接状态 (ipsec status)
        5. 内置 direct 通道
        """

    def get_tunnel_status(self, tunnel_id: str) -> Optional[Tunnel]:
        """获取单通道状态"""

    def get_tunnel_latency(self, tunnel_id: str) -> Optional[float]:
        """获取当前通道延迟（ping 对端或端点）"""

    # ─── WireGuard 操作 ────────────────────────────

    def list_wg_peers(self) -> List[dict]:
        """
        查看 WireGuard Peer 状态
        
        实现: wg show wg0 dump
        返回: peer 公钥、端点、允许IP、传输量、最后握手时间
        """

    def add_wg_peer(self, peer: WireGuardPeer) -> None:
        """添加 Peer"""

    def remove_wg_peer(self, public_key: str) -> None:
        """移除 Peer"""

    def generate_wg_client_config(self, peer_name: str) -> str:
        """
        生成 WireGuard 客户端配置文件
        
        根据服务端配置生成：
        [Interface]
        PrivateKey = <生成的客户端密钥>
        Address = 10.0.1.2/32
        DNS = 192.168.21.1
        
        [Peer]
        PublicKey = <服务端公钥>
        Endpoint = <公网IP>:51820
        AllowedIPs = 192.168.21.0/24, 10.0.1.0/24
        """

    def generate_wg_qrcode_data(self, config_str: str) -> str:
        """
        生成 WireGuard 配置二维码
        
        返回: base64 编码的 PNG 或配置字符串（供前端生成二维码）
        """

    # ─── Tailscale ─────────────────────────────────

    def get_tailscale_status(self) -> TailscaleStatus:
        """
        获取 Tailscale 状态
        
        实现: tailscale status --json
        解析: Exit Node 列表、Mesh 节点列表、延迟
        """

    def set_tailscale_exit_node(self, node_name: str) -> None:
        """
        切换 Tailscale Exit Node
        
        实现: tailscale set --exit-node={node_name}
        """

    # ─── Clash ─────────────────────────────────────

    def get_clash_status(self) -> ClashConfig:
        """
        获取 Clash 状态
        
        实现: GET http://localhost:9090/proxies
        """

    def get_clash_traffic(self) -> dict:
        """
        获取 Clash 实时流量
        
        实现: GET http://localhost:9090/traffic (WebSocket)
        """

    def switch_clash_proxy(self, group: str, proxy: str) -> None:
        """
        切换 Clash 代理组
        
        实现: PUT http://localhost:9090/proxies/{group}
        参数: {"name": proxy}
        """

    def test_clash_delay(self, proxy: str) -> Optional[float]:
        """
        测试 Clash 节点延迟
        
        实现: GET http://localhost:9090/proxies/{proxy}/delay
        """

    # ─── 唯一通道抽象操作 ──────────────────────────

    def test_tunnel(self, tunnel_id: str) -> Optional[float]:
        """测试指定通道的连通性和延迟"""

    def switch_to_fallback(self, tunnel_id: str) -> bool:
        """
        将流量切换到备用通道
        
        用于 Traffic Orchestrator 的故障转移
        """

    # ─── 配置 Apply ─────────────────────────────────

    def apply(self, config: UbunturouterConfig) -> None:
        """
        应用 VPN 配置
        
        WireGuard: 生成 /etc/wireguard/wg0.conf → wg-quick up wg0
        IPSec: 生成 /etc/ipsec.conf / /etc/ipsec.secrets → ipsec reload
        Tailscale/Clash: 不直接管理（外部安装），只监控状态
        """
```

---

## 4. WireGuard 配置生成

```python
# ubunturouter/engine/generators/wireguard.py

class WireGuardGenerator(ConfigGenerator):

    def generate(self, config: UbunturouterConfig) -> Dict[str, str]:
        """
        生成 /etc/wireguard/wg0.conf
        
        如果 private_key 未设置，自动生成:
          umask 077 && wg genkey > /etc/wireguard/key
        """
```

### WireGuard 配置示例（服务端）

```
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <服务端私钥>
Address = 10.0.1.1/24
ListenPort = 51820
MTU = 1420
PostUp = iptables -A FORWARD -i %i -j ACCEPT
PostUp = iptables -A FORWARD -o %i -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -o enp1s0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT
PostDown = iptables -D FORWARD -o %i -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -o enp1s0 -j MASQUERADE

# Peer: phone (iPhone)
[Peer]
PublicKey = <客户端公钥>
PresharedKey = <预共享密钥>
AllowedIPs = 10.0.1.2/32, 192.168.21.0/24

# Peer: office (Site-to-Site)
[Peer]
PublicKey = <办公室公钥>
AllowedIPs = 10.0.2.0/24, 172.16.0.0/24
Endpoint = office.example.com:51820
PersistentKeepalive = 25
```

### WireGuard 客户端配置文件

```
# 文件名: phone.conf
# 同时生成二维码供手机扫码导入

[Interface]
PrivateKey = <客户端私钥>
Address = 10.0.1.2/32
DNS = 192.168.21.1

[Peer]
PublicKey = <服务端公钥>
PresharedKey = <预共享密钥>
Endpoint = your-home.com:51820
AllowedIPs = 192.168.21.0/24, 10.0.1.0/24
PersistentKeepalive = 25
```

---

## 5. IPSec/IKEv2 配置生成

### 5.1 strongSwan 配置示例

```
# /etc/ipsec.conf
config setup
    charondebug="ike 2, knl 2, cfg 2, net 2, esp 2, dmn 2, mgr 2"

# IKEv2 远程接入（移动客户端）
conn ikev2-vpn
    auto=add
    compress=no
    type=tunnel
    keyexchange=ikev2
    fragmentation=yes
    forceencaps=yes
    
    # 证书认证
    ike=aes256-sha256-modp2048!
    esp=aes256-sha256-modp2048!
    
    left=%any
    leftid=@vpn.ubunturouter.local
    leftcert=server-cert.pem
    leftsendcert=always
    leftsubnet=0.0.0.0/0
    
    right=%any
    rightid=%any
    rightauth=eap-mschapv2
    rightsourceip=10.0.100.0/24
    rightdns=192.168.21.1
    rightsendcert=never
    
    eap_identity=%identity

# 站点互联 (Site-to-Site)
conn site-a
    auto=start
    type=tunnel
    keyexchange=ikev2
    ikelifetime=24h
    lifetime=8h
    
    left=192.168.21.1
    leftsubnet=192.168.21.0/24
    
    right=1.2.3.4
    rightid=@vpn.office.local
    rightsubnet=10.0.0.0/24
    
    ike=aes256-sha256-modp2048!
    esp=aes256-sha256!
    authby=secret
```

```
# /etc/ipsec.secrets
: RSA server-key.pem   # 服务器证书私钥
1.2.3.4 : PSK "shared_secret"  # 站点互联 PSK
: EAP "vpn_user" : "password"  # 客户端用户名密码
```

---

## 6. Tailscale 状态集成

### 6.1 Tailscale 状态获取

```python
class TailscaleMonitor:
    """Tailscale 状态监控"""

    def get_status(self) -> dict:
        """
        执行 tailscale status --json
        
        返回 json 示例:
        {
            "Version": "1.76.0",
            "TUN": "tailscale0",
            "Self": {
                "ID": "123",
                "PublicKey": "...",
                "HostName": "router",
                "DNSName": "router.tail-xxxxx.ts.net.",
                "TailscaleIPs": ["100.x.x.1"],
                "ExitNode": "us-node"
            },
            "Peer": [
                {
                    "ID": "456",
                    "HostName": "phone",
                    "DNSName": "phone.tail-xxxxx.ts.net.",
                    "TailscaleIPs": ["100.x.x.2"],
                    "IsExitNode": true,
                    "ExitNodeOption": true,
                    "Online": true,
                    "LastSeen": "2026-04-25T10:00:00Z"
                }
            ]
        }
        """

    def get_exit_nodes(self) -> List[TailscaleNode]:
        """提取 Exit Node 列表"""

    def get_mesh_peers(self) -> List[TailscaleNode]:
        """提取 Mesh 节点列表"""

    def is_exit_node_used(self) -> Optional[str]:
        """当前是否在使用 Exit Node，返回节点名"""
```

### 6.2 Tailscale Exit Node 管理

```python
def set_exit_node(node_name: Optional[str]):
    """
    设置/清除 Tailscale Exit Node
    
    设置: tailscale set --exit-node={node_name}
    清除: tailscale set --exit-node=""
    """

def test_exit_node_latency(node_name: str) -> float:
    """
    测试 Exit Node 延迟
    
    ping Tailscale 接口 IP 计算延迟
    """
```

---

## 7. Clash 代理集成

### 7.1 Clash 状态获取

```python
class ClashMonitor:
    """Clash 代理状态监控"""

    def __init__(self, api_url="http://localhost:9090", secret=None):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {secret}"} if secret else {}

    def get_proxies(self) -> dict:
        """获取所有节点和代理组"""
        resp = requests.get(f"{self.api_url}/proxies", headers=self.headers)
        return resp.json()

    def get_proxy_delay(self, proxy_name: str) -> Optional[float]:
        """测试节点延迟"""
        resp = requests.get(
            f"{self.api_url}/proxies/{proxy_name}/delay",
            params={"timeout": 5000, "url": "http://www.gstatic.com/generate_204"},
            headers=self.headers
        )
        if resp.status_code == 200:
            return resp.json().get("delay")
        return None

    def switch_proxy(self, group: str, proxy: str):
        """切换代理组"""
        requests.put(
            f"{self.api_url}/proxies/{group}",
            json={"name": proxy},
            headers=self.headers
        )

    def get_traffic(self) -> dict:
        """获取实时流量"""
        resp = requests.get(f"{self.api_url}/traffic", headers=self.headers, stream=True)
        # WebSocket 流，实时推送
```

### 7.2 Clash 地理定位

```python
def get_proxy_location(proxy: ClashProxy) -> Optional[str]:
    """
    从代理节点名或 IP 解析地理位置
    
    "US 01" → "🇺🇸 美国"
    "JP 04 东京" → "🇯🇵 东京"
    "HK 01" → "🇭🇰 香港"
    
    如果名称无法推断，走 GeoIP:
      proxy.server IP → GeoIP DB → 城市/国家
    """

def get_proxy_group_locations(group: ClashProxyGroup) -> List[str]:
    """获取代理组所有节点的地理位置"""
```

---

## 8. 通道统一抽象与流量编排联动

### 8.1 通道发现

```python
class TunnelDiscovery:
    """
    自动发现系统上的所有可用通道
    
    发现来源:
    - WireGuard: wg show 列出所有接口
    - Tailscale: tailscale status 列出 Exit Node
    - Clash: API /proxies 获取代理组
    - IPSec: ipsec statusall
    - 内置: direct（始终可用）
    """

    def discover_all(self) -> List[Tunnel]:
        """发现所有通道"""
        tunnels = []
        
        # 1. 直连
        tunnels.append(Tunnel(
            id="direct",
            name="直连",
            type=TunnelType.DIRECT,
            status=TunnelStatus.CONNECTED,
            latency_ms=0,
            is_exit_node=True,
            health="healthy"
        ))
        
        # 2. WireGuard
        for wg_iface in self._list_wg_interfaces():
            tunnels.append(...)
        
        # 3. Tailscale Exit Nodes
        for node in self._tailscale_monitor.get_exit_nodes():
            tunnels.append(Tunnel(
                id=f"ts-exit-{node.name}",
                name=f"Tailscale {node.name}",
                type=TunnelType.TAILSCALE,
                status=TunnelStatus.CONNECTED if node.is_online else TunnelStatus.DISCONNECTED,
                latency_ms=node.latency_ms,
                location=node.location,
                is_exit_node=True,
                is_mesh=False
            ))
        
        # 4. Clash 代理组
        for group in self._clash_monitor.get_proxy_groups():
            tunnels.append(...)
        
        return tunnels
```

### 8.2 通道健康检查集成

```
Traffic Orchestrator 使用 VPN Manager 的通道列表做编排：

编排规则示例:
  电视 → Netflix → ts-exit-us [主] oc-us [备]
  
健康检查循环:
  Every 10s:
    foreach tunnel in orchestration_rules:
      latency = VPNManager.get_tunnel_latency(tunnel_id)
      if latency is None:
        tunnel.health = "dead"
        if tunnel has backup:
          switch_to_fallback(tunnel_id)
        
VPNManager.get_tunnel_latency("ts-exit-us"):
  1. tailscale ping us-node → 延迟
  2. 如失败: tailscale status 检查节点是否在线
  3. 返回延迟或 None
```

---

## 9. 服务 Reload 顺序

```
VPN Manager apply()
    │
    ▼
┌──────────────────────┐
│ 1. WireGuard         │
│    wg-quick up/down  │  ← 短暂断连
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. IPSec             │
│    ipsec reload      │  ← 不影响已建立的连接
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 3. 防火墙端口放行     │
│    自动放行 WG/IPsec  │  ← 调用 FirewallManager
│    端口              │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 4. 连通性检测         │
│    - wg show 握手时间 │
│    - tailscale ping  │
│    - ipsec status    │
└──────────────────────┘
```

---

## 10. 测试用例

| 测试场景 | 预期 |
|----------|------|
| WireGuard 服务端启动 | wg0 接口 UP，监听 51820 端口 |
| iPhone 连接 WireGuard | peer 列表中显示 handshake 时间 < 5s |
| WireGuard 回家访问 NAS | 手机通过 10.0.1.x ping 通 192.168.21.50 |
| 客户端配置生成 | 配置文件格式正确，导入手机后可用 |
| 客户端二维码 | 扫码后手机自动导入配置 |
| IPSec/IKEv2 连接 | Windows/iOS 内置 VPN 连接成功 |
| Tailscale Exit Node 状态 | Dashboard 显示节点在线/延迟 |
| Clash 节点延迟测试 | 各节点延迟显示正确 |
| Clash 代理组切换 | 成功切换到指定节点 |
| 通道发现 | direct + wg0 + ts-exit-* + oc-* 全部列出 |
| 通道故障转移 | 主通道 dead 后 10s 内切换到备用 |
| 防火墙端口自动放行 | WG 端口 51820 在 nftables 中自动放行 |
