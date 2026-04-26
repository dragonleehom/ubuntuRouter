"""DNS Manager API routes — forwarding, rewrite, cache, hosts, logs"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from ..deps import require_auth
from ...dns import DNSManager

router = APIRouter()
dns_manager = DNSManager()


class ForwardCreate(BaseModel):
    domain: str = Field(..., min_length=1, description="Domain to forward (e.g. 'example.com')")
    target: str = Field(..., min_length=1, description="Target DNS server IP")


class ForwardRemove(BaseModel):
    domain: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class RewriteCreate(BaseModel):
    domain: str = Field(..., min_length=1, description="Domain to override")
    ip: str = Field(..., min_length=1, description="IP address to return")


class RewriteRemove(BaseModel):
    domain: str = Field(..., min_length=1)
    ip: str = Field(..., min_length=1)


class HostCreate(BaseModel):
    ip: str = Field(..., min_length=1, description="IP address")
    hostname: str = Field(..., min_length=1, description="Hostname")


class HostRemove(BaseModel):
    ip: str = Field(..., min_length=1)
    hostname: str = Field(..., min_length=1)


@router.get("/status")
async def get_dns_status(auth=Depends(require_auth)):
    """Get DNS service status and cache stats."""
    return dns_manager.get_status()


@router.post("/flush-cache")
async def flush_dns_cache(auth=Depends(require_auth)):
    """Flush dnsmasq DNS cache."""
    result = dns_manager.flush_cache()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result


@router.get("/forwards")
async def list_forwards(auth=Depends(require_auth)):
    """List DNS forwarding rules."""
    forwards = dns_manager.get_forwards()
    return {"forwards": forwards, "count": len(forwards)}


@router.post("/forwards", status_code=201)
async def add_forward(body: ForwardCreate, auth=Depends(require_auth)):
    """Add a DNS forwarding rule (domain → target DNS)."""
    result = dns_manager.add_forward(body.domain, body.target)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.delete("/forwards")
async def remove_forward(body: ForwardRemove, auth=Depends(require_auth)):
    """Remove a DNS forwarding rule."""
    result = dns_manager.remove_forward(body.domain, body.target)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.get("/rewrites")
async def list_rewrites(auth=Depends(require_auth)):
    """List DNS rewrite rules."""
    rewrites = dns_manager.get_rewrites()
    return {"rewrites": rewrites, "count": len(rewrites)}


@router.post("/rewrites", status_code=201)
async def add_rewrite(body: RewriteCreate, auth=Depends(require_auth)):
    """Add a DNS rewrite rule (domain → custom IP)."""
    result = dns_manager.add_rewrite(body.domain, body.ip)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.delete("/rewrites")
async def remove_rewrite(body: RewriteRemove, auth=Depends(require_auth)):
    """Remove a DNS rewrite rule."""
    result = dns_manager.remove_rewrite(body.domain, body.ip)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.get("/hosts")
async def list_hosts(auth=Depends(require_auth)):
    """List /etc/hosts entries (excluding localhost defaults)."""
    hosts = dns_manager.get_hosts()
    return {"hosts": hosts, "count": len(hosts)}


@router.post("/hosts", status_code=201)
async def add_host(body: HostCreate, auth=Depends(require_auth)):
    """Add a /etc/hosts entry."""
    result = dns_manager.add_host(body.ip, body.hostname)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.delete("/hosts")
async def remove_host(body: HostRemove, auth=Depends(require_auth)):
    """Remove a /etc/hosts entry."""
    result = dns_manager.remove_host(body.ip, body.hostname)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.get("/logs")
async def get_dns_logs(lines: int = Query(50, ge=1, le=500, description="Number of log lines"),
                       auth=Depends(require_auth)):
    """Get recent DNS query logs."""
    return dns_manager.get_logs(lines)
