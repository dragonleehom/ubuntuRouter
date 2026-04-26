"""Network Diagnostics API routes — ping, traceroute, nslookup, mtr, tcpcheck"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from ..deps import require_auth
from ...diag import DiagManager

router = APIRouter()
diag_manager = DiagManager()


class PingRequest(BaseModel):
    target: str = Field(..., min_length=1, description="IP or hostname to ping")
    count: int = Field(4, ge=1, le=100, description="Number of ping packets")
    timeout: int = Field(15, ge=5, le=120, description="Max timeout in seconds")


class TraceRequest(BaseModel):
    target: str = Field(..., min_length=1, description="Target hostname or IP")
    timeout: int = Field(30, ge=10, le=120)


class LookupRequest(BaseModel):
    domain: str = Field(..., min_length=1, description="Domain name to look up")
    dns_server: Optional[str] = Field(None, description="Optional specific DNS server")
    timeout: int = Field(15, ge=5, le=60)


class MtrRequest(BaseModel):
    target: str = Field(..., min_length=1, description="Target hostname or IP")
    count: int = Field(10, ge=3, le=100)
    timeout: int = Field(60, ge=15, le=180)


class TcpCheckRequest(BaseModel):
    host: str = Field(..., min_length=1, description="Hostname or IP")
    port: int = Field(..., ge=1, le=65535, description="TCP port")
    timeout: int = Field(10, ge=5, le=60)


class CurlRequest(BaseModel):
    url: str = Field(..., min_length=1, description="URL to check (http/https)")
    timeout: int = Field(15, ge=5, le=60)


@router.post("/ping")
async def diag_ping(body: PingRequest, auth=Depends(require_auth)):
    """Execute ping diagnostic."""
    result = diag_manager.ping(body.target, body.count, body.timeout)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/traceroute")
async def diag_traceroute(body: TraceRequest, auth=Depends(require_auth)):
    """Execute traceroute diagnostic."""
    result = diag_manager.traceroute(body.target, body.timeout)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/nslookup")
async def diag_nslookup(body: LookupRequest, auth=Depends(require_auth)):
    """Execute DNS lookup."""
    result = diag_manager.nslookup(body.domain, body.dns_server, body.timeout)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/mtr")
async def diag_mtr(body: MtrRequest, auth=Depends(require_auth)):
    """Execute MTR diagnostic (report mode)."""
    result = diag_manager.mtr(body.target, body.count, body.timeout)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/tcpcheck")
async def diag_tcpcheck(body: TcpCheckRequest, auth=Depends(require_auth)):
    """Check TCP port reachability."""
    result = diag_manager.tcp_check(body.host, body.port, body.timeout)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/curl")
async def diag_curl(body: CurlRequest, auth=Depends(require_auth)):
    """Check HTTP endpoint reachability."""
    result = diag_manager.curl(body.url, body.timeout)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.get("/result/{task_id}")
async def get_diag_result(task_id: str, auth=Depends(require_auth)):
    """Get diagnostic task result by ID."""
    result = diag_manager.get_task_result(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result
