"""PPPoE API routes — dial-up connection management"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..deps import require_auth
from ...pppoe import PPPoEManager

router = APIRouter()
pppoe_manager = PPPoEManager()


class PPPoEConfigUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    mtu: Optional[int] = Field(None, ge=576, le=1500)
    auto_reconnect: Optional[bool] = None
    enabled: Optional[bool] = None


@router.get("/status")
async def get_pppoe_status(auth=Depends(require_auth)):
    """Get PPPoE connection status and interface statistics."""
    return pppoe_manager.get_status()


@router.get("/config")
async def get_pppoe_config(auth=Depends(require_auth)):
    """Get PPPoE dial-up configuration."""
    return pppoe_manager.get_config()


@router.put("/config")
async def update_pppoe_config(body: PPPoEConfigUpdate, auth=Depends(require_auth)):
    """Update PPPoE dial-up configuration."""
    update_data = body.model_dump(exclude_none=True)
    result = pppoe_manager.update_config(update_data)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "update failed"))
    return result


@router.post("/connect")
async def pppoe_connect(auth=Depends(require_auth)):
    """Dial PPPoE connection."""
    result = pppoe_manager.connect()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "connect failed"))
    return result


@router.post("/disconnect")
async def pppoe_disconnect(auth=Depends(require_auth)):
    """Hang up PPPoE connection."""
    result = pppoe_manager.disconnect()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "disconnect failed"))
    return result


@router.post("/reconnect")
async def pppoe_reconnect(auth=Depends(require_auth)):
    """Reconnect PPPoE (disconnect + connect)."""
    return pppoe_manager.reconnect()
