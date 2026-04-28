"""VPN API 路由 — WireGuard / PPTP / IPSec / OpenVPN 管理"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from ..deps import require_auth
from ...vpn import VpnManager, WireGuardTunnel, WireGuardPeer
from ...vpn.pptp import PptpManager, PptpUser
from ...vpn.ipsec import IpsecManager, IpsecConfig, IpsecUser
from ...vpn.openvpn import OpenvpnManager, OpenvpnConfig

router = APIRouter()
vm = VpnManager()


# ===================================================================
# WireGuard — 隧道管理
# ===================================================================

# ─── 请求/响应模型 ──────────────────────────────────────────

class TunnelCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    listen_port: int = Field(51820, ge=1024, le=65535)
    address: str = ""          # 如 10.0.0.1/24
    dns: str = ""
    mtu: int = 1420
    private_key: str = ""      # 留空自动生成


class PeerCreate(BaseModel):
    public_key: str
    preshared_key: str = ""
    endpoint: str = ""
    allowed_ips: List[str] = []
    persistent_keepalive: int = 0


class PeerDelete(BaseModel):
    public_key: str


# ─── 隧道 CRUD ─────────────────────────────────────────────

@router.get("/tunnels")
async def list_tunnels(auth=Depends(require_auth)):
    """列出所有 WireGuard 隧道"""
    tunnels = vm.list_tunnels()
    return {
        "tunnels": [
            {
                "name": t.name,
                "public_key": t.public_key,
                "listen_port": t.listen_port,
                "address": t.address,
                "running": t.running,
                "peers_count": len(t.peers),
                "mtu": t.mtu,
            }
            for t in tunnels
        ],
        "count": len(tunnels),
    }


@router.get("/tunnels/{name}")
async def get_tunnel(name: str, auth=Depends(require_auth)):
    """获取单个隧道详情"""
    tunnel = vm.get_tunnel(name)
    if not tunnel:
        raise HTTPException(status_code=404, detail=f"隧道 {name} 不存在")
    return {
        "name": tunnel.name,
        "public_key": tunnel.public_key,
        "listen_port": tunnel.listen_port,
        "address": tunnel.address,
        "dns": tunnel.dns,
        "mtu": tunnel.mtu,
        "table": tunnel.table,
        "running": tunnel.running,
        "config_path": tunnel.config_path,
        "peers": [
            {
                "public_key": p.public_key,
                "endpoint": p.endpoint,
                "allowed_ips": p.allowed_ips,
                "latest_handshake": p.latest_handshake,
                "transfer_rx": p.transfer_rx,
                "transfer_tx": p.transfer_tx,
                "persistent_keepalive": p.persistent_keepalive,
            }
            for p in tunnel.peers
        ],
    }


@router.post("/tunnels")
async def create_tunnel(tc: TunnelCreate, auth=Depends(require_auth)):
    """创建 WireGuard 隧道"""
    tunnel = WireGuardTunnel(
        name=tc.name,
        listen_port=tc.listen_port,
        address=tc.address,
        dns=tc.dns,
        mtu=tc.mtu,
        private_key=tc.private_key,
    )
    success, msg = vm.create_tunnel(tunnel)
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg, "public_key": tunnel.public_key}


@router.delete("/tunnels/{name}")
async def delete_tunnel(name: str, auth=Depends(require_auth)):
    """删除隧道"""
    success, msg = vm.delete_tunnel(name)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


# ─── 隧道启停 ─────────────────────────────────────────────

@router.post("/tunnels/{name}/start")
async def start_tunnel(name: str, auth=Depends(require_auth)):
    """启动隧道"""
    success, msg = vm.start_tunnel(name)
    return {"success": success, "message": msg}


@router.post("/tunnels/{name}/stop")
async def stop_tunnel(name: str, auth=Depends(require_auth)):
    """停止隧道"""
    success, msg = vm.stop_tunnel(name)
    return {"success": success, "message": msg}


@router.post("/tunnels/{name}/restart")
async def restart_tunnel(name: str, auth=Depends(require_auth)):
    """重启隧道"""
    success, msg = vm.restart_tunnel(name)
    return {"success": success, "message": msg}


# ─── Peer 管理 ─────────────────────────────────────────────

@router.post("/tunnels/{name}/peers")
async def add_peer(name: str, peer: PeerCreate, auth=Depends(require_auth)):
    """添加 Peer"""
    p = WireGuardPeer(
        public_key=peer.public_key,
        preshared_key=peer.preshared_key,
        endpoint=peer.endpoint,
        allowed_ips=peer.allowed_ips,
        persistent_keepalive=peer.persistent_keepalive,
    )
    success, msg = vm.add_peer(name, p)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.delete("/tunnels/{name}/peers/{public_key}")
async def remove_peer(name: str, public_key: str, auth=Depends(require_auth)):
    """移除 Peer"""
    success, msg = vm.remove_peer(name, public_key)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


# ─── 统计 ──────────────────────────────────────────────────

@router.get("/stats")
async def get_vpn_stats(auth=Depends(require_auth)):
    """获取 VPN 全局统计"""
    stats = vm.get_stats()
    return {
        "tunnels_count": stats.tunnels_count,
        "active_tunnels": stats.active_tunnels,
        "total_peers": stats.total_peers,
        "total_rx_bytes": stats.total_rx_bytes,
        "total_tx_bytes": stats.total_tx_bytes,
    }


@router.get("/dump")
async def get_wg_dump(auth=Depends(require_auth)):
    """获取 wg show dump 原始状态"""
    dump = vm.get_dump()
    return {"interfaces": dump}


# ─── 密钥生成 ─────────────────────────────────────────────

@router.get("/generate-key")
async def generate_key(auth=Depends(require_auth)):
    """生成 WireGuard 密钥对"""
    from ...vpn import VpnManager
    mgr = VpnManager()
    privkey = mgr._generate_private_key()
    if not privkey:
        raise HTTPException(status_code=500, detail="密钥生成失败")
    pubkey = mgr._derive_public_key(privkey)
    return {
        "private_key": privkey,
        "public_key": pubkey,
    }


# ===================================================================
# PPTP — 服务管理
# ===================================================================

pptp_mgr = PptpManager()


class PptpUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


@router.get("/pptp/status")
async def pptp_status(auth=Depends(require_auth)):
    """PPTP 服务状态"""
    config = pptp_mgr.get_config()
    connections = pptp_mgr.get_connections()
    return {
        "running": config.running,
        "config": {
            "local_ip": config.local_ip,
            "remote_ip_range": config.remote_ip_range,
            "dns1": config.dns1,
            "dns2": config.dns2,
            "mppe": config.mppe,
            "require_mppe": config.require_mppe,
            "max_connections": config.max_connections,
            "idle_timeout": config.idle_timeout,
        },
        "active_connections": len(connections),
        "connections": [
            {
                "username": c.username,
                "remote_ip": c.remote_ip,
                "assigned_ip": c.assigned_ip,
                "connected_since": c.connected_since.isoformat() if c.connected_since else None,
            }
            for c in connections
        ],
    }


@router.get("/pptp/users")
async def pptp_list_users(auth=Depends(require_auth)):
    """PPTP 用户列表"""
    users = pptp_mgr.list_users()
    return {
        "users": [
            {
                "username": u.username,
                "ip": u.ip,
                "enabled": u.enabled,
            }
            for u in users
        ],
        "count": len(users),
    }


@router.post("/pptp/users")
async def pptp_add_user(user: PptpUserCreate, auth=Depends(require_auth)):
    """添加 PPTP 用户"""
    pptp_user = PptpUser(username=user.username, password=user.password)
    success, msg = pptp_mgr.add_user(pptp_user)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.delete("/pptp/users/{username}")
async def pptp_delete_user(username: str, auth=Depends(require_auth)):
    """删除 PPTP 用户"""
    success, msg = pptp_mgr.delete_user(username)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@router.post("/pptp/start")
async def pptp_start(auth=Depends(require_auth)):
    """启动 PPTP 服务"""
    success, msg = pptp_mgr.start()
    return {"success": success, "message": msg}


@router.post("/pptp/stop")
async def pptp_stop(auth=Depends(require_auth)):
    """停止 PPTP 服务"""
    success, msg = pptp_mgr.stop()
    return {"success": success, "message": msg}


@router.post("/pptp/restart")
async def pptp_restart(auth=Depends(require_auth)):
    """重启 PPTP 服务"""
    success, msg = pptp_mgr.restart()
    return {"success": success, "message": msg}


# ===================================================================
# IPSec/IKEv2 — 服务管理
# ===================================================================

ipsec_mgr = IpsecManager()


class IpsecConfigUpdate(BaseModel):
    psk: Optional[str] = None
    left_subnet: Optional[str] = None
    right_subnet: Optional[str] = None
    ports: Optional[dict] = None          # {ike_port: int, nat_t_port: int}
    dns1: Optional[str] = None
    dns2: Optional[str] = None
    lifetime: Optional[int] = None


class IpsecUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


@router.get("/ipsec/status")
async def ipsec_status(auth=Depends(require_auth)):
    """IPSec 服务状态"""
    status = ipsec_mgr.get_status()
    return {
        "running": status["running"],
        "version": status["version"],
        "active_connections": status["active_connections"],
        "connections": status["connections"],
    }


@router.get("/ipsec/config")
async def ipsec_get_config(auth=Depends(require_auth)):
    """获取 IPSec 配置"""
    cfg = ipsec_mgr.get_config()
    return {
        "server_ip": cfg.server_ip,
        "server_domain": cfg.server_domain,
        "psk": bool(cfg.psk),          # 不返回明文 PSK
        "ike_port": cfg.ike_port,
        "nat_t_port": cfg.nat_t_port,
        "dns1": cfg.dns1,
        "dns2": cfg.dns2,
        "left_subnet": cfg.left_subnet,
        "right_subnet": cfg.right_subnet,
        "enforce_server_cert": cfg.enforce_server_cert,
        "lifetime": cfg.lifetime,
        "running": cfg.running,
    }


@router.put("/ipsec/config")
async def ipsec_update_config(upd: IpsecConfigUpdate, auth=Depends(require_auth)):
    """更新 IPSec 配置"""
    cfg = ipsec_mgr.get_config()
    if upd.psk is not None:
        cfg.psk = upd.psk
    if upd.left_subnet is not None:
        cfg.left_subnet = upd.left_subnet
    if upd.right_subnet is not None:
        cfg.right_subnet = upd.right_subnet
    if upd.ports is not None:
        if "ike_port" in upd.ports:
            cfg.ike_port = upd.ports["ike_port"]
        if "nat_t_port" in upd.ports:
            cfg.nat_t_port = upd.ports["nat_t_port"]
    if upd.dns1 is not None:
        cfg.dns1 = upd.dns1
    if upd.dns2 is not None:
        cfg.dns2 = upd.dns2
    if upd.lifetime is not None:
        cfg.lifetime = upd.lifetime

    success, msg = ipsec_mgr.update_config(cfg)
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg}


@router.get("/ipsec/users")
async def ipsec_list_users(auth=Depends(require_auth)):
    """IPSec 用户列表"""
    users = ipsec_mgr.list_users()
    return {
        "users": [
            {
                "username": u.username,
                "enabled": u.enabled,
            }
            for u in users
        ],
        "count": len(users),
    }


@router.post("/ipsec/users")
async def ipsec_add_user(user: IpsecUserCreate, auth=Depends(require_auth)):
    """添加 IPSec 用户"""
    ipsec_user = IpsecUser(username=user.username, password=user.password)
    success, msg = ipsec_mgr.add_user(ipsec_user)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.delete("/ipsec/users/{username}")
async def ipsec_delete_user(username: str, auth=Depends(require_auth)):
    """删除 IPSec 用户"""
    success, msg = ipsec_mgr.delete_user(username)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@router.post("/ipsec/start")
async def ipsec_start(auth=Depends(require_auth)):
    """启动 IPSec 服务"""
    success, msg = ipsec_mgr.start()
    return {"success": success, "message": msg}


@router.post("/ipsec/stop")
async def ipsec_stop(auth=Depends(require_auth)):
    """停止 IPSec 服务"""
    success, msg = ipsec_mgr.stop()
    return {"success": success, "message": msg}


@router.post("/ipsec/generate-cert")
async def ipsec_generate_cert(auth=Depends(require_auth)):
    """生成 CA + 服务端证书"""
    ok_ca, msg_ca = ipsec_mgr.generate_ca_cert()
    if not ok_ca and "已存在" not in msg_ca:
        raise HTTPException(status_code=500, detail=f"CA 生成失败: {msg_ca}")
    ok_srv, msg_srv = ipsec_mgr.generate_server_cert()
    if not ok_srv:
        raise HTTPException(status_code=500, detail=f"服务器证书生成失败: {msg_srv}")
    return {"success": True, "message": "CA 和服务器证书已就绪"}


@router.get("/ipsec/export-config/{username}")
async def ipsec_export_config(username: str, auth=Depends(require_auth)):
    """导出 .mobileconfig 配置"""
    success, result = ipsec_mgr.export_mobileconfig(username)
    if not success:
        raise HTTPException(status_code=400, detail=result)
    return {"success": True, "file": result}


# ===================================================================
# OpenVPN — 服务管理
# ===================================================================

openvpn_mgr = OpenvpnManager()


class OpenvpnConfigUpdate(BaseModel):
    proto: Optional[str] = None            # udp / tcp
    port: Optional[int] = None
    cipher: Optional[str] = None
    auth: Optional[str] = None
    dns1: Optional[str] = None
    dns2: Optional[str] = None
    redirect_gateway: Optional[bool] = None
    client_to_client: Optional[bool] = None
    max_clients: Optional[int] = None
    keepalive_interval: Optional[int] = None
    keepalive_timeout: Optional[int] = None
    compress: Optional[str] = None
    tls_version: Optional[str] = None


class OpenvpnClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


@router.get("/openvpn/status")
async def openvpn_status(auth=Depends(require_auth)):
    """OpenVPN 服务状态"""
    cfg = openvpn_mgr.get_config()
    connections = openvpn_mgr.get_connections()
    return {
        "running": cfg.running,
        "config_name": cfg.config_name,
        "protocol": cfg.protocol,
        "port": cfg.port,
        "dev_type": cfg.dev_type,
        "active_connections": len(connections),
        "connections": [
            {
                "common_name": c.common_name,
                "remote_ip": c.remote_ip,
                "virtual_ip": c.virtual_ip,
                "bytes_received": c.bytes_received,
                "bytes_sent": c.bytes_sent,
                "connected_since": c.connected_since.isoformat() if c.connected_since else None,
            }
            for c in connections
        ],
    }


@router.get("/openvpn/config")
async def openvpn_get_config(auth=Depends(require_auth)):
    """获取 OpenVPN 配置"""
    cfg = openvpn_mgr.get_config()
    return {
        "protocol": cfg.protocol,
        "port": cfg.port,
        "dev_type": cfg.dev_type,
        "cipher": cfg.cipher,
        "auth": cfg.auth,
        "dh_bits": cfg.dh_bits,
        "server_network": cfg.server_network,
        "server_netmask": cfg.server_netmask,
        "max_clients": cfg.max_clients,
        "keepalive_interval": cfg.keepalive_interval,
        "keepalive_timeout": cfg.keepalive_timeout,
        "compress": cfg.compress,
        "dns1": cfg.dns1,
        "dns2": cfg.dns2,
        "redirect_gateway": cfg.redirect_gateway,
        "client_to_client": cfg.client_to_client,
        "duplicate_cn": cfg.duplicate_cn,
        "tls_version": cfg.tls_version,
        "running": cfg.running,
    }


@router.put("/openvpn/config")
async def openvpn_update_config(upd: OpenvpnConfigUpdate, auth=Depends(require_auth)):
    """更新 OpenVPN 配置"""
    cfg = openvpn_mgr.get_config()
    if upd.proto is not None:
        cfg.protocol = upd.proto
    if upd.port is not None:
        cfg.port = upd.port
    if upd.cipher is not None:
        cfg.cipher = upd.cipher
    if upd.auth is not None:
        cfg.auth = upd.auth
    if upd.dns1 is not None:
        cfg.dns1 = upd.dns1
    if upd.dns2 is not None:
        cfg.dns2 = upd.dns2
    if upd.redirect_gateway is not None:
        cfg.redirect_gateway = upd.redirect_gateway
    if upd.client_to_client is not None:
        cfg.client_to_client = upd.client_to_client
    if upd.max_clients is not None:
        cfg.max_clients = upd.max_clients
    if upd.keepalive_interval is not None:
        cfg.keepalive_interval = upd.keepalive_interval
    if upd.keepalive_timeout is not None:
        cfg.keepalive_timeout = upd.keepalive_timeout
    if upd.compress is not None:
        cfg.compress = upd.compress
    if upd.tls_version is not None:
        cfg.tls_version = upd.tls_version

    success, msg = openvpn_mgr.update_config(cfg)
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg}


@router.get("/openvpn/clients")
async def openvpn_list_clients(auth=Depends(require_auth)):
    """OpenVPN 客户端列表"""
    clients = openvpn_mgr.list_clients()
    return {
        "clients": [
            {
                "name": c.name,
                "enabled": c.enabled,
                "certificate_expiry": c.certificate_expiry.isoformat() if c.certificate_expiry else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in clients
        ],
        "count": len(clients),
    }


@router.post("/openvpn/clients")
async def openvpn_add_client(client: OpenvpnClientCreate, auth=Depends(require_auth)):
    """添加 OpenVPN 客户端并签发证书"""
    success, msg = openvpn_mgr.generate_client_cert(client.name)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.delete("/openvpn/clients/{name}")
async def openvpn_delete_client(name: str, auth=Depends(require_auth)):
    """吊销 OpenVPN 客户端证书"""
    success, msg = openvpn_mgr.revoke_client(name)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"success": True, "message": msg}


@router.post("/openvpn/init-pki")
async def openvpn_init_pki(auth=Depends(require_auth)):
    """初始化 PKI (CA + DH + TLS-Crypt + 服务端证书)"""
    success, msg = openvpn_mgr.init_full_pki()
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg}


@router.post("/openvpn/start")
async def openvpn_start(auth=Depends(require_auth)):
    """启动 OpenVPN 服务"""
    success, msg = openvpn_mgr.start()
    return {"success": success, "message": msg}


@router.post("/openvpn/stop")
async def openvpn_stop(auth=Depends(require_auth)):
    """停止 OpenVPN 服务"""
    success, msg = openvpn_mgr.stop()
    return {"success": success, "message": msg}


@router.get("/openvpn/export-config/{name}")
async def openvpn_export_config(name: str, auth=Depends(require_auth)):
    """导出 .ovpn 客户端配置"""
    success, result = openvpn_mgr.export_client_config(name)
    if not success:
        raise HTTPException(status_code=400, detail=result)
    return {"success": True, "file": result}
