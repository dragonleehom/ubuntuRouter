"""DHCP API 路由 — 租约 + 绑定 + 状态"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from ..deps import require_auth
from ...dhcp import DnsmasqManager
from pathlib import Path

router = APIRouter()
dm = DnsmasqManager()


# ─── 请求/响应模型 ──────────────────────────────────────────

class StaticLeaseCreate(BaseModel):
    mac: str = Field(..., pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    ip: str = Field(..., pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    hostname: str = ""
    description: str = ""


class StaticLeaseDelete(BaseModel):
    mac: str = ""
    ip: str = ""


class DnsUpstreamCreate(BaseModel):
    server: str


class DnsRewriteCreate(BaseModel):
    domain: str
    ip: str


class DnsRewriteDelete(BaseModel):
    rule: str


# ─── 租约 ──────────────────────────────────────────────────

@router.get("/leases")
async def get_leases(auth=Depends(require_auth)):
    """获取所有 DHCP 租约"""
    leases = dm.get_leases()
    return {
        "total": len(leases),
        "active": sum(1 for l in leases if l.remaining_seconds > 0),
        "leases": [
            {
                "mac": l.mac,
                "ip": l.ip,
                "hostname": l.hostname or l.ip,
                "expires": l.expires,
                "remaining_seconds": l.remaining_seconds,
                "interface": l.interface,
            }
            for l in leases
        ],
    }


@router.get("/leases/active")
async def get_active_leases_count(auth=Depends(require_auth)):
    """获取活跃租约数量"""
    leases = dm.get_leases()
    active = sum(1 for l in leases if l.remaining_seconds > 0)
    return {"active": active, "total": len(leases)}


@router.post("/leases/release")
async def release_lease(mac: str, auth=Depends(require_auth)):
    """释放指定 MAC 的租约"""
    success = dm.release_lease(mac)
    return {"success": success, "message": "租约已释放" if success else "释放失败"}


# ─── 静态绑定 ──────────────────────────────────────────────

@router.get("/static-leases")
async def get_static_leases(auth=Depends(require_auth)):
    """获取所有静态绑定"""
    pool = dm.get_pool_info()
    if pool:
        return {"leases": []}  # 从 config 读取，暂简化
    return {"leases": []}


@router.post("/static-leases")
async def add_static_lease(lease: StaticLeaseCreate,
                            auth=Depends(require_auth)):
    """添加静态绑定"""
    # 写入 dnsmasq 配置并重载
    bind_line = f"dhcp-host={lease.mac},{lease.ip},{lease.hostname}"
    try:
        with open(dm.config_path, 'a') as f:
            f.write("\n" + bind_line)
        import subprocess
        subprocess.run(["systemctl", "reload-or-restart", "dnsmasq"],
                       capture_output=True, timeout=10)
        return {"success": True, "message": "静态绑定已添加"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/static-leases")
async def delete_static_lease(body: StaticLeaseDelete, auth=Depends(require_auth)):
    """删除静态绑定"""
    config = Path(dm.config_path)
    if not config.exists():
        return {"success": False, "message": "配置文件不存在"}
    try:
        content = config.read_text(encoding='utf-8')
        lines = content.split('\n')
        new_lines = []
        removed = 0
        for line in lines:
            if line.startswith('dhcp-host=') and (body.mac in line or body.ip in line):
                removed += 1
                continue
            new_lines.append(line)
        if removed == 0:
            return {"success": False, "message": "未找到匹配的静态绑定"}
        config.write_text('\n'.join(new_lines), encoding='utf-8')
        import subprocess
        subprocess.run(["systemctl", "reload-or-restart", "dnsmasq"],
                       capture_output=True, timeout=10)
        return {"success": True, "message": f"已删除 {removed} 条静态绑定"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── DNS 上游管理 ─────────────────────────────────────────

@router.post("/dns/upstream")
async def add_dns_upstream(body: DnsUpstreamCreate, auth=Depends(require_auth)):
    """添加上游 DNS 服务器"""
    config = Path(dm.config_path)
    try:
        with open(config, 'a') as f:
            f.write(f"\nserver={body.server}")
        import subprocess
        subprocess.run(["systemctl", "reload-or-restart", "dnsmasq"],
                       capture_output=True, timeout=10)
        return {"success": True, "message": f"上游 DNS {body.server} 已添加"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dns/upstream")
async def delete_dns_upstream(body: DnsUpstreamCreate, auth=Depends(require_auth)):
    """删除上游 DNS 服务器"""
    config = Path(dm.config_path)
    if not config.exists():
        return {"success": False, "message": "配置文件不存在"}
    try:
        content = config.read_text(encoding='utf-8')
        lines = content.split('\n')
        new_lines = [l for l in lines if l.strip() != f"server={body.server}"]
        config.write_text('\n'.join(new_lines), encoding='utf-8')
        import subprocess
        subprocess.run(["systemctl", "reload-or-restart", "dnsmasq"],
                       capture_output=True, timeout=10)
        return {"success": True, "message": f"上游 DNS {body.server} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── DNS 重写管理 ─────────────────────────────────────────

@router.post("/dns/rewrite")
async def add_dns_rewrite(body: DnsRewriteCreate, auth=Depends(require_auth)):
    """添加 DNS 重写规则"""
    config = Path(dm.config_path)
    try:
        with open(config, 'a') as f:
            f.write(f"\naddress=/{body.domain}/{body.ip}")
        import subprocess
        subprocess.run(["systemctl", "reload-or-restart", "dnsmasq"],
                       capture_output=True, timeout=10)
        return {"success": True, "message": f"DNS 重写 /{body.domain}/{body.ip} 已添加"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dns/rewrite")
async def delete_dns_rewrite(body: DnsRewriteDelete, auth=Depends(require_auth)):
    """删除 DNS 重写规则"""
    config = Path(dm.config_path)
    if not config.exists():
        return {"success": False, "message": "配置文件不存在"}
    try:
        content = config.read_text(encoding='utf-8')
        lines = content.split('\n')
        new_lines = [l for l in lines if l.strip() != f"address=/{body.rule}/"]
        config.write_text('\n'.join(new_lines), encoding='utf-8')
        import subprocess
        subprocess.run(["systemctl", "reload-or-restart", "dnsmasq"],
                       capture_output=True, timeout=10)
        return {"success": True, "message": "DNS 重写已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 池配置 ──────────────────────────────────────────────

@router.get("/pool")
async def get_dhcp_pool(auth=Depends(require_auth)):
    """获取 DHCP 池配置"""
    pool = dm.get_pool_info()
    if not pool:
        return {"configured": False}
    return {
        "configured": True,
        "interface": pool.interface,
        "range_start": pool.range_start,
        "range_end": pool.range_end,
        "gateway": pool.gateway,
        "lease_time": pool.lease_time,
        "domain": pool.domain,
        "active_leases": pool.active_leases,
    }


# ─── DNS ───────────────────────────────────────────────────

@router.get("/dns/config")
async def get_dns_config(auth=Depends(require_auth)):
    """获取 DNS 配置"""
    config = dm.get_dns_config()
    return config


@router.post("/dns/flush")
async def flush_dns_cache(auth=Depends(require_auth)):
    """刷新 DNS 缓存"""
    success = dm.flush_dns_cache()
    return {"success": success, "message": "DNS 缓存已刷新" if success else "刷新失败"}


@router.get("/dns/resolve")
async def resolve_dns(domain: str, server: str = "",
                       auth=Depends(require_auth)):
    """DNS 查询测试"""
    result = dm.resolve_query(domain, server)
    return {"domain": domain, "result": result, "server": server or "default"}


# ─── 服务状态 ──────────────────────────────────────────────

@router.get("/status")
async def get_dhcp_dns_status(auth=Depends(require_auth)):
    """获取 DHCP/DNS 服务综合状态"""
    status = dm.service_status()
    leases = dm.get_leases()
    active = sum(1 for l in leases if l.remaining_seconds > 0)
    return {
        "active": status["active"],
        "enabled": status["enabled"],
        "active_leases": active,
        "total_leases": len(leases),
        "cached_entries": dm.get_cached_entries_count(),
    }
