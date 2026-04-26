"""VPN API 路由 — WireGuard 隧道管理"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from ..deps import require_auth
from ...vpn import VpnManager, WireGuardTunnel, WireGuardPeer

router = APIRouter()
vm = VpnManager()


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
