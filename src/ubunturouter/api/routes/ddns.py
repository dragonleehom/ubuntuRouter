"""DDNS API 路由 — 动态 DNS 管理接口"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from ..deps import require_auth
from ...ddns import DDNSManager
from ...ddns.scheduler import DDNSScheduler
from ...ddns.providers import list_providers

router = APIRouter()

# Global instances (singleton)
_manager = DDNSManager()
_scheduler = DDNSScheduler()


# ─── 请求/响应模型 ──────────────────────────────────────────

class DDNSRecordCreate(BaseModel):
    type: str = Field(..., min_length=1, max_length=32, description="Provider type")
    domain: str = Field(..., min_length=1, max_length=255, description="Domain name")
    subdomain: str = Field("", max_length=255, description="Subdomain (empty for root)")
    enabled: bool = Field(True, description="Whether this record is active")
    ttl: int = Field(120, ge=30, le=86400, description="DNS TTL in seconds")
    # Provider-specific config fields are merged into the record
    token: Optional[str] = Field(None, description="API token (DDNSTO, DuckDNS)")
    api_token: Optional[str] = Field(None, description="Cloudflare API token or global key")
    zone_id: Optional[str] = Field(None, description="Cloudflare Zone ID")
    proxied: bool = Field(False, description="Cloudflare proxy mode")
    access_key_id: Optional[str] = Field(None, description="Aliyun AccessKey ID")
    access_key_secret: Optional[str] = Field(None, description="Aliyun AccessKey Secret")
    login_token: Optional[str] = Field(None, description="DNSPod login token")


class DDNSRecordResponse(BaseModel):
    id: str
    type: str
    domain: str
    subdomain: str
    enabled: bool
    ttl: int
    # Provider-specific fields exposed for the client
    token: Optional[str] = None
    api_token: Optional[str] = None
    zone_id: Optional[str] = None
    proxied: bool = False
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    login_token: Optional[str] = None


class DDNSSuccessResponse(BaseModel):
    success: bool
    message: str
    ip: Optional[str] = None
    provider: Optional[str] = None


class DDNSCheckResponse(BaseModel):
    checked: int
    updated: int
    errors: int
    total: int
    details: list


class DDNSStatusResponse(BaseModel):
    total_records: int
    enabled_records: int
    disabled_records: int
    config_path: str
    last_check: Optional[float] = None
    next_check: Optional[float] = None
    scheduler_running: bool = False


# ─── 辅助函数 ──────────────────────────────────────────────

def _record_to_response(record: dict) -> dict:
    """Convert stored record dict to response format."""
    return {
        "id": record.get("id", ""),
        "type": record.get("type", ""),
        "domain": record.get("domain", ""),
        "subdomain": record.get("subdomain", ""),
        "enabled": record.get("enabled", True),
        "ttl": record.get("ttl", 120),
        "token": record.get("token"),
        "api_token": record.get("api_token"),
        "zone_id": record.get("zone_id"),
        "proxied": record.get("proxied", False),
        "access_key_id": record.get("access_key_id"),
        "access_key_secret": record.get("access_key_secret"),
        "login_token": record.get("login_token"),
    }


def _build_record(create: DDNSRecordCreate) -> dict:
    """Build a record dict from creation model."""
    record = {
        "type": create.type,
        "domain": create.domain,
        "subdomain": create.subdomain,
        "enabled": create.enabled,
        "ttl": create.ttl,
    }
    # Merge in provider-specific fields that are set
    provider_fields = {
        "token": create.token,
        "api_token": create.api_token,
        "zone_id": create.zone_id,
        "proxied": create.proxied,
        "access_key_id": create.access_key_id,
        "access_key_secret": create.access_key_secret,
        "login_token": create.login_token,
    }
    for key, value in provider_fields.items():
        if value is not None:
            record[key] = value
    return record


# ─── 端点 ──────────────────────────────────────────────────

@router.get("/records")
async def list_records(auth=Depends(require_auth)):
    """List all configured DDNS records."""
    records = _manager.get_records()
    return {
        "total": len(records),
        "records": [_record_to_response(r) for r in records],
    }


@router.post("/records", status_code=201)
async def add_record(body: DDNSRecordCreate, auth=Depends(require_auth)):
    """Add a new DDNS record."""
    record = _build_record(body)
    saved = _manager.add_record(record)
    return _record_to_response(saved)


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, auth=Depends(require_auth)):
    """Delete a DDNS record by ID."""
    result = _manager.remove_record(record_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/records/{record_id}/update")
async def force_update_record(record_id: str, auth=Depends(require_auth)):
    """Force an immediate update for a specific record."""
    result = _manager.force_update(record_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return DDNSSuccessResponse(
        success=True,
        message=result["message"],
        ip=result.get("ip"),
        provider=result.get("provider"),
    )


@router.get("/providers")
async def list_available_providers(auth=Depends(require_auth)):
    """List all available DDNS provider types with their parameter schemas."""
    providers = list_providers()
    return {
        "total": len(providers),
        "providers": providers,
    }


@router.get("/status")
async def get_ddns_status(auth=Depends(require_auth)):
    """Get DDNS module status."""
    status = _manager.get_status()
    return DDNSStatusResponse(
        total_records=status["total_records"],
        enabled_records=status["enabled_records"],
        disabled_records=status["disabled_records"],
        config_path=status["config_path"],
        last_check=_scheduler.last_check,
        next_check=_scheduler.next_check,
        scheduler_running=_scheduler.running,
    )


@router.post("/check")
async def trigger_check(auth=Depends(require_auth)):
    """Trigger an immediate check and update for all records."""
    result = _manager.check_and_update()
    return DDNSCheckResponse(
        checked=result["checked"],
        updated=result["updated"],
        errors=result["errors"],
        total=result["total"],
        details=result["details"],
    )
